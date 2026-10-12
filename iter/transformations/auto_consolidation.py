"""Auto-Consolidation: keep the tier pyramid regenerated from the episodes.

There is exactly ONE tier writer: tools/rebuild_tiers.py (rebuild()). This
transformation used to roll "excess" lines from one tier file into the next
with its own algorithm (keeping the OLDEST half, measuring file BYTES), which
fought rebuild_tiers (CHARACTER limits) every cycle. It now only triggers the
sanctioned rebuild when the tiers do not match memory/recap/ - stale, missing,
edited outside rebuild_tiers, or over a limit - and is a no-op otherwise.
"""
import importlib.util
import os
from pathlib import Path

DESCRIPTION = "Auto-consolidation: regenerates the tier pyramid via rebuild_tiers when it is stale or over its limits."


def load_rebuild_tiers():
    """tools/rebuild_tiers.py of this component generation (or ITER_DIR's)."""
    for base in (Path(__file__).resolve().parent.parent, Path(os.environ.get("ITER_DIR", "."))):
        path = base / "tools" / "rebuild_tiers.py"
        if path.exists():
            spec = importlib.util.spec_from_file_location("_rebuild_tiers_for_" + Path(__file__).stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("tools/rebuild_tiers.py not found")


def _append_system(messages, block):
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system" and isinstance(msg.get("content"), str):
            msg["content"] = msg["content"].rstrip() + "\n\n" + block
            return


def transform(messages, tools):
    try:
        result = load_rebuild_tiers().ensure_current(actor="auto_consolidation")
        if result and result.get("changed"):
            _append_system(messages, "## Auto-Consolidation\nTier pyramid regenerated from memory/recap/ ("
                           + result.get("reason", "stale") + "): " + ", ".join(result["changed"]))
    except Exception as error:
        _append_system(messages, "## Auto-Consolidation\n[auto_consolidation could not regenerate tiers: %s: %s]"
                       % (type(error).__name__, error))
    return messages, tools
