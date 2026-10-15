"""Shared helpers for the Milestone 6 (Soul base) tests. Spec: docs/milestones/M6_soul_base.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented
(remove the decorator to activate the test). Service-backed tests use `m6_root`, which fails
fast without starting a service until iter/iterbrow_runtime/soul_settings.py exists.
"""
import importlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ITER_SRC = REPO / "iter"
NODE = shutil.which("node")
if str(ITER_SRC) not in sys.path:
    sys.path.insert(0, str(ITER_SRC))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

M6_IMPLEMENTED = (ITER_SRC / "iterbrow_runtime" / "soul_settings.py").exists()

PATTERNS = ["AgencyBalance", "CognitiveResilience", "ConnectionDepth", "WonderPreservation", "TimeCoherence",
            "PurposeBeyondUtility", "SharedUnderstanding", "CreativeTranscendence", "AttentionStewardship"]
PAIRS = [("Safety", "Helpfulness"), ("AgencyBalance", "PurposeBeyondUtility"),
         ("TimeCoherence", "CreativeTranscendence"), ("SharedUnderstanding", "WonderPreservation")]
FACETS = ["soul-pattern", "soul-pattern-pole+", "soul-pattern-pole-", "soul-pattern-signal", "soul-pattern-felt",
          "soul-pattern-moat", "soul-pattern-anti", "soul-pattern-proxy", "soul-pattern-gap"]
FEATURES = ["forks", "brief", "read", "wonder", "felt", "browsing_ally", "margin"]
DEFAULT_ON = {"forks", "brief"}


def pending(item):
    assert item.startswith("M6-"), item
    return unittest.expectedFailure


def require_m6():
    if not M6_IMPLEMENTED:
        raise AssertionError("Milestone 6 not implemented: iter/iterbrow_runtime/soul_settings.py is missing")


class _Unimplemented:
    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m6()
        raise AttributeError(name)


def m6_root(name):
    """A SemanticRoot (real AtomSpace service + tool runner) once M6 exists; else the stand-in."""
    if not M6_IMPLEMENTED:
        return _Unimplemented()
    from semantic_memory_support import SemanticRoot
    return SemanticRoot(name)


def soul_settings():
    return importlib.import_module("iterbrow_runtime.soul_settings")


def soul_lens():
    return importlib.import_module("iterbrow_runtime.soul_lens")


def node(script, cwd=None, timeout=120):
    """Run a node script (text) and return (returncode, stdout, stderr)."""
    proc = subprocess.run([NODE, "-e", script], cwd=str(cwd or REPO), capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def chat_bridge_script(iter_root, body):
    """Node snippet that opens the REAL chat bridge on iter_root and runs `body` with
    `bridge`, `received`, `logs`, `fs`, `path` in scope; prints JSON `out`."""
    return """
const fs = require('fs'); const path = require('path');
const { makeChatBridge } = require(%s);
const received = []; const logs = [];
const bridge = makeChatBridge(%s, (m) => received.push(m), { pollIntervalMs: 60000, settleMs: 0, log: (l) => logs.push(l) });
const settle = (p) => fs.utimesSync(p, new Date(0), new Date(0));
let out = {};
%s
bridge.stop();
process.stdout.write(JSON.stringify(out) + '\\n');
""" % (json.dumps(str(REPO / "bridge" / "chat_bridge.js")), json.dumps(str(iter_root)), body)


def run_bridge(iter_root, body):
    code, stdout, stderr = node(chat_bridge_script(iter_root, body))
    assert code == 0, stdout + stderr
    return json.loads(stdout.strip().splitlines()[-1])


SYSTEM_PYTHON = shutil.which("python3")


def playwright_available():
    if not SYSTEM_PYTHON:
        return False
    probe = subprocess.run([SYSTEM_PYTHON, "-c", "import playwright.sync_api"], capture_output=True)
    return probe.returncode == 0


def run_playwright(script, timeout=180):
    """Run a Playwright script with the system Python (the venv has no browser); returns stdout."""
    proc = subprocess.run([SYSTEM_PYTHON, "-I", "-c", script], capture_output=True, text=True, timeout=timeout)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def sidebar_page_script(setup_js, probe_js, iter_api_js="{}"):
    """Playwright script: load renderer/index.html with a stubbed window.iterApi, run setup, print probe result."""
    return """
import json, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 520, "height": 900})
    pg.add_init_script("window.__calls=[];window.iterApi=new Proxy(%s,{get:(t,k)=>k in t?t[k]:(...a)=>{window.__calls.push([k,...a]);return Promise.resolve([]);}});")
    pg.goto(%s); pg.wait_for_timeout(400)
    pg.evaluate(%s); pg.wait_for_timeout(200)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (iter_api_js, json.dumps("file://" + str(REPO / "renderer" / "index.html")), json.dumps(setup_js), json.dumps(probe_js))


def card(kind="fork", title="Which way?", body="Two poles.", choices=None, card_id="card-test-1", links=None):
    return {"id": card_id, "kind": kind, "title": title, "body": body,
            "choices": choices if choices is not None else [{"id": "a", "label": "Keep it playful", "hint": "wonder"},
                                                           {"id": "b", "label": "Keep it obvious", "hint": "shared understanding"}],
            **({"links": links} if links else {})}


def outbox_message(card_obj, content=None, message_id="iter-card-1"):
    return {"schema_version": 1, "id": message_id, "role": "iter", "at": 1700000000000,
            "content": content if content is not None else "**%s**\n\n%s" % (card_obj["title"], card_obj["body"]),
            "card": card_obj}


def reference_kernel():
    """The ClarityOmega reference kernel if a checkout is present (facet texts are compared verbatim)."""
    for candidate in (Path("/home/claude/berton-c/clarityomega/soul/soul_kernel.metta"),
                      REPO.parent / "clarityomega" / "soul" / "soul_kernel.metta"):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return None


def count_atoms(text, head):
    import re
    return len(re.findall(r"^\s*\(%s[\s)]" % re.escape(head), text, flags=re.M))


def read_manifest():
    return json.loads((ITER_SRC / "state_manifest.json").read_text())
