"""Channel: the Electron sidebar chat panel.

Follows Iter's own convention (see reprogramming.txt: channels expose
receive() and optionally send(content)). No daemon subprocess is needed
here — Electron's main process is already the long-lived side and reads
this same directory pair directly (see bridge/chat_bridge.js), so this
file only has to read/write plain text files.
"""
import json
import os
import time
import uuid
from pathlib import Path

# Hot-load executes this module from an immutable generation copy.  Runtime
# queues belong to the canonical Iter root, never to that copy.  Electron and
# lifecycle helpers already use ITER_DIR as the canonical-root contract; the
# cwd fallback preserves direct `python iter.py` launches.
ITER_ROOT = Path(os.environ.get("ITER_DIR") or Path.cwd()).resolve()
RUNTIME = ITER_ROOT / ".runtime" / "electron_ui"
INBOX = RUNTIME / "inbox"
OUTBOX = RUNTIME / "outbox"
STAGING = RUNTIME / "staging"


def _publish(directory, filename, content):
    directory.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)
    temporary = STAGING / (filename + ".%s.tmp" % uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, directory / filename)
    finally:
        temporary.unlink(missing_ok=True)


def receive():
    INBOX.mkdir(parents=True, exist_ok=True)
    messages = []
    for path in sorted(INBOX.glob("*")):
        try:
            messages.append(path.read_text(encoding="utf-8"))
            path.unlink()
        except FileNotFoundError:
            pass
    return "\n".join(messages)


def send(content):
    message_id = "iter-%s" % uuid.uuid4()
    _publish(OUTBOX, message_id + ".json", json.dumps({
        "schema_version": 1, "id": message_id, "role": "iter",
        "content": str(content), "at": int(time.time() * 1000),
    }, ensure_ascii=False, sort_keys=True))
