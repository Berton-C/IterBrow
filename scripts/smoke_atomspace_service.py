#!/usr/bin/env python3
"""Exercise the installed Hyperon service against disposable durable state.

Run this with IterBrow's virtual-environment Python. The script loads the real
declared seeds and engine package, but overrides the state, work, lock, and
socket paths with a temporary directory. It never touches the live AtomSpace
under ``iter/.runtime``.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ITER_DIR = ROOT / "iter"
SERVER = ITER_DIR / "metta_server.py"


def call(socket_path, method, params=None, timeout=10):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(socket_path))
        request = {"method": method, "params": params or {}}
        client.sendall((json.dumps(request) + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = client.recv(1 << 20)
            if not chunk:
                raise RuntimeError("AtomSpace service closed without a response")
            data += chunk
    finally:
        client.close()
    response = json.loads(data.split(b"\n", 1)[0])
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "%s failed" % method)
    return response["result"]


def start_service(temp_root, log_name, source_iter_dir):
    socket_path = temp_root / "atomspace.sock"
    environment = dict(os.environ)
    environment.update({
        "ITER_DIR": str(source_iter_dir),
        "ITER_METTA_SOCKET": str(socket_path),
        "ITER_METTA_LOCKFILE": str(temp_root / "atomspace.lock"),
        "ITER_ATOMSPACE_STATE_DIR": str(temp_root / "state"),
        "ITER_METTA_WORKDIR": str(temp_root / "work"),
        "PYTHONUNBUFFERED": "1",
    })
    log_path = temp_root / log_name
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=str(ROOT),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
        )
    deadline = time.time() + 20
    last_error = None
    while time.time() < deadline:
        if process.poll() is not None:
            break
        try:
            status = call(socket_path, "status", timeout=0.5)
            if status.get("ready"):
                return process, socket_path, status, log_path
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    output = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
    try:
        process.kill()
        process.wait(timeout=5)
    except Exception:
        pass
    raise RuntimeError("AtomSpace did not become ready: %s\n%s" % (last_error, output))


def main(source_iter_dir=ITER_DIR):
    source_iter_dir = Path(source_iter_dir).resolve()
    if not (source_iter_dir / "state_manifest.json").is_file():
        raise RuntimeError("legacy source has no state manifest: %s" % source_iter_dir)
    with tempfile.TemporaryDirectory(prefix="iterbrow-atomspace-smoke-") as temporary:
        temp_root = Path(temporary)
        process = None
        try:
            process, socket_path, initial, _log = start_service(
                temp_root, "before-crash.log", source_iter_dir
            )
            if initial.get("engine") != "hyperon":
                raise RuntimeError("unexpected initial service status: %r" % initial)
            baseline_commit = int(initial["commit"])
            baseline_atom_count = int(initial["runtime_atom_count"])
            committed = call(socket_path, "transact", {
                "transaction_id": "live-crash-once",
                "actor": "build-verifier",
                "source": "Build Atlas INV-01",
                "operations": [{
                    "op": "add",
                    "key": "smoke:crash",
                    "atom": "(survives crash exactly-once)",
                }],
            })
            if committed.get("commit") != baseline_commit + 1:
                raise RuntimeError("unexpected commit result: %r" % committed)
            original_hash = committed["state_hash"]

            process.kill()
            process.wait(timeout=10)
            process = None

            process, socket_path, recovered, log_path = start_service(
                temp_root, "after-crash.log", source_iter_dir
            )
            if (
                recovered.get("commit") != baseline_commit + 1
                or recovered.get("runtime_atom_count") != baseline_atom_count + 1
                or recovered.get("state_hash") != original_hash
            ):
                raise RuntimeError("crash recovery state mismatch: %r" % recovered)
            query = call(socket_path, "query", {
                "code": "!(match &self (survives crash exactly-once) "
                        "(survives crash exactly-once))",
            })
            if query["result"].count("survives crash exactly-once") != 1:
                raise RuntimeError("expected one recovered atom: %r" % query)
            duplicate = call(socket_path, "transact", {
                "transaction_id": "live-crash-once",
                "actor": "build-verifier",
                "source": "Build Atlas INV-01",
                "operations": [{
                    "op": "add",
                    "key": "smoke:crash",
                    "atom": "(survives crash exactly-once)",
                }],
            })
            if (
                not duplicate.get("duplicate")
                or duplicate.get("commit") != baseline_commit + 1
            ):
                raise RuntimeError("transaction replay was not idempotent: %r" % duplicate)
            removed = call(socket_path, "transact", {
                "transaction_id": "live-crash-cleanup",
                "actor": "build-verifier",
                "source": "Build Atlas INV-01",
                "operations": [{"op": "remove", "key": "smoke:crash"}],
            })
            call(socket_path, "shutdown")
            process.wait(timeout=10)
            process = None

            logs = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in temp_root.glob("*.log")
            ).lower()
            bad_markers = [
                marker
                for marker in ("panic", "traceback", "engine reconstruction")
                if marker in logs
            ]
            if bad_markers:
                raise RuntimeError(
                    "service logs contain failure markers %r; see %s"
                    % (bad_markers, log_path)
                )
            print(json.dumps({
                "ok": True,
                "legacy_source": str(source_iter_dir),
                "engine": recovered["engine"],
                "seed_atom_count": recovered["seed_atom_count"],
                "legacy_migration": initial.get("legacy_migration"),
                "baseline_commit": baseline_commit,
                "baseline_runtime_atom_count": baseline_atom_count,
                "commit_after_crash": recovered["commit"],
                "state_hash_preserved": recovered["state_hash"] == original_hash,
                "runtime_atom_count_after_crash": recovered["runtime_atom_count"],
                "idempotent_replay": duplicate["duplicate"],
                "cleanup_commit": removed["commit"],
                "query": query["result"],
            }, sort_keys=True))
            return 0
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--legacy-source",
        default=str(ITER_DIR),
        help="Iter directory whose declared seeds and legacy projections are read-only inputs",
    )
    arguments = parser.parse_args()
    raise SystemExit(main(arguments.legacy_source))
