import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = (
    'Apply positive NAL evidence from an episode to a memory item (UUID from chroma_query) and link it. '
    'Each episode counts once (support or contradict, never both).'
)

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
    chroma_client.get_or_create_collection(name="memories")

    def revise(document, metadata):
        evidence = petta_db.counted_evidence(metadata)
        if episode_time in evidence:
            how = "supporting" if evidence[episode_time] == "+" else "contradicting"
            return "SUPPORT-FAIL: episode %s was already counted as %s evidence for this memory" % (episode_time, how)
        linked_episodes = list(metadata.get("linkedEpisodes", []))
        if episode_time not in linked_episodes:
            linked_episodes.append(episode_time)
        s1 = metadata.get("strength", 1.0)
        c1 = metadata.get("confidence", 0.5)
        new_s, new_c = truth_revision(s1, c1, 1.0, 0.5)
        evidence[episode_time] = "+"
        metadata.update({"linkedEpisodes": linked_episodes, "evidenceEpisodes": evidence,
                         "strength": new_s, "confidence": new_c})
        return document, metadata, "SUPPORT-SUCCESS: item %s stv (%s,%s) -> (%s,%s), episode %s linked" % (
            item_id, s1, c1, new_s, new_c, episode_time)

    result = petta_db.modify_memory(item_id, revise)
    return result if result is not None else f"ERROR: memory not found: {item_id}"
