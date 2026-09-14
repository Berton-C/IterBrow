import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Click an element in the attached tab. Pass a CSS selector (preferred, e.g. '#submit' or 'button.primary'), "
    "or raw x,y viewport coordinates if there is no good selector."
)


def run(selector=None, x=None, y=None):
    params = {}
    if selector:
        params["selector"] = selector
    if x is not None and y is not None:
        params["x"], params["y"] = float(x), float(y)
    result = call("click", **params)
    return "clicked %s" % result["clicked"]
