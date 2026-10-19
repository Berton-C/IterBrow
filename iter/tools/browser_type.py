import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call, refused, named, where

DESCRIPTION = (
    "Type text into a field. Pass a CSS selector to click the field first (recommended); without one it types into "
    "the focused element, and fails if nothing editable has focus. Returns the field and its value after typing. "
    "tab_id: optional (default: the target tab, which must be on screen)."
)


def run(text, selector=None, tab_id=""):
    params = dict({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}, text=text)
    if selector:
        params["selector"] = selector
    result = call("type", **params)
    if refused(result):
        return result
    return "typed %s into %s · %s" % (result["typed"], named(result.get("target")), where(result))
