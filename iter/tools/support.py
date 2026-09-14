import sys
TOOLS_DIR = "tools"
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Support a memory item in chroma_db by linking an episode and applying NAL truth revision with positive evidence. Item_id must be a UUID from chroma_query results."

def c2w(c):
    return c / (1.0 - c) if c < 1.0 else 999999.0

def w2c(w):
    return w / (w + 1.0)

def truth_revision(s1, c1, s2, c2):
    w1 = c2w(c1)
    w2 = c2w(c2)
    w = w1 + w2
    f = (w1 * s1 + w2 * s2) / w if w > 0 else 0.0
    c = w2c(w)
    f = min(1.00, f)
    c = min(0.99, max(max(c, c1), c2))
    return round(f, 6), round(c, 6)

def run(item_id, episode_time):
    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")

    res = collection.get(ids=[item_id], include=["metadatas"])
    if not res.get("ids"):
        return f"ERROR: memory not found: {item_id}"

    metadata = dict(res["metadatas"][0] or {})
    linked_episodes = metadata.get("linkedEpisodes", [])
    if episode_time in linked_episodes:
        return "SUPPORT-FAIL: episode already in episode list"

    linked_episodes.append(episode_time)
    metadata["linkedEpisodes"] = linked_episodes

    s1 = metadata.get("strength", 1.0)
    c1 = metadata.get("confidence", 0.5)
    s2, c2 = 1.0, 0.5
    new_s, new_c = truth_revision(s1, c1, s2, c2)

    metadata["strength"] = new_s
    metadata["confidence"] = new_c
    collection.update(ids=[item_id], metadatas=[metadata])

    return f"SUPPORT-SUCCESS: item {item_id} stv ({s1},{c1}) -> ({new_s},{new_c}), episode {episode_time} linked"
