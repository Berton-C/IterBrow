import base64
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Screenshot the target tab's viewport and attach it for the next turn. The tab must be displayed "
    '(browser_switch_tab). An unavailable capture is a failure, not evidence. tab_id: optional.'
)


def run(tab_id=""):
    result = call("screenshot", **({"tabId": int(tab_id)} if str(tab_id or "").strip() else {}))
    data_url = result["dataUrl"]
    _, encoded = data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded, validate=True)
    if not image_bytes:
        raise RuntimeError("Browser screenshot capture returned an empty image; no screenshot was saved or attached.")
    path = str(Path(tempfile.gettempdir()) / ("iter-browser-screenshot-%d.png" % int(time.time() * 1000)))
    Path(path).write_bytes(image_bytes)
    return "__ITER_BROWSER_SCREENSHOT__ " + path
