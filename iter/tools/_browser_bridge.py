# Shared helper for tools/browser_*.py — NOT a tool itself (leading
# underscore means Iter's own tool loader ignores this file, per
# reprogramming.txt's "#LESSONS" convention).
#
# Talks to the Unix domain socket opened by the Iter Browser (Electron)
# app's main process — see bridge/browser_bridge_server.js. That process
# IS the browser now, so there is no extension or native-messaging host
# in between any more.
import json
import os
import socket

SOCKET_PATH = os.environ.get("ITER_BRIDGE_SOCKET", "/tmp/iter-browser-bridge.sock")
# The bridge's lock refusal (bridge/browser_bridge_server.js lockedError) starts "Tab N is locked by the user".
LOCK_MARKER = "locked by the user"


def _refusal(message):
    try:
        from iterbrow_runtime.tool_results import ToolOutput
    except ImportError:  # run outside the loop (tests, a shell): the runtime sits beside tools/
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from iterbrow_runtime.tool_results import ToolOutput
    return ToolOutput(message, None, state="refused")


def call(method, timeout=30, _raw_params=None, **params):
    if _raw_params is not None:
        params = _raw_params  # escape hatch for payload keys colliding with signature names
    if not os.path.exists(SOCKET_PATH):
        raise RuntimeError(
            "Iter Browser is not running (no bridge socket found). Start the Iter "
            "Browser Electron app first — this tool talks to its embedded tabs."
        )
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    try:
        connection.connect(SOCKET_PATH)
        connection.sendall((json.dumps({"method": method, "params": params}) + "\n").encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            chunk = connection.recv(65536)
            if not chunk:
                break
            buffer += chunk
        line, _, _ = buffer.partition(b"\n")
        response = json.loads(line.decode("utf-8"))
    finally:
        connection.close()
    if not response.get("ok"):
        error = response.get("error") or "Unknown Iter Browser Bridge error"
        if LOCK_MARKER in error:
            # The person's lock is a refusal, not a tool defect (M12-A3): success=None moves no belief.
            return _refusal(error)
        raise RuntimeError(error)
    return response.get("result")


def refused(value):
    """True when `call` returned the person's refusal; a tool returns it as its own result."""
    outcome = getattr(value, "execution_outcome", None)
    return isinstance(outcome, dict) and outcome.get("state") == "refused"


def named(summary):
    """An element summary {tag, id, text} as `button#go 'Go'` (M13)."""
    if not isinstance(summary, dict):
        return "nothing"
    label = (summary.get("tag") or "element") + ("#" + summary["id"] if summary.get("id") else "")
    return label + (" %r" % summary["text"] if summary.get("text") else "")


def where(result):
    """Where the page is after an action: `now: <title> <url>`."""
    title = (result or {}).get("title") or ""
    url = (result or {}).get("url") or ""
    return "now: %s%s" % ((repr(title) + " ") if title else "", url)
