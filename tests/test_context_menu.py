#!/usr/bin/env python3
"""Right-click (two-finger click) context menus with spelling suggestions, everywhere.

Electron's spellchecker underlines misspellings on its own; the menu that offers
the corrections only exists if a 'context-menu' handler is attached. These tests
pin the menu contents (node, no Electron) and the wiring into every surface.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "needs node")
class ContextMenuTests(unittest.TestCase):
    def test_menu_template_contract(self):
        result = subprocess.run([NODE, str(ROOT / "tests" / "node" / "context_menu_test.js")],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("context_menu_test: ok", result.stdout)

    def test_every_surface_gets_the_menu(self):
        main = (ROOT / "main.js").read_text(encoding="utf-8")
        tabs = (ROOT / "bridge" / "tab_manager.js").read_text(encoding="utf-8")
        # The three UI views share pinUiViewToItsPage, which attaches the menu once for all of them.
        pin = main[main.index("function pinUiViewToItsPage"):main.index("async function recoverRevisionBeforeStart")]
        self.assertIn("contextMenu.attach(contents", pin)
        for name in ("sidebarView", "toolbarView", "tabstripView"):
            self.assertIn("pinUiViewToItsPage(%s" % name, main)
        # Every browser tab: TabManager calls the hook on creation; main.js installs it with navigation actions.
        self.assertIn("if (this.onTabCreated) this.onTabCreated(view.webContents, tab);", tabs)
        self.assertLess(tabs.index("this.tabs.set(id, tab);"), tabs.index("this.onTabCreated(view.webContents, tab)"))
        hook = main[main.index("tabs.onTabCreated = (contents, tab) => contextMenu.attach(contents"):]
        for action in ("openLinkInNewTab", "searchSelection", "back:", "forward:", "reload:"):
            self.assertIn(action, hook[:900], action)

    def test_spellcheck_is_not_disabled_anywhere(self):
        for rel in ("main.js", "bridge/tab_manager.js"):
            source = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("spellcheck: false", source, rel)

    def test_menu_opens_at_the_cursor_not_at_view_coordinates(self):
        source = (ROOT / "bridge" / "context_menu.js").read_text(encoding="utf-8")
        attach = source[source.index("function attach("):]
        self.assertNotIn("x: params.x", attach, "view-relative x/y would misplace the menu in an offset view")
        self.assertIn("event.preventDefault()", attach)


if __name__ == "__main__":
    unittest.main()
