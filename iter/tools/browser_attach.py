import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Mark a tab as the current target for navigate/click/type/screenshot/eval/scroll, so you don't have to "
    "pass tab_id on every call. Pass tab_id from browser_tabs, or omit to target the current active tab."
)


def run(tab_id=None):
    params = {"tabId": int(tab_id)} if tab_id else {}
    result = call("attach", **params)
    return "attached to tabId=%s title=%r url=%s" % (result["attached"], result["title"], result["url"])
