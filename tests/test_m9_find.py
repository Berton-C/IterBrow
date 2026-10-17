#!/usr/bin/env python3
"""M9-D1..D2: find-in-page — the toolbar bar and the main-process plumbing.

Spec: docs/milestones/M9_soul_wonder_ally.md section D.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m9_support import pending, require_m9, toolbar_page_script, TOOLBAR_API, run_playwright, playwright_available, NODE, REPO  # noqa: E402


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class FindBarTests(unittest.TestCase):
    """M9-D1"""

    def _page(self, setup, probe):
        return json.loads(run_playwright(toolbar_page_script(setup, probe, TOOLBAR_API)).strip().splitlines()[-1])

    @pending("M9-D1")
    def test_bar_opens_queries_steps_and_closes(self):
        require_m9()
        out = self._page("window.__handlers.findOpen();", """(async () => {
const bar = document.querySelector('#find-bar'); const text = document.querySelector('#find-text');
const shown = getComputedStyle(bar).display !== 'none'; const focused = document.activeElement === text;
text.value = 'asyncio'; text.dispatchEvent(new Event('input', {bubbles: true}));
await new Promise((r) => setTimeout(r, 50));
window.__handlers.findResult({ active: 2, total: 7 });
const count = document.querySelector('#find-count').textContent;
text.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
text.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', shiftKey: true, bubbles: true}));
document.querySelector('#find-next').click(); document.querySelector('#find-prev').click();
window.__handlers.findResult({ active: 0, total: 0 });
const none = document.querySelector('#find-count').textContent;
text.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
const hidden = getComputedStyle(bar).display === 'none';
window.__handlers.findOpen(); document.querySelector('#find-close').click();
return { shown, focused, count, none, hidden, calls: window.__calls.filter((c) => c[0].startsWith('find')) };
})()""")
        self.assertTrue(out["shown"])
        self.assertTrue(out["focused"])
        self.assertEqual(out["count"], "2 of 7")
        self.assertEqual(out["none"], "no matches")
        self.assertTrue(out["hidden"])
        self.assertEqual(out["calls"], [["findQuery", "asyncio"], ["findNext"], ["findPrev"], ["findNext"], ["findPrev"], ["findClose"], ["findClose"]])

    @pending("M9-D1")
    def test_bar_is_hidden_by_default_and_reopen_selects_the_text(self):
        out = self._page("0", """(() => {
const hidden = getComputedStyle(document.querySelector('#find-bar')).display === 'none';
window.__handlers.findOpen(); const t = document.querySelector('#find-text'); t.value = 'abc';
t.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
window.__handlers.findOpen();
return { hidden, selected: t.selectionStart === 0 && t.selectionEnd === 3 };
})()""")
        self.assertEqual(out, {"hidden": True, "selected": True})


class FindMainTests(unittest.TestCase):
    """M9-D2"""

    @pending("M9-D2")
    def test_menu_handlers_and_tab_switch_close(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        preload = (REPO / "preload.js").read_text(encoding="utf-8")
        self.assertIn("label: 'Find…'", main)
        self.assertIn("accelerator: 'CmdOrCtrl+F'", main[main.index("label: 'Find…'"):][:300])
        for handler in ("find:query", "find:next", "find:prev", "find:close"):
            self.assertIn("ipcMain.handle('%s'" % handler, main, handler)
        self.assertIn("findInPage(", main)
        self.assertIn("'found-in-page'", main)
        self.assertIn("stopFindInPage('clearSelection')", main)
        self.assertIn("find:result", main)
        self.assertIn("find:open", main)
        for name in ("onFindOpen", "onFindResult", "findQuery", "findNext", "findPrev", "findClose"):
            self.assertIn(name, preload, name)
        switch = main[main.index("ipcMain.handle('tabs:switch'"):][:600]
        self.assertIn("find", switch.lower(), "switching tabs closes the find")


if __name__ == "__main__":
    unittest.main()
