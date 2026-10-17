#!/usr/bin/env python3
"""M11-C1..C3: browsing history and its search — the pure list logic, the recording rule and switch
in main.js, and the toolbar history bar.

Spec: docs/milestones/M11_browser_track.md section C.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m11_support import (pending, require_m11, bridge_json, main_js, preload_js, section, toolbar, playwright_available,  # noqa: E402
                         NODE, REPO)


@unittest.skipUnless(NODE, "needs node")
class PureHistoryTests(unittest.TestCase):
    """M11-C1"""

    def test_should_record_is_the_ally_rule(self):
        require_m11()
        out = bridge_json("history.js", """process.stdout.write(JSON.stringify([
  M.shouldRecord({ url: 'https://a.test/', locked: false, appScope: null }, true),
  M.shouldRecord({ url: 'https://a.test/', locked: true, appScope: null }, true),
  M.shouldRecord({ url: 'file:///x/index.html', locked: false, appScope: { appId: 'crm' } }, true),
  M.shouldRecord({ url: 'https://a.test/', locked: false, appScope: null }, false),
  M.shouldRecord({ url: 'file:///x.html', locked: false, appScope: null }, true),
  M.shouldRecord({ url: 'data:text/html,hi', locked: false, appScope: null }, true),
  M.shouldRecord({ url: 'about:blank', locked: false, appScope: null }, true) ]));""")
        self.assertEqual(out, [True, False, False, False, False, False, False])

    def test_append_coalesces_and_caps(self):
        out = bridge_json("history.js", """
let lines = [];
lines = M.append(lines, { at: 1000, url: 'https://a.test/', title: '' });
lines = M.append(lines, { at: 3000, url: 'https://a.test/', title: 'A' });      // same URL within 5 s: replaces
lines = M.append(lines, { at: 9000, url: 'https://a.test/', title: 'A' });      // later: a new visit
lines = M.append(lines, { at: 9500, url: 'https://b.test/', title: 'B' });
const titled = M.titled(lines, 'https://a.test/', 'A — the page');
let capped = [];
for (let i = 0; i < 12; i++) capped = M.append(capped, { at: 100000 + i * 10000, url: 'https://n.test/' + i, title: String(i) }, 10);
process.stdout.write(JSON.stringify({ lines, titled, capped: capped.map((l) => l.url) }));""")
        self.assertEqual(out["lines"], [{"at": 3000, "url": "https://a.test/", "title": "A"}, {"at": 9000, "url": "https://a.test/", "title": "A"},
                                        {"at": 9500, "url": "https://b.test/", "title": "B"}])
        self.assertEqual([l["title"] for l in out["titled"]], ["A", "A — the page", "B"], "only the latest line for the URL is retitled")
        self.assertEqual(out["capped"], ["https://n.test/%d" % i for i in range(2, 12)])

    def test_search_newest_first_unique_by_url_with_visits(self):
        out = bridge_json("history.js", """
const lines = [ { at: 1, url: 'https://docs.python.org/3/library/asyncio.html', title: 'asyncio' },
  { at: 2, url: 'https://news.ycombinator.com/', title: 'Hacker News' },
  { at: 3, url: 'https://docs.python.org/3/library/asyncio.html', title: 'asyncio — Asynchronous I/O' },
  { at: 4, url: 'https://python.org/', title: 'Welcome to Python' } ];
