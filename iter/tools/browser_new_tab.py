import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Open a new tab at the given URL (defaults to a search page), wait for it to load, and make it the displayed "
    "tab and your target. To open one of the person's apps as they see it, use browser_open_app instead."
)


def run(url=""):
    result = call("newTab", url=url or "https://www.google.com")
    line = "opened tab %s: %s %s" % (result["created"], repr(result.get("title") or ""), result.get("url") or url)
    if result.get("warning"):
        line += " — load problem: %s" % result["warning"]
    return line
