"""Shared helpers for the Milestone 13 (the builder's eyes) tests. Spec: docs/milestones/M13_builder_eyes.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented (remove the
decorator to activate the test). `M13_IMPLEMENTED` is keyed on bridge/page_scripts.js.

Three ways to test without Electron: page scripts run in a real Chromium (Playwright); bridge methods
run in node against a fake tab manager (`bridge_call`); tools run in a fresh process against a fake
bridge socket that answers every call with one canned response (`fake_bridge`).
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, node, run_playwright, playwright_available  # noqa: E402,F401
from m12_support import m12_root, run_tool, tool_text  # noqa: E402,F401

BRIDGE = REPO / "bridge"
M13_IMPLEMENTED = (BRIDGE / "page_scripts.js").exists()


def pending(item):
    assert item.startswith("M13-"), item
    return unittest.expectedFailure


def require_m13():
    if not M13_IMPLEMENTED:
        raise AssertionError("Milestone 13 not implemented: bridge/page_scripts.js is missing")


def page_script(name, *args):
    """The expression string bridge/page_scripts.js builds for `name(*args)`."""
    code, out, err = node("const P = require(%s); process.stdout.write(JSON.stringify(P.%s(%s)));"
                          % (json.dumps(str(BRIDGE / "page_scripts.js")), name, ", ".join(json.dumps(a) for a in args)))
    assert code == 0, err
    return json.loads(out.strip().splitlines()[-1])


def run_in_page(html, expression, setup_js="0", wait_ms=100):
    """Evaluate a page-script expression in a Chromium page built from `html`; returns its value."""
    script = """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 900, "height": 600})
    pg.set_content(%s); pg.wait_for_timeout(50)
    pg.evaluate(%s); pg.wait_for_timeout(%d)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (json.dumps(html), json.dumps(setup_js), wait_ms, json.dumps(expression))
    return json.loads(run_playwright(script).strip().splitlines()[-1])


def bridge_call(fake_tabs_js, method, params, apps_js="{}"):
    """Run bridge/browser_bridge_server.js buildMethods(fakeTabs, apps)[method](params) in node.

    `fake_tabs_js` is a JS object literal standing in for the TabManager. Returns {"ok", "result"|"error"}."""
    code, out, err = node("""
const { buildMethods } = require(%s);
const tabs = %s;
const methods = buildMethods(tabs, %s);
(async () => {
  try { const result = await methods[%s](%s); process.stdout.write(JSON.stringify({ ok: true, result })); }
  catch (error) { process.stdout.write(JSON.stringify({ ok: false, error: String(error && error.message || error) })); }
})();
""" % (json.dumps(str(BRIDGE / "browser_bridge_server.js")), fake_tabs_js, apps_js, json.dumps(method), json.dumps(params)))
    assert code == 0, err
    return json.loads(out.strip().splitlines()[-1])


class fake_bridge:
    """A Unix socket that answers every bridge call with `response` (a dict: {"ok": ..., "result"|"error"}),
    recording the requests. Use as a context manager; `env` gives the tool its socket."""

    def __init__(self, root, response):
        self.path = root.root / ".runtime" / ("fake-bridge-%d.sock" % (time.time() * 1000 % 1000000))
        self.response = response
        self.requests = []
        self._server = None
        self._thread = None

    def __enter__(self):
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self.path))
        self._server.listen(8)
        self._server.settimeout(0.2)

        def serve():
            while self._server:
                try:
                    conn, _ = self._server.accept()
                except (socket.timeout, OSError):
                    continue
                data = b""
                while b"\n" not in data:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                try:
                    self.requests.append(json.loads(data.decode("utf-8").split("\n")[0]))
                except Exception:
                    self.requests.append({"raw": data.decode("utf-8", "replace")})
                reply = self.response(self.requests[-1]) if callable(self.response) else self.response
                conn.sendall((json.dumps(reply) + "\n").encode("utf-8"))
                conn.close()

        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        server, self._server = self._server, None
        server.close()
        try:
            os.unlink(self.path)
        except OSError:
            pass

    @property
    def env(self):
        return {"ITER_BRIDGE_SOCKET": str(self.path)}


def main_js():
    return (REPO / "main.js").read_text(encoding="utf-8")


def tab_manager_js():
    return (BRIDGE / "tab_manager.js").read_text(encoding="utf-8")


def tool_source(name):
    return (ITER_SRC / "tools" / (name + ".py")).read_text(encoding="utf-8")
