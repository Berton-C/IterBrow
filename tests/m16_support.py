"""Shared helpers for the Milestone 16 tests (pop-out tabs and the model settings panel, ported from EAOS).
Spec: docs/milestones/M16_shell_from_eaos.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented (remove the decorator
to activate the test). `M16_IMPLEMENTED` is keyed on bridge/model_settings.js (B1).

The tab manager runs in node with the stub electron of m10_support plus a fake pop-out window factory
(`popout_prelude`); the settings module runs in node with a fake fetch (`settings_node`).
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, node  # noqa: E402,F401
from m10_support import tab_manager_with_fake_electron  # noqa: E402

BRIDGE = REPO / "bridge"
RENDERER = REPO / "renderer"
M16_IMPLEMENTED = (BRIDGE / "model_settings.js").exists()


def pending(item):
    assert item.startswith("M16-"), item
    return unittest.expectedFailure


def require_m16():
    if not M16_IMPLEMENTED:
        raise AssertionError("Milestone 16 not implemented: bridge/model_settings.js is missing")


def source(rel):
    return (REPO / rel).read_text(encoding="utf-8")


POPOUT_PRELUDE = """
// m10_support's fake webContents has no close(); closeTab needs one.
FakeWebContents.prototype.close = function close() { this.closed = true; };
// A fake pop-out window: contentView like the main window's, close() fires its own close then closed handlers.
let nextWin = 100;
const windows = [];
function makePopoutWindow(tab) {
  const kids = [];
  const w = { id: nextWin++, tab, shown: 0, focused: 0, destroyed: false, handlers: {}, size: [900, 700],
    contentView: { children: kids, addChildView(v) { kids.push(v); }, removeChildView(v) { const i = kids.indexOf(v); if (i >= 0) kids.splice(i, 1); } },
    getContentSize() { return this.size; }, on(ev, cb) { (this.handlers[ev] = this.handlers[ev] || []).push(cb); },
    show() { this.shown += 1; }, focus() { this.focused += 1; }, isDestroyed() { return this.destroyed; },
    close() { if (this.destroyed) return; (this.handlers.close || []).forEach((cb) => cb()); this.destroyed = true; (this.handlers.closed || []).forEach((cb) => cb()); },
    resize(w2, h2) { this.size = [w2, h2]; (this.handlers.resize || []).forEach((cb) => cb()); } };
  windows.push(w);
  return w;
}
const tabs = new TabManager(win, { getContentBounds: bounds });
tabs.makePopoutWindow = makePopoutWindow;
const out = {};
"""


def popout_node(body):
    """Run `body` (JS) after a TabManager with the fake electron and fake pop-out windows; prints JSON `out`."""
    script = tab_manager_with_fake_electron() + POPOUT_PRELUDE + body + "\nprocess.stdout.write(JSON.stringify(out));"
    code, stdout, stderr = node(script)
    assert code == 0, stderr
    return json.loads(stdout.strip().splitlines()[-1])


def settings_node(body, responses="{}"):
    """Run `body` (JS) with `S` = bridge/model_settings.js and `fakeFetch`: a fetch whose answers come from the
    `responses` object literal {"<method> <url suffix>": {status, json} | [first, second]} (a list answers in
    order); `calls` records every request {method, url, body}. Prints JSON `out`."""
    script = """
const S = require(%s);
const responses = %s;
const calls = [];
async function fakeFetch(url, init = {}) {
  const method = (init.method || 'GET').toUpperCase();
  calls.push({ method, url, body: init.body ? JSON.parse(init.body) : null, auth: (init.headers || {}).Authorization || (init.headers || {}).authorization || null });
  const key = Object.keys(responses).find((k) => { const [m, suffix] = k.split(' '); return m === method && url.endsWith(suffix); });
  let answer = key ? responses[key] : { status: 404, json: { error: 'no fake for ' + method + ' ' + url } };
  if (Array.isArray(answer)) { answer = answer.length > 1 ? answer.shift() : answer[0]; }
  return { ok: answer.status >= 200 && answer.status < 300, status: answer.status, statusText: '', text: async () => JSON.stringify(answer.json) };
}
const out = {};
(async () => { %s
process.stdout.write(JSON.stringify(out)); })().catch((e) => { process.stdout.write(JSON.stringify({ error: String(e && e.stack || e) })); });
""" % (json.dumps(str(BRIDGE / "model_settings.js")), responses, body)
    code, stdout, stderr = node(script)
    assert code == 0, stderr
    result = json.loads(stdout.strip().splitlines()[-1])
    assert "error" not in result, result.get("error")
    return result
