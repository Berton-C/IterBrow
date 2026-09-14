import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db

DESCRIPTION = "Query the PeTTa chroma_db for similar memories by text. Returns matching entries with their content and metadata."

def run(query, k=5):
    chroma_client = petta_db.PersistentClient()
    collection = chroma_client.get_or_create_collection(name="memories")

    if not collection.get(include=["metadatas"]).get("ids"):
        return "No results found."

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
            return "Long-term-memory search unavailable: no OpenRouter key configured in Settings (needed for embeddings even when chatting via LM Studio). Not a bug — set a key there if you want this back; otherwise safe to ignore and continue without it."
        raise

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
        return "No results found."

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
        output_lines.append("Content: " + str(doc))
        output_lines.append("")

    return "\n".join(output_lines)
