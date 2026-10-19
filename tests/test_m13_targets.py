#!/usr/bin/env python3
"""M13-C1..C5: targets and apps — only Iter's own tabs move its target, browser_tabs tells the truth,
browser_open_app, app_probe for every app, app tabs stay on their app.

Spec: docs/milestones/M13_builder_eyes.md section C.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m13_support import (pending, require_m13, bridge_call, fake_bridge, m12_root, tool_text, main_js, tab_manager_js,  # noqa: E402
                         tool_source, node, BRIDGE, NODE)


class TargetTests(unittest.TestCase):
    """M13-C1 (source: createTab needs Electron)"""

    def test_only_agent_tabs_retarget(self):
        require_m13()
        tm = tab_manager_js()
        create = tm[tm.index("createTab(url = "):tm.index("appScopeForWebContentsId(")]
        self.assertRegex(create, r"if \(opts\.agent === true\) this\.attachedId = id;")
        self.assertNotRegex(create, r"^\s*this\.attachedId = id;", "no unconditional retarget")
        bridge = (BRIDGE / "browser_bridge_server.js").read_text(encoding="utf-8")
        new_tab = bridge[bridge.index("async newTab("):bridge.index("async closeTab(")]
        self.assertIn("agent: true", new_tab)
        main = main_js()
        self.assertNotIn("agent: true", main, "no main.js caller (menus, links, restore, Apps) moves Iter's target")
        restore = main[main.index("const savedSession = loadTabSession();"):main.index("const savedSession = loadTabSession();") + 1500]
        self.assertIn("tabs.attachedId = null", restore, "after restore the target is the displayed tab")


@unittest.skipUnless(NODE, "needs node")
class TabsListTests(unittest.TestCase):
    """M13-C2"""

    def test_browser_tabs_shows_displayed_target_locked_app(self):
        require_m13()
        tm = tab_manager_js()
        listing = tm[tm.index("  list() {"):tm.index("  list() {") + 700]
        self.assertIn("attached: t.id === this.attachedId", listing)
        r = m12_root("m13tabs")
        self.addCleanup(r.close)
        tabs = [{"id": 1, "title": "Google", "url": "https://www.google.com/", "active": True, "locked": False, "pinned": False, "app": None, "attached": False},
                {"id": 3, "title": "Iter Map Station", "url": "file:///x/iter/mapstation/index.html", "active": False, "locked": True, "pinned": False, "app": "mapstation", "attached": True}]
        with fake_bridge(r, {"ok": True, "result": tabs}) as bridge:
            out = tool_text(r, "browser_tabs", env=bridge.env)
        self.assertEqual(out.splitlines(), [
            "tabId=1 displayed=true target=false locked=false app=- title='Google' url=https://www.google.com/",
            "tabId=3 displayed=false target=true locked=true app=mapstation title='Iter Map Station' url=file:///x/iter/mapstation/index.html"])


class OpenAppTests(unittest.TestCase):
    """M13-C3"""

    def test_browser_open_app_tool(self):
        require_m13()
        r = m12_root("m13open")
        self.addCleanup(r.close)
        with fake_bridge(r, {"ok": True, "result": {"appId": "mapstation", "tabId": 4, "focused": False, "url": "file:///x/iter/mapstation/index.html", "title": "Iter Map Station"}}) as bridge:
            out = tool_text(r, "browser_open_app", env=bridge.env, app_id="mapstation")
            self.assertEqual(out, "app mapstation: tabId=4 opened file:///x/iter/mapstation/index.html")
            self.assertEqual(bridge.requests[-1]["method"], "openApp")
            self.assertEqual(bridge.requests[-1]["params"], {"appId": "mapstation"})
        with fake_bridge(r, {"ok": True, "result": {"appId": "crm", "tabId": 2, "focused": True, "url": "file:///x/crm/index.html"}}) as bridge:
            self.assertEqual(tool_text(r, "browser_open_app", env=bridge.env, app_id="crm"), "app crm: tabId=2 focused file:///x/crm/index.html")
        with fake_bridge(r, {"ok": False, "error": "no app named nope"}) as bridge:
            self.assertIn("no app named nope", tool_text(r, "browser_open_app", env=bridge.env, app_id="nope"))
        bridge_src = (BRIDGE / "browser_bridge_server.js").read_text(encoding="utf-8")
        open_app = bridge_src[bridge_src.index("async openApp("):bridge_src.index("async inspectApp(")]
        self.assertIn("awaitLoad", open_app, "the opened app is loaded before the tool returns")
        self.assertIn("browser_open_app", tool_source("apps"))


@unittest.skipUnless(NODE, "needs node")
class ProbeTests(unittest.TestCase):
    """M13-C4"""

    FAKE = """{
  activeId: 2, attachedId: null,
  tabs: new Map([[2, { id: 2, appScope: { appId: 'todo', consumerId: 'x' }, view: { webContents: { getURL: () => 'file:///v/todo/index.html',
    executeJavaScript: async (expr) => ({ observations: [
      { kind: 'text', selector: '#title', actual: 'Todo', expected: 'Todo' },
      { kind: 'count', selector: 'li', actual: 2, expected: 3 } ], title: 'Todo', ready: false }) } } }]]),
  isLocked(id) { return id === 9; },
  resolveTabId(id) { return id ? Number(id) : 2; },
  list() { return []; },
}"""

    def test_validate_probe_spec_and_bridge_probe(self):
        require_m13()
        code, out, err = node("""const F = require(%s);
