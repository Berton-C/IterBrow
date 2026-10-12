"""End-to-end harness: the real iter.py loop, the real AtomSpace service, a fake model.

A run gets a fresh copy of iter/ (code and seeds only, no personal state) as its
ITER_DIR, its own AtomSpace service on a private socket, and a scripted model.
Tests talk to the agent the way the Electron shell does: drop a file in the
electron_ui inbox, read replies from the outbox, send SIGTERM to stop.
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ITER_SRC = REPO / "iter"
PYTHON = sys.executable
HERE = Path(__file__).resolve().parent

COPY = ["tools", "transformations", "channels", "iterbrow_runtime", "seeds", "vendor",
        "kb_substrate.metta", "capability_lifecycle.metta", "self_map.metta",
        "state_manifest.json", "metta_server.py", "metta_query_worker.py", "iter.py",
        "prompt.txt", "AGENTS.md", "reprogramming.txt", "rollup_helper.py", "hotload_control.py"]
SKIP = shutil.ignore_patterns("__pycache__", ".runtime", "*.pyc", "scratch")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def atomspace_call(sock_path, method, params=None, timeout=20):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.connect(str(sock_path))
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


class IterRun:
    def __init__(self, script, name="e2e", keep=False):
        self.name = name
        self.keep = keep
        self.script = script
        self.work = Path(tempfile.mkdtemp(prefix="iterbrow-%s-" % name))
        self.root = self.work / "iter"
        self.root.mkdir()
        for item in COPY:
            source = ITER_SRC / item
            if source.is_dir():
                shutil.copytree(source, self.root / item, ignore=SKIP)
            elif source.exists():
                shutil.copy2(source, self.root / item)
        (self.root / ".runtime").mkdir()
        self.sock = self.root / ".runtime" / "atomspace.sock"
        self.port = _free_port()
        self.requests_log = self.work / "requests.jsonl"
        self.script_path = self.work / "script.json"
        self.script_path.write_text(json.dumps(script), encoding="utf-8")
        self.inbox = self.root / ".runtime" / "electron_ui" / "inbox"
        self.outbox = self.root / ".runtime" / "electron_ui" / "outbox"
        self.inbox.mkdir(parents=True)
        self.log = (self.work / "iter.log").open("ab")
        self.service_log = (self.work / "atomspace.log").open("ab")
        self.model_log = (self.work / "model.log").open("ab")
        self.service = self.model = self.iter = None
        self._inbox_counter = 0

    # -- lifecycle ---------------------------------------------------------
    def env(self):
        env = dict(os.environ)
        env.pop("HTTPS_PROXY", None); env.pop("HTTP_PROXY", None)
        env.pop("https_proxy", None); env.pop("http_proxy", None)
        env.update({
            "ITER_DIR": str(self.root),
            "ITER_METTA_SOCKET": str(self.sock),
            "ITER_REQUIRE_ATOMSPACE": "1",
            "ITER_INIT_WAIT": "0",
            "BASE_URL": "http://127.0.0.1:%d/v1" % self.port,
            "AI_API_KEY": "fake",
            "OPENROUTER_API_KEY": "fake",
            "ITER_EMBEDDING_URL": "http://127.0.0.1:%d/v1/embeddings" % self.port,
            "LLM_PROVIDER": "compatible",
            "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
        })
        return env

    def start(self):
        env = self.env()
        self.service = subprocess.Popen([PYTHON, str(self.root / "metta_server.py")], cwd=str(self.root),
                                        env=env, stdout=self.service_log, stderr=self.service_log,
                                        stdin=subprocess.DEVNULL)
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                if atomspace_call(self.sock, "status", timeout=1).get("ready"):
                    break
            except Exception:
                pass
            if self.service.poll() is not None:
                raise RuntimeError("AtomSpace service died: " + self.read_log("atomspace.log"))
            time.sleep(0.2)
        else:
            raise RuntimeError("AtomSpace service never became ready")
        self.model = subprocess.Popen([PYTHON, str(HERE / "fake_model.py"), str(self.port),
                                       str(self.script_path), str(self.requests_log)],
                                      stdout=self.model_log, stderr=self.model_log)
        self.iter = subprocess.Popen([PYTHON, str(self.root / "iter.py")], cwd=str(self.root), env=env,
                                     stdout=self.log, stderr=self.log, stdin=subprocess.DEVNULL)
        return self

    def stop(self, how="sigterm", timeout=30):
        """Stop Iter the way main.js does (SIGTERM) and wait for it to exit."""
        if self.iter and self.iter.poll() is None:
            self.iter.send_signal(signal.SIGTERM if how == "sigterm" else signal.SIGKILL)
            try:
                self.iter.wait(timeout)
            except subprocess.TimeoutExpired:
                self.iter.kill()
                self.iter.wait(10)
        return self.iter.returncode if self.iter else None

    def close(self):
        self.stop()
        for proc in (self.model, self.service):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        for handle in (self.log, self.service_log, self.model_log):
            handle.close()
        if not (self.keep or os.environ.get("ITERBROW_E2E_KEEP")):
            shutil.rmtree(self.work, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()

    # -- interaction -------------------------------------------------------
    def say(self, text):
        self._inbox_counter += 1
        path = self.inbox / ("%06d.txt" % self._inbox_counter)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    def replies(self):
        out = []
        if self.outbox.exists():
            for path in sorted(self.outbox.iterdir()):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try:
                            out.append(json.loads(line).get("content", line))
                        except ValueError:
                            out.append(line)
        return out

    def wait_for_reply(self, needle, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for reply in self.replies():
                if needle in reply:
                    return reply
            if self.iter.poll() is not None:
                raise RuntimeError("Iter exited early:\n" + self.read_log("iter.log"))
            time.sleep(0.25)
        raise AssertionError("no reply containing %r within %ss\n%s" % (needle, timeout, self.read_log("iter.log")))

    def wait_for_tool_result(self, needle, call_id=None, timeout=60):
        """Wait until a tool result containing `needle` (for `call_id`, if given) is saved."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for message in self.experience():
                if (message.get("role") == "tool" and needle in message.get("content", "")
                        and (call_id is None or message.get("tool_call_id") == call_id)):
                    return message
            time.sleep(0.1)
        raise AssertionError("no saved tool result containing %r within %ss" % (needle, timeout))

    def wait_for_requests(self, count, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.requests()) >= count:
                return self.requests()
            if self.iter.poll() is not None:
                raise RuntimeError("Iter exited early:\n" + self.read_log("iter.log"))
            time.sleep(0.25)
        raise AssertionError("fewer than %d model requests within %ss" % (count, timeout))

    def wait_for_log(self, needle, timeout=180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if needle in self.read_log("iter.log"):
                return True
            time.sleep(0.25)
        raise AssertionError("%r not seen in iter.log within %ss" % (needle, timeout))

    # -- inspection --------------------------------------------------------
    def requests(self):
        if not self.requests_log.exists():
            return []
        return [json.loads(line) for line in self.requests_log.read_text(encoding="utf-8").splitlines() if line]

    def experience(self):
        path = self.root / "experience.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def read(self, relative):
        path = self.root / relative
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def read_log(self, name):
        return (self.work / name).read_text(encoding="utf-8", errors="replace")

    def atoms(self, prefix=""):
        return atomspace_call(self.sock, "read_atoms", {"prefix": prefix})["atoms"]


def send(text, channel="electron_ui"):
    return {"name": "send", "arguments": {"channel": channel, "content": text}}


def nop(seconds=0):
    return {"name": "nop", "arguments": {"wait_seconds": seconds}}


def shell(cmd):
    return {"name": "shell", "arguments": {"cmd": cmd}}


def tool(name, **arguments):
    return {"name": name, "arguments": arguments}
