import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Run JavaScript in a tab's page and return its JSON-serializable value: page state, form values, "
    'computed styles. tab_id: optional.'
)


def run(expression, tab_id=""):
    return call("eval", expression=expression, **({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}))  # a refusal (M12-A3) passes through
