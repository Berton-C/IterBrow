import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Clear the currently attached/targeted tab, so subsequent browser_* calls fall back to whichever tab is active."


def run():
    result = call("detach")
    return "detached tabId=%s" % result["detached"]
