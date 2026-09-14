"""OpenUI-inspired browser feature #1+#2: live-DOM co-pilot + vision-feedback
loop, built on Iter Browser's real CDP/eval bridge (something OpenUI's own
sandboxed-iframe architecture cannot do - OpenUI can only preview a
generated page in isolation, never patch a page the user is actually
looking at).

One tool call: inject CSS and/or JS into the REAL, currently-attached page
(not a sandboxed iframe), immediately re-screenshot the result so the next
model turn can see whether the patch looks right (closing the
vision-feedback loop in a single round trip instead of eval-then-separately-
screenshot), and automatically save the patch into the component museum
(tools/_component_museum.py) so it is never only-in-the-live-DOM again.

Pass patch_id to iterate on the SAME injected <style>/<script> pair (it
gets replaced in place) rather than stacking up duplicate injections.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call
import _component_museum as museum

DESCRIPTION = (
    "Live-DOM co-pilot with built-in vision feedback: inject CSS and/or JS into the REAL, "
    "currently-attached browser tab (via CDP/eval - not a sandboxed preview) and immediately "
    "screenshot the result so you can see whether the patch looks right. Pass patch_id to "
    "replace/iterate on a previous patch in place instead of stacking duplicates. Every call "
    "auto-saves the patch (css/js/html snapshot/screenshot) into the component museum so it "
    "survives even if the tab later closes or navigates away. Pass tab_id to target any open "
    "tab without switching to it."
)

_INJECT_JS_TEMPLATE = """
(function() {
  var id = %(patch_id)r;
  var css = %(css)r;
  var existingStyle = document.getElementById('iter-patch-style-' + id);
  if (existingStyle) existingStyle.remove();
  if (css) {
    var style = document.createElement('style');
    style.id = 'iter-patch-style-' + id;
    style.textContent = css;
    document.head.appendChild(style);
  }
  return {patched: id, hadCss: !!css};
})();
"""


def _params(tab_id):
    return {"tabId": int(tab_id)} if tab_id else {}


def run(css="", js="", tab_id="", patch_id="", label=""):
    if not css and not js:
        raise ValueError("pass at least one of css or js")

    patch_id = patch_id or ("patch-%d" % int(time.time() * 1000))
    params = _params(tab_id)

    results = {"patch_id": patch_id}

    if css:
        inject_expr = _INJECT_JS_TEMPLATE % {"patch_id": patch_id, "css": css}
        results["css_inject"] = call("eval", expression=inject_expr, **params)

    if js:
        results["js_result"] = call("eval", expression=js, **params)

    url = ""
    html_snapshot = ""
    try:
        url = call("eval", expression="window.location.href", **params)
    except Exception:
        pass
    try:
        html_snapshot = call("eval", expression="document.documentElement.outerHTML", **params)
    except Exception:
        pass

    screenshot_path = ""
    try:
        shot = call("screenshot", **params)
        data_url = shot["dataUrl"]
        import base64
        import tempfile
        _, encoded = data_url.split(",", 1)
        screenshot_path = str(Path(tempfile.gettempdir()) / ("iter-browser-patch-%d.png" % int(time.time() * 1000)))
        Path(screenshot_path).write_bytes(base64.b64decode(encoded))
    except Exception:
        pass

    record = museum.save(
        label=label or ("live patch %s" % patch_id),
        url=url,
        tab_id=str(tab_id),
        css=css,
        js=js,
        html_snapshot=html_snapshot,
        screenshot_path=screenshot_path,
        source="live_patch",
    )
    results["museum_id"] = record["id"]

    if screenshot_path:
        # NOTE: transformations/browser_vision.py treats everything AFTER the
        # marker as the literal file path, so metadata must go BEFORE it.
        prefix = "[patch_id=%s museum_id=%s]\n" % (patch_id, record["id"])
        return prefix + "__ITER_BROWSER_SCREENSHOT__ " + screenshot_path
    return str(results)
