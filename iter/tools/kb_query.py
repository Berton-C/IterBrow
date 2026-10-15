import os
import sys
from pathlib import Path
TOOLS_DIR = str(Path(__file__).resolve().parent)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
# Same root rule as _petta_db: runtime modules come from ITER_DIR, never from a hot-load generation.
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from iterbrow_runtime import kb_terms, kb_inference
from iterbrow_runtime.cognitive_events import _call_atomspace

DESCRIPTION = """Ask the knowledge base: pattern is a statement with $variables, e.g. (--> $1 ([] cancerous)) or (--> anna $what). Returns stored statements that match (truth value + evidence memory ids), then conclusions derived by NAL deduction over stored statements (up to depth steps, max 3), each with its premises. Derived lines are computed now, not stored."""


def run(pattern, depth=2):
    try:
        registry = kb_terms.read_registry(_call_atomspace)
        canonical, _ = kb_terms.resolve_statement(pattern, registry, mode="permissive")
    except ValueError as error:
        return "ERROR: %s. Input: %s" % (error, pattern)
    stored = kb_inference.stored_statements(
        lambda prefix: _call_atomspace("read_atoms", timeout=10, prefix=prefix)["atoms"])
    lines = []
    for statement in sorted(stored):
        if kb_inference.unifies(canonical, statement):
            stv, evidence = stored[statement]
            lines.append("[stored] %s %s evidence: %s" % (statement, kb_terms.stv_text(stv), ", ".join(evidence) or "none"))
    try:
        derived = kb_inference.derive(kb_inference.service_query, depth=depth, limit=200)
    except Exception as error:
        lines.append("Derived: unavailable (%s: %s)" % (type(error).__name__, str(error)[:160]))
        derived = kb_inference.Derivations()
    for item in derived:
        if kb_inference.unifies(canonical, item["statement"]):
            lines.append(kb_inference.format_derivation(item))
    if not lines:
        return "No stored or derived statement matches %s." % canonical
    if derived.truncated:
        lines.append("(derivation was cut short by its depth/time budget; results may be incomplete)")
    return "\n".join(lines)
