import sys
TOOLS_DIR = "tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = (
    "Delete a memory from the PeTTa chroma_db. Item_id must be a UUID from "
    "chroma_query results. Typed-memory retention rule (Headlong-inspired): "
    "items typed fact/belief/value/preference are durable and refuse to "
    "delete unless force=True is passed explicitly; items typed todo (or "
    "untyped legacy memories) delete freely. Every deletion is journaled."
)

DURABLE_TYPES = {"fact", "belief", "value", "preference"}


def run(item_id, force="false"):
    force_bool = str(force).strip().lower() in ("true", "1", "yes")

    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")

    res = collection.get(ids=[item_id], include=["metadatas", "documents"])
    if not res.get("ids"):
        return f"ERROR: memory not found: {item_id}"

    metadata = (res.get("metadatas") or [{}])[0] or {}
    mem_type = metadata.get("mem_type", "unspecified")

    if mem_type in DURABLE_TYPES and not force_bool:
        return (
            f"FORGET-REFUSED: item {item_id} is typed '{mem_type}' (durable) and was "
            "NOT deleted. Pass force=True only if you are certain this specific item "
            "is wrong or obsolete, not merely inconvenient for the current budget."
        )

    collection.delete(ids=[item_id])
    try:
        import memory_journal
        memory_journal.log("forget", "deleted", {"item_id": item_id, "mem_type": mem_type, "forced": force_bool})
    except Exception:
        pass
    return f"FORGET-SUCCESS: item {item_id} (type: {mem_type}) deleted from chroma_db"
