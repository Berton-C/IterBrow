#!/usr/bin/env python3
"""M16-A1..A3: a tab pops out into its own window and comes back — the view moves, nothing reloads; the person's
gestures (double-click, menu); Iter can act in a popped tab and sees which window it is in.

Spec: docs/milestones/M16_shell_from_eaos.md section A. The tab manager runs in node with a stub electron and a
fake pop-out window (m16_support.popout_node).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m16_support import pending, require_m16, popout_node, source  # noqa: E402


class MoveTests(unittest.TestCase):
    """M16-A1"""

    def test_pop_out_moves_the_view_and_pop_in_brings_it_back(self):
        out = popout_node("""
const a = tabs.createTab('https://a.example'); const b = tabs.createTab('https://b.example');
tabs.switchTab(b);
const viewB = tabs.tabs.get(b).view; const loadedBefore = viewB.webContents.loaded.length;
const popped = tabs.popOut(b);
out.popped = popped; out.isPopped = tabs.isPopped(b);
out.mainHasB = children.includes(viewB); out.windowHasB = windows[0].contentView.children.includes(viewB);
out.bounds = viewB.bounds; out.shown = windows[0].shown; out.focused = windows[0].focused;
out.activeAfterPop = tabs.activeId; out.windowFor = tabs.windowFor(b) === windows[0];
out.rows = tabs.list().map((t) => [t.id, t.window]);
windows[0].resize(500, 400); out.boundsAfterResize = viewB.bounds;
out.again = tabs.popOut(b); out.focusedAgain = windows[0].focused; out.windowsMade = windows.length;
const back = tabs.popIn(b);
out.back = back; out.destroyed = windows[0].destroyed; out.mainHasBAgain = children.includes(viewB);
out.activeAfterIn = tabs.activeId; out.isPoppedAfter = tabs.isPopped(b); out.windowForMain = tabs.windowFor(b) === win;
out.loaded = viewB.webContents.loaded.length - loadedBefore;
""")
        self.assertEqual(out["popped"], {"id": 2, "window": 100})
        self.assertTrue(out["isPopped"])
        self.assertFalse(out["mainHasB"]); self.assertTrue(out["windowHasB"])
        self.assertEqual(out["bounds"], {"x": 0, "y": 0, "width": 900, "height": 700})
        self.assertEqual((out["shown"], out["focused"]), (1, 1))
        self.assertEqual(out["activeAfterPop"], 1, "the newest remaining strip tab is active")
        self.assertTrue(out["windowFor"])
        self.assertEqual(out["rows"], [[1, "main"], [2, 100]])
        self.assertEqual(out["boundsAfterResize"], {"x": 0, "y": 0, "width": 500, "height": 400})
        self.assertEqual(out["again"], {"id": 2, "window": 100}); self.assertEqual(out["focusedAgain"], 2); self.assertEqual(out["windowsMade"], 1)
        self.assertEqual(out["back"], {"id": 2, "window": "main"})
        self.assertTrue(out["destroyed"]); self.assertTrue(out["mainHasBAgain"])
        self.assertEqual(out["activeAfterIn"], 2, "a tab that comes back is the active tab")
        self.assertFalse(out["isPoppedAfter"]); self.assertTrue(out["windowForMain"])
        self.assertEqual(out["loaded"], 0, "nothing reloads")

    def test_closing_the_window_returns_the_tab_and_closing_the_tab_closes_the_window(self):
        out = popout_node("""
