import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Bring a specific browser tab to the front / give it focus. Pass tab_id from browser_tabs."


def run(tab_id):
    call("switchTab", tabId=int(tab_id))
    return "switched to tabId=%s" % tab_id
