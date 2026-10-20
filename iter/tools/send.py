import importlib.util
import re
from pathlib import Path

DESCRIPTION = "Send a message through a communication channel."

def run(channel, content):
    # Model-produced string arguments occasionally carry harmless surrounding
    # whitespace.  Treat that as formatting noise, but still reject anything
    # that could escape the channel namespace.
    channel = str(channel or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", channel):
        return f"Invalid channel: {channel}"

    # Channel code is executable generation content, so a hot-loaded send tool
    # must dispatch through the sibling channel in the same immutable
    # generation.  Channel application state still resolves through ITER_DIR.
    path = Path(__file__).resolve().parents[1] / "channels" / (channel + ".py")
    if not path.is_file():
        return f"Unknown channel: {channel}"
    spec = importlib.util.spec_from_file_location("channel_" + channel, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "send"):
        return f"Channel {channel} cannot send"
    module.send(content)
    # M14-J2: the result says how many replies went out since the person last spoke, so a model reading
    # its own tool results sees a repeat before it sends one. Counted from the channel's inbox/outbox when
    # the channel keeps them (electron_ui); never a refusal.
    return "SUCCESS" + _since_input_note(path.parent, channel)


def _since_input_note(channels_dir, channel):
    if channel != "electron_ui":
        return ""
    try:
        import json
        import os
        root = Path(os.environ.get("ITER_DIR") or Path(__file__).resolve().parents[1]) / ".runtime" / "electron_ui"
        outbox = sorted(root.glob("outbox/*.json"), key=lambda p: p.stat().st_mtime)
        last_in = max((p.stat().st_mtime for p in (root / "inbox").glob("*")), default=0.0)
        marker = root / ".last_input_at"
        try:
            last_in = max(last_in, float(marker.read_text().strip() or 0))
        except (OSError, ValueError):
            pass
        count = sum(1 for p in outbox if p.stat().st_mtime > last_in)
    except Exception:
        return ""
    if count <= 1:
        return ""
    return (" — %d messages sent since the person last spoke; they have your report. Wait for them (nop wait_seconds=0) "
            "or do unfinished work; do not send it again." % count)
