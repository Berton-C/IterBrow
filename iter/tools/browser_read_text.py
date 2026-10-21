import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Get a tab's visible text (innerText, up to 20000 chars); cheaper than a screenshot for reading. "
    'tab_id: optional.'
)


def run(tab_id=""):
    return call("getText", **({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}))
