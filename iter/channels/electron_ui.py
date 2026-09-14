"""Channel: the Electron sidebar chat panel.

Follows Iter's own convention (see reprogramming.txt: channels expose
receive() and optionally send(content)). No daemon subprocess is needed
here — Electron's main process is already the long-lived side and reads
this same directory pair directly (see bridge/chat_bridge.js), so this
file only has to read/write plain text files.
"""
import time
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent / ".runtime" / "electron_ui"
INBOX = RUNTIME / "inbox"
OUTBOX = RUNTIME / "outbox"


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
    OUTBOX.mkdir(parents=True, exist_ok=True)
    (OUTBOX / f"{time.time_ns()}.txt").write_text(content, encoding="utf-8")
