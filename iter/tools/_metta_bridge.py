# Shared helper for tools/metta.py (and anything else that wants direct
# socket access) -- NOT a tool itself (leading underscore, same convention
# as tools/_browser_bridge.py that this file deliberately mirrors).
#
# Talks to the Unix domain socket opened by metta_server.py -- a long-lived
# companion process holding one persistent hyperon.MeTTa() atomspace for the
# app's whole session, started/checked by main.js the same way it starts
# iter.py (see startMettaServer()). Same protocol shape as the browser
# bridge: one line of JSON in, one line of JSON out.
import json
import os
import socket

SOCKET_PATH = os.environ.get("ITER_METTA_SOCKET", "/tmp/iter-metta-bridge.sock")


def call(method, timeout=30, **params):
    if not os.path.exists(SOCKET_PATH):
        raise RuntimeError(
            "MeTTa server is not running (no bridge socket found). It should "
            "auto-start with `npm start` -- if this persists, check the "
            "Electron app's logs for metta_server.py errors."
        )
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    try:
        connection.connect(SOCKET_PATH)
        connection.sendall((json.dumps({"method": method, "params": params}) + "\n").encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            chunk = connection.recv(1 << 20)
            if not chunk:
                break
            buffer += chunk
        line, _, _ = buffer.partition(b"\n")
        response = json.loads(line.decode("utf-8"))
    finally:
        connection.close()
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "Unknown MeTTa server error")
    return response.get("result")


def is_running():
    return os.path.exists(SOCKET_PATH)
