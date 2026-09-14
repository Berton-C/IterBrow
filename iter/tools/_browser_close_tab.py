import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Close a browser tab. Omit tab_id to close the currently attached/active tab."


def run(tab_id=""):
    params = {"tabId": int(tab_id)} if tab_id else {}
    result = call("closeTab", **params)
    return "closed: %s" % result["closed"]
