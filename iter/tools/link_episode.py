import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = (
    "Link an episode timestamp (e.g. '2026-08-12 17:25:05') to a memory item (UUID from chroma_query). A "
    'link is not evidence; use support/contradict.'
)

def run(item_id, linked_time):
    if not isinstance(item_id, str):
        raise TypeError("item_id must be a str")
    if not isinstance(linked_time, str):
        raise TypeError("linked_time must be a str")

    chroma_client = petta_db.PersistentClient()
    chroma_client.get_or_create_collection(name="memories")
    message = f"LINK-SUCCESS: episode {linked_time} linked to item {item_id}"

    def link(document, metadata):
        linked_episodes = list(metadata.get("linkedEpisodes", []))
        if linked_time in linked_episodes:
            return message
        petta_db.with_counted_evidence(metadata)
        linked_episodes.append(linked_time)
        metadata["linkedEpisodes"] = linked_episodes
        return document, metadata, message

    result = petta_db.modify_memory(item_id, link)
    return result if result is not None else f"ERROR: memory not found: {item_id}"
