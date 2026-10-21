import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call, refused, named

DESCRIPTION = (
    'Scroll: with a CSS selector, bring it into view; else by (x, y) pixels (positive y is down) in the '
    'focused scrollable container or the page, and report how far it moved. tab_id: optional.'
)


def run(x=0, y=0, selector="", tab_id=""):
    params = dict({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}, x=float(x or 0), y=float(y or 0))
    if selector:
        params["selector"] = selector
    result = call("scroll", **params)
    if refused(result):
        return result
    result = result or {}
    if result.get("target"):
        return "scrolled %s into view" % named(result["target"])
    before, after = result.get("before") or {}, result.get("after") or {}
    box = named(result["container"]) if result.get("container") else "the page"
    return "scrolled %s from %s,%s to %s,%s" % (box, before.get("x"), before.get("y"), after.get("x"), after.get("y"))