process.stdout.write(JSON.stringify([ M.search(lines, 'python'), M.search(lines, 'ASYNC io'), M.search(lines, 'zzz'), M.search(lines, '', 2).map((r) => r.url) ]));""")
        self.assertEqual(out[0], [{"url": "https://python.org/", "title": "Welcome to Python", "at": 4, "visits": 1},
                                  {"url": "https://docs.python.org/3/library/asyncio.html", "title": "asyncio — Asynchronous I/O", "at": 3, "visits": 2}])
        self.assertEqual([r["url"] for r in out[1]], ["https://docs.python.org/3/library/asyncio.html"])
        self.assertEqual(out[2], [])
        self.assertEqual(out[3], ["https://python.org/", "https://docs.python.org/3/library/asyncio.html"])


class WiringTests(unittest.TestCase):
    """M11-C2"""

    def test_main_records_only_by_the_rule_and_the_switch_leaves_no_trace(self):
        main = main_js()
        self.assertIn("require('./bridge/history')", main)
        self.assertIn("'.runtime', 'history.jsonl'", main)
        record = section(main, "shouldRecord(", before=1200, after=1200)
        self.assertIn("keepHistory", record)
        self.assertIn("did-navigate", record)
        settings = section(main, "function loadSettings", after=1200)
        self.assertIn("keepHistory: true", settings, "default on")
        save = section(main, "ipcMain.handle('settings:save'", after=1200)
        self.assertIn("keepHistory", save)
        self.assertIn("history.jsonl", save, "switching history off deletes the file")
        menu = section(main, "label: 'Search History", after=800)
        self.assertIn("'CmdOrCtrl+Y'", menu)
        self.assertIn("label: 'Clear History'", main)
        for channel in ("ipcMain.handle('history:search'", "ipcMain.handle('history:openUrl'", "ipcMain.handle('history:clear'", "'history:open'"):
            self.assertIn(channel, main, channel)
        preload = preload_js()
        for name in ("historySearch", "historyOpen", "onHistoryOpen"):
            self.assertIn(name, preload, name)
        manifest = json.loads((REPO / "iter" / "state_manifest.json").read_text(encoding="utf-8"))
        entry = next((e for e in manifest["entries"] if e["path"] == ".runtime/history.jsonl"), None)
        self.assertEqual(entry and (entry["portable"], entry["reset"]), (True, False))
        index = (REPO / "renderer" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="setting-history"', index)
        self.assertIn("never locked tabs", index)
        renderer = (REPO / "renderer" / "renderer.js").read_text(encoding="utf-8")
        self.assertIn("keepHistory", renderer)


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class HistoryBarTests(unittest.TestCase):
    """M11-C3"""

    def test_bar_searches_navigates_opens_and_closes(self):
        require_m11()
        out = toolbar("0", """(async () => {
const bar = document.querySelector('#history-bar'), text = document.querySelector('#history-text');
const hidden = getComputedStyle(bar).display === 'none';
window.__historyResults = [ { url: 'https://docs.python.org/3/library/asyncio.html', title: 'asyncio', at: 3, visits: 2 },
                            { url: 'https://python.org/', title: 'Welcome to Python', at: 4, visits: 1 } ];
window.__handlers.historyOpen();
const shown = getComputedStyle(bar).display !== 'none', focused = document.activeElement === text;
text.value = 'python'; text.dispatchEvent(new Event('input', { bubbles: true }));
await new Promise((r) => setTimeout(r, 300));
const items = [...document.querySelectorAll('#history-results li')].map((li) => li.textContent);
text.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
text.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
const closedAfterEnter = getComputedStyle(bar).display === 'none';
window.__handlers.historyOpen();
document.querySelectorAll('#history-results li')[0] && document.querySelectorAll('#history-results li')[0].click();
window.__handlers.historyOpen();
window.__handlers.findOpen();
const closedByFind = getComputedStyle(bar).display === 'none';
window.__handlers.historyOpen();
const findClosedByHistory = getComputedStyle(document.querySelector('#find-bar')).display === 'none';
text.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
const closedByEscape = getComputedStyle(bar).display === 'none';
return { hidden, shown, focused, items, closedAfterEnter, closedByFind, findClosedByHistory, closedByEscape,
         calls: window.__calls.filter((c) => c[0].startsWith('history')) };
})()""")
        self.assertTrue(out["hidden"])
        self.assertTrue(out["shown"])
        self.assertTrue(out["focused"])
        self.assertEqual(len(out["items"]), 2)
        self.assertIn("asyncio", out["items"][0])
        self.assertIn("docs.python.org", out["items"][0])
        self.assertTrue(out["closedAfterEnter"])
        self.assertTrue(out["closedByFind"])
        self.assertTrue(out["findClosedByHistory"])
        self.assertTrue(out["closedByEscape"])
        self.assertEqual(out["calls"][0], ["historySearch", "python"])
        opens = [c for c in out["calls"] if c[0] == "historyOpen"]
        self.assertEqual(opens[0], ["historyOpen", "https://python.org/"], "ArrowDown moved to the second result")
        self.assertEqual(opens[1], ["historyOpen", "https://docs.python.org/3/library/asyncio.html"], "a click opens that result")


if __name__ == "__main__":
    unittest.main()
