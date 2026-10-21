import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    'Make a tab the target for navigate/click/type/screenshot/eval/scroll (tab_id from browser_tabs; omit'
    ' for the displayed tab). Does not display it; browser_switch_tab displays and targets.'
)


def run(tab_id=None):
    params = {"tabId": int(tab_id)} if tab_id else {}
    result = call("attach", **params)
    return "attached to tabId=%s title=%r url=%s displayed=%s" % (result["attached"], result["title"], result["url"], result.get("displayed", "unknown"))
