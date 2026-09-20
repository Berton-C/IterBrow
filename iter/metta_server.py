#!/usr/bin/env python3
"""Persistent local MeTTa atomspace server for IterBrow.

This is a long-lived companion process (started by main.js the same way it
starts iter.py — see startMettaServer() / startIter()) that holds ONE live
hyperon.MeTTa() atomspace in memory for the whole app session, instead of
iter.py's usual per-tool-call subprocess model where nothing survives
between calls (see tools/metta.py's own docstring on this).

Protocol is intentionally identical in shape to bridge/browser_bridge_server.js
+ tools/_browser_bridge.py: a Unix domain socket, one line of JSON in, one
line of JSON out. Same trust boundary (local-machine only, no network
listener), same failure style (connection refused/timeout -> caller degrades
gracefully rather than crashing).

READ-ONLY toward existing *.metta files
----------------------------------------
Several of these files already have a dedicated writer (e.g.
nace_beliefs.metta is explicitly "Written at runtime by nace_courier.py").
This server only ever READS them, once, at boot, to seed the shared space
with context. It never writes back to them — avoiding a second-writer
conflict with whatever process already owns each file. New atoms added at
runtime via the `run` method live only in this process's memory for the
life of the session; a durable, conflict-free write-back design (or a real
DAS-backed store) is a deliberate follow-up, not bolted on here.

Usage: iter/.venv/bin/python3 metta_server.py
Env vars:
  ITER_METTA_SOCKET  - Unix socket path (default /tmp/iter-metta-bridge.sock)
  ITER_DIR           - directory to scan for *.metta files (default: this
                        script's own directory, i.e. iter/)
"""
import json
import os
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

SOCKET_PATH = os.environ.get("ITER_METTA_SOCKET", "/tmp/iter-metta-bridge.sock")
ITER_DIR = os.environ.get("ITER_DIR", os.path.dirname(os.path.abspath(__file__)))
# Overridable mainly for testing (e.g. exercising this server against real
# iter/*.metta files from a restricted-write test harness without touching
# the real .runtime/ dir). Production runs use the default.
WORKING_DIR = os.environ.get(
    "ITER_METTA_WORKDIR", os.path.join(ITER_DIR, ".runtime", "metta_server_workdir")
)

# Names to skip when scanning for *.metta files to load — build artifacts,
# venvs, node_modules, anything not real knowledge content.
_SKIP_DIR_PARTS = {"node_modules", ".venv", ".git", "build_v3"}


def _log(msg):
    print(f"[metta_server] {msg}", flush=True)


def _find_metta_files(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_PARTS]
        for fn in filenames:
            if fn.endswith(".metta"):
                found.append(os.path.join(dirpath, fn))
    return sorted(found)


def _logical_units(text):
    """Group physical lines into balanced-paren logical atoms, stripping
    full-line and trailing inline ';;'/';' comments (but not inside quoted
    strings). Mirrors the sandbox spike's tested comment-stripping logic."""
    depth = 0
    buf = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        in_str = False
        cut = len(line)
        for i, ch in enumerate(line):
            if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                in_str = not in_str
            elif ch == ";" and not in_str:
                cut = i
                break
        line = line[:cut].rstrip()
        if not line:
            continue
        buf.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            yield " ".join(buf)
            buf = []
            depth = 0
    if buf:
        yield " ".join(buf)


class MettaSpace:
    """Owns the one persistent hyperon.MeTTa() instance for this process."""

    def __init__(self):
        self.lock = threading.Lock()
        self.loaded_files = []
        self.boot_atoms_loaded = 0
        self.boot_atoms_failed = 0
        self.started_at = time.time()
        self._engine_error = None
        self.metta = None
        try:
            from hyperon import MeTTa, Environment
            os.makedirs(WORKING_DIR, exist_ok=True)
            env = Environment.custom_env(
                working_dir=WORKING_DIR, config_dir=None, create_config=False
            )
            self.metta = MeTTa(env_builder=env)
        except Exception as e:  # pragma: no cover - hyperon not installed
            self._engine_error = f"{type(e).__name__}: {e}"
            _log(f"FAILED to start hyperon engine: {self._engine_error}")

    @property
    def engine_available(self):
        return self.metta is not None

    def load_boot_files(self):
        if not self.engine_available:
            return
        files = _find_metta_files(ITER_DIR)
        for path in files:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                _log(f"could not open {path}: {e}")
                continue
            file_loaded, file_failed = 0, 0
            for unit in _logical_units(text):
                try:
                    self.metta.run("!(add-atom &self " + unit + ")")
                    file_loaded += 1
                except Exception:
                    file_failed += 1
            self.loaded_files.append(
                {"path": path, "loaded": file_loaded, "failed": file_failed}
            )
            self.boot_atoms_loaded += file_loaded
            self.boot_atoms_failed += file_failed
            _log(f"loaded {file_loaded} atoms from {path} ({file_failed} skipped)")
        _log(
            f"boot complete: {self.boot_atoms_loaded} atoms loaded from "
            f"{len(self.loaded_files)} files, {self.boot_atoms_failed} skipped"
        )

    def run(self, code):
        if not self.engine_available:
            raise RuntimeError(f"hyperon engine unavailable: {self._engine_error}")
        code = str(code).strip()
        if not code:
            raise ValueError("empty MeTTa code")
        if "\n" not in code and code.startswith("(") and code.endswith(")"):
            code = "!" + code
        with self.lock:
            result = self.metta.run(code)
        return str(result)

    def status(self):
        return {
            "engine_available": self.engine_available,
            "engine_error": self._engine_error,
            "uptime_s": round(time.time() - self.started_at, 1),
            "boot_atoms_loaded": self.boot_atoms_loaded,
            "boot_atoms_failed": self.boot_atoms_failed,
            "files_loaded": self.loaded_files,
        }


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        space = self.server.metta_space
        try:
            buffer = b""
            while b"\n" not in buffer:
                chunk = self.request.recv(1 << 20)
                if not chunk:
                    return
                buffer += chunk
            line, _, _ = buffer.partition(b"\n")
            request = json.loads(line.decode("utf-8"))
            method = request.get("method")
            params = request.get("params") or {}
            if method == "run":
                result = space.run(params.get("code", ""))
            elif method == "status":
                result = space.status()
            else:
                raise ValueError(f"Unknown method: {method}")
            response = {"ok": True, "result": result}
        except Exception as e:
            response = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        try:
            self.request.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except Exception:
            pass


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    space = MettaSpace()
    space.load_boot_files()

    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass
    except Exception as e:
        _log(f"could not remove stale socket: {e}")

    server = _Server(SOCKET_PATH, _Handler)
    server.metta_space = space
    _log(f"listening on {SOCKET_PATH} (engine_available={space.engine_available})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        try:
            os.unlink(SOCKET_PATH)
        except Exception:
            pass


if __name__ == "__main__":
    main()
