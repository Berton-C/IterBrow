"""Shared helpers for the Milestone 9 (wonder, growth voice, browsing ally, find) tests.
Spec: docs/milestones/M9_soul_wonder_ally.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented
(remove the decorator to activate the test). Service-backed tests use `m9_root`, which fails
fast without starting a service until iter/tools/wonder.py exists.
"""
import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, FEATURES, node, run_bridge, playwright_available, run_playwright  # noqa: E402,F401
from m7_support import write_soul_settings, run_transformation, tool_entry, card_atoms, choice_atom  # noqa: E402,F401
from m8_support import make_app_dir  # noqa: E402,F401

M9_IMPLEMENTED = (ITER_SRC / "tools" / "wonder.py").exists()
HOUR = 3600 * 1000


def pending(item):
    assert item.startswith("M9-"), item
    return unittest.expectedFailure


def require_m9():
    if not M9_IMPLEMENTED:
        raise AssertionError("Milestone 9 not implemented: iter/tools/wonder.py is missing")


class _Unimplemented:
    def start(self):
        return None

    def close(self):
        return None

    def __getattr__(self, name):
        require_m9()
        raise AttributeError(name)


def m9_root(name):
    if not M9_IMPLEMENTED:
        return _Unimplemented()
    from semantic_memory_support import SemanticRoot
    return SemanticRoot(name)


def wonder_atom(person, app, wid, idea, status="open", at=1700000000000):
    return '(soul-wonder "%s" "%s" "%s" "%s" "%s" %d)' % (person, app, wid, idea, status, at)


def seed_wonder(root, person, app, wid, idea, status="open", at=1700000000000):
    root.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_wonder:%s" % wid,
                                           "atom": wonder_atom(person, app, wid, idea, status, at)}],
                           "actor": "iter", "source": "wonder"})


def seed_offered(root, person, wid, at):
    root.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_wonder_offer:%s" % person,
                                           "atom": '(soul-wonder-offered "%s" "%s" %d)' % (person, wid, at)},
                                          {"op": "upsert", "key": "state:soul_wonder_last:%s" % wid,
                                           "atom": '(soul-wonder-last "%s" %d)' % (wid, at)}],
                           "actor": "iter", "source": "soul_wonder"})


def seed_topic_card(root, card_id, topic, person="berton", kind="offer", choices=("take", "keep", "let_go"), at=1700000000000):
    ops = card_atoms(card_id, kind, person, [(c, None, None) for c in choices], at)
    ops.append({"op": "upsert", "key": "state:soul_card_topic:%s" % card_id,
                "atom": '(soul-card-topic "%s" "%s")' % (card_id, topic)})
    root.call("transact", {"operations": ops, "actor": "iter", "source": "card"})


def seed_pick(root, card_id, pick, person="berton", kind="offer", at=1700000000001):
    root.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_choice:%s" % card_id,
                                           "atom": choice_atom(person, kind, card_id, pick, at)}],
                           "actor": "person", "source": "sidebar"})


def wonders(root, person="berton"):
    """{id: status} for a person's ideas."""
    import re
    out = {}
    for atom in root.call("read_atoms", {"prefix": "state:soul_wonder:"})["atoms"].values():
        m = re.match(r'\(soul-wonder "([^"]*)" "([^"]*)" "([^"]*)" "((?:[^"\\]|\\.)*)" "([^"]*)" (\d+)\)', atom)
        if m and m.group(1) == person:
            out[m.group(3)] = m.group(5)
    return out


def write_browsing_log(root, entries):
    path = Path(root) / ".runtime" / "browsing_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries))
    return path


def now_ms():
    return int(time.time() * 1000)


def toolbar_page_script(setup_js, probe_js, api_js="{}"):
    """Playwright script: renderer/toolbar.html with a stubbed window.iterApi, run setup, print probe."""
    return """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1000, "height": 120})
    pg.add_init_script("window.__calls=[];window.__handlers={};window.iterApi=new Proxy(%s,{get:(t,k)=>k in t?t[k]:(...a)=>{window.__calls.push([k,...a]);return Promise.resolve([]);}});")
    pg.goto(%s); pg.wait_for_timeout(300)
    pg.evaluate(%s); pg.wait_for_timeout(200)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (api_js, json.dumps("file://" + str(REPO / "renderer" / "toolbar.html")), json.dumps(setup_js), json.dumps(probe_js))


TOOLBAR_API = ("{onTabsUpdate:(cb)=>{window.__handlers.tabs=cb;},listTabs:()=>Promise.resolve([{id:1,active:true,url:'https://a.test/',canGoBack:false,canGoForward:false,locked:false}]),"
               "onFindOpen:(cb)=>{window.__handlers.findOpen=cb;},onFindResult:(cb)=>{window.__handlers.findResult=cb;},"
               "onAllySuggest:(cb)=>{window.__handlers.allySuggest=cb;},onCompassState:(cb)=>{window.__handlers.compass=cb;}}")
