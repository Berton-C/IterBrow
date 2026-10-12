"""Small persistent vector store for Iter, ported from the browser build.

Ported from the browser/MicroPython build's tools/_petta_db.py. That version
requested embeddings through `bridge.llm(...)` / `js.fetch(...)` inside the
WASM sandbox. This native port makes the same OpenRouter embeddings request
directly via urllib.request, using the OPENROUTER_API_KEY environment
variable (the same one main.js sets for the chat provider) instead of
reading a browser-side `bridge.config()` blob. Everything else — the
pure-Python cosine-similarity store, on-disk JSON format, int8 quantization —
is unchanged, so an existing chroma_db/memories.json carried over from the
browser build stays compatible (same model/dimensions/schema).
"""

import os
import json
import time
import math
import hashlib
import binascii
import sys
import uuid
import fcntl
import shutil
import urllib.request
from contextlib import contextmanager
from pathlib import Path


# Component code may execute from an immutable hot-load generation.  The
# semantic-memory projection is application state and must never move with it.
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
DB_DIR = ROOT + "/chroma_db"
DB_FILE = DB_DIR + "/memories.json"

# ITER_EMBEDDING_URL lets tests (and, later, a local embedding server) supply
# the embeddings endpoint; the default is OpenRouter as before.
EMBEDDING_URL = os.environ.get("ITER_EMBEDDING_URL") or "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_SCHEMA = 3
EMBEDDING_BATCH_SIZE = 32

_id_counter = 0

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from iterbrow_runtime.cognitive_events import (
    commit_batch, metta_string, parse_semantic_atom, _call_atomspace, SEMANTIC_PREFIX)


class MemoryCommitUncertain(RuntimeError):
    execution_outcome = {"success": None, "state": "uncertain", "scope": "invocation",
                         "task_fulfillment": "unverified"}


class MemoryAuthorityUnavailable(RuntimeError):
    """The AtomSpace could not be reached; nothing was sent, nothing changed."""
    execution_outcome = {"success": False, "state": "not_executed", "scope": "invocation",
                         "task_fulfillment": "unverified"}


class MemoryProjectionPending(RuntimeError):
    execution_outcome = {"success": None, "state": "projection_pending", "scope": "invocation",
                         "task_fulfillment": "unverified"}


def _pending_dir():
    return Path(ROOT) / ".runtime" / "memory_pending"


def _normal(text):
    return " ".join(str(text or "").split())


