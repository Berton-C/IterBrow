import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = "Display a browser tab and select it as the target for subsequent browser tools. Pass tab_id from browser_tabs."


def run(tab_id):
    call("switchTab", tabId=int(tab_id))
    return "switched to tabId=%s" % tab_id
