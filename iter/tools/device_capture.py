"""
Device Capture tool -- lets Iter take a photo with the camera or record a
clip with the microphone, from inside its own browser.

Design: opens a normal, visible tab (so the user always sees when the
camera/mic tab is open, per their explicit preference) pointed at the local
renderer/capture.html page, then drives it the exact same way
browser_tab_variants.py's screenshot/eval already do -- through the Unix
socket bridge (see bridge/browser_bridge_server.js) calling the tab
manager's existing `eval` method. No changes to the bridge server or tab
manager were needed: capture.html exposes plain window functions
(iterCapturePhoto / iterCaptureAudio) that request getUserMedia access and
return a base64 data URL, and `eval` already waits for a returned Promise
to resolve before answering.

The macOS Camera/Microphone system permission prompt (Privacy & Security)
appears the first time this runs, driven by the OS itself -- if the user
denies it, capture fails with a clear error pointing at Settings ->
Permissions in the app (or System Settings) to grant it.

Captured files are saved under memory/captures/ as new, uniquely
timestamped files -- never overwriting anything, so no memory-guard
protection class applies.
"""
import base64
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _browser_bridge import call

DESCRIPTION = (
    "Take a photo with the camera or record a clip with the microphone, using a "
    "visible browser tab the user can see. Args: action (str: 'photo'|'record'|"
    "'close'), duration (float, optional, seconds to record audio for -- only "
    "used by 'record', default 5, max 30), tab_id (int, optional -- required for "
    "'close', pass the tab_id a previous call returned to close a capture tab "
    "instead of leaving it open). Returns a dict; 'photo' and 'record' include "
    "'saved_path' (file under memory/captures/) and 'tab_id' (the capture tab, "
    "left open so the user can see the result -- close it yourself with action "
    "'close' once you're done with it, or leave it for the user)."
)

_TOOLS_DIR = Path(__file__).resolve().parent
_ITER_DIR = _TOOLS_DIR.parent
_SOURCE_DIR = _ITER_DIR.parent
_CAPTURE_HTML = _SOURCE_DIR / "renderer" / "capture.html"
_CAPTURE_DIR = _ITER_DIR / "memory" / "captures"


def _open_tab(mode):
    url = "file://" + str(_CAPTURE_HTML) + "?mode=" + mode
    result = call("newTab", url=url)
    tid = result["created"]
    _wait_ready(tid)
    return tid


def _wait_ready(tab_id, timeout=8.0):
    # newTab returns before the page has finished loading, and eval() runs
    # immediately -- without this, the very first capture call on a fresh
    # tab can race the page's own script and fail with "iterCapturePhoto is
    # not a function". Poll until capture.js has actually defined it.
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            kind = call("eval", timeout=10, tabId=tab_id, expression="typeof window.iterCapturePhoto")
        except Exception:
            kind = None
        if kind == "function":
            return True
        time.sleep(0.15)
    return False


def _save_data_url(data_url, ext):
    _CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    _, _, b64data = str(data_url).partition(",")
    raw = base64.b64decode(b64data)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = _CAPTURE_DIR / ("capture_%s.%s" % (stamp, ext))
    with open(path, "wb") as f:
        f.write(raw)
    return str(path)


def run(action="photo", duration=5, tab_id=None):
    action = str(action) if action else "photo"

    if action == "photo":
        tid = _open_tab("photo")
        try:
            data_url = call("eval", timeout=120, tabId=tid, expression="window.iterCapturePhoto()")
        except Exception as exc:
            return {
                "error": "camera capture failed: %s" % exc,
                "tab_id": tid,
                "hint": "Check Settings > Permissions in the app, or System Settings > Privacy & Security > Camera.",
            }
        saved = _save_data_url(data_url, "png")
        return {"saved_path": saved, "tab_id": tid}

    if action == "record":
        try:
            dur = float(duration) if duration else 5.0
        except (TypeError, ValueError):
            dur = 5.0
        dur = max(0.5, min(dur, 30.0))
        tid = _open_tab("audio")
        try:
            data_url = call(
                "eval",
                timeout=int(dur) + 60,
                tabId=tid,
                expression="window.iterCaptureAudio(%d)" % int(dur * 1000),
            )
        except Exception as exc:
            return {
                "error": "microphone capture failed: %s" % exc,
                "tab_id": tid,
                "hint": "Check Settings > Permissions in the app, or System Settings > Privacy & Security > Microphone.",
            }
        saved = _save_data_url(data_url, "webm")
        return {"saved_path": saved, "tab_id": tid, "duration": dur}

    if action == "close":
        if tab_id is None:
            return {"error": "close requires tab_id (from a previous photo/record call)"}
        call("closeTab", tabId=int(tab_id))
        return {"closed": int(tab_id)}

    return {"error": "unknown action %r (use photo|record|close)" % action}
