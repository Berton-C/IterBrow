import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = 'List open tabs: id, displayed, your target, locked by the person, and which app (app=- for a page).'


def run():
    tabs = call("getTabs") or []
    # The target is the tab Iter attached to; with none attached, the displayed tab (resolveTabId's rule).
    any_attached = any(tab.get("attached") for tab in tabs)
    lines = []
    for tab in tabs:
        target = bool(tab.get("attached")) if any_attached else bool(tab.get("active"))
        lines.append("tabId=%s displayed=%s target=%s locked=%s app=%s title=%r url=%s" % (
            tab["id"], str(bool(tab.get("active"))).lower(), str(target).lower(), str(bool(tab.get("locked"))).lower(),
            tab.get("app") or "-", tab.get("title") or "", tab.get("url") or ""))
    return "\n".join(lines) if lines else "no tabs"