const spec = F.validateProbeSpec({ appId: 'todo', steps: [{ kind: 'click', selector: '#add' }], assertions: [{ kind: 'text', selector: '#title', expected: 'Todo' }], timeoutMs: 999999 });
let bad = null; try { F.validateProbeSpec({ appId: 'todo', assertions: [] }); } catch (e) { bad = e.message; }
let rev = null; try { F.validateProbe({ appId: 'todo', assertions: [{ kind: 'text', selector: '#t', expected: 'x' }] }); } catch (e) { rev = e.message; }
process.stdout.write(JSON.stringify({ spec, bad, rev }));""" % json.dumps(str(BRIDGE / "foundry_apps.js")))
        self.assertEqual(code, 0, err)
        got = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(got["spec"]["timeoutMs"], 10000)
        self.assertNotIn("revisionId", got["spec"])
        self.assertIn("assertions", got["bad"])
        self.assertIn("revisionId", got["rev"], "the revisioned inspectApp keeps its own rule")
        out = bridge_call(self.FAKE, "probe", {"appId": "todo", "assertions": [{"kind": "text", "selector": "#title", "expected": "Todo"},
                                                                                {"kind": "count", "selector": "li", "expected": 3}]})
        self.assertTrue(out["ok"], out)
        result = out["result"]
        self.assertEqual((result["passed"], result["failed"], result["ready"], result["title"]), (1, 1, False, "Todo"))
        self.assertEqual([o["passed"] for o in result["observations"]], [True, False])
        missing = bridge_call(self.FAKE, "probe", {"appId": "nope", "assertions": [{"kind": "text", "selector": "#t", "expected": "x"}]})
        self.assertFalse(missing["ok"])
        self.assertIn("nope", missing["error"])

    def test_app_probe_tool_reports_each_assertion(self):
        r = m12_root("m13probe")
        self.addCleanup(r.close)
        result = {"observations": [{"kind": "text", "selector": "#title", "expected": "Todo", "actual": "Todo", "passed": True},
                                   {"kind": "count", "selector": "li", "expected": 3, "actual": 2, "passed": False}],
                  "passed": 1, "failed": 1, "ready": False, "title": "Todo"}
        with fake_bridge(r, {"ok": True, "result": result}) as bridge:
            out = tool_text(r, "app_probe", env=bridge.env, app="todo", steps='[{"kind":"click","selector":"#add"}]',
                            assertions='[{"kind":"text","selector":"#title","expected":"Todo"},{"kind":"count","selector":"li","expected":3}]', timeout="2")
            lines = out.splitlines()
            self.assertEqual(lines[0], "PROBE todo: 1 passed, 1 failed")
            self.assertEqual(lines[1], "✓ text #title: expected 'Todo' got 'Todo'")
            self.assertEqual(lines[2], "✗ count li: expected 3 got 2")
            self.assertEqual(bridge.requests[-1]["method"], "probe")
            self.assertEqual(bridge.requests[-1]["params"]["timeoutMs"], 2000)
            self.assertEqual(bridge.requests[-1]["params"]["steps"], [{"kind": "click", "selector": "#add"}])
        with fake_bridge(r, {"ok": False, "error": "Tab 9 is locked by the user and cannot be modified."}) as bridge:
            res = __import__("m13_support").run_tool(r, "app_probe", env=bridge.env, app="todo", assertions='[{"kind":"text","selector":"#t","expected":"x"}]')
            self.assertTrue(res["ok"])
            self.assertEqual((res.get("execution") or {}).get("state"), "refused")
        self.assertTrue(tool_text(r, "app_probe", app="todo", assertions="not json").startswith("ERROR"))


@unittest.skipUnless(NODE, "needs node")
class AppTabNavigationTests(unittest.TestCase):
    """M13-C5"""

    FAKE = """{
  activeId: 2, attachedId: null, navigated: [],
  tabs: new Map([[2, { id: 2, url: 'file:///v/todo/index.html', allowedUrl: 'file:///v/todo/index.html', appScope: { appId: 'todo', consumerId: 'x' } }],
                 [3, { id: 3, url: 'https://a.test/', appScope: null }]]),
  _insideAppDir(tab, url) { return url.startsWith('file:///v/todo/'); },
  isLocked() { return false; },
  resolveTabId(id) { return id ? Number(id) : 2; },
  async navigate(id, url) { this.navigated.push([id, url]); return { navigated: url }; },
  list() { return []; },
}"""

    def test_bridge_refuses_to_navigate_an_app_tab_away(self):
        require_m13()
        away = bridge_call(self.FAKE, "navigate", {"tabId": 2, "url": "https://evil.test/"})
        self.assertFalse(away["ok"])
        self.assertIn("App tab 2 stays on its app", away["error"])
        same = bridge_call(self.FAKE, "navigate", {"tabId": 2, "url": "file:///v/todo/index.html"})
        self.assertTrue(same["ok"], same)
        inside = bridge_call(self.FAKE, "navigate", {"tabId": 2, "url": "file:///v/todo/help.html"})
        self.assertTrue(inside["ok"], inside)
        ordinary = bridge_call(self.FAKE, "navigate", {"tabId": 3, "url": "https://b.test/"})
        self.assertTrue(ordinary["ok"], ordinary)


if __name__ == "__main__":
    unittest.main()
