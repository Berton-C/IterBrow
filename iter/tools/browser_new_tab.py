import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Open a new tab in the Iter Browser window at the given URL (defaults to a blank/search page) and make it the active/attached tab."


def run(url=""):
    result = call("newTab", url=url or "https://www.google.com")
    return "opened tab %s" % result["created"]
