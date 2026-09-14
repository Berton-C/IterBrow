import time
import re
import sys
TOOLS_DIR = "tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = (
    "Store a memory in the PeTTa chroma_db long-term memory. The memory will be "
    "retrievable via chroma_query. Valid provenance types: observed, inferred, "
    "model_estimated. Valid mem_type (Headlong-style typed memory, controls "
    "retention rules in forget.py): fact, belief, value, todo, preference. "
    "fact/belief/value/preference are durable and cannot be forgotten without "
    "force=True; todo items may be freely forgotten once resolved."
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

def run(text, provenance_type="observed", mem_type="fact"):
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

    embedding = petta_db.get_embedding(text, "search_document")
    current = time.localtime()
    ts = "%04d-%02d-%02d %02d:%02d:%02d" % (
        current[0], current[1], current[2], current[3], current[4], current[5]
    )
    item_id = petta_db.gen_id()
    collection.add(
        ids=[item_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{"time": ts, "provenance_type": provenance_type, "mem_type": mem_type}]
    )
    try:
        import memory_journal
        memory_journal.log("remember", "stored", {"item_id": item_id, "mem_type": mem_type, "provenance_type": provenance_type})
    except Exception:
        pass
    return f"REMEMBER-SUCCESS: stored {item_id} at {ts} (provenance: {provenance_type}, type: {mem_type})"
