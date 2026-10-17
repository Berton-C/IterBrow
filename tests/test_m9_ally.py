#!/usr/bin/env python3
"""M9-C1..C5: the browsing ally (off by default) — lock suggestions, the browsing log and block,
the compass, and the toolbar notice.

Spec: docs/milestones/M9_soul_wonder_ally.md section C.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m9_support import (pending, m9_root, require_m9, write_soul_settings, run_transformation, write_browsing_log,  # noqa: E402
                        now_ms, toolbar_page_script, TOOLBAR_API, run_playwright, playwright_available, NODE, REPO, FEATURES)


def ally(script):
    code, stdout, stderr = __import__("m9_support").node("const A = require(%s);\n%s" % (json.dumps(str(REPO / "bridge" / "browsing_ally.js")), script))
    assert code == 0, stderr
    return json.loads(stdout.strip().splitlines()[-1])


@unittest.skipUnless(NODE, "needs node")
class PureAllyTests(unittest.TestCase):
    """M9-C1"""

    def test_suggest_lock_is_conservative(self):
        require_m9()
        out = ally("""process.stdout.write(JSON.stringify([
  A.suggestLock('https://online.chase.com/login', 'Chase'), A.suggestLock('https://www.mybank.co.uk/accounts', 'My Bank'),
  A.suggestLock('https://mail.google.com/mail/u/0/', 'Inbox'), A.suggestLock('https://outlook.live.com/mail/', 'Mail'),
  A.suggestLock('https://mychart.example.org/', 'MyChart'), A.suggestLock('https://www.irs.gov/account', 'IRS'),
  A.suggestLock('https://www.wikipedia.org/wiki/Bank', 'Bank - Wikipedia'), A.suggestLock('https://news.ycombinator.com/', 'HN'),
  A.suggestLock('http://localhost:8080/bank', 'local'), A.suggestLock('file:///Users/x/bank.html', 'file'),
  A.suggestLock('https://github.com/Berton-C/IterBrow', 'IterBrow'), A.suggestLock('not a url', 'x') ]));""")
        self.assertEqual([x and x["reason"] for x in out[:6]],
                         ["looks like your bank", "looks like your bank", "looks like your mail", "looks like your mail",
                          "looks like a health or government account", "looks like a health or government account"])
        self.assertEqual(out[6:], [None] * 6)

    def test_should_log_only_plain_unlocked_http_tabs_when_on(self):
        out = ally("""process.stdout.write(JSON.stringify([
  A.shouldLog({ url: 'https://a.test/', locked: false, appScope: null }, true),
  A.shouldLog({ url: 'https://a.test/', locked: true, appScope: null }, true),
  A.shouldLog({ url: 'file:///x/index.html', locked: false, appScope: { appId: 'crm' } }, true),
  A.shouldLog({ url: 'https://a.test/', locked: false, appScope: null }, false),
  A.shouldLog({ url: 'file:///x.html', locked: false, appScope: null }, true),
  A.shouldLog({ url: 'about:blank', locked: false, appScope: null }, true) ]));""")
        self.assertEqual(out, [True, False, False, False, False, False])

    def test_compass_state_from_the_journal(self):
        out = ally("""
const card = (id, topic) => ({ role: 'iter', at: 1, card: { id, kind: 'offer', title: 't', choices: [{ id: 'a', label: 'A' }], ...(topic ? { topic } : {}) } });
const pick = (id) => ({ role: 'user', at: 2, content: '[choice ...]', choice: { card: id, pick: 'a', by: 'berton' } });
process.stdout.write(JSON.stringify([
  A.compassState([]), A.compassState([card('c1', 'ally:wonder-time')]), A.compassState([card('c1', 'ally:wonder-time'), pick('c1')]),
  A.compassState([card('c1', 'wonder:x')]), A.compassState([card('c1', 'ally:wonder-shared'), pick('c9')]) ]));""")
        self.assertEqual(out, [{"live": False, "pair": None}, {"live": True, "pair": "wonder-time"}, {"live": False, "pair": None},
                               {"live": False, "pair": None}, {"live": True, "pair": "wonder-shared"}])

    def test_recent_browsing_merges_dwell_per_domain_newest_first(self):
        out = ally("""
const now = 1700000000000, m = 60000;
const lines = [ { at: now - 50*m, tab: 1, domain: 'old.test', title: 'too old' },
  { at: now - 20*m, tab: 1, domain: 'docs.python.org', title: 'asyncio' }, { at: now - 14*m, tab: 1, domain: 'docs.python.org', title: 'asyncio streams' },
  { at: now - 9*m, tab: 2, domain: 'news.ycombinator.com', title: 'HN' }, { at: now - 2*m, tab: 1, domain: 'docs.python.org', title: 'asyncio' } ];
process.stdout.write(JSON.stringify(A.recentBrowsing(lines, now)));""")
        self.assertEqual([d["domain"] for d in out], ["docs.python.org", "news.ycombinator.com", "docs.python.org"])
        self.assertEqual(out[0]["minutes"], 2)
        self.assertEqual(out[1]["minutes"], 7)
        self.assertEqual(out[2]["minutes"], 11)
        self.assertEqual(out[2]["title"], "asyncio streams")
        self.assertNotIn("old.test", json.dumps(out))
        # A long stay on one page: the current page always counts, with its full dwell.
        alone = ally("""
