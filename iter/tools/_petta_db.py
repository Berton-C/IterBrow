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
import urllib.request
from pathlib import Path


# Component code may execute from an immutable hot-load generation.  The
# semantic-memory projection is application state and must never move with it.
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
DB_DIR = ROOT + "/chroma_db"
DB_FILE = DB_DIR + "/memories.json"

EMBEDDING_URL = "https://openrouter.ai/api/v1/embeddings"
EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_SCHEMA = 3
EMBEDDING_BATCH_SIZE = 32

_id_counter = 0

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from iterbrow_runtime.cognitive_events import commit_batch, metta_string, _call_atomspace


class MemoryCommitUncertain(RuntimeError):
    execution_outcome = {"success": None, "state": "uncertain", "scope": "invocation",
                         "task_fulfillment": "unverified"}


class MemoryProjectionPending(RuntimeError):
    execution_outcome = {"success": None, "state": "projection_pending", "scope": "invocation",
                         "task_fulfillment": "unverified"}


def pending_remember(text):
    """Reuse the original identity after an interrupted write, not a new fact."""
    wanted = " ".join(text.split())
    for path in sorted((Path(ROOT) / ".runtime" / "memory_pending").glob("*.json")):
        entry = json.loads(path.read_text())
        kind, records, _ = entry["request"]
        if kind == "remembered" and len(records) == 1 and " ".join(records[0]["document"].split()) == wanted:
            return records[0]
    return None


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
    if isinstance(result, dict) and result.get("_pending_path"):
        path = Path(result["_pending_path"])
        if path.exists() and json.loads(path.read_text())["operation_id"] == result["_operation_id"]:
            path.unlink()


def _save_committed_projection(db, committed):
    try:
        _save(db)
    except Exception as error:
        if isinstance(committed, dict) and not committed.get("deferred"):
            raise MemoryProjectionPending(
                "Durable memory commit %s is confirmed, but its search projection could not be saved. "
                "Retry the original text/IDs to finish the projection; do not create a replacement."
                % committed.get("commit")
            ) from error
        raise
    _finish_memory_projection(committed)


def _memory_atom(item_id, document, metadata):
    return "(semantic-memory %s %s %s)" % (
        metta_string(item_id), metta_string(document),
        metta_string(json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False)),
    )


