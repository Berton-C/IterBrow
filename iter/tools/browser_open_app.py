import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Open one of the person's apps (an id from the apps tool, e.g. mapstation) the way they see it: as an app tab "
    "with its preload (window.iterApp), focusing it if it is already open. Waits for it to load and makes it your "
    "target. Use this, not browser_new_tab, before testing an app with app_probe or clicking in it."
)


def run(app_id):
    result = call("openApp", appId=str(app_id).strip())
    return "app %s: tabId=%s %s %s" % (result.get("appId") or app_id, result.get("tabId"),
                                       "focused" if result.get("focused") else "opened", result.get("url") or "")
