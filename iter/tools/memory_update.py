import sys
TOOLS_DIR = "tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Update the text content and embedding of a specific memory in chroma_db. All metadata (creation time, linked episodes, stv values) is preserved. Item_id must be a UUID from chroma_query results."

def run(item_id, text):
    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")

    res = collection.get(ids=[item_id], include=["metadatas"])
    if not res.get("ids"):
        return f"ERROR: memory not found: {item_id}"

    metadata = dict(res["metadatas"][0] or {})
    embedding = petta_db.get_embedding(text, "search_document")

    collection.update(
        ids=[item_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata]
    )
    return f"MEMORY-UPDATE-SUCCESS: item {item_id} content updated, embedding refreshed, metadata preserved"
