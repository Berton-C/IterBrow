import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Open a new tab at a URL, wait for the load, and make it displayed and your target. For the person's "
    'apps use browser_open_app.'
)


def run(url=""):
    result = call("newTab", url=url or "https://www.google.com")
    line = "opened tab %s: %s %s" % (result["created"], repr(result.get("title") or ""), result.get("url") or url)
    if result.get("warning"):
        line += " — load problem: %s" % result["warning"]
    return line
