import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db
from iterbrow_runtime import kb_terms

DESCRIPTION = """Fold a duplicate knowledge-base term into another: drop becomes an alias of keep, every statement using drop is rewritten to keep, and statements that become identical are revised into one (their evidence adds up). Both must be registered terms. Safe to repeat."""


def run(keep, drop):
    chroma_client = petta_db.PersistentClient()
    chroma_client.get_or_create_collection(name="memories")
    try:
        return petta_db.commit_kb_change(lambda atoms: kb_terms.plan_merge(atoms, keep, drop), "terms_merged")
    except ValueError as error:
        return "ERROR: %s" % error
