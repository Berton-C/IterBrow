import time
import json
import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = (
    'Commit a semantic memory. provenance_type: observed|inferred|model_estimated. mem_type: '
    'fact|belief|value|todo|preference. If a write was uncertain, status_id alone reads its state; retry '
    'with the exact same text, never reworded.'
)

VALID_MEM_TYPES = {"fact", "belief", "value", "todo", "preference"}

def _find_duplicate(collection, text):
    """Same text up to whitespace, checked against the AUTHORITY's documents
    (the index may lag); the index is only a fallback when it is unreachable."""
    wanted = " ".join((text or "").split())
    if not wanted:
        return None
    try:
        _, memories = petta_db.authority_memories()
        candidates = ((item_id, fields[0]) for item_id, fields in sorted(memories.items()))
    except Exception:
        res = collection.get(include=["documents"])
        candidates = zip(res.get("ids", []), res.get("documents", []))
    for item_id, document in candidates:
        if " ".join((document or "").split()) == wanted:
            return item_id
    return None

def run(text="", provenance_type="observed", mem_type="fact", status_id=""):
    out = _remember(text, provenance_type, mem_type, status_id)
    notice = petta_db.reconcile_notice()
    return out + "\n" + notice if notice else out


def _remember(text, provenance_type, mem_type, status_id):
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
        petta_db.discard_pending_remember(text)  # any uncertain earlier write is settled
        return f"REMEMBER-DUPLICATE: identical memory already stored as {existing_id}; not re-storing"

    pending = petta_db.pending_remember(text, mem_type, provenance_type)
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
    petta_db.discard_pending_remember(text)  # superseded entries for the same text
    try:
        import memory_journal
        memory_journal.log("remember", "stored", {"item_id": item_id, "mem_type": mem_type, "provenance_type": provenance_type})
    except Exception:
        pass
    return f"REMEMBER-SUCCESS: stored {item_id} at {metadata.get('time', ts)} (provenance: {metadata.get('provenance_type')}, type: {metadata.get('mem_type')})"
