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
    return "SUCCESS"
