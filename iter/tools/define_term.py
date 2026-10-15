import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _petta_db as petta_db
from iterbrow_runtime import kb_terms

DESCRIPTION = """Add or confirm a knowledge-base term (marks it known) with a one-line definition and optional aliases (list or comma-separated). Aliases resolve to the term in every statement. Provisional terms (first used in formalize_metta) become known. To fold an existing duplicate term into this one use merge_terms instead."""


def run(name, definition, aliases=None):
    def plan(atoms):
        registry = kb_terms.Registry({k: v for k, v in atoms.items() if k.startswith(kb_terms.TERM_PREFIX)})
        key, atom = kb_terms.plan_define(registry, name, definition, aliases)
        row = kb_terms.parse_term_atom(atom)
        return {}, {key: atom}, "SUCCESS: term '%s' is known%s" % (
            row["name"], (" (aliases: %s)" % ", ".join(row["aliases"])) if row["aliases"] else "")

    try:
        return petta_db.commit_kb_change(plan, "term_defined")
    except ValueError as error:
        return "ERROR: %s" % error
