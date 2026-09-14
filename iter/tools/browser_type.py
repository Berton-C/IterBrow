import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Type text into the attached tab. Optionally pass a CSS selector to click-to-focus first, otherwise types "
    "into whatever element already has focus."
)


def run(text, selector=None):
    params = {"text": text}
    if selector:
        params["selector"] = selector
    result = call("type", **params)
    return "typed %s" % result["typed"]
