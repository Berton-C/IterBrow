import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Navigate the attached browser tab to a URL."


def run(url):
    result = call("navigate", url=url) or {}
    warning = result.get("warning")
    if warning:
        # The bridge DID detect a real problem (e.g. ERR_FILE_NOT_FOUND for a
        # bad file:// path) — previously this was silently thrown away here,
        # so a failed navigation looked identical to a successful one. Surface
        # it so a wrong path/URL cannot be mistaken for success.
        return "navigate to %s reported a problem: %s — verify with browser_eval before assuming this worked" % (url, warning)
    return "navigated to %s" % url