def pending_remember(text, mem_type=None, provenance_type=None):
    """Resume the identity of an interrupted (uncertain) remember of the same request.

    Entries only survive an uncertain outcome (sent without a reply, or a worker
    killed mid-write); every definite outcome removes its entry.  An entry is
    reused only when text, mem_type and provenance_type all match, so a later,
    different request never inherits an old identity or type.
    """
    wanted = _normal(text)
    for path in sorted(_pending_dir().glob("*.json")):
        try:
            entry = json.loads(path.read_text())
            kind, records, _ = entry["request"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if kind != "remembered" or len(records) != 1:
            continue
        record = records[0]
        metadata = record.get("metadata") or {}
        if (_normal(record.get("document")) == wanted
                and (mem_type is None or metadata.get("mem_type") == mem_type)
                and (provenance_type is None or metadata.get("provenance_type") == provenance_type)):
            return record
    return None


def discard_pending_remember(text, keep_path=None):
    """Drop remember entries for `text` superseded by a definite outcome."""
    wanted = _normal(text)
    for path in sorted(_pending_dir().glob("*.json")):
        if keep_path and str(path) == str(keep_path):
            continue
        try:
            kind, records, _ = json.loads(path.read_text())["request"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if kind == "remembered" and len(records) == 1 and _normal(records[0].get("document")) == wanted:
            _remove_if_present(str(path))


class MemoryConflict(RuntimeError):
    """The memory changed between read and commit; nothing was written."""
    execution_outcome = {"success": False, "state": "not_executed", "scope": "invocation",
                         "task_fulfillment": "unverified"}


def _read_authority(prefix):
    try:
        return _call_atomspace("read_atoms", timeout=10, prefix=prefix)
    except OSError as error:
        if getattr(error, "atomspace_not_sent", False):
            raise MemoryAuthorityUnavailable(
                "The AtomSpace authority is unreachable (%s); semantic memory cannot be read "
                "or changed until the AtomSpace service is running." % error) from error
        raise


def authority_memories():
    """(snapshot, {id: (document, metadata, atom)}) for every semantic-memory atom."""
    snapshot = _read_authority(SEMANTIC_PREFIX)
    memories = {}
    for key, atom in snapshot["atoms"].items():
        try:
            item_id, document, metadata = parse_semantic_atom(key, atom)
        except ValueError:
            continue
        memories[item_id] = (document, metadata, atom)
    return snapshot, memories


def read_memory(item_id):
    """The authority's current (document, metadata, atom) for item_id, or None."""
    key = SEMANTIC_PREFIX + str(item_id)
    atom = _read_authority(key)["atoms"].get(key)
    if atom is None:
        return None
    _, document, metadata = parse_semantic_atom(key, atom)
    return document, metadata, atom


DEFAULT_STV = (1.0, 0.5)


def counted_evidence(metadata):
    """Episodes already counted in this memory's truth value: {episode: "+"|"-"}.

    linkedEpisodes are pure links; evidenceEpisodes records what truth revision
    has counted, so each episode contributes evidence at most once and
    link/unlink never change it.  Memories written before evidenceEpisodes
    existed used linkedEpisodes for both.  Rule for those (migrate on read):
    if the memory's stv was ever revised away from the default (1.0, 0.5), every
    pre-existing linked episode counts as already-counted positive evidence;
    if it never was, none of its links were counted.
    """
    evidence = metadata.get("evidenceEpisodes")
    if isinstance(evidence, dict):
        return {str(k): v for k, v in evidence.items()}
    try:
        stv = (float(metadata.get("strength", 1.0)), float(metadata.get("confidence", 0.5)))
    except (TypeError, ValueError):
        stv = None
    linked = metadata.get("linkedEpisodes") or []
    if stv == DEFAULT_STV or not isinstance(linked, list):
        return {}
    return {str(episode): "+" for episode in linked}


def with_counted_evidence(metadata):
    """Materialise counted evidence before linkedEpisodes is edited (legacy memories)."""
    if "evidenceEpisodes" not in metadata:
        evidence = counted_evidence(metadata)
        if evidence:
            metadata["evidenceEpisodes"] = evidence
    return metadata


def _index_put(db, item_id, document, metadata, embedding=None):
    """Mirror one authoritative memory into the index (vector kept if text unchanged)."""
    if item_id in db["ids"]:
        index = db["ids"].index(item_id)
        if embedding is None and db["documents"][index] != document:
            _index_drop(db, [item_id])  # stale vector: reconcile re-embeds it
            return
        db["documents"][index] = document
        db["metadatas"][index] = metadata
        if embedding is not None:
            db["embeddings"][index] = embedding
    elif embedding is not None:
        db["ids"].append(item_id)
        db["documents"].append(document)
        db["metadatas"].append(metadata)
        db["embeddings"].append(embedding)


def _index_drop(db, ids):
    for item_id in ids:
        while item_id in db["ids"]:
            index = db["ids"].index(item_id)
            for field in ("ids", "documents", "metadatas", "embeddings"):
                del db[field][index]


def _conflict_guard(error):
    if "TransactionConflict" in str(error):
        return MemoryConflict(
            "The memory changed while this edit was being made; nothing was written. "
            "Re-read it and retry.")
    return None


def modify_memory(item_id, mutate, embedding=None):
    """Read-modify-write one memory against the AUTHORITY.

    mutate(document, metadata) returns a refusal string (nothing written) or
    (new_document, new_metadata, message).  The commit carries the atom that
    was read as expected_atoms, so a stale base raises a conflict instead of
    overwriting committed evidence.  Returns the message, or None when the
    authority has no such memory.
    """
    key = SEMANTIC_PREFIX + str(item_id)
    with writer_lock():
        current = read_memory(item_id)
        if current is None:
            return None
        document, metadata, atom = current
        outcome = mutate(document, json.loads(json.dumps(metadata)))
        if isinstance(outcome, str):
            return outcome
        new_document, new_metadata, message = outcome
        if new_document == document and new_metadata == metadata:
            return message
        try:
            committed = _commit_memory_change(
                "memory_updated", [{"id": item_id, "document": new_document, "metadata": new_metadata}],
                expected_atoms={key: atom})
        except RuntimeError as error:
            conflict = _conflict_guard(error)
            if conflict:
                raise conflict from error
            raise
        db = _load(write=True)
        _index_put(db, item_id, new_document, new_metadata, embedding)
        _save_committed_projection(db, committed)
        return message


def memory_status(item_id):
    """Read committed identity without embeddings or repeating the write."""
    key = "state:semantic_memory:" + str(item_id)
    snapshot = _call_atomspace("read_atoms", timeout=10, prefix=key)
    atom = snapshot["atoms"].get(key)
    return {"memory_id": item_id, "state": "committed" if atom else "not_observed",
            "commit": snapshot["commit"], "atom": atom,
            "search_projection_present": item_id in _load()["ids"],
            "notice": "A missing record is not proof that an in-flight write failed."}


def _finish_memory_projection(result):
    """Kept for callers of the old two-step API; pending entries now end at commit."""
    if isinstance(result, dict) and result.get("_pending_path"):
        _settle_pending(result["_pending_path"], result["_operation_id"])


def _settle_pending(path, operation_id):
    path = Path(path)
    try:
        if json.loads(path.read_text())["operation_id"] == operation_id:
            path.unlink()
    except (OSError, ValueError, KeyError):
        pass


def _save_committed_projection(db, committed):
    try:
        _save(db)
    except Exception as error:
        if isinstance(committed, dict):
            raise MemoryProjectionPending(
                "Durable memory commit %s is confirmed (the memory IS stored), but the search index "
                "could not be saved (%s). Do not retry or create a replacement: the index is rebuilt "
                "from the AtomSpace authority automatically." % (committed.get("commit"), error)
            ) from error
        raise


def _memory_atom(item_id, document, metadata):
    return "(semantic-memory %s %s %s)" % (
        metta_string(item_id), metta_string(document),
        metta_string(json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False)),
    )


def _commit_memory_change(kind, records, remove_ids=None, expected_atoms=None):
    """Commit one semantic-memory change to the AtomSpace authority.

    A pending entry (.runtime/memory_pending/<request digest>.json) holds the
    transaction id while the outcome is unknown, so an uncertain write can be
    retried without minting a second identity.  It is removed on every definite
    outcome; after a commit it is kept until the index is saved too.  A reused
    transaction id that the AtomSpace reports as an earlier duplicate is only
    accepted when the expected state is actually present (remember -> forget
    -> remember must not be swallowed by the first transaction).
    """
    canonical = json.dumps([kind, records, remove_ids or []], sort_keys=True, ensure_ascii=False)
    pending_dir = _pending_dir()
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending = pending_dir / (hashlib.sha256(canonical.encode()).hexdigest() + ".json")
    from iterbrow_runtime.atomspace_store import _atomic_json
    with writer_lock():
        created = not pending.exists()
        operation_id = None
        if not created:
            try:
                operation_id = json.loads(pending.read_text())["operation_id"]
            except (OSError, ValueError, KeyError):
                created = True
        if created:
            operation_id = uuid.uuid4().hex
            _atomic_json(pending, {"operation_id": operation_id, "request": json.loads(canonical)})
        ids = ",".join(str(record["id"]) for record in records)
        try:
            result = _commit_memory_operation(kind, records, remove_ids, operation_id, expected_atoms)
            if not created and result.get("duplicate") and not _expected_state_present(kind, records, remove_ids):
                # The old transaction committed long ago and the memory changed
                # since; re-sending its id is a no-op.  This is a new operation.
                operation_id = uuid.uuid4().hex
                _atomic_json(pending, {"operation_id": operation_id, "request": json.loads(canonical)})
                result = _commit_memory_operation(kind, records, remove_ids, operation_id, expected_atoms)
        except (OSError, json.JSONDecodeError) as error:
            if getattr(error, "atomspace_not_sent", False):
                # Definite: nothing reached the AtomSpace.  An entry left by an
                # earlier uncertain attempt stays; one made just now goes.
                if created:
                    _remove_if_present(str(pending))
                raise MemoryAuthorityUnavailable(
                    "Memory NOT stored: the AtomSpace authority is unreachable (%s); nothing was "
                    "changed for memory ID(s) %s. Retry once the AtomSpace service is running."
                    % (error, ids)
                ) from error
            raise MemoryCommitUncertain(
                "No confirmed reply for memory ID(s) %s, transaction %s. The write may commit later. "
                "Use remember(status_id=ID) to inspect it; retry the exact same text/IDs, not a reworded replacement."
                % (ids, "cognitive:memory:" + operation_id)
            ) from error
        except Exception:
            # The AtomSpace answered with a rejection: a definite outcome.
            _remove_if_present(str(pending))
            raise
        # A confirmed commit is a definite outcome.  The index may still lag;
        # reconcile_index() repairs it from the authority, so no entry is kept.
        _settle_pending(pending, operation_id)
        return {**result, "_pending_path": str(pending), "_operation_id": operation_id}


def _memory_state(kind, records, remove_ids):
    state_atoms = {}
    if kind != "forgotten":
        for record in records:
            state_atoms["semantic_memory:%s" % record["id"]] = _memory_atom(
                record["id"], record.get("document", ""), record.get("metadata", {}))
    return state_atoms, ["semantic_memory:%s" % item_id for item_id in (remove_ids or [])]


def _expected_state_present(kind, records, remove_ids):
    state_atoms, removed = _memory_state(kind, records, remove_ids)
    snapshot = _call_atomspace("read_atoms", timeout=10, prefix=SEMANTIC_PREFIX)["atoms"]
    return (all(snapshot.get("state:" + key) == atom for key, atom in state_atoms.items())
            and all(("state:" + key) not in snapshot for key in removed))


def _commit_memory_operation(kind, records, remove_ids, operation_id, expected_atoms=None):
    digest = operation_id
    events = []
    for record in records:
        item_id = record["id"]
        events.append({
            "event_id": "memory:%s:%s:%s" % (kind, item_id, digest[:16]),
            "domain": "semantic_memory",
            "entity_id": item_id,
            "event_type": kind,
            "payload": record,
        })
    state_atoms, removed = _memory_state(kind, records, remove_ids)
    return commit_batch(
        events,
        require=True,  # semantic memory always fails closed (never "deferred")
        state_atoms=state_atoms,
        remove_state_keys=removed,
        actor="iter",
        source="tools._petta_db",
        transaction_id="cognitive:memory:%s" % digest,
        expected_atoms=expected_atoms,
    )


def _exists(path):
    return os.path.exists(path)


def _mkdirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass


def _empty():
    # "authority_index" (written by reconcile_index) records which authority
    # state the index was last aligned with; older files simply lack it.
    return {
        "ids": [],
        "documents": [],
        "metadatas": [],
        "embeddings": [],
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "embedding_schema": EMBEDDING_SCHEMA,
    }


def _ensure_dir():
    try:
        _mkdirs(DB_DIR)
    except OSError:
        pass


def _validate(db, source):
    if not isinstance(db, dict):
        raise RuntimeError("Memory database is not an object: " + source)
    for key in ("ids", "documents", "metadatas", "embeddings"):
        if not isinstance(db.get(key), list):
            raise RuntimeError("Memory database has invalid " + key + ": " + source)
    count = len(db["ids"])
    if len(db["documents"]) != count or len(db["metadatas"]) != count or len(db["embeddings"]) != count:
        raise RuntimeError("Memory database arrays have different lengths: " + source)
    return db


def _read(path):
    with open(path, "r") as file:
        raw = file.read()
    try:
        db = json.loads(raw)
    except Exception as error:
        raise RuntimeError("Memory database JSON is corrupt at " + path + ": " + str(error))
    # Vectors stay in their stored (packed) form; they are decoded only for
    # scoring, so a load->save cycle writes back exactly the bytes it read.
    return _validate(db, path)


def _remove_if_present(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _write_new_file(path, db):
    storage_db = {
        "ids": db["ids"],
        "documents": db["documents"],
        "metadatas": db["metadatas"],
        "embeddings": [_quantize_embedding(e) for e in db["embeddings"]],
        "embedding_model": db.get("embedding_model", EMBEDDING_MODEL),
        "embedding_dimensions": db.get("embedding_dimensions", EMBEDDING_DIMENSIONS),
        "embedding_schema": EMBEDDING_SCHEMA,
    }
    if "authority_index" in db:
        storage_db["authority_index"] = db["authority_index"]
    with open(path, "w", encoding="utf-8") as file:
        file.write(json.dumps(storage_db))
        file.flush()
        os.fsync(file.fileno())


def _fsync_db_dir():
    try:
        descriptor = os.open(DB_DIR, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


_writer_depth = 0
_writer_handle = None


@contextmanager
def writer_lock():
    """One exclusive writer for the index: load -> authority commit -> save.

    flock on chroma_db/.writer.lock; re-entrant within a process.  Readers never
    take it and never write.
    """
    global _writer_depth, _writer_handle
    if _writer_depth:
        _writer_depth += 1
        try:
            yield
        finally:
            _writer_depth -= 1
        return
    _ensure_dir()
    handle = open(os.path.join(DB_DIR, ".writer.lock"), "a")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        _writer_depth, _writer_handle = 1, handle
        try:
            yield
        finally:
            _writer_depth, _writer_handle = 0, None
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _save(db):
    """Replace the index atomically; memories.json exists at every instant.

    tmp is written and fsynced, the current file is hard-linked (or copied) to
    .bak, then os.replace(tmp, DB_FILE).  A concurrent reader sees either the
    previous or the new complete file, never a gap.
    """
    _ensure_dir()
    _validate(db, "in-memory database")
    with writer_lock():
        tmp = "%s.tmp.%d" % (DB_FILE, os.getpid())
        backup = DB_FILE + ".bak"
        _remove_if_present(tmp)
        try:
            _write_new_file(tmp, db)
            if _exists(DB_FILE):
                staged = backup + ".tmp"
                _remove_if_present(staged)
                try:
                    os.link(DB_FILE, staged)
                except OSError:
                    shutil.copy2(DB_FILE, staged)
                os.replace(staged, backup)
            os.replace(tmp, DB_FILE)
            _fsync_db_dir()
        finally:
            _remove_if_present(tmp)


def _restore_backup(backup):
    """Writer-only: put the last good index back in place (under writer_lock)."""
    with writer_lock():
        db = _read(backup)
        recover = DB_FILE + ".recover"
        _remove_if_present(recover)
        _write_new_file(recover, db)
        os.replace(recover, DB_FILE)
        _fsync_db_dir()
        return db


def _load(write=False):
    """Read the index.  Readers fall back to .bak in memory and never write;
    only a writer (write=True, under writer_lock) restores .bak on disk."""
    _ensure_dir()
    backup = DB_FILE + ".bak"
    if _exists(DB_FILE):
        try:
            return _read(DB_FILE)
        except Exception:
            if not _exists(backup):
                raise
    elif not _exists(backup):
        return _empty()
    if write:
        return _restore_backup(backup)
    return _read(backup)


def _hex(data):
    return binascii.hexlify(data).decode("ascii")


def _quantize_embedding(vec):
    """Convert a float list to int8-packed dict for compact storage."""
    if not isinstance(vec, list) or not vec:  # already packed (or empty): unchanged
        return vec
    mn = min(vec)
    mx = max(vec)
    rng = mx - mn
    if rng == 0:
        rng = 1.0
    scale = rng / 255.0
    offset = mn
    packed = bytearray(len(vec))
    for i, v in enumerate(vec):
        q = int(round((v - offset) / scale))
        if q < 0:
            q = 0
        if q > 255:
            q = 255
        packed[i] = q
    return {"q": _hex(bytes(packed)), "s": scale, "o": offset}


def _dequantize_embedding(emb):
    """Convert int8-packed dict back to float list. Pass-through for float lists.

    Packed vectors are kept as they were stored (see _read) and _quantize_embedding
    passes them through, so re-saving never re-quantizes an already stored vector.
    """
    if isinstance(emb, dict) and "q" in emb:
        raw = binascii.unhexlify(emb["q"])
        scale = emb["s"]
        offset = emb["o"]
        return [b * scale + offset for b in raw]
    return emb


def gen_id():
    global _id_counter
    _id_counter += 1
    raw = str(time.time()) + ":" + str(_id_counter) + ":" + str(time.perf_counter_ns())
    return _hex(hashlib.sha256(raw.encode("utf-8")).digest())[:36]


def _cosine(a, b):
    if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b) or not a:
        return None
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _configured_key():
    key = os.environ.get("OPENROUTER_API_KEY") or ""
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set — long-term-memory embeddings need an OpenRouter "
            "key even while chatting through LM Studio. Set it in Settings."
        )
    return key


def _request_embedding_batch(texts, input_type):
    payload = {
        "model": EMBEDDING_MODEL,
        "input": texts,
        "dimensions": EMBEDDING_DIMENSIONS,
        "encoding_format": "float",
        "input_type": input_type,
        "provider": {"allow_fallbacks": True, "data_collection": "deny"},
    }
    key = _configured_key()
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        EMBEDDING_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
    except Exception as error:
        raise RuntimeError("Embedding transport failed: " + str(error))

    try:
        response = json.loads(raw)
    except Exception as error:
        raise RuntimeError("Invalid OpenRouter embeddings response: " + str(error))
    if response.get("error"):
        error = response.get("error") or {}
        raise RuntimeError("OpenRouter embeddings error: " + str(error.get("message", error)))
    data = response.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise RuntimeError("OpenRouter returned the wrong number of embeddings")
    data.sort(key=lambda item: int(item.get("index", 0)))
    vectors = []
    for item in data:
        vector = item.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise RuntimeError("OpenRouter returned an invalid embedding vector")
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                "OpenRouter returned " + str(len(vector)) + " dimensions; expected " + str(EMBEDDING_DIMENSIONS)
            )
        vectors.append(vector)
    return vectors


