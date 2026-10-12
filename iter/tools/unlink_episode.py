import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Unlink an episode timestamp from a memory item. Evidence already counted from that episode stays counted. The item_id must be a UUID from chroma_query results, and linked_time is the timestamp string to remove."

def run(item_id, linked_time):
    if not isinstance(item_id, str):
        raise TypeError("item_id must be a str")
    if not isinstance(linked_time, str):
        raise TypeError("linked_time must be a str")

    chroma_client = petta_db.PersistentClient()
    chroma_client.get_or_create_collection(name="memories")
    message = f"UNLINK-SUCCESS: episode {linked_time} unlinked from item {item_id}"

    def unlink(document, metadata):
        linked_episodes = list(metadata.get("linkedEpisodes", []))
        if linked_time not in linked_episodes:
            return message
        petta_db.with_counted_evidence(metadata)
        linked_episodes.remove(linked_time)
        if linked_episodes:
            metadata["linkedEpisodes"] = linked_episodes
        else:
            metadata.pop("linkedEpisodes", None)
        return document, metadata, message

    result = petta_db.modify_memory(item_id, unlink)
    return result if result is not None else f"ERROR: memory not found: {item_id}"