const now = 1700000000000, m = 60000;
process.stdout.write(JSON.stringify(A.recentBrowsing([ { at: now - 47*m, tab: 1, domain: 'feed.example', title: 'The feed' } ], now)));""")
        self.assertEqual(alone, [{"domain": "feed.example", "minutes": 47, "title": "The feed"}])


class WiringTests(unittest.TestCase):
    """M9-C2"""

    def test_main_logs_suggests_and_pushes_compass_only_when_on(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        self.assertIn("require('./bridge/browsing_ally')", main)
        self.assertIn("browsing_log.jsonl", main)
        for channel in ("ally:suggest", "ally:lock", "ally:decline", "compass:state"):
            self.assertIn(channel, main, channel)
        log_fn = main[main.index("browsing_log.jsonl") - 2500:main.index("browsing_log.jsonl") + 2500]
        self.assertIn("shouldLog(", log_fn)
        self.assertIn("500", log_fn, "the log is capped")
        save = main[main.index("ipcMain.handle('soul:save'"):][:2000]
        self.assertIn("browsing_log.jsonl", save, "switching the ally off deletes the log")
        lock = main[main.index("ipcMain.handle('ally:lock'"):][:600]
        self.assertIn("setLocked(", lock)
        preload = (REPO / "preload.js").read_text(encoding="utf-8")
        for name in ("onAllySuggest", "allyLock", "allyDecline", "onCompassState"):
            self.assertIn(name, preload, name)


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class ToolbarAllyTests(unittest.TestCase):
    """M9-C3"""

    def _page(self, setup, probe):
        return json.loads(run_playwright(toolbar_page_script(setup, probe, TOOLBAR_API)).strip().splitlines()[-1])

    def test_notice_and_compass(self):
        require_m9()
        out = self._page("""
window.__handlers.allySuggest({ tab: 1, reason: 'looks like your bank', host: 'online.chase.com' });
""", """(() => {
const n = document.querySelector('#ally-notice');
const shownAtFirst = n && getComputedStyle(n).display !== 'none' ? n.textContent : null;
const compassHidden = getComputedStyle(document.querySelector('#compass')).display === 'none';
document.querySelector('#ally-lock').click();
const afterLock = getComputedStyle(n).display;
window.__handlers.allySuggest({ tab: 2, reason: 'looks like your mail', host: 'mail.google.com' });
document.querySelector('#ally-no').click();
window.__handlers.compass({ live: true, pair: 'wonder-time', on: true });
const liveTitle = document.querySelector('#compass').title;
const liveClass = document.querySelector('#compass').classList.contains('live');
window.__handlers.compass({ live: false, pair: null, on: true });
return { shown: shownAtFirst, compassHiddenAtStart: compassHidden,
         afterLock, calls: window.__calls.filter((c) => c[0].startsWith('ally')), liveTitle, liveClass,
         darkClass: document.querySelector('#compass').classList.contains('live'),
         shownNow: getComputedStyle(document.querySelector('#compass')).display !== 'none' };
})()""")
        self.assertIn("looks like your bank", out["shown"])
        self.assertTrue(out["compassHiddenAtStart"], "compass hidden until the feature reports on")
        self.assertEqual(out["afterLock"], "none")
        self.assertEqual(out["calls"], [["allyLock", 1], ["allyDecline", "mail.google.com"]])
        self.assertEqual(out["liveTitle"], "A pair is live — Iter has handed you a choice")
        self.assertTrue(out["liveClass"])
        self.assertFalse(out["darkClass"])
        self.assertTrue(out["shownNow"])


class BrowsingBlockTests(unittest.TestCase):
    """M9-C4"""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="m9browse-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))

    def _block(self, features, **profile):
        write_soul_settings(self.temp, "berton", features, **profile)
        msgs, _ = run_transformation(self.temp, "soul_browsing.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        return msgs[-1]["content"]

    def test_block_lists_recent_domains_and_the_rule(self):
        now = now_ms()
        write_browsing_log(self.temp, [{"at": now - 20 * 60000, "tab": 1, "domain": "docs.python.org", "title": "asyncio"},
                                       {"at": now - 5 * 60000, "tab": 2, "domain": "news.ycombinator.com", "title": "Hacker News"}])
        content = self._block({"browsing_ally": True})
        self.assertIn("## Browsing (ally)", content)
        self.assertIn("news.ycombinator.com · 5 min · Hacker News", content)
        self.assertIn("docs.python.org · 15 min · asyncio", content)
        for word in ("ally:", "wonder-time", "wonder-shared", "hand the choice back", "otherwise say nothing", "30 min"):
            self.assertIn(word, content, word)

    def test_nothing_when_off_quiet_or_empty(self):
        now = now_ms()
        write_browsing_log(self.temp, [{"at": now - 60000, "tab": 1, "domain": "a.test", "title": "A"}])
        self.assertEqual(self._block({"browsing_ally": False}), "base")
        self.assertEqual(self._block({f: False for f in FEATURES}), "base")
        self.assertEqual(self._block({"browsing_ally": True}, mode="quiet"), "base")
        # A long stay on one page is the capture case: the current page counts however old its entry.
        write_browsing_log(self.temp, [{"at": now - 40 * 60000, "tab": 1, "domain": "a.test", "title": "A"}])
        self.assertIn("a.test · 40 min · A", self._block({"browsing_ally": True}))
        (Path(self.temp) / ".runtime" / "browsing_log.jsonl").unlink()
        self.assertEqual(self._block({"browsing_ally": True}), "base", "no log")


if __name__ == "__main__":
    unittest.main()
