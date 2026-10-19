import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Run arbitrary JavaScript in a tab's page context and return its (JSON-serializable) return value. Use for "
    "reading page state, form values, computed styles, etc. that don't need a screenshot. tab_id: optional "
    "(default: the target tab)."
)


def run(expression, tab_id=""):
    return call("eval", expression=expression, **({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}))  # a refusal (M12-A3) passes through
