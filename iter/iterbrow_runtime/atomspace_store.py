"""Durable, engine-neutral transaction store for IterBrow's AtomSpace.

The store owns transaction identity, ordering, idempotency, WAL durability,
snapshots, and replay. A reasoning engine is supplied as a callback so Hyperon
is the first engine without becoming the persistence contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path


SCHEMA_VERSION = 1


class AtomspaceStoreError(RuntimeError):
    pass


class TransactionConflict(AtomspaceStoreError):
    pass


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_atoms(atoms):
    return hashlib.sha256(_canonical_json(atoms).encode("utf-8")).hexdigest()


def _fsync_directory(path):
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except (AttributeError, OSError):
        pass


def _atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, indent=2, ensure_ascii=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp), str(path))
    _fsync_directory(path.parent)


def _atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp), str(path))
    _fsync_directory(path.parent)


class AtomspaceStore:
    """Keyed mutable atoms backed by an append-only transaction journal."""

    def __init__(self, state_dir, snapshot_every=50):
        self.state_dir = Path(state_dir)
        self.wal_path = self.state_dir / "journal.jsonl"
        self.snapshot_path = self.state_dir / "snapshot.json"
        self.snapshot_every = max(1, int(snapshot_every))
        self.lock = threading.RLock()
        self.epoch = ""
        self.commit = 0
        self.atoms = {}
        self.transactions = {}
        self.transaction_payloads = {}
        self.quiesced = False
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._recover()

    @property
    def state_hash(self):
        return _hash_atoms(self.atoms)

    def _new_epoch(self):
        return str(uuid.uuid4())

    def _load_snapshot(self):
        if not self.snapshot_path.exists():
            return None
        try:
            with self.snapshot_path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except Exception as exc:
            raise AtomspaceStoreError("snapshot is unreadable: %s" % exc) from exc
        checksum = payload.pop("checksum", None)
        actual = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        if checksum != actual:
            raise AtomspaceStoreError("snapshot checksum mismatch")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise AtomspaceStoreError("unsupported snapshot schema")
        if not isinstance(payload.get("atoms"), dict):
            raise AtomspaceStoreError("snapshot atoms must be an object")
        return payload

    def _journal_records(self):
        if not self.wal_path.exists():
            return []
        records = []
        raw = self.wal_path.read_bytes()
        ended_with_newline = raw.endswith(b"\n")
        lines = raw.split(b"\n")
        if ended_with_newline:
            lines = lines[:-1]
        incomplete_tail = None
        for index, raw_line in enumerate(lines):
            if not raw_line.strip():
                continue
            try:
                records.append(json.loads(raw_line.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if index == len(lines) - 1 and not ended_with_newline:
                    incomplete_tail = raw_line
                    break
                raise AtomspaceStoreError("journal corruption at line %d" % (index + 1)) from exc
        if incomplete_tail is not None:
            records.append({
                "schema_version": SCHEMA_VERSION,
                "kind": "recovery",
                "epoch": self.epoch,
                "at": time.time(),
                "reason": "discarded incomplete final journal record",
                "discarded_tail_sha256": hashlib.sha256(incomplete_tail).hexdigest(),
            })
            _atomic_text(
                self.wal_path,
                "".join(_canonical_json(record) + "\n" for record in records),
            )
        elif raw and not ended_with_newline:
            # A complete final record with only its newline missing is valid,
            # but normalise it before a later append so records cannot join.
            _atomic_text(
                self.wal_path,
                "".join(_canonical_json(record) + "\n" for record in records),
            )
        return records

    def _recover(self):
        snapshot = self._load_snapshot()
        if snapshot:
            self.epoch = snapshot["epoch"]
        records = self._journal_records()
        if snapshot:
            self.epoch = snapshot["epoch"]
            self.commit = int(snapshot["commit"])
            self.atoms = dict(snapshot["atoms"])
            if snapshot.get("state_hash") != self.state_hash:
                raise AtomspaceStoreError("snapshot state hash mismatch")
        else:
            epochs = {r.get("epoch") for r in records if r.get("kind") in ("prepare", "commit")}
            if len(epochs) > 1 or (epochs and not all(epochs)):
                raise AtomspaceStoreError("Missing snapshot: journal epochs are ambiguous; retained journal was not reset")
            self.epoch = next(iter(epochs)) if epochs else self._new_epoch()
            self.commit = 0
            self.atoms = {}

        prepares = {}
        for record in records:
            if record.get("schema_version") != SCHEMA_VERSION:
                raise AtomspaceStoreError("unsupported journal schema")
            if record.get("epoch") != self.epoch:
                continue
            kind = record.get("kind")
            txid = record.get("transaction_id")
            if kind == "prepare":
                prepares[txid] = record
            elif kind == "abort":
                prepares.pop(txid, None)
            elif kind == "commit":
                prepared = prepares.get(txid)
                if not prepared:
                    raise AtomspaceStoreError("commit without prepare: %s" % txid)
                sequence = int(record.get("commit", 0))
                result = {
                    "transaction_id": txid,
                    "epoch": self.epoch,
                    "commit": sequence,
                    "state_hash": record.get("state_hash"),
                    "duplicate": False,
                }
                self.transactions[txid] = result
                self.transaction_payloads[txid] = _canonical_json([
                    prepared["operations"], prepared.get("metadata") or {}])
                if sequence > self.commit:
                    if sequence != self.commit + 1:
                        raise AtomspaceStoreError("non-contiguous commit sequence")
                    self.atoms = self._apply_operations(self.atoms, prepared["operations"])
                    if record.get("state_hash") != self.state_hash:
                        raise AtomspaceStoreError("journal state hash mismatch at commit %d" % sequence)
                    self.commit = sequence

        if not snapshot:
            self.checkpoint()

    def _append(self, record):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.wal_path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical_json(record) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        _fsync_directory(self.state_dir)

    def _normalise_operations(self, operations):
        if not isinstance(operations, list) or not operations:
            raise AtomspaceStoreError("operations must be a non-empty list")
        normalised = []
        for raw in operations:
            if not isinstance(raw, dict):
                raise AtomspaceStoreError("each operation must be an object")
            op = str(raw.get("op", "")).lower()
            if op not in ("add", "replace", "upsert", "remove"):
                raise AtomspaceStoreError("unknown operation: %s" % op)
            atom = raw.get("atom")
            key = raw.get("key")
            if op in ("add", "replace", "upsert"):
                if not isinstance(atom, str) or not atom.strip():
                    raise AtomspaceStoreError("%s requires a non-empty atom" % op)
                atom = atom.strip()
            if key is None and atom:
                key = "sha256:" + hashlib.sha256(atom.encode("utf-8")).hexdigest()
            if not isinstance(key, str) or not key.strip():
                raise AtomspaceStoreError("operation requires a key")
            item = {"op": op, "key": key.strip()}
            if atom is not None:
                item["atom"] = atom
            normalised.append(item)
        return normalised

    def _apply_operations(self, base, operations):
        result = dict(base)
        for operation in operations:
            op = operation["op"]
            key = operation["key"]
            if op == "add":
                if key in result and result[key] != operation["atom"]:
                    raise TransactionConflict("atom key already exists with different value: %s" % key)
                result[key] = operation["atom"]
            elif op == "replace":
                if key not in result:
                    raise TransactionConflict("cannot replace missing atom key: %s" % key)
                result[key] = operation["atom"]
            elif op == "upsert":
                result[key] = operation["atom"]
            elif op == "remove":
                result.pop(key, None)
        return result

    def transact(self, operations, actor="unknown", source="unknown", transaction_id=None,
                 rebuild_engine=None, metadata=None, expected_atoms=None):
        with self.lock:
            if self.quiesced:
                raise AtomspaceStoreError("AtomSpace is quiesced")
            transaction_id = str(transaction_id or uuid.uuid4())
            operations = self._normalise_operations(operations)
            payload = _canonical_json([operations, metadata or {}])
            if transaction_id in self.transactions:
                if self.transaction_payloads.get(transaction_id) != payload:
                    raise TransactionConflict("transaction identity reused with different content")
                previous = dict(self.transactions[transaction_id])
                previous["duplicate"] = True
                return previous
            if expected_atoms is not None:
                if not isinstance(expected_atoms, dict):
                    raise AtomspaceStoreError("expected_atoms must be an object")
                if any(self.atoms.get(key) != value for key, value in expected_atoms.items()):
                    raise TransactionConflict("source beliefs changed; recompute the pending observation")
            next_atoms = self._apply_operations(self.atoms, operations)
            sequence = self.commit + 1
            prepared = {
                "schema_version": SCHEMA_VERSION,
                "kind": "prepare",
                "epoch": self.epoch,
                "transaction_id": transaction_id,
                "commit": sequence,
                "actor": str(actor),
                "source": str(source),
                "at": time.time(),
                "operations": operations,
                "metadata": metadata if isinstance(metadata, dict) else {},
                "previous_state_hash": self.state_hash,
                "next_state_hash": _hash_atoms(next_atoms),
            }
            self._append(prepared)
            try:
                if rebuild_engine:
                    rebuild_engine(next_atoms)
            except Exception as exc:
                self._append({
                    "schema_version": SCHEMA_VERSION,
                    "kind": "abort",
                    "epoch": self.epoch,
                    "transaction_id": transaction_id,
                    "commit": sequence,
                    "at": time.time(),
                    "error": "%s: %s" % (type(exc).__name__, exc),
                })
                if rebuild_engine:
                    rebuild_engine(self.atoms)
                raise

            commit_record = {
                "schema_version": SCHEMA_VERSION,
                "kind": "commit",
                "epoch": self.epoch,
                "transaction_id": transaction_id,
                "commit": sequence,
                "at": time.time(),
                "state_hash": _hash_atoms(next_atoms),
            }
            try:
                self._append(commit_record)
            except Exception:
                if rebuild_engine:
                    rebuild_engine(self.atoms)
                raise
            self.atoms = next_atoms
            self.commit = sequence
            result = {
                "transaction_id": transaction_id,
                "epoch": self.epoch,
                "commit": self.commit,
                "state_hash": self.state_hash,
                "duplicate": False,
            }
            self.transactions[transaction_id] = result
            self.transaction_payloads[transaction_id] = payload
            if self.commit % self.snapshot_every == 0:
                self.checkpoint()
            return dict(result)

    def checkpoint(self):
        with self.lock:
            payload = {
                "schema_version": SCHEMA_VERSION,
                "epoch": self.epoch,
                "commit": self.commit,
                "state_hash": self.state_hash,
                "atoms": self.atoms,
                "created_at": time.time(),
            }
            payload["checksum"] = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
            _atomic_json(self.snapshot_path, payload)
            return {
                "epoch": self.epoch,
                "commit": self.commit,
                "state_hash": self.state_hash,
                "snapshot": str(self.snapshot_path),
            }

    def set_quiesced(self, value):
        with self.lock:
            self.quiesced = bool(value)
            return self.quiesced

    def reset(self, rebuild_engine=None):
        with self.lock:
            previous_epoch = self.epoch
            previous_commit = self.commit
            previous_atoms = dict(self.atoms)
            previous_transactions = dict(self.transactions)
            previous_payloads = dict(self.transaction_payloads)
            previous_wal = self.wal_path.read_text(encoding="utf-8") if self.wal_path.exists() else ""
            previous_snapshot = self.snapshot_path.read_text(encoding="utf-8") if self.snapshot_path.exists() else None
            try:
                if rebuild_engine:
                    rebuild_engine({})
                self.epoch = self._new_epoch()
                self.commit = 0
                self.atoms = {}
                self.transactions = {}
                self.transaction_payloads = {}
                _atomic_text(self.wal_path, "")
                return self.checkpoint()
            except Exception:
                self.epoch = previous_epoch
                self.commit = previous_commit
                self.atoms = previous_atoms
                self.transactions = previous_transactions
                self.transaction_payloads = previous_payloads
                _atomic_text(self.wal_path, previous_wal)
                if previous_snapshot is None:
                    try:
                        self.snapshot_path.unlink()
                    except FileNotFoundError:
                        pass
                else:
                    _atomic_text(self.snapshot_path, previous_snapshot)
                if rebuild_engine:
                    rebuild_engine(previous_atoms)
                raise

    def state_copy(self):
        with self.lock:
            return {
                "epoch": self.epoch,
                "commit": self.commit,
                "state_hash": self.state_hash,
                "atoms": copy.deepcopy(self.atoms),
                "quiesced": self.quiesced,
            }

    def events_after(self, after_commit=0, limit=100):
        after_commit = int(after_commit or 0)
        limit = max(1, min(int(limit or 100), 1000))
        prepares = {}
        events = []
        with self.lock:
            for record in self._journal_records():
                if record.get("epoch") != self.epoch:
                    continue
                if record.get("kind") == "prepare":
                    prepares[record.get("transaction_id")] = record
                elif record.get("kind") == "commit" and int(record.get("commit", 0)) > after_commit:
                    prepared = prepares.get(record.get("transaction_id"))
                    if prepared:
                        events.append({
                            "epoch": self.epoch,
                            "commit": int(record["commit"]),
                            "transaction_id": record["transaction_id"],
                            "actor": prepared.get("actor"),
                            "source": prepared.get("source"),
                            "at": record.get("at"),
                            "operations": prepared.get("operations", []),
                            "metadata": prepared.get("metadata", {}),
                            "state_hash": record.get("state_hash"),
                        })
                        if len(events) >= limit:
                            break
        return events