def _commit_memory_change(kind, records, remove_ids=None):
    # Keep uncertain retries stable, but never confuse a later A->B->A edit
    # with an earlier completed operation. Reuse the existing runtime directory.
    canonical = json.dumps([kind, records, remove_ids or []], sort_keys=True, ensure_ascii=False)
    pending_dir = Path(ROOT) / ".runtime" / "memory_pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    pending = pending_dir / (hashlib.sha256(canonical.encode()).hexdigest() + ".json")
    from iterbrow_runtime.atomspace_store import _atomic_json
    with (pending_dir / "writer.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if pending.exists():
            operation_id = json.loads(pending.read_text())["operation_id"]
        else:
            operation_id = uuid.uuid4().hex
            _atomic_json(pending, {"operation_id": operation_id, "request": json.loads(canonical)})
        try:
            result = _commit_memory_operation(kind, records, remove_ids, operation_id)
        except (OSError, json.JSONDecodeError) as error:
            ids = ",".join(str(record["id"]) for record in records)
            raise MemoryCommitUncertain(
                "No confirmed reply for memory ID(s) %s, transaction %s. The write may commit later. "
                "Use remember(status_id=ID) to inspect it; retry the exact same text/IDs, not a reworded replacement."
                % (ids, "cognitive:memory:" + operation_id)
            ) from error
        # Keep the existing recovery entry until the local search projection is
        # saved too. An acknowledged commit followed by a crash is recoverable.
        return {**result, **({"_pending_path": str(pending), "_operation_id": operation_id}
                            if not result.get("deferred") else {})}


def _commit_memory_operation(kind, records, remove_ids, operation_id):
    canonical = json.dumps(
        {"kind": kind, "records": records, "remove_ids": remove_ids or []},
        sort_keys=True, ensure_ascii=False,
    )
    digest = operation_id
    events = []
    state_atoms = {}
    for record in records:
        item_id = record["id"]
        events.append({
            "event_id": "memory:%s:%s:%s" % (kind, item_id, digest[:16]),
            "domain": "semantic_memory",
            "entity_id": item_id,
            "event_type": kind,
            "payload": record,
        })
        if kind != "forgotten":
            state_atoms["semantic_memory:%s" % item_id] = _memory_atom(
                item_id, record.get("document", ""), record.get("metadata", {})
            )
    return commit_batch(
        events,
        state_atoms=state_atoms,
        remove_state_keys=["semantic_memory:%s" % item_id for item_id in (remove_ids or [])],
        actor="iter",
        source="tools._petta_db",
        transaction_id="cognitive:memory:%s" % digest,
    )


def _exists(path):
    return os.path.exists(path)


def _mkdirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass


def _empty():
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
    db = _validate(db, path)
    db["embeddings"] = [_dequantize_embedding(e) for e in db["embeddings"]]
    return db


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


def _save(db):
    """Write through a temporary file while retaining the previous valid file."""
    _ensure_dir()
    _validate(db, "in-memory database")
    tmp = DB_FILE + ".tmp"
    backup = DB_FILE + ".bak"
    _remove_if_present(tmp)
    _write_new_file(tmp, db)

    moved_old = False
    try:
        if _exists(DB_FILE):
            _remove_if_present(backup)
            os.replace(DB_FILE, backup)
            moved_old = True
        os.replace(tmp, DB_FILE)
        _fsync_db_dir()
    except Exception:
        _remove_if_present(tmp)
        if moved_old and not _exists(DB_FILE) and _exists(backup):
            try:
                os.replace(backup, DB_FILE)
                _fsync_db_dir()
            except Exception:
                pass
        raise


def _restore_backup(backup):
    db = _read(backup)
    recover = DB_FILE + ".recover"
    _remove_if_present(recover)
    _write_new_file(recover, db)
    _remove_if_present(DB_FILE)
    os.replace(recover, DB_FILE)
    _fsync_db_dir()
    return db


def _load():
    _ensure_dir()
    backup = DB_FILE + ".bak"
    if _exists(DB_FILE):
        try:
            return _read(DB_FILE)
        except Exception:
            if _exists(backup):
                return _restore_backup(backup)
            raise

    if _exists(backup):
        return _restore_backup(backup)

    return _empty()


def _hex(data):
    return binascii.hexlify(data).decode("ascii")


def _quantize_embedding(vec):
    """Convert a float list to int8-packed dict for compact storage."""
    if not isinstance(vec, list) or not vec:
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
        q = int((v - offset) / scale)
        if q < 0:
            q = 0
        if q > 255:
            q = 255
        packed[i] = q
    return {"q": _hex(bytes(packed)), "s": scale, "o": offset}


def _dequantize_embedding(emb):
    """Convert int8-packed dict back to float list. Pass-through for float lists."""
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
        if not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS:
            return False
    return True


def require_current_index():
    """Reject old/hash vectors instead of silently re-embedding them."""
    db = _load()
    if not _index_is_current(db):
        raise RuntimeError(
            "Incompatible legacy/hash-vector memory database at " + DB_FILE
            + ". Automatic re-embedding is disabled. Remove " + DB_DIR
            + " and retry to create a fresh OpenRouter index."
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


class Collection:
    def add(self, ids, embeddings, documents, metadatas):
        db = _load()
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
            result["embeddings"].append(db["embeddings"][i] if "embeddings" in inc else None)
            if limit and len(result["ids"]) >= int(limit):
                break
        return result

    def query(self, query_embeddings, n_results=5, include=None):
        db = _load()
        query_embedding = query_embeddings[0]
        scored = []
        for i in range(len(db["ids"])):
            similarity = _cosine(query_embedding, db["embeddings"][i])
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

    def update(self, ids, documents=None, metadatas=None, embeddings=None):
        db = _load()
        for target_index in range(len(ids)):
            item_id = ids[target_index]
            if item_id not in db["ids"]:
                continue
            index = db["ids"].index(item_id)
            if documents is not None:
                db["documents"][index] = documents[target_index]
            if metadatas is not None:
                db["metadatas"][index] = metadatas[target_index]
            if embeddings is not None:
                db["embeddings"][index] = embeddings[target_index]
        records = []
        for item_id in ids:
            if item_id in db["ids"]:
                index = db["ids"].index(item_id)
                records.append({
                    "id": item_id,
                    "document": db["documents"][index],
                    "metadata": db["metadatas"][index],
                })
        committed = _commit_memory_change("memory_updated", records) if records else None
        _save_committed_projection(db, committed)

    def delete(self, ids):
        db = _load()
        removed = []
        for item_id in ids:
            if item_id in db["ids"]:
                index = db["ids"].index(item_id)
                removed.append({
                    "id": item_id,
                    "document": db["documents"][index],
                    "metadata": db["metadatas"][index],
                })
                del db["ids"][index]
                del db["documents"][index]
                del db["metadatas"][index]
                del db["embeddings"][index]
        committed = _commit_memory_change("forgotten", removed, remove_ids=[item["id"] for item in removed]) if removed else None
        _save_committed_projection(db, committed)


class PersistentClient:
    def __init__(self, path=None):
        pass

    def get_or_create_collection(self, name="memories", embedding_function=None):
        require_current_index()
        return Collection()
