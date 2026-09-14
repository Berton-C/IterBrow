import base64
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Take a screenshot of the attached browser tab's current viewport and attach it as visual context for the "
    "next model turn. Use this to see what the page actually looks like before deciding on clicks."
)


def run():
    result = call("screenshot")
    data_url = result["dataUrl"]
    _, encoded = data_url.split(",", 1)
    path = str(Path(tempfile.gettempdir()) / ("iter-browser-screenshot-%d.png" % int(time.time() * 1000)))
    Path(path).write_bytes(base64.b64decode(encoded))
    return "__ITER_BROWSER_SCREENSHOT__ " + path
