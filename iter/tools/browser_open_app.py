import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Open one of the person's apps (an id from the apps tool, e.g. mapstation) the way they see it: as an app tab "
    "with its preload (window.iterApp); if it is already open, focuses it and reloads it when its files changed "
    "since it loaded (so what you look at is what is on disk). Waits for the load and makes it your target. Use "
    "this, not browser_new_tab, after every edit and before app_probe or clicking in it."
)


def run(app_id):
    result = call("openApp", appId=str(app_id).strip())
    how = "reloaded (files changed since it loaded)" if result.get("reloaded") else ("focused" if result.get("focused") else "opened")
    return "app %s: tabId=%s %s %s" % (result.get("appId") or app_id, result.get("tabId"), how, result.get("url") or "")