const a = tabs.createTab('https://a.example'); const b = tabs.createTab('https://b.example'); const c = tabs.createTab('https://c.example');
tabs.setLocked(b, true); tabs.setPinned(b, true);
tabs.popOut(b);
windows[0].close();  // the person closes the window
out.backInStrip = children.includes(tabs.tabs.get(b).view) && !tabs.isPopped(b) && tabs.tabs.has(b);
out.lockedPinned = [tabs.isLocked(b), tabs.isPinned(b)];
tabs.popOut(c);
out.closed = tabs.closeTab(c);
out.windowClosed = windows[1].destroyed; out.cGone = !tabs.tabs.has(c); out.count = tabs.list().length;
""")
        self.assertTrue(out["backInStrip"])
        self.assertEqual(out["lockedPinned"], [True, True])
        self.assertTrue(out["closed"]); self.assertTrue(out["windowClosed"]); self.assertTrue(out["cGone"]); self.assertEqual(out["count"], 2)

    def test_main_js_makes_a_bare_window_and_closes_pop_outs_at_quit(self):
        require_m16()
        main = source("main.js")
        self.assertIn("function makePopoutWindow", main)
        block = main[main.index("function makePopoutWindow"):main.index("function makePopoutWindow") + 1500]
        self.assertIn("BaseWindow", block)
        self.assertIn("setMenuBarVisibility(false)", block)
        self.assertRegex(block, r"IterBrow — ")
        self.assertRegex(block, r"1100|work\.width")
        self.assertIn("tabs.makePopoutWindow = makePopoutWindow", main)
        self.assertIn("tabs:popOut", main); self.assertIn("tabs:popIn", main)
        self.assertRegex(main, r"popout[^\n]*(destroy|close)\(\)", "quit closes the pop-outs")


class GestureTests(unittest.TestCase):
    """M16-A2"""

    def test_double_click_and_the_popped_pill(self):
        require_m16()
        strip = source("renderer/tabstrip.js")
        self.assertIn("'dblclick'", strip)
        self.assertRegex(strip, r"popOutTab|popInTab")
        self.assertIn("⧉", strip)
        self.assertIn("double-click to bring it back", strip)
        self.assertRegex(strip, r"e\.detail === 2|detail > 1", "the second click of a double does not switch")
        preload = source("preload.js")
        self.assertIn("popOutTab", preload); self.assertIn("popInTab", preload)

    def test_menu_items(self):
        require_m16()
        main = source("main.js")
        self.assertIn("Open in its own window", main)
        self.assertIn("Return to the tab strip", main)
        self.assertIn("CmdOrCtrl+Shift+P", main)
        self.assertIn("CmdOrCtrl+Shift+P", main[main.index("Tabs"):] if "Tabs" in main else "")


class IterTests(unittest.TestCase):
    """M16-A3"""

    def test_a_popped_tab_is_displayed_for_iter_and_listed_with_its_window(self):
        out = popout_node("""
const a = tabs.createTab('https://a.example'); const b = tabs.createTab('https://b.example');
tabs.popOut(b);
try { tabs._displayed(tabs.tabs.get(b)); out.displayed = true; } catch (e) { out.displayed = e.message; }
out.switched = tabs.switchTab(b); out.stillPopped = tabs.isPopped(b); out.focused = windows[0].focused;
out.mainActive = tabs.activeId;
out.list = tabs.list().map((t) => ({ id: t.id, window: t.window, active: t.active }));
tabs.relayout(); out.boundsKept = tabs.tabs.get(b).view.bounds.width === 900;
tabs.setLocked(b, true); out.locked = tabs.isLocked(b);
""")
        self.assertIs(out["displayed"], True)
        self.assertTrue(out["stillPopped"], "switchTab focuses the window, never moves the view back")
        self.assertGreaterEqual(out["focused"], 2)
        self.assertEqual(out["mainActive"], 1, "the strip keeps its own active tab")
        self.assertEqual(out["list"][1]["window"], 100)
        self.assertTrue(out["boundsKept"], "relayout leaves popped views alone")
        self.assertTrue(out["locked"])

    def test_browser_tabs_names_the_window(self):
        require_m16()
        server = source("bridge/browser_bridge_server.js")
        self.assertIn("window", server[server.index("async getTabs"):server.index("async getTabs") + 400] + source("bridge/tab_manager.js"))
        tool = source("iter/tools/browser_tabs.py")
        self.assertIn("window=", tool)


if __name__ == "__main__":
    unittest.main()