def get_embeddings(texts, input_type="search_document"):
    texts = [str(text or "") for text in texts]
    if not texts:
        return []
    vectors = []
    start = 0
    while start < len(texts):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        vectors.extend(_request_embedding_batch(batch, input_type))
        start += EMBEDDING_BATCH_SIZE
    return vectors


def get_embedding(text, input_type="search_document"):
    return get_embeddings([text], input_type)[0]


def _index_is_current(db):
    if db.get("embedding_model") != EMBEDDING_MODEL:
        return False
    if int(db.get("embedding_dimensions", 0) or 0) != EMBEDDING_DIMENSIONS:
        return False
    schema = int(db.get("embedding_schema", 0) or 0)
    if schema < 2:
        return False
    for vector in db.get("embeddings", []):
        if _vector_dimensions(vector) != EMBEDDING_DIMENSIONS:
            return False
    return True


def _vector_dimensions(vector):
    if isinstance(vector, dict) and isinstance(vector.get("q"), str):
        return len(vector["q"]) // 2
    return len(vector) if isinstance(vector, list) else 0


RECONCILE_RETRY_S = 60
TRUSTED_MIGRATION_STATES = ("migrated", "already_migrated", "not_needed")


def _authority_digest(atoms):
    pairs = sorted((key, atom) for key, atom in atoms.items() if key.startswith(SEMANTIC_PREFIX))
    return hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode("utf-8")).hexdigest()


