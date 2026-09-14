"""Live Preview tool, ported to Iter Browser's real Chromium engine.

The browser build rendered HTML into a hidden same-page iframe and only
checked the resulting innerHTML length as a crude "did it render" proxy —
it never actually took a screenshot despite the docstring's promise.

This native port does better: it opens a real (temporary) tab in the Iter
Browser window via the same bridge the browser_* tools use, navigates it
to a data: URL containing your HTML, takes a real screenshot, closes the
tab, and restores whichever tab was attached before — so this doesn't
disturb whatever you were already looking at. Requires the Iter Browser
app to be running (same requirement as the other browser_* tools).
"""

import base64
import json
import sys
import tempfile
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Render HTML in a real (temporary, off-screen) browser tab and capture a screenshot for "
    "visual verification. Args: html (str), width (int, default 800), height (int, default 600). "
    "Returns render status JSON; the screenshot is attached separately as visual context."
)


def run(html="", width=800, height=600):
    html = str(html) if html else "<p>No HTML provided</p>"
    width = int(width) if width else 800
    height = int(height) if height else 600

    prior_active_id = None
    try:
        for tab in call("getTabs"):
            if tab.get("active"):
                prior_active_id = tab.get("id")
                break
    except Exception:
        pass

    data_url = "data:text/html;charset=utf-8," + urllib.parse.quote(html)
    new_tab = call("newTab", url=data_url)
    new_tab_id = new_tab["created"]

    result = {"status": "rendered", "width": width, "height": height, "html_length": len(html)}
    screenshot_marker = None
    try:
        try:
            text = call("getText")
            result["rendered_chars"] = len(text or "")
            result["has_content"] = len(text or "") > 5
        except Exception:
            result["has_content"] = False

        try:
            shot = call("screenshot")
            data_url_out = shot["dataUrl"]
            _, encoded = data_url_out.split(",", 1)
            path = str(Path(tempfile.gettempdir()) / ("iter-preview-screenshot-%d.png" % int(time.time() * 1000)))
            Path(path).write_bytes(base64.b64decode(encoded))
            screenshot_marker = "__ITER_BROWSER_SCREENSHOT__ " + path
        except Exception as shot_error:
            result["screenshot_error"] = str(shot_error)
    finally:
        try:
            call("closeTab", tabId=int(new_tab_id))
        except Exception:
            pass
        if prior_active_id is not None:
            try:
                call("switchTab", tabId=int(prior_active_id))
            except Exception:
                pass

    if screenshot_marker:
        return json.dumps(result) + "\n" + screenshot_marker
    return json.dumps(result)
