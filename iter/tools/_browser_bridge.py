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


def call(method, timeout=30, **params):
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
        raise RuntimeError(response.get("error") or "Unknown Iter Browser Bridge error")
    return response.get("result")
