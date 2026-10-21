import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db
from iterbrow_runtime import kb_terms

DESCRIPTION = (
    'Give an LTM item (UUID from chroma_query) a NAL statement; it becomes a knowledge-base atom. Terms '
    'are canonicalized; no stv. Forms: (--> raven bird), (==> (--> $1 ([] smokes)) (--> $1 ([] '
    'cancerous))). Query with kb_query.'
)


def run(LTM_item, formalization):
    chroma_client = petta_db.PersistentClient()
    chroma_client.get_or_create_collection(name="memories")
    try:
        registry = kb_terms.read_registry(petta_db._call_atomspace)
        statement, _ = kb_terms.resolve_statement(formalization, registry)
    except ValueError as error:
        return "ERROR: %s. Nothing was written. Input: %s" % (error, formalization)
    digest = kb_terms.statement_hash(statement)

    def assign(document, metadata):
        metadata["formalization"] = statement
        metadata["formalization_hash"] = digest
        metadata.pop("formalization_error", None)
        return document, metadata, "SUCCESS: Assigned statement to LTM item %s:\n  %s" % (LTM_item, statement)

    result = petta_db.modify_memory(LTM_item, assign)
    return result if result is not None else "ERROR: LTM item %s not found in chroma_db." % LTM_item
