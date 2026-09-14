import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Get the attached tab's visible page text (document.body.innerText, truncated to 20000 chars). Cheaper "
    "than a screenshot when you just need to read content."
)


def run():
    return call("getText")