def _authority_complete():
    """Orphans may only be removed when the authority holds every legacy memory:
    a failed legacy migration means the authority is missing what the index has."""
    try:
        status = _call_atomspace("status", timeout=10)
    except Exception:
        return False
    return (status.get("legacy_migration") or {}).get("status") in TRUSTED_MIGRATION_STATES


def index_gap(db=None):
    """Authority memories not yet searchable (embedding pending), per the last reconcile."""
    state = (db or _load()).get("authority_index") or {}
    return list(state.get("unindexed") or []), state.get("last_error")


def reconcile_index(force=False):
    """Align chroma_db (a rebuildable index) with the AtomSpace authority.

    Missing in the index -> embedded (batched) and added; index-only ids ->
    removed; differing document -> re-embedded; differing metadata -> the
    authority's.  Without embeddings, removals and metadata fixes still apply
    and the missing ids are recorded as unindexed (retried after a back-off).
    The authority's semantic-atom digest is stored in the index, so an aligned
    index costs one read_atoms and no writes.  Returns a summary dict.
    """
    try:
        snapshot, memories = authority_memories()
    except Exception as error:
        return {"status": "authority_unavailable", "error": str(error)}
    db = _load()
    state = db.get("authority_index") or {}
    if (not force and state.get("digest") == _authority_digest(snapshot["atoms"])
            and not state.get("unindexed") and _index_is_current(db)):
        return {"status": "current"}
    with writer_lock():
        snapshot, memories = authority_memories()
        digest = _authority_digest(snapshot["atoms"])
        db = _load(write=True)
        state = db.get("authority_index") or {}
        before = json.dumps(db, sort_keys=True, default=str)
        rebuilt = not _index_is_current(db)
        if rebuilt:
            # Old model/dimensions/hash vectors: drop the vectors, rebuild every
            # entry from the authority (never "delete chroma_db and start over").
            db = _empty()
        orphans = [item_id for item_id in db["ids"] if item_id not in memories]
        trusted = not orphans or _authority_complete()
        if trusted:
            _index_drop(db, orphans)
        missing = []
        for item_id, (document, metadata, _atom) in sorted(memories.items()):
            if item_id in db["ids"]:
                index = db["ids"].index(item_id)
                if db["documents"][index] != document:
                    _index_drop(db, [item_id])
                    missing.append(item_id)
                elif db["metadatas"][index] != metadata:
                    db["metadatas"][index] = metadata
            else:
                missing.append(item_id)
        error_text = None
        retry_after = float(state.get("retry_after") or 0)
        if missing and (force or time.time() >= retry_after):
            try:
                vectors = get_embeddings([memories[item_id][0] for item_id in missing], "search_document")
            except Exception as error:
                error_text = str(error)
                retry_after = time.time() + RECONCILE_RETRY_S
            else:
                for item_id, vector in zip(missing, vectors):
                    document, metadata, _atom = memories[item_id]
                    _index_put(db, item_id, document, metadata, vector)
                missing, retry_after = [], 0
        elif missing:
            error_text = state.get("last_error")
        db["embedding_model"] = EMBEDDING_MODEL
        db["embedding_dimensions"] = EMBEDDING_DIMENSIONS
        db["embedding_schema"] = EMBEDDING_SCHEMA
        db["authority_index"] = {
            "digest": digest if trusted and not missing else None,
            "epoch": snapshot.get("epoch"), "commit": snapshot.get("commit"),
            "count": len(memories), "unindexed": missing,
            "retry_after": retry_after if missing else 0,
            "last_error": error_text if missing else None,
        }
        changed = json.dumps(db, sort_keys=True, default=str) != before
        if changed:
            _save(db)
        return {"status": "reconciled" if changed else "current", "rebuilt": rebuilt,
                "removed": orphans if trusted else [], "orphans_kept": [] if trusted else orphans,
                "unindexed": missing, "error": error_text}


