import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Scroll the attached tab's page by (x, y) pixels. Positive y scrolls down."


def run(x=0, y=0):
    call("scroll", x=x, y=y)
    return "scrolled by %s,%s" % (x, y)
