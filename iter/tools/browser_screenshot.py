import base64
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Take a screenshot of the attached browser tab's current viewport and attach it as visual context for the "
    "next model turn. The tab needs a rendered surface; browser_attach alone does not display it. "
    "browser_switch_tab displays and targets an existing tab. An unavailable capture is a failure, not visual evidence."
)


def run():
    result = call("screenshot")
    data_url = result["dataUrl"]
    _, encoded = data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded, validate=True)
    if not image_bytes:
        raise RuntimeError("Browser screenshot capture returned an empty image; no screenshot was saved or attached.")
    path = str(Path(tempfile.gettempdir()) / ("iter-browser-screenshot-%d.png" % int(time.time() * 1000)))
    Path(path).write_bytes(image_bytes)
    return "__ITER_BROWSER_SCREENSHOT__ " + path
