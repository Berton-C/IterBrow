#!/usr/bin/env python3
"""M11-B1..B3: bookmarks — the pure list logic, the menu / IPC / file in main.js, and the toolbar star.

Spec: docs/milestones/M11_browser_track.md section B.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m11_support import (pending, require_m11, bridge_json, main_js, preload_js, section, toolbar, playwright_available,  # noqa: E402
                         NODE, REPO)


@unittest.skipUnless(NODE, "needs node")
class PureBookmarkTests(unittest.TestCase):
    """M11-B1"""

    @pending("M11-B1")
    def test_add_remove_toggle_unique_newest_first(self):
        require_m11()
        out = bridge_json("bookmarks.js", """
let list = [];
list = M.add(list, { url: 'https://a.test/one', title: 'One', at: 1 });
list = M.add(list, { url: 'https://b.test/two#frag', title: 'Two', at: 2 });
list = M.add(list, { url: 'https://a.test/one', title: 'One again', at: 3 });
const unchanged = M.add(list, { url: 'about:blank', title: 'x', at: 4 }) === list && M.add(list, { url: 'data:text/html,hi', title: 'x', at: 4 }) === list;
const fileOk = M.add(list, { url: 'file:///Users/x/app/index.html', title: 'App', at: 5 }).length === 3;
const t1 = M.toggle(list, { url: 'https://b.test/two', title: 'Two', at: 6 });
const t2 = M.toggle(t1.list, { url: 'https://c.test/', title: 'C', at: 7 });
process.stdout.write(JSON.stringify({ list, unchanged, fileOk,
  isA: M.isBookmarked(list, 'https://a.test/one#top'), isB: M.isBookmarked(list, 'https://b.test/two'), isC: M.isBookmarked(list, 'https://c.test/'),
  removed: M.remove(list, 'https://a.test/one'), t1, t2: { bookmarked: t2.bookmarked, n: t2.list.length, first: t2.list[0].url },
  norm: [M.normalizeUrl('  https://x.test/p#frag '), M.normalizeUrl('https://x.test/p?q=1')] }));""")
        self.assertEqual([b["url"] for b in out["list"]], ["https://a.test/one", "https://b.test/two"])
        self.assertEqual(out["list"][0], {"url": "https://a.test/one", "title": "One again", "addedAt": 3})
        self.assertTrue(out["unchanged"])
        self.assertTrue(out["fileOk"])
        self.assertEqual([out["isA"], out["isB"], out["isC"]], [True, True, False])
        self.assertEqual([b["url"] for b in out["removed"]], ["https://b.test/two"])
        self.assertEqual(out["t1"]["bookmarked"], False)
        self.assertEqual([b["url"] for b in out["t1"]["list"]], ["https://a.test/one"])
        self.assertEqual(out["t2"], {"bookmarked": True, "n": 2, "first": "https://c.test/"})
        self.assertEqual(out["norm"], ["https://x.test/p", "https://x.test/p?q=1"])

    @pending("M11-B1")
    def test_search_matches_every_word_in_title_or_url(self):
        out = bridge_json("bookmarks.js", """
const list = [ { url: 'https://docs.python.org/3/library/asyncio.html', title: 'asyncio — Asynchronous I/O', addedAt: 3 },
  { url: 'https://news.ycombinator.com/', title: 'Hacker News', addedAt: 2 }, { url: 'https://python.org/', title: 'Welcome to Python', addedAt: 1 } ];
process.stdout.write(JSON.stringify([ M.search(list, 'python').map((b) => b.url), M.search(list, 'PYTHON async').map((b) => b.url),
  M.search(list, 'hacker').map((b) => b.url), M.search(list, 'nothing here'), M.search(list, '', 2).map((b) => b.url) ]));""")
        self.assertEqual(out, [["https://docs.python.org/3/library/asyncio.html", "https://python.org/"],
                               ["https://docs.python.org/3/library/asyncio.html"], ["https://news.ycombinator.com/"], [],
                               ["https://docs.python.org/3/library/asyncio.html", "https://news.ycombinator.com/"]])


class WiringTests(unittest.TestCase):
    """M11-B2"""

    @pending("M11-B2")
    def test_main_menu_ipc_and_file(self):
        main = main_js()
        self.assertIn("require('./bridge/bookmarks')", main)
        self.assertIn("'.runtime', 'bookmarks.json'", main)
        menu = section(main, "label: 'Bookmarks'", after=2500)
        self.assertIn("'CmdOrCtrl+D'", menu)
        self.assertIn("Remove Bookmark", menu)
        self.assertIn("(No bookmarks)", menu)
        for channel in ("ipcMain.handle('bookmarks:list'", "ipcMain.handle('bookmarks:toggle'", "ipcMain.handle('bookmarks:open'", "'bookmarks:state'"):
            self.assertIn(channel, main, channel)
        preload = preload_js()
        for name in ("bookmarkToggle", "onBookmarkState", "bookmarks"):
            self.assertIn(name, preload, name)
        manifest = json.loads((REPO / "iter" / "state_manifest.json").read_text(encoding="utf-8"))
        entry = next((e for e in manifest["entries"] if e["path"] == ".runtime/bookmarks.json"), None)
        self.assertEqual(entry and (entry["portable"], entry["reset"]), (True, False))


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class ToolbarStarTests(unittest.TestCase):
    """M11-B3"""

    @pending("M11-B3")
    def test_star_reflects_state_and_toggles_the_active_tab(self):
        require_m11()
        out = toolbar("0", """(() => {
const star = document.querySelector('#btn-bookmark');
const offTitle = star.title, offText = star.textContent;
window.__handlers.bookmark({ bookmarked: true });
const onClass = star.classList.contains('on'), onTitle = star.title, onText = star.textContent;
star.click();
window.__handlers.bookmark({ bookmarked: false });
window.__handlers.tabs([{ id: 2, active: true, url: 'about:blank', canGoBack: false, canGoForward: false, locked: false }]);
const disabledOnBlank = star.disabled;
window.__handlers.tabs([{ id: 3, active: true, url: 'https://b.test/', canGoBack: false, canGoForward: false, locked: true }]);
star.click();
return { offTitle, offText, onClass, onTitle, onText, disabledOnBlank, enabledOnLocked: !star.disabled,
         calls: window.__calls.filter((c) => c[0] === 'bookmarkToggle') };
})()""")
        self.assertEqual(out["offText"], "☆")
        self.assertEqual(out["offTitle"], "Bookmark this tab")
        self.assertTrue(out["onClass"])
        self.assertEqual(out["onText"], "★")
        self.assertEqual(out["onTitle"], "Bookmarked — click to remove")
        self.assertTrue(out["disabledOnBlank"])
        self.assertTrue(out["enabledOnLocked"], "the person may bookmark a locked tab")
        self.assertEqual(out["calls"], [["bookmarkToggle", 1], ["bookmarkToggle", 3]])


if __name__ == "__main__":
    unittest.main()
