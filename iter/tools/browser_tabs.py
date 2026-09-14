import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "List every open browser tab (id, title, url, active, windowId) so you can pick one to attach to or switch to."


def run():
    tabs = call("getTabs")
    lines = []
    for tab in tabs:
        lines.append(
            "tabId=%s active=%s title=%r url=%s" % (tab["id"], tab["active"], tab["title"], tab["url"])
        )
    return "\n".join(lines)
