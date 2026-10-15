"""Shared fixture for semantic-memory tests: a throwaway ITER_DIR, the real
AtomSpace service (metta_server.py) on a private socket, a deterministic local
embeddings endpoint, and tools run the way iter.py's dynamic worker runs them
(a fresh process per call, the tool's own directory first on sys.path).

Not a test module itself (no test_ prefix); imported by test_semantic_*.py.
"""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITER_SRC = REPO / "iter"
PYTHON = sys.executable
RUNNER = Path(__file__).resolve().parent / "semantic_tool_runner.py"

COPY = ["tools", "iterbrow_runtime", "seeds", "transformations", "channels", "kb_substrate.metta",
        "capability_lifecycle.metta", "self_map.metta", "state_manifest.json",
        "metta_server.py", "metta_query_worker.py"]
SKIP = shutil.ignore_patterns("__pycache__", ".runtime", "*.pyc", "scratch")


def fake_vector(text, dimensions=1024):
    seed = hashlib.sha256(str(text).encode("utf-8")).digest()
    return [((seed[i % 32] ^ (i * 31 % 251)) / 255.0) - 0.5 for i in range(dimensions)]


class EmbeddingServer:
    """Deterministic OpenAI-style /embeddings endpoint; `fail` simulates an outage."""

    def __init__(self):
        owner = self
        self.fail = False
        self.requests = 0

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests += 1
                if owner.fail:
                    payload = {"error": {"message": "embedding endpoint down (test)"}}
                else:
                    texts = body.get("input") or []
                    texts = [texts] if isinstance(texts, str) else texts
                    payload = {"data": [{"index": i, "embedding": fake_vector(t, body.get("dimensions", 1024))}
                                        for i, t in enumerate(texts)]}
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d/v1/embeddings" % self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def atomspace_call(sock, method, params=None, timeout=20):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.connect(str(sock))
    client.sendall((json.dumps({"method": method, "params": params or {}}) + "\n").encode())
    data = b""
    while b"\n" not in data:
        chunk = client.recv(1 << 20)
        if not chunk:
            break
        data += chunk
    client.close()
    reply = json.loads(data.split(b"\n")[0])
    if not reply.get("ok"):
        raise RuntimeError(reply.get("error"))
    return reply["result"]


class SemanticRoot:
    """A canonical ITER_DIR with its own AtomSpace service and embeddings endpoint."""

    def __init__(self, name="sem"):
        self.base = Path(tempfile.mkdtemp(prefix="iterbrow-%s-" % name))
        self.root = self.base / "iter"
        self.root.mkdir()
        for item in COPY:
            source = ITER_SRC / item
            if source.is_dir():
                shutil.copytree(source, self.root / item, ignore=SKIP)
            elif source.exists():
                shutil.copy2(source, self.root / item)
        (self.root / ".runtime").mkdir()
        # Keep the Unix socket path short (108-byte limit).
        self.sock = Path(tempfile.mkdtemp(prefix="ibs-")) / "a.sock"
        self.embeddings = EmbeddingServer()
        self.proc = None
        self.service_log = self.base / "atomspace.log"

    # -- service -----------------------------------------------------------
    def start(self):
        env = dict(os.environ, ITER_DIR=str(self.root), ITER_METTA_SOCKET=str(self.sock),
                   PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
        log = self.service_log.open("ab")
        self.proc = subprocess.Popen([PYTHON, str(self.root / "metta_server.py")], cwd=str(self.root),
                                     env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL)
        log.close()
        deadline = time.time() + 120
        last = None
        while time.time() < deadline:
            try:
                last = atomspace_call(self.sock, "status", timeout=2)
                if last.get("ready") or last.get("legacy_migration", {}).get("status") == "failed":
                    return last
            except Exception:
                pass
            if self.proc.poll() is not None:
                raise RuntimeError("AtomSpace service died:\n" + self.service_log.read_text()[-3000:])
            time.sleep(0.1)
        raise RuntimeError("AtomSpace service never became ready: %r" % (last,))

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                atomspace_call(self.sock, "shutdown", timeout=5)
            except Exception:
                pass
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        self.proc = None

    def close(self):
        # End of test: the journal is already durable, so skip the graceful
        # shutdown (its server poll alone costs ~1s per test).
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(5)
        self.proc = None
        self.embeddings.close()
        if not os.environ.get("ITERBROW_TEST_KEEP"):
            shutil.rmtree(self.base, ignore_errors=True)
            shutil.rmtree(self.sock.parent, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def call(self, method, params=None, timeout=20):
        return atomspace_call(self.sock, method, params, timeout)

    def atoms(self, prefix="state:semantic_memory:"):
        return self.call("read_atoms", {"prefix": prefix})["atoms"]

    def memories(self):
        """Authority view: {id: (document, metadata)}."""
        sys.path.insert(0, str(ITER_SRC))
        try:
            from iterbrow_runtime.cognitive_events import parse_semantic_atom
        except ImportError:  # before the Hyperon-escape parser existed
            from iterbrow_runtime.foundry_memory import _semantic as parse_semantic_atom
        out = {}
        for key, atom in self.atoms().items():
            item_id, document, metadata = parse_semantic_atom(key, atom)
            out[item_id] = (document, metadata)
        return out

    # -- tools -------------------------------------------------------------
    def env(self, extra=None):
        env = dict(os.environ)
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy"):
            env.pop(name, None)
        env.update({
            "ITER_DIR": str(self.root), "ITER_METTA_SOCKET": str(self.sock),
            "ITER_REQUIRE_ATOMSPACE": "1", "OPENROUTER_API_KEY": "fake-key",
            "ITER_EMBEDDING_URL": self.embeddings.url,
            "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        for key, value in (extra or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return env

    def tool(self, name, /, cwd=None, env=None, tool_dir=None, timeout=120, **kwargs):
        """Run tools/<name>.py run(**kwargs) in a fresh process; returns the runner's JSON.

        `name` is positional-only so a tool may itself take a `name` argument (define_term)."""
        path = Path(tool_dir or (self.root / "tools")) / (name + ".py")
        proc = subprocess.run([PYTHON, str(RUNNER), str(path), json.dumps(kwargs)],
                              cwd=str(cwd or self.root), env=self.env(env),
                              capture_output=True, text=True, timeout=timeout)
        lines = proc.stdout.strip().splitlines()
        try:
            return json.loads(lines[-1])
        except Exception:
            return {"ok": False, "error": "runner crash", "stdout": proc.stdout[-2000:],
                    "stderr": proc.stderr[-3000:]}

    def text(self, name, /, **kwargs):
        """Tool result text, or the error string when the tool raised."""
        result = self.tool(name, **kwargs)
        return result.get("result") if result.get("ok") else "RAISED " + str(result.get("error"))

    def remember(self, text, **kwargs):
        out = self.text("remember", text=text, **kwargs)
        assert out.startswith("REMEMBER-SUCCESS"), out
        return out.split()[2]

    def index(self):
        path = self.root / "chroma_db" / "memories.json"
        return json.loads(path.read_text()) if path.exists() else None

    def index_ids(self):
        index = self.index()
        return set(index["ids"]) if index else set()

    def pending_files(self):
        return sorted((self.root / ".runtime" / "memory_pending").glob("*.json"))
