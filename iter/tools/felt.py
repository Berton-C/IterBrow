"""The felt channel: a short note, in Iter's own voice, on what it found interesting.

docs/milestones/M7_soul_personality.md section B. Offered only when the person turned the
"felt" Soul feature on (transformations/soul_presence.py removes it otherwise). The note
shows in the sidebar as a voice, not a card: nothing to answer, nothing decided.
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

DESCRIPTION = (
    'Say in one short paragraph (under 280 chars) what you enjoyed in the work just now; it shows in your'
    ' own voice, nothing to answer. Now and then, never as a status report.'
)

MAX_CHARS = 280
TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _channel():
    path = TOOLS_DIR.parent / "channels" / "electron_ui.py"
    spec = importlib.util.spec_from_file_location("electron_ui_channel_for_felt", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _person():
    try:
        from iterbrow_runtime import soul_settings
        return soul_settings.person()
    except Exception:
        return "guest"


def run(text):
    text = str(text or "").strip()
    if not text:
        return "ERROR: a felt note needs some words"
    if len(text) > MAX_CHARS:
        return "ERROR: keep a felt note under 280 characters"
    message_id = _channel().send_felt(text)
    try:
        from iterbrow_runtime.cognitive_events import _call_atomspace
        _call_atomspace("transact", actor="iter", source="felt", operations=[{
            "op": "upsert", "key": "state:soul_felt:%s" % message_id,
            "atom": "(soul-felt %s %d)" % (json.dumps(_person()), int(time.time() * 1000))}])
    except Exception:
        return "FELT-SENT: %s (unrecorded)" % message_id
    return "FELT-SENT: %s" % message_id
