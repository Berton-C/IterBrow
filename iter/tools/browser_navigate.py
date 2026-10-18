import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _browser_bridge import call, refused
from iterbrow_runtime.tool_results import ToolOutput

DESCRIPTION = "Navigate the attached browser tab to a URL."


def run(url):
    result = call("navigate", url=url)
    if refused(result):
        return result
    result = result or {}
    warning = result.get("warning")
    if warning:
        # The bridge DID detect a real problem (e.g. ERR_FILE_NOT_FOUND for a
        # bad file:// path) — previously this was silently thrown away here,
        # so a failed navigation looked identical to a successful one. Surface
        # it so a wrong path/URL cannot be mistaken for success.
        # A failed navigation is a failure (M12-A3), not success text the reliability record believes.
        message = "navigate to %s reported a problem: %s — verify with browser_eval before assuming this worked" % (url, warning)
        return ToolOutput(message, False, state="failed")
    return "navigated to %s" % url
