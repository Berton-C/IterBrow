import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call, refused, named, where

DESCRIPTION = (
    'Click an element by CSS selector (preferred) or x,y viewport coordinates. Scrolls it into view and '
    'clicks only if visible and uncovered; says what it hit and where the page is now. tab_id: optional '
    '(the target tab).'
)


def run(selector=None, x=None, y=None, tab_id=""):
    params = {"tabId": int(tab_id)} if str(tab_id or "").strip() else {}
    if selector:
        params["selector"] = selector
    if x not in (None, "") and y not in (None, ""):
        params["x"], params["y"] = float(x), float(y)
    result = call("click", **params)
    if refused(result):
        return result
    hit = (" → %s" % named(result.get("target"))) if result.get("target") else ""
    focus = (" · focus: %s" % named(result.get("active"))) if result.get("active") else ""
    return "clicked %s%s · %s%s" % (result["clicked"], hit, where(result), focus)
