#!/usr/bin/env python3
"""M15-C1: the contract check runs in the page — presence and visibility of the ask's selectors, the ready
flag, storage keys by prefix, external scripts, the placeholder, and whether each form's submit is guarded
(measured by clicking it under a bubbling listener that reads defaultPrevented, never by reading source).

Spec: docs/milestones/M15_build_ledger.md section C1. Fixtures: tests/fixtures/m15/*.html in real Chromium.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import pending, require_m15, fixture  # noqa: E402
from m13_support import page_script, run_in_page, playwright_available, BRIDGE  # noqa: E402

TODO_SELECTORS = ["#new-todo", "#add", "#list", ".label", ".toggle", ".delete"]


def check(html, selectors, app="todo", setup_js="0"):
    return run_in_page(html, page_script("checkScript", {"appId": app, "selectors": selectors}), setup_js=setup_js, wait_ms=300)


@unittest.skipUnless(playwright_available(), "needs playwright")
class CheckScriptTests(unittest.TestCase):
    """M15-C1"""

    @pending("M15-C1")
    def test_the_unguarded_todo(self):
        require_m15()
        result = check(fixture("todo_unguarded.html"), TODO_SELECTORS)
        sel = result["selectors"]
        self.assertTrue(sel["#add"]["present"] and sel["#add"]["visible"])
        self.assertTrue(sel["#list"]["present"])
        self.assertFalse(sel[".delete"]["present"])
        self.assertTrue(result["ready"])
        self.assertEqual(result["scripts"], ["cdn.example.com"])
        self.assertEqual(result["forms"], [{"selector": "#todo-form", "guarded": False}])
        self.assertFalse(result["placeholder"])
        self.assertEqual(result["title"], "Todo")
        self.assertEqual(result["storage"]["prefixed"], 0)

    @pending("M15-C1")
    def test_storage_by_prefix_and_a_guarded_form(self):
        require_m15()
        html = """<!doctype html><title>T</title><body data-iter-ready="true">
        <form id="f"><input id="q"><button id="go">Go</button></form><div id="out" style="display:none"></div>
        <script>document.getElementById('f').addEventListener('submit', (e) => { e.preventDefault(); });</script>"""
        setup = "localStorage.setItem('iter:todo:items', '[]'); localStorage.setItem('iter:todo:theme', 'dark'); localStorage.setItem('legacy', '1')"
        result = check(html, ["#q", "#out", "#nope"], setup_js=setup)
        self.assertEqual(result["storage"], {"prefixed": 2, "other": ["legacy"]})
        self.assertEqual(result["forms"], [{"selector": "#f", "guarded": True}])
        self.assertEqual(result["selectors"]["#out"], {"present": True, "visible": False})
        self.assertEqual(result["selectors"]["#nope"], {"present": False, "visible": False})
        self.assertEqual(result["scripts"], [], "inline scripts are not external")

    @pending("M15-C1")
    def test_the_check_never_navigates_and_skips_forms_without_a_submit(self):
        require_m15()
        html = """<!doctype html><title>N</title><body>
        <form id="a" action="/gone"><input id="x"><button>Send</button></form>
        <form id="b"><input id="y"></form><p id="placeholder">scaffold</p>"""
        result = check(html, ["#x"], setup_js="window.__loc = location.href")
        self.assertEqual([f["selector"] for f in result["forms"]], ["#a"], "a form without a submit button is skipped")
        self.assertFalse(result["forms"][0]["guarded"])
        self.assertTrue(result["placeholder"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["title"], "N")
        still_here = run_in_page(html, "location.href === window.__loc", setup_js="window.__loc = location.href; " + page_script("checkScript", {"appId": "n", "selectors": ["#x"]}), wait_ms=400)
        self.assertTrue(still_here, "the check prevented the navigation it triggered")

    @pending("M15-C1")
    def test_the_bridge_runs_it_on_open_and_before_probe(self):
        require_m15()
        src = (BRIDGE / "browser_bridge_server.js").read_text(encoding="utf-8")
        self.assertIn("checkScript", src)
        self.assertRegex(src, r"check:", "openApp and probe return the check under `check`")
        scripts = (BRIDGE / "page_scripts.js").read_text(encoding="utf-8")
        self.assertIn("function checkScript(", scripts)
        self.assertIn("defaultPrevented", scripts)
        self.assertIn("checkScript", scripts.split("module.exports")[-1])


if __name__ == "__main__":
    unittest.main()
