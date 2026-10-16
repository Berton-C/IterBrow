"""Shared helpers for the Milestone 8 (Soul presence) tests. Spec: docs/milestones/M8_soul_presence.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented
(remove the decorator to activate the test). Service-backed tests use `m8_root`, which fails
fast without starting a service until bridge/margin.js exists.
"""
import hashlib
import importlib
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, PATTERNS, FEATURES, node, run_bridge, playwright_available, run_playwright  # noqa: E402,F401
from m7_support import (write_soul_settings, run_transformation, tool_entry, museum_save, museum_get,  # noqa: E402,F401
                        card_atoms, choice_atom, seed_choice)

M8_IMPLEMENTED = (REPO / "bridge" / "margin.js").exists()
MODES = ["open", "jam", "quiet", "critique", "museum"]


def pending(item):
    assert item.startswith("M8-"), item
    return unittest.expectedFailure


def require_m8():
    if not M8_IMPLEMENTED:
        raise AssertionError("Milestone 8 not implemented: bridge/margin.js is missing")


class _Unimplemented:
    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m8()
        raise AttributeError(name)


def m8_root(name):
    """A SemanticRoot (real AtomSpace service + tool runner) once M8 exists; else the stand-in."""
    if not M8_IMPLEMENTED:
        return _Unimplemented()
    from semantic_memory_support import SemanticRoot
    return SemanticRoot(name)


def soul_settings():
    return importlib.import_module("iterbrow_runtime.soul_settings")


def write_settings_with_mode(root, person, mode, features=None, **profile):
    write_soul_settings(root, person, features, mode=mode, **profile)


def dir_digest(path):
    """sha256 over every file (relative path + bytes) under `path`, for 'nothing changed' checks."""
    digest = hashlib.sha256()
    for file in sorted(p for p in Path(path).rglob("*") if p.is_file()):
        digest.update(str(file.relative_to(path)).encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def make_app_dir(root, name="crm", body="<h1 id='title'>crm</h1><button class='primary big'>Save</button>"):
    (Path(root) / name).mkdir(exist_ok=True)
    (Path(root) / name / "index.html").write_text("<!doctype html><title>%s</title>%s" % (name, body))
    return Path(root) / name


def margin_page_script(api_js, setup_js, probe_js, body="<h1 id='title'>App</h1><p class='note lead'>hello</p>"):
    """Playwright script: a plain page with bridge/margin.js loaded as a classic script (it must
    expose window.IterMargin.installMargin when not under CommonJS), a stubbed api, then setup/probe."""
    return """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 900, "height": 700})
    pg.set_content(%s)
    pg.add_script_tag(path=%s)
    pg.evaluate("window.__api = " + %s)
    pg.evaluate("window.IterMargin.installMargin(document, window.__api)")
    pg.wait_for_timeout(300)
    pg.evaluate(%s); pg.wait_for_timeout(200)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (json.dumps("<!doctype html><html><body>%s</body></html>" % body), json.dumps(str(REPO / "bridge" / "margin.js")),
       json.dumps(api_js), json.dumps(setup_js), json.dumps(probe_js))


ENABLED_API = ("({enabled: () => Promise.resolve({enabled: true, app: 'orbit'}),"
               " send: (p) => { window.__sent = (window.__sent || []).concat([p]); return Promise.resolve({ok: true}); },"
               " onState: (cb) => { window.__state = cb; }})")
DISABLED_API = ("({enabled: () => Promise.resolve({enabled: false}),"
                " send: (p) => Promise.resolve({ok: true}), onState: (cb) => { window.__state = cb; }})")
