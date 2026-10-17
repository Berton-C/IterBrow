"""Shared helpers for the Milestone 10 (ally SDK, apps) tests. Spec: docs/milestones/M10_ally_sdk.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented
(remove the decorator to activate the test). Service-backed tests use `m10_root`, which fails
fast without starting a service until iter/sdk/iter_ally.js exists.
"""
import hashlib
import json
import os
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, PATTERNS, PAIRS, node, run_playwright, playwright_available  # noqa: E402,F401
from m7_support import write_soul_settings, run_transformation  # noqa: E402,F401
from m8_support import make_app_dir, dir_digest  # noqa: E402,F401
from m9_support import toolbar_page_script, TOOLBAR_API  # noqa: E402,F401

SDK = ITER_SRC / "sdk" / "iter_ally.js"
KERNEL_JSON = ITER_SRC / "sdk" / "soul_kernel.json"
M10_IMPLEMENTED = SDK.exists()
BRIEF = {"for": "Bright, learning without dread", "flourishing": "she leaves curious, not drained"}


def pending(item):
    assert item.startswith("M10-"), item
    return unittest.expectedFailure


def require_m10():
    if not M10_IMPLEMENTED:
        raise AssertionError("Milestone 10 not implemented: iter/sdk/iter_ally.js is missing")


class _Unimplemented:
    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m10()
        raise AttributeError(name)


def m10_root(name):
    if not M10_IMPLEMENTED:
        return _Unimplemented()
    from semantic_memory_support import SemanticRoot
    return SemanticRoot(name)


def kernel_json():
    return json.loads(KERNEL_JSON.read_text(encoding="utf-8"))


def sdk_page_script(body, setup_js, probe_js, kernel=None, fetch_js=None, brief=None, extra_files=None, page_dir=None):
    """Playwright: a static page that loads iter/sdk/iter_ally.js as a classic script, with fetch stubbed
    (default: record calls and fail), installs the SDK with the kernel inline, runs setup, prints probe."""
    kernel_literal = json.dumps(kernel if kernel is not None else kernel_json())
    brief_literal = json.dumps(brief if brief is not None else BRIEF)
    fetch = fetch_js or "(...a) => { window.__fetches.push(a); return Promise.reject(new Error('no network in tests')); }"
    html = "<!doctype html><html><head><title>Test App</title></head><body>%s</body></html>" % body
    return """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 900, "height": 700})
    pg.set_content(%s)
    pg.evaluate("(() => { window.__fetches = []; window.fetch = %s; })()")  # set_content does not re-run init scripts
    pg.add_script_tag(path=%s)
    pg.evaluate("window.__kernel = " + %s)
    pg.evaluate("window.__brief = " + %s)
    pg.evaluate("window.__installed = window.IterAlly.install({ brief: window.__brief, person: 'bright', kernel: window.__kernel })")
    pg.wait_for_timeout(200)
    pg.evaluate(%s); pg.wait_for_timeout(200)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (json.dumps(html), fetch, json.dumps(str(SDK)), json.dumps(kernel_literal), json.dumps(brief_literal),
       json.dumps(setup_js), json.dumps(probe_js))


def run_sdk(body, setup_js, probe_js, **kwargs):
    return json.loads(run_playwright(sdk_page_script(body, setup_js, probe_js, **kwargs)).strip().splitlines()[-1])


def copy_nodequest(root):
    target = Path(root) / "nodequest"
    shutil.copytree(ITER_SRC / "nodequest", target, ignore=shutil.ignore_patterns("godot"))
    return target


def root_digest_excluding(root, *skip):
    """sha256 over the root's files except the named top-level dirs (and the usual runtime noise)."""
    skip = set(skip) | {".runtime", "memory", "transformations", "tools", "__pycache__", ".venv"}
    digest = hashlib.sha256()
    for file in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        rel = file.relative_to(root)
        if rel.parts[0] in skip or "__pycache__" in rel.parts or file.suffix in (".log", ".pyc"):
            continue
        digest.update(str(rel).encode()); digest.update(b"\0"); digest.update(file.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


def tab_manager_with_fake_electron():
    """Node snippet prelude: load bridge/tab_manager.js with a stub `electron` so TabManager can be driven
    without a window. Views record loadURL calls; webContents.on is a no-op registry."""
    return """
const Module = require('module');
const realLoad = Module._load;
let nextWc = 1;
class FakeWebContents { constructor() { this.id = nextWc++; this.handlers = {}; this.loaded = []; }
  on(ev, cb) { (this.handlers[ev] = this.handlers[ev] || []).push(cb); } setWindowOpenHandler(cb) { this.openHandler = cb; }
  loadURL(u) { this.loaded.push(u); } isDestroyed() { return false; } get navigationHistory() { return { canGoBack: () => false, canGoForward: () => false }; }
  send() {} focus() {} setZoomLevel() {} getZoomLevel() { return 0; } }
class WebContentsView { constructor(opts) { this.opts = opts; this.webContents = new FakeWebContents(); this.bounds = null; }
  setBounds(b) { this.bounds = b; } setVisible() {} }
Module._load = function (request, ...rest) { if (request === 'electron') return { WebContentsView }; return realLoad.call(this, request, ...rest); };
const { TabManager } = require(%s);
const children = [];
const win = { contentView: { children, addChildView(v) { children.push(v); }, removeChildView(v) { const i = children.indexOf(v); if (i >= 0) children.splice(i, 1); } } };
const bounds = () => ({ x: 0, y: 0, width: 1000, height: 800 });
""" % json.dumps(str(REPO / "bridge" / "tab_manager.js"))
