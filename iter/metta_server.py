#!/usr/bin/env python3
"""Authoritative local AtomSpace service for IterBrow.

Hyperon remains the live native MeTTa engine. Durable authority lives in a
structured transaction journal plus checksummed snapshots, so acknowledged
atoms survive process loss and can be reconstructed exactly. Versioned source
seeds are loaded only from state_manifest.json; runtime directory recursion is
deliberately forbidden.

The Unix-socket protocol remains compatible with the former `run`/`status`
client while adding `query`, `transact`, `checkpoint`, `subscribe`, `quiesce`,
`resume`, `reset`, and `shutdown`.
"""

import fcntl
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import hashlib
from pathlib import Path

from iterbrow_runtime.atomspace_store import AtomspaceStore
from iterbrow_runtime.das_adapter import DASProjectionWorker
from iterbrow_runtime.legacy_migration import migrate_legacy_state


ITER_DIR = Path(os.environ.get("ITER_DIR", Path(__file__).resolve().parent)).resolve()
WORKING_DIR = Path(os.environ.get(
    "ITER_METTA_WORKDIR", ITER_DIR / ".runtime" / "metta_server_workdir"
)).resolve()
STATE_DIR = Path(os.environ.get(
    "ITER_ATOMSPACE_STATE_DIR", ITER_DIR / ".runtime" / "atomspace"
)).resolve()
SOCKET_PATH = os.environ.get("ITER_METTA_SOCKET", "/tmp/iter-metta-bridge.sock")
# The lock belongs to the authoritative state, not its transport endpoint.
# Two Electron versions or alternate socket names must never create two
# writers for one journal/snapshot directory.
LOCK_PATH = os.environ.get(
    "ITER_METTA_LOCKFILE", str(STATE_DIR / "service.lock")
)
MANIFEST_PATH = Path(os.environ.get(
    "ITER_STATE_MANIFEST", ITER_DIR / "state_manifest.json"
)).resolve()
MAX_REQUEST_BYTES = 16 * 1024 * 1024
QUERY_WORKER_PATH = (ITER_DIR / "metta_query_worker.py").resolve()
QUERY_TIMEOUT_S = int(os.environ.get("ITER_METTA_QUERY_TIMEOUT", "30"))


def _log(message):
    print("[atomspace] %s" % message, flush=True)


def _acquire_singleton_lock():
    # A clean packaged workspace has no runtime directories yet. The lock is
    # state-owned, so its parent must be established before the first writer
    # attempts to acquire it; development checkouts previously masked this by
    # already containing ``.runtime/atomspace``.
    lock_path = Path(LOCK_PATH)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    try:
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
    except Exception:
        pass
    return handle


def _logical_units(text):
    """Yield balanced MeTTa units while removing comments outside strings."""
    depth = 0
    buffer = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        in_string = False
        cut = len(line)
        for index, char in enumerate(line):
            if char == '"' and (index == 0 or line[index - 1] != "\\"):
                in_string = not in_string
            elif char == ";" and not in_string:
                cut = index
                break
        line = line[:cut].rstrip()
        if not line:
            continue
        buffer.append(line)
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            yield " ".join(buffer)
            buffer = []
            depth = 0
    if buffer:
        raise RuntimeError("unbalanced MeTTa source unit")


def _load_declared_seeds():
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("entries"), list):
        raise RuntimeError("state_manifest.json has an unsupported shape")
    seeds = []
    for entry in manifest["entries"]:
        if entry.get("role") != "source_seed" or entry.get("format") != "metta":
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            raise RuntimeError("source_seed entry has no path")
        source_path = (ITER_DIR / relative).resolve()
        if ITER_DIR not in source_path.parents:
            raise RuntimeError("source seed escapes ITER_DIR: %s" % relative)
        if not source_path.is_file():
            raise RuntimeError("declared source seed is missing: %s" % relative)
        text = source_path.read_text(encoding="utf-8", errors="replace")
        units = list(_logical_units(text))
        seeds.append({"path": relative, "units": units})
    if not seeds:
        raise RuntimeError("state manifest declares no MeTTa source seeds")
    return seeds


