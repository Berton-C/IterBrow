#!/usr/bin/env python3
"""M13-B1..B6: honest actions — the page scripts in a real Chromium, click/type/scroll in the tab manager,
wait_for on the bridge and as a tool, newTab that waits, tab_id everywhere, cdp with DevTools open.

Spec: docs/milestones/M13_builder_eyes.md section B.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m13_support import (pending, require_m13, page_script, run_in_page, bridge_call, fake_bridge, m12_root, tool_text,  # noqa: E402
                         tab_manager_js, tool_source, playwright_available, NODE)

PAGE = """<!doctype html><html><head><style>
  body { margin: 0; } #tall { height: 2000px; } #below { position: absolute; top: 1500px; }
  #hidden { display: none; } #zero { width: 0; height: 0; overflow: hidden; }
  #cover { position: fixed; left: 0; top: 0; width: 200px; height: 100px; background: red; z-index: 10; }
  #under { position: absolute; left: 10px; top: 10px; width: 50px; height: 30px; }
  #box { height: 100px; overflow: auto; } #box div { height: 1000px; }
</style></head><body>
<button id="under">Under</button><div id="cover"></div>
<input id="name" value="">
<div id="tall">tall</div>
<button id="below">Below the fold</button>
<span id="hidden">hidden</span><span id="zero">zero</span>
<div id="box"><div>scrollable</div></div>
<p id="late"></p>
</body></html>"""


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class PageScriptTests(unittest.TestCase):
    """M13-B1"""

    @pending("M13-B1")
    def test_locate_names_every_way_a_click_could_not_happen(self):
        require_m13()
        invalid = run_in_page(PAGE, page_script("locateScript", "button[id="))
        self.assertEqual(invalid.get("error"), "invalid")
        missing = run_in_page(PAGE, page_script("locateScript", "#nope"))
        self.assertEqual(missing.get("error"), "missing")
        hidden = run_in_page(PAGE, page_script("locateScript", "#hidden"))
        self.assertFalse(hidden["visible"])
        zero = run_in_page(PAGE, page_script("locateScript", "#zero"))
        self.assertFalse(zero["visible"])
        covered = run_in_page(PAGE, page_script("locateScript", "#under"))
        self.assertTrue(covered["visible"])
        self.assertTrue(covered["covered"])
        self.assertEqual(covered["coveredBy"]["id"], "cover")
        below = run_in_page(PAGE, page_script("locateScript", "#below"))
        self.assertTrue(below["visible"], "scrolled into view first")
        self.assertFalse(below["covered"])
        self.assertTrue(0 <= below["rect"]["y"] <= 600, below["rect"])
        self.assertEqual(below["summary"], {"tag": "button", "id": "below", "text": "Below the fold"})
        self.assertFalse(below["editable"])
        self.assertTrue(run_in_page(PAGE, page_script("locateScript", "#name"))["editable"])

    @pending("M13-B1")
    def test_state_wait_and_scroll(self):
        state = run_in_page(PAGE, page_script("stateScript"), setup_js="document.getElementById('name').value='Ada'; document.getElementById('name').focus()")
        self.assertEqual(state["active"], {"tag": "input", "id": "name", "text": "Ada"})
        self.assertIn("title", state)
        self.assertTrue(state["url"].startswith("about:") or state["url"].startswith("http") or state["url"].startswith("file"))
        waited = run_in_page(PAGE, page_script("waitScript", {"text": "arrived", "timeoutMs": 3000}),
                             setup_js="setTimeout(() => { document.getElementById('late').textContent = 'arrived'; }, 300)", wait_ms=0)
        self.assertTrue(waited["found"])
        self.assertGreaterEqual(waited["afterMs"], 200)
        self.assertIn("arrived", json.dumps(waited["match"]))
        gone = run_in_page(PAGE, page_script("waitScript", {"selector": "#never", "timeoutMs": 400}), wait_ms=0)
        self.assertEqual(gone["found"], False)
        self.assertGreaterEqual(gone["afterMs"], 350)
        both = run_in_page(PAGE, page_script("waitScript", {"selector": "#below", "text": "tall", "timeoutMs": 500}), wait_ms=0)
        self.assertTrue(both["found"], "every given condition holds")
        boxed = run_in_page(PAGE, page_script("scrollScript", {"selector": "#box"}))
        self.assertEqual(boxed["target"]["id"], "box")
        moved = run_in_page(PAGE, page_script("scrollScript", {"x": 0, "y": 300}))
        self.assertEqual(moved["before"]["y"], 0)
        self.assertEqual(moved["after"]["y"], 300)
        inner = run_in_page(PAGE, page_script("scrollScript", {"x": 0, "y": 200}),
                            setup_js="document.getElementById('box').tabIndex = 0; document.getElementById('box').focus()")
        self.assertEqual(inner["after"]["y"], 200, "the focused scrollable container moved, not the window")

    @pending("M13-B1")
    def test_probe_script_moved_and_reexported(self):
        import subprocess
        from m13_support import BRIDGE
        out = subprocess.run([NODE, "-e", "const P=require(%s), F=require(%s); console.log(P.probeScript === F.probeScript)"
                              % (json.dumps(str(BRIDGE / "page_scripts.js")), json.dumps(str(BRIDGE / "foundry_apps.js")))],
                             capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), "true", out.stderr)


class TabManagerTests(unittest.TestCase):
    """M13-B2 / M13-B6 (source: tab_manager.js needs Electron)"""

    @pending("M13-B2")
    def test_click_and_type_are_honest(self):
        require_m13()
        src = tab_manager_js()
        self.assertIn("require('./page_scripts')", src)
        click = src[src.index("async click("):src.index("async type(")]
        self.assertIn("is not displayed; browser_switch_tab(", click)
        self.assertIn("locateScript(", click)
        for message in ("Invalid CSS selector:", "No element matched selector:", "but is not visible", "but is covered by"):
            self.assertIn(message, click, message)
        self.assertIn("stateScript()", click)
        self.assertRegex(click, r"return \{[^}]*clicked[^}]*target[^}]*url[^}]*title[^}]*active")
        typed = src[src.index("async type("):src.index("async scroll(")]
        self.assertIn("Nothing editable is focused; pass a selector for the field", typed)
        self.assertIn("insertText(", typed)
        self.assertRegex(typed, r"return \{[^}]*typed[^}]*target")
        scroll = src[src.index("async scroll("):src.index("async cdp(")]
        self.assertIn("scrollScript(", scroll)
        self.assertNotIn("elementCenter", src, "the old center-only locator is gone")

    @pending("M13-B6")
    def test_cdp_explains_devtools(self):
        src = tab_manager_js()
        cdp = src[src.index("async cdp("):]
        self.assertIn("DevTools is open on tab", cdp)


@unittest.skipUnless(NODE, "needs node")
class BridgeWaitAndNewTabTests(unittest.TestCase):
    """M13-B3 / M13-B4"""

    FAKE = """{
  activeId: 1, attachedId: null, calls: [],
  resolveTabId(id) { return id ? Number(id) : 1; },
  isLocked() { return false; },
  async waitFor({ id, selector, text, url, timeoutMs }) { this.calls.push({ id, selector, text, url, timeoutMs });
    return selector === '#never' ? { found: false, afterMs: timeoutMs } : { found: true, afterMs: 120, match: { tag: 'button', id: 'go', text: 'Go' } }; },
  createTab(url, opts) { this.calls.push({ createTab: url, opts }); return 7; },
  async navigate() { return { navigated: 'x' }; },
  async awaitLoad(id) { return { url: 'https://a.test/', title: 'A', warning: id === 9 ? 'slow' : undefined }; },
  list() { return []; },
}"""

    @pending("M13-B3")
    def test_wait_for_clamps_and_throws_on_timeout(self):
        require_m13()
        out = bridge_call(self.FAKE, "waitFor", {"selector": "#go", "timeoutMs": 50})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["result"]["match"]["id"], "go")
        out = bridge_call(self.FAKE, "waitFor", {"selector": "#never", "text": "x", "timeoutMs": 99999})
        self.assertFalse(out["ok"])
        self.assertRegex(out["error"], r"timed out after 30s waiting for .*#never.*x")

    @pending("M13-B4")
    def test_new_tab_waits_and_reports(self):
        out = bridge_call(self.FAKE, "newTab", {"url": "https://a.test/"})
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["result"]["created"], 7)
        self.assertEqual(out["result"]["url"], "https://a.test/")
        self.assertEqual(out["result"]["title"], "A")
        src = tab_manager_js()
        self.assertIn("awaitLoad(", src, "newTab's load wait shares navigate's event correlation")


class ToolWrapperTests(unittest.TestCase):
    """M13-B3 (tool) / M13-B5"""

    @pending("M13-B3")
    def test_browser_wait_for_tool(self):
        require_m13()
        r = m12_root("m13wait")
        self.addCleanup(r.close)
        with fake_bridge(r, {"ok": True, "result": {"found": True, "afterMs": 120, "match": {"tag": "button", "id": "go", "text": "Go"}}}) as bridge:
            out = tool_text(r, "browser_wait_for", env=bridge.env, selector="#go", timeout="5")
            self.assertEqual(out, "found button#go 'Go' after 120 ms")
            self.assertEqual(bridge.requests[-1]["params"], {"selector": "#go", "timeoutMs": 5000})
        with fake_bridge(r, {"ok": False, "error": "timed out after 5s waiting for selector #go"}) as bridge:
            out = tool_text(r, "browser_wait_for", env=bridge.env, selector="#go", timeout="5")
            self.assertTrue(out.startswith("RAISED"), "a timeout is a failure the loop scores")
            self.assertIn("timed out", out)

    @pending("M13-B5")
    def test_tab_id_on_every_action_tool(self):
        for name in ("browser_click", "browser_type", "browser_scroll", "browser_eval", "browser_read_text", "browser_screenshot", "browser_wait_for"):
            src = tool_source(name)
            self.assertRegex(src, r"def run\([^)]*tab_id", name)
            self.assertIn("tabId", src, name)
            self.assertIn("tab_id", src[src.index("DESCRIPTION"):src.index("def run(")], name + " description")
        attach = tool_source("browser_attach")
        self.assertNotIn("don't have to pass tab_id", attach)


if __name__ == "__main__":
    unittest.main()
