"""Every local app with its real file URL (docs/milestones/M10_ally_sdk.md C6).

An app opened from the Apps menu runs as an app tab, with the app preload (window.iterApp); navigating a
tab to the listed URL shows the page without it. Never guess a path.
"""
import os
import sys
from pathlib import Path

DESCRIPTION = """List every local app the person has (Foundry projects under apps/ and plain folders like crm, mapstation, nodequest) with its real file URL and brief. The person opens an app from the Apps menu (an app tab, with window.iterApp); browser_navigate to the listed URL shows the page without the app preload. Never guess a path."""

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def run():
    from iterbrow_runtime import local_apps
    apps = local_apps.list_apps()
    if not apps:
        return "ALLY: none"
    lines = []
    for app in apps:
        line = "%s (%s) %s" % (app["id"], app["kind"], local_apps.entry_url(app))
        if app["brief"]:
            line += " — for %s" % app["brief"]["for"]
        lines.append(line)
    return "\n".join(lines)