def _add_atom_source(engine, source):
    """Insert one stored atom with Hyperon's tokenizer and native space API.

    This is loading, not evaluation. Running add-atom through the interpreter
    for every stored atom dominates reconstruction of an otherwise small space.
    Parse the complete unit so malformed/multiple atoms cannot be silently lost.
    """
    atoms = engine.parse_all(source)
    if len(atoms) != 1:
        raise ValueError("stored source unit must contain exactly one atom")
    engine.space().add_atom(atoms[0])


class MettaSpace:
    """Combines durable transactions with reconstructable Hyperon engines."""

    def __init__(self):
        self.started_at = time.time()
        self.engine_lock = threading.RLock()
        self.engine_error = None
        self.engine = None
        self.query_cache = {}
        self.seed_files = _load_declared_seeds()
        self.seed_units = [unit for seed in self.seed_files for unit in seed["units"]]
        self.store = AtomspaceStore(STATE_DIR)
        self.foundry_service = None
        self.foundry_lock = threading.RLock()
        try:
            self._rebuild_engine(self.store.atoms)
            self.legacy_migration = migrate_legacy_state(
                self.store, self._rebuild_engine, ITER_DIR
            )
        except Exception as exc:
            self.engine = None
            self.engine_error = "%s: %s" % (type(exc).__name__, exc)
            _log("engine reconstruction/migration failed: %s" % self.engine_error)
            self.legacy_migration = {
                "status": "failed",
                "error": self.engine_error,
            }
        self.das_projection = DASProjectionWorker(
            lambda after, limit: self.store.events_after(after, limit),
            STATE_DIR.parent,
            current_epoch=lambda: self.store.epoch,
        )
        self.das_projection.start()

    @property
    def engine_available(self):
        return self.engine is not None

    def _new_engine_unlocked(self, atoms):
        from hyperon import Environment, MeTTa

        WORKING_DIR.mkdir(parents=True, exist_ok=True)
        environment = Environment.custom_env(
            working_dir=str(WORKING_DIR), config_dir=None, create_config=False
        )
        engine = MeTTa(env_builder=environment)
        for unit in self.seed_units:
            _add_atom_source(engine, unit)
        for key in sorted(atoms):
            _add_atom_source(engine, atoms[key])
        return engine

    def _new_engine(self, atoms):
        # Hyperon's native runtime is not safe to enter concurrently, even
        # when callers construct separate MeTTa objects.  The RPC server is
        # threaded, so every native construction/run path shares this gate.
        with self.engine_lock:
            return self._new_engine_unlocked(atoms)

    def _rebuild_engine(self, atoms):
        with self.engine_lock:
            replacement = self._new_engine_unlocked(atoms)
            self.engine = replacement
            self.engine_error = None

    def _require_engine(self):
        if not self.engine_available:
            raise RuntimeError("Hyperon engine unavailable: %s" % self.engine_error)

    def query(self, code, cacheable=False, view="full"):
        """Evaluate one named snapshot in a disposable native process."""
        self._require_engine()
        code = str(code).strip()
        if not code:
            raise ValueError("empty MeTTa code")
        snapshot = self.store.state_copy()
        if view not in ("full", "current"):
            raise ValueError("query view must be full or current")
        # Explicit internal working view; historical queries keep full access.
        # No stored atom is removed. All non-event atoms and source rules remain.
        query_snapshot = snapshot
        if view == "current":
            query_snapshot = {**snapshot, "atoms": {
                key: atom for key, atom in snapshot["atoms"].items()
                if not key.startswith("event:")
            }}
        view_hash = hashlib.sha256(json.dumps(query_snapshot["atoms"], sort_keys=True).encode()).hexdigest()
        if ("\n" not in code and code.startswith("(") and code.endswith(")")
                and not code.startswith("!(")):
            code = "!" + code
        with self.engine_lock:
            self._require_engine()
            # Seeds are small source files, not the growing event journal.
            # Read changes before considering a cached internal read.
            current_seeds = _load_declared_seeds()
            if current_seeds != self.seed_files:
                self.seed_files = current_seeds
                self.seed_units = [u for seed in current_seeds for u in seed["units"]]
                self.query_cache.clear()
            seed_hash = hashlib.sha256(json.dumps(self.seed_units).encode()).hexdigest()
            key = (snapshot["epoch"], view, view_hash, seed_hash, code)
            result = self.query_cache.get(key) if cacheable else None
            if result is None:
                result = self._run_query_worker(query_snapshot, code)
                if cacheable:
                    if len(self.query_cache) >= 64:
                        self.query_cache.clear()
                    self.query_cache[key] = result
        return {
            "result": result,
            "epoch": snapshot["epoch"],
            "commit": snapshot["commit"],
            "state_hash": snapshot["state_hash"],
            "view": view,
            "view_hash": view_hash,
        }

    def _run_query_worker(self, snapshot, code):
        payload = {
            "schema_version": 1,
            "epoch": snapshot["epoch"],
            "commit": snapshot["commit"],
            "state_hash": snapshot["state_hash"],
            "seed_units": snapshot.get("seed_units", self.seed_units),
            "atoms": snapshot["atoms"],
            "code": code,
            "working_dir": str(WORKING_DIR / "queries"),
        }
        try:
            completed = subprocess.run(
                [sys.executable, str(QUERY_WORKER_PATH)],
                input=json.dumps(payload),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(ITER_DIR),
                timeout=QUERY_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "isolated Hyperon query exceeded %ss" % QUERY_TIMEOUT_S
            ) from exc
        stderr_tail = completed.stderr.strip()[-2000:]
        if completed.returncode != 0:
            raise RuntimeError(
                "isolated Hyperon query worker exited %s: %s"
                % (completed.returncode, stderr_tail or "no native diagnostic")
            )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("isolated Hyperon query worker returned no response")
        try:
            response = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("isolated Hyperon query worker returned invalid JSON") from exc
        if not response.get("ok"):
            raise RuntimeError(response.get("error") or "isolated Hyperon query failed")
        return str(response.get("result", ""))

    def run(self, code):
        """Compatibility alias: generic execution is isolated/read-only."""
        return self.query(code)["result"]

    def transact(self, params):
        self._require_engine()
        # Check the exact canonical keys the store will write. Checking raw
        # caller spelling first would permit whitespace-prefixed fabric keys,
        # because the journal's normalizer strips that whitespace afterwards.
        operations = self.store._normalise_operations(params.get("operations"))
        if any(op["key"].startswith("fabric:") for op in operations):
            raise PermissionError("named cognitive spaces are service-owned; use the scoped foundry interface")
        return self.store.transact(
            operations=operations,
            actor=params.get("actor", "unknown"),
            source=params.get("source", "unknown"),
            transaction_id=params.get("transaction_id"),
            metadata=params.get("metadata"),
            expected_atoms=params.get("expected_atoms"),
            rebuild_engine=self._rebuild_engine,
        )

    def foundry(self, params):
        self._require_engine()
        with self.foundry_lock:
            if self.foundry_service is None:
                from iterbrow_runtime.foundry_service import FoundryService
                self.foundry_service = FoundryService(self, ITER_DIR)
        return self.foundry_service.request(params)

    def checkpoint(self):
        return self.store.checkpoint()

    def quiesce(self):
        self.store.set_quiesced(True)
        result = self.store.checkpoint()
        result["quiesced"] = True
        return result

    def resume(self):
        self.store.set_quiesced(False)
        return {"quiesced": False, "commit": self.store.commit, "epoch": self.store.epoch}

    def reset(self):
        return self.store.reset(rebuild_engine=self._rebuild_engine)

    def subscribe(self, params):
        return {
            "epoch": self.store.epoch,
            "events": self.store.events_after(
                params.get("after_commit", 0), params.get("limit", 100)
            ),
            "current_commit": self.store.commit,
        }

    def status(self):
        state = self.store.state_copy()
        return {
            "ready": self.engine_available,
            "engine": "hyperon",
            "engine_available": self.engine_available,
            "engine_error": self.engine_error,
            "query_isolation": "one_shot_process",
            "uptime_s": round(time.time() - self.started_at, 1),
            "epoch": state["epoch"],
            "commit": state["commit"],
            "state_hash": state["state_hash"],
            "runtime_atom_count": len(state["atoms"]),
            "seed_atom_count": len(self.seed_units),
            "seed_files": [seed["path"] for seed in self.seed_files],
            "quiesced": state["quiesced"],
            "snapshot_path": str(self.store.snapshot_path),
            "journal_path": str(self.store.wal_path),
            "iter_dir": str(ITER_DIR),
            "state_dir": str(STATE_DIR),
            "lock_path": str(LOCK_PATH),
            "manifest_path": str(MANIFEST_PATH),
            "legacy_migration": self.legacy_migration,
            "pid": os.getpid(),
            "das": self.das_projection.status(),
        }


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        space = self.server.metta_space
        try:
            buffer = b""
            while b"\n" not in buffer:
                remaining = MAX_REQUEST_BYTES - len(buffer)
                if remaining <= 0:
                    raise ValueError("request exceeds maximum size")
                chunk = self.request.recv(min(1 << 20, remaining))
                if not chunk:
                    return
                buffer += chunk
            line, _, _ = buffer.partition(b"\n")
            request = json.loads(line.decode("utf-8"))
            method = request.get("method")
            params = request.get("params") or {}
            if method == "run":
                result = space.run(params.get("code", ""))
            elif method == "query":
                result = space.query(params.get("code", ""), cacheable=params.get("cacheable") is True,
                                     view=params.get("view", "full"))
            elif method == "transact":
                result = space.transact(params)
            elif method == "foundry":
                result = space.foundry(params)
            elif method == "checkpoint":
                result = space.checkpoint()
            elif method == "subscribe":
                result = space.subscribe(params)
            elif method == "quiesce":
                result = space.quiesce()
            elif method == "resume":
                result = space.resume()
            elif method == "reset":
                result = space.reset()
            elif method == "status":
                result = space.status()
            elif method == "read_atoms":
                # Structured read of canonical bytes for projection/revision;
                # no second writer and no native query needed to read state.
                prefix = str(params.get("prefix", ""))
                if not prefix:
                    raise ValueError("read_atoms requires a prefix")
                result = space.store.state_copy()
                result["atoms"] = {k: v for k, v in result["atoms"].items() if k.startswith(prefix)}
            elif method == "shutdown":
                result = space.checkpoint()
                result["shutting_down"] = True
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                raise ValueError("unknown method: %s" % method)
            response = {"ok": True, "result": result}
        except Exception as exc:
            response = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
        try:
            self.request.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except Exception:
            pass


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    lock_handle = _acquire_singleton_lock()
    if lock_handle is None:
        _log("another AtomSpace service owns %s; refusing a second instance" % LOCK_PATH)
        return 0

    try:
        space = MettaSpace()
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass
        server = _Server(SOCKET_PATH, _Handler)
        server.metta_space = space
        _log(
            "ready on %s (engine=%s, epoch=%s, commit=%s, pid=%s)"
            % (SOCKET_PATH, space.engine_available, space.store.epoch, space.store.commit, os.getpid())
        )
        try:
            server.serve_forever()
        finally:
            space.das_projection.close()
            server.server_close()
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
