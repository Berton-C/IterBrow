import sys
TOOLS_DIR = "tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Unlink an episode timestamp from a memory item in chroma_db. The item_id must be a UUID from chroma_query results, and linked_time is the timestamp string to remove."

def run(item_id, linked_time):
    if not isinstance(item_id, str):
        raise TypeError("item_id must be a str")
    if not isinstance(linked_time, str):
        raise TypeError("linked_time must be a str")

    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")

    res = collection.get(ids=[item_id], include=["metadatas"])
    if not res.get("ids"):
        return f"ERROR: memory not found: {item_id}"

    metadata = dict(res["metadatas"][0] or {})
    linked_episodes = metadata.get("linkedEpisodes", [])
    if linked_time in linked_episodes:
        linked_episodes.remove(linked_time)
        if linked_episodes:
            metadata["linkedEpisodes"] = linked_episodes
        else:
            metadata.pop("linkedEpisodes", None)
        collection.update(ids=[item_id], metadatas=[metadata])
    return f"UNLINK-SUCCESS: episode {linked_time} unlinked from item {item_id}"
