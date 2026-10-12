import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Update the text content and embedding of a specific memory in chroma_db. All metadata (creation time, linked episodes, stv values) is preserved. Item_id must be a UUID from chroma_query results."

def run(item_id, text):
    chroma_client = petta_db.PersistentClient()
    chroma_client.get_or_create_collection(name="memories")

    if petta_db.read_memory(item_id) is None:
        return f"ERROR: memory not found: {item_id}"
    embedding = petta_db.get_embedding(text, "search_document")

    def replace_text(document, metadata):
        return text, metadata, f"MEMORY-UPDATE-SUCCESS: item {item_id} content updated, embedding refreshed, metadata preserved"

    result = petta_db.modify_memory(item_id, replace_text, embedding=embedding)
    return result if result is not None else f"ERROR: memory not found: {item_id}"