def require_current_index():
    """The index must use the current embedding model; otherwise it is rebuilt
    from the authority (reconcile_index) rather than deleted by hand."""
    db = _load()
    if not _index_is_current(db):
        raise RuntimeError(
            "The semantic-memory index at " + DB_FILE + " uses an old embedding format and could "
            "not be rebuilt yet: the AtomSpace authority (the source of every memory) is not "
            "reachable. Nothing is lost; it is rebuilt automatically once the AtomSpace service "
            "runs. Do not delete chroma_db."
        )
    return True


def status():
    db = _load()
    return {
        "count": len(db["ids"]),
        "path": DB_FILE,
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "index_current": _index_is_current(db),
    }


def _exclusive(method):
    """Hold the writer lock across load-index -> authority commit -> save-index."""
    def locked(*args, **kwargs):
        with writer_lock():
            return method(*args, **kwargs)
    locked.__name__ = method.__name__
    locked.__doc__ = method.__doc__
    return locked


class Collection:
    @_exclusive
    def add(self, ids, embeddings, documents, metadatas):
        db = _load(write=True)
        for i in range(len(ids)):
            item_id = ids[i]
            if item_id in db["ids"]:
                raise RuntimeError("Duplicate memory ID: " + str(item_id))
            db["ids"].append(item_id)
            db["documents"].append(documents[i])
            db["metadatas"].append(metadatas[i])
            db["embeddings"].append(embeddings[i])
        db["embedding_model"] = EMBEDDING_MODEL
        db["embedding_dimensions"] = EMBEDDING_DIMENSIONS
        db["embedding_schema"] = EMBEDDING_SCHEMA
        committed = _commit_memory_change("remembered", [
            {"id": ids[i], "document": documents[i], "metadata": metadatas[i]}
            for i in range(len(ids))
        ])
        _save_committed_projection(db, committed)

    def get(self, ids=None, include=None, where=None, where_document=None, limit=None):
        db = _load()
        result = {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
        inc = include or ["metadatas", "documents", "embeddings"]
        for i in range(len(db["ids"])):
            if ids is not None and db["ids"][i] not in ids:
                continue
            document = db["documents"][i]
            if where_document is not None:
                regex = where_document.get("$regex")
                if regex:
                    import re
                    if not re.search(regex, document):
                        continue
                else:
                    matched = False
                    for value in where_document.values():
                        if isinstance(value, dict):
                            contains = value.get("$contains", "")
                            if contains and contains.lower() in document.lower():
                                matched = True
                        elif isinstance(value, str) and value.lower() in document.lower():
                            matched = True
                    if not matched:
                        continue
            result["ids"].append(db["ids"][i])
            result["documents"].append(document if "documents" in inc else None)
            result["metadatas"].append(db["metadatas"][i] if "metadatas" in inc else None)
            result["embeddings"].append(_dequantize_embedding(db["embeddings"][i]) if "embeddings" in inc else None)
            if limit and len(result["ids"]) >= int(limit):
                break
        return result

    def query(self, query_embeddings, n_results=5, include=None):
        db = _load()
        query_embedding = query_embeddings[0]
        scored = []
        for i in range(len(db["ids"])):
            similarity = _cosine(query_embedding, _dequantize_embedding(db["embeddings"][i]))
            if similarity is not None:
                scored.append((1.0 - similarity, i))
        scored.sort(key=lambda item: item[0])
        count = min(int(n_results), len(scored))
        inc = include or ["documents", "metadatas", "distances"]
        result = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
        for j in range(count):
            distance, index = scored[j]
            result["ids"][0].append(db["ids"][index])
            result["documents"][0].append(db["documents"][index] if "documents" in inc else None)
            result["metadatas"][0].append(db["metadatas"][index] if "metadatas" in inc else None)
            result["distances"][0].append(distance if "distances" in inc else None)
        return result

    @_exclusive
    def update(self, ids, documents=None, metadatas=None, embeddings=None):
        """Replace fields of existing memories; unspecified fields keep the AUTHORITY's
        current value, and the commit expects the atoms it read (no stale base)."""
        _, memories = authority_memories()
        records, expected = [], {}
        for position, item_id in enumerate(ids):
            if item_id not in memories:
                continue
            document, metadata, atom = memories[item_id]
            records.append({
                "id": item_id,
                "document": documents[position] if documents is not None else document,
                "metadata": metadatas[position] if metadatas is not None else metadata,
            })
            expected[SEMANTIC_PREFIX + item_id] = atom
        if not records:
            return
        try:
            committed = _commit_memory_change("memory_updated", records, expected_atoms=expected)
        except RuntimeError as error:
            conflict = _conflict_guard(error)
            if conflict:
                raise conflict from error
            raise
        db = _load(write=True)
        for record in records:
            vector = embeddings[ids.index(record["id"])] if embeddings is not None else None
            _index_put(db, record["id"], record["document"], record["metadata"], vector)
        _save_committed_projection(db, committed)

    @_exclusive
    def delete(self, ids):
        """Forget memories in the authority; ids the authority lacks are index orphans
        and are only dropped from the index."""
        _, memories = authority_memories()
        removed = [{"id": item_id, "document": memories[item_id][0], "metadata": memories[item_id][1]}
                   for item_id in ids if item_id in memories]
        db = _load(write=True)
        before = len(db["ids"])
        committed = None
        if removed:
            committed = _commit_memory_change(
                "forgotten", removed, remove_ids=[item["id"] for item in removed],
                expected_atoms={SEMANTIC_PREFIX + item["id"]: memories[item["id"]][2] for item in removed})
        _index_drop(db, ids)
        if committed is not None:
            _save_committed_projection(db, committed)
        elif len(db["ids"]) != before:
            _save(db)


class PersistentClient:
    def __init__(self, path=None):
        pass

    def get_or_create_collection(self, name="memories", embedding_function=None):
        try:
            reconcile_index()
        except Exception:
            pass  # index upkeep is best effort; the authority stays correct
        require_current_index()
        return Collection()
