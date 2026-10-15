import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Query the chroma_db vector projection for semantically similar authoritative memories. Returns matching entries with their content and metadata."

def _gap_note():
    unindexed, error = petta_db.index_gap()
    if not unindexed:
        return ""
    count = len(unindexed)
    one = count == 1
    if not error:
        return ("NOTE: %d %s still being indexed: %s stored in the AtomSpace and %s searchable within "
                "the next few memory calls; nothing is lost."
                % (count, "memory is" if one else "memories are", "it is" if one else "they are",
                   "becomes" if one else "become"))
    return ("NOTE: %d %s not yet searchable: %s stored in the AtomSpace but %s embedding could not be "
            "computed%s. %s indexed automatically once embeddings work; nothing is lost."
            % (count, "memory is" if one else "memories are", "it is" if one else "they are",
               "its" if one else "their", " (" + str(error)[:160] + ")" if error else "",
               "It is" if one else "They are"))


DERIVED_PER_MEMORY = 5


class _LazyDerivations:
    """Derive once per chroma_query call, and only if a result is formalized."""

    def __init__(self):
        self.items = None
        self.error = None

    def get(self):
        if self.items is None and self.error is None:
            try:
                from iterbrow_runtime import kb_inference
                self.items = kb_inference.derive(kb_inference.service_query, depth=2)
            except Exception as error:  # reasoning is an addition; search must still answer
                self.error = "%s: %s" % (type(error).__name__, str(error)[:160])
        return self.items, self.error


def _derived_lines(statement, derivations):
    """`Derived:` section: conclusions (depth <= 2) that rest on this memory's statement."""
    from iterbrow_runtime import kb_inference
    items, error = derivations.get()
    if error:
        return ["Derived: unavailable (%s)" % error]
    mine = [item for item in items if statement in item["sources"]]
    if not mine:
        return []
    lines = ["Derived:"] + ["  " + kb_inference.format_derivation(item) for item in mine[:DERIVED_PER_MEMORY]]
    if len(mine) > DERIVED_PER_MEMORY:
        lines.append("  (+%d more derived; use kb_query)" % (len(mine) - DERIVED_PER_MEMORY))
    return lines


def run(query, k=5):
    out = _search(query, k)
    notice = petta_db.reconcile_notice()
    return out + "\n" + notice if notice else out


def _search(query, k):
    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")
    note = _gap_note()

    if not collection.get(include=["metadatas"]).get("ids"):
        return ("No results found.\n" + note) if note else "No results found."

    try:
        query_embedding = petta_db.get_embedding(query, "search_query")
    except RuntimeError as error:
        if "OPENROUTER_API_KEY" in str(error):
            # Calm, low-noise degrade: this is a config gap (no OpenRouter key set for
            # this install), not a real failure. Raising here used to read as an alarming
            # "Tool execution failed" error every call, which kept nudging self-repair
            # attention at this instead of onto replying to the user. Long-term-memory
            # search just isn't available until a key is set in Settings; say so once,
            # calmly, and move on.
            return "Long-term-memory search unavailable: no OpenRouter key configured in Settings (needed for embeddings even when chatting via LM Studio). Not a bug — set a key there if you want this back; otherwise safe to ignore and continue without it." + ("\n" + note if note else "")
        return ("Long-term-memory search unavailable right now: the embeddings request failed (%s). "
                "Stored memories are safe; try again later.%s" % (str(error)[:200], "\n" + note if note else ""))

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=int(k),
        include=["documents", "metadatas", "distances"]
    )

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        return ("No results found.\n" + note) if note else "No results found."

    derivations = _LazyDerivations()
    output_lines = ["Found " + str(len(documents)) + ' results for query: "' + query + '"\n']
    for i in range(len(documents)):
        id_val = ids[i] if i < len(ids) else "unknown"
        doc = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
        dist = distances[i] if i < len(distances) else 0.0

        if meta is None:
            meta = {}

        time_val = meta.get("time", "unknown")
        linked = meta.get("linkedEpisodes", [])
        strength = meta.get("strength", 1.0)
        confidence = meta.get("confidence", 0.5)
        formalization = meta.get("formalization", None)
        prov = meta.get("provenance_type", "unknown")

        output_lines.append("--- Result " + str(i+1) + " (distance: " + str(round(dist, 4)) + ") ---")
        output_lines.append("ID: " + str(id_val))
        output_lines.append("Time: " + str(time_val))
        output_lines.append("Provenance: " + str(prov))
        output_lines.append("STV: (" + str(strength) + ", " + str(confidence) + ")")
        if linked:
            output_lines.append("Linked Episodes: " + str(linked))
        if formalization:
            output_lines.append("Formalization: " + str(formalization))
            if meta.get("formalization_hash"):
                output_lines.extend(_derived_lines(str(formalization), derivations))
        output_lines.append("Content: " + str(doc))
        output_lines.append("")

    if note:
        output_lines.append(note)
    return "\n".join(output_lines)
