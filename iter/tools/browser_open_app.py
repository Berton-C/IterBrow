import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Open one of the person's apps (id from apps) as they see it: an app tab with window.iterApp. If "
    'open, focuses it and reloads when its files changed. Waits for the load and makes it your target. '
    'Use after every edit, before app_probe or clicking.'
)


def run(app_id):
    result = call("openApp", appId=str(app_id).strip())
    how = "reloaded (files changed since it loaded)" if result.get("reloaded") else ("focused" if result.get("focused") else "opened")
    return "app %s: tabId=%s %s %s" % (result.get("appId") or app_id, result.get("tabId"), how, result.get("url") or "")
