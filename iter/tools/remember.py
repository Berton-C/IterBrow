import time
import json
import re
import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = (
    "Commit semantic memory and refresh its search projection. If a write is uncertain, "
    "use status_id alone to read its committed state without embedding or rewriting. "
    "Retrying the exact same text resumes its original pending identity; do not reword an uncertain write. "
    "provenance_type: observed/inferred/model_estimated. mem_type: fact/belief/value/todo/preference. "
    "Non-todo memories require force=True to forget."
)

VALID_MEM_TYPES = {"fact", "belief", "value", "todo", "preference"}

def _escape_re(text):
    """Manual regex escape since re.escape is not available."""
    special = '.^$*+?{}[]\\|()'
    result = ""
    for ch in text:
        if ch in special:
            result += "\\" + ch
        else:
            result += ch
    return result

def _dupe_regex(text):
    norm = " ".join((text or "").split())
    if not norm:
        return None
    tokens = norm.split(" ")
    return "^" + r"\s+".join(_escape_re(t) for t in tokens) + "$"

def _find_duplicate(collection, text):
    regex = _dupe_regex(text)
    if not regex:
        return None
    res = collection.get(where_document={"$regex": regex}, limit=1)
    ids = res.get("ids", [])
    return ids[0] if ids else None

def run(text="", provenance_type="observed", mem_type="fact", status_id=""):
    if status_id:
        return json.dumps(petta_db.memory_status(status_id), ensure_ascii=False)
    if not isinstance(text, str) or not text.strip():
        return "ERROR: supply nonempty text to remember, or status_id to inspect a previous write."
    valid_types = {"observed", "inferred", "model_estimated"}
    if provenance_type not in valid_types:
        return f"ERROR: provenance_type must be one of {valid_types}, got '{provenance_type}'"
    if mem_type not in VALID_MEM_TYPES:
        return f"ERROR: mem_type must be one of {VALID_MEM_TYPES}, got '{mem_type}'"

    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")

    existing_id = _find_duplicate(collection, text)
    if existing_id:
        return f"REMEMBER-DUPLICATE: identical memory already stored as {existing_id}; not re-storing"

    pending = petta_db.pending_remember(text)
    text = pending["document"] if pending else text
    embedding = petta_db.get_embedding(text, "search_document")
    current = time.localtime()
    ts = "%04d-%02d-%02d %02d:%02d:%02d" % (
        current[0], current[1], current[2], current[3], current[4], current[5]
    )
    item_id = pending["id"] if pending else petta_db.gen_id()
    metadata = pending["metadata"] if pending else {"time": ts, "provenance_type": provenance_type, "mem_type": mem_type}
    collection.add(
        ids=[item_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata]
    )
    try:
        import memory_journal
        memory_journal.log("remember", "stored", {"item_id": item_id, "mem_type": mem_type, "provenance_type": provenance_type})
    except Exception:
        pass
    return f"REMEMBER-SUCCESS: stored {item_id} at {metadata.get('time', ts)} (provenance: {metadata.get('provenance_type')}, type: {metadata.get('mem_type')})"
