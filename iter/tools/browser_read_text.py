import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Get a tab's visible page text (document.body.innerText, truncated to 20000 chars). Cheaper than a screenshot "
    "when you just need to read content. tab_id: optional (default: the target tab)."
)


def run(tab_id=""):
    return call("getText", **({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}))
