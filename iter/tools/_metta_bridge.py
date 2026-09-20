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


def call(method, timeout=2, **params):
    # timeout defaults to 2s (was 30s) -- deliberately well under iter.py's
    # DYNAMIC_TIMEOUT=5s outer subprocess kill, so a down/stale server fails
    # fast and cleanly here instead of the whole subprocess being SIGKILLed
    # from outside at 5s (that outer kill was the real "TIMEOUT after 5s"
    # every metta-touching transformation was hitting on 2026-09-20).
    if not os.path.exists(SOCKET_PATH):
        raise RuntimeError(
            "MeTTa server is not running (no bridge socket found). It should "
            "auto-start with `npm start` -- if this persists, check the "
            "Electron app's logs for metta_server.py errors."
        )
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    try:
        try:
            connection.connect(SOCKET_PATH)
        except (ConnectionRefusedError, FileNotFoundError) as e:
            raise RuntimeError(
                "MeTTa server socket is stale (server crashed) -- it should "
                "auto-restart within a minute; if this persists, check the "
                "Electron app's logs for metta_server.py errors."
            ) from e
        connection.sendall((json.dumps({"method": method, "params": params}) + "\n").encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer:
            chunk = connection.recv(1 << 20)
            if not chunk:
                break
            buffer += chunk
        if b"\n" not in buffer:
            raise RuntimeError("MeTTa server closed the connection without a full response")
        line, _, _ = buffer.partition(b"\n")
        response = json.loads(line.decode("utf-8"))
    except socket.timeout as e:
        raise RuntimeError(f"MeTTa server did not respond within {timeout}s") from e
    finally:
        connection.close()
    if not response.get("ok"):
        raise RuntimeError(response.get("error") or "Unknown MeTTa server error")
    return response.get("result")


def is_running():
    return os.path.exists(SOCKET_PATH)
