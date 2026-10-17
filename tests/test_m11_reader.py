#!/usr/bin/env python3
"""M11-D1..D3: reader mode and picture-in-picture — the page scripts, the reader document, the wiring.

Spec: docs/milestones/M11_browser_track.md section D.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m11_support import (pending, require_m11, bridge_json, main_js, section, toolbar, run_playwright, playwright_available,  # noqa: E402
                         page_script_eval, reader_script, ARTICLE_HTML, NODE, REPO)


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class ReaderScriptTests(unittest.TestCase):
    """M11-D1 (extraction)"""

    def _run(self, html, name, probe="window.__out"):
        return json.loads(run_playwright(page_script_eval(html, reader_script(name), probe)).strip().splitlines()[-1])

    def test_extracts_the_article_and_strips_everything_live(self):
        require_m11()
        out = self._run(ARTICLE_HTML, "READER_SCRIPT")
        self.assertEqual(out["title"], "Why the sky is blue — Example Journal")
        self.assertEqual(out["byline"], "By Ada Example")
        self.assertGreaterEqual(out["textLength"], 400)
        html = out["html"]
        self.assertIn("Rayleigh scattering", html)
        self.assertIn("blues are scattered away", html)
        for gone in ("Subscribe now", "Trending", "Copyright Example Journal", "<script", "<form", "<input", "<button", "<style",
                     "onclick", "onerror", "onmouseover", "style=", "javascript:", "steal("):
            self.assertNotIn(gone, html, gone)
        self.assertIn('href="https://example.org/rayleigh"', html)
        self.assertIn('src="https://example.org/sky.jpg"', html)
        self.assertIn('alt="A blue sky"', html)

    def test_short_pages_yield_no_article(self):
        out = self._run("<html><head><title>Tiny</title></head><body><div><p>Hello.</p></div></body></html>", "READER_SCRIPT")
        self.assertEqual(out, {"title": "Tiny", "html": "", "textLength": 0, "byline": ""})

    def test_largest_text_block_without_article_tags(self):
        body = "".join("<div class='x'><a href='/l%d'>link</a></div>" % i for i in range(20))
        body += "<div id='story'>%s</div>" % ("<p>The story goes on and on with plenty of words to read. </p>" * 20)
        out = self._run("<html><head><title>Blocks</title></head><body>%s</body></html>" % body, "READER_SCRIPT")
        self.assertIn("The story goes on", out["html"])
        self.assertNotIn("/l3", out["html"])


@unittest.skipUnless(NODE, "needs node")
class ReaderDocumentTests(unittest.TestCase):
    """M11-D1 (document)"""

    def test_render_reader_escapes_and_wraps(self):
        require_m11()
        out = bridge_json("reader.js", """process.stdout.write(JSON.stringify(M.renderReader({
  title: 'Sky <b>& "blue"</b>', byline: 'By <Ada>', url: 'https://example.org/sky?a=1&b=2',
  html: '<p>Body <a href="https://example.org/x">x</a></p>' })));""")
        self.assertIn('<meta charset="utf-8">', out)
        self.assertIn("Sky &lt;b&gt;&amp; &quot;blue&quot;&lt;/b&gt;", out)
        self.assertIn("By &lt;Ada&gt;", out)
        self.assertIn('href="https://example.org/sky?a=1&amp;b=2"', out)
        self.assertIn('<p>Body <a href="https://example.org/x">x</a></p>', out)
        self.assertNotIn("<script", out)
        self.assertIn("prefers-color-scheme", out)
        self.assertIn("68ch", out)


class WiringTests(unittest.TestCase):
    """M11-D2 / M11-D3 (main.js)"""

    def test_reader_menu_button_and_data_url(self):
        main = main_js()
        self.assertIn("require('./bridge/reader')", main)
        menu = section(main, "label: 'Reader Mode'", after=800)
        self.assertIn("'Shift+CmdOrCtrl+R'", menu)
        reader = section(main, "READER_SCRIPT", before=200, after=2000)
        self.assertIn("executeJavaScript(", reader)
        self.assertIn("renderReader(", reader)
        self.assertIn("data:text/html;charset=utf-8,", reader)
        self.assertIn("encodeURIComponent(", reader)
        self.assertIn("No article found on this page", main)
        self.assertIn("ipcMain.handle('reader:open'", main)
        preload = (REPO / "preload.js").read_text(encoding="utf-8")
        for name in ("readerOpen", "onReaderNotice"):
            self.assertIn(name, preload, name)

    def test_pip_menu_runs_with_a_user_gesture(self):
        main = main_js()
        menu = section(main, "label: 'Picture in Picture'", after=1200)
        self.assertIn("'Shift+CmdOrCtrl+P'", menu)
        self.assertIn("PIP_SCRIPT", menu)
        self.assertRegex(menu, r"executeJavaScript\(\s*reader\.PIP_SCRIPT\s*,\s*true\s*\)|executeJavaScript\(PIP_SCRIPT,\s*true\)")
        self.assertIn("No video on this page", main)


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class PipScriptTests(unittest.TestCase):
    """M11-D3 (page script)"""

    def test_pip_picks_the_largest_video_and_reports_none(self):
        require_m11()
        html = """<html><body>
<video id="small" width="100" height="60"></video><video id="big" width="640" height="360"></video>
<script>window.__pip = [];
for (const v of document.querySelectorAll('video')) v.requestPictureInPicture = function () { window.__pip.push(this.id); return Promise.resolve({}); };
</script></body></html>"""
        script = page_script_eval(html, reader_script("PIP_SCRIPT"), "(async () => ({ result: await window.__out, picked: window.__pip }))()")
        out = json.loads(run_playwright(script).strip().splitlines()[-1])
        self.assertEqual(out["picked"], ["big"])
        self.assertTrue(out["result"]["ok"])
        none = json.loads(run_playwright(page_script_eval("<html><body><p>no video</p></body></html>", reader_script("PIP_SCRIPT"),
                                                          "(async () => await window.__out)()")).strip().splitlines()[-1])
        self.assertEqual(none, {"ok": False, "reason": "no-video"})


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class ToolbarReaderTests(unittest.TestCase):
    """M11-D2 (toolbar)"""

    def test_reader_button_enabled_only_on_web_pages_and_notice_hides_itself(self):
        require_m11()
        out = toolbar("0", """(async () => {
const btn = document.querySelector('#btn-reader');
const onHttps = !btn.disabled;
btn.click();
window.__handlers.tabs([{ id: 2, active: true, url: 'data:text/html;charset=utf-8,x', canGoBack: true, canGoForward: false, locked: false }]);
const onData = !btn.disabled;
window.__handlers.tabs([{ id: 3, active: true, url: 'https://b.test/', canGoBack: false, canGoForward: false, locked: true }]);
const onLocked = !btn.disabled;
window.__handlers.readerNotice({ text: 'No article found on this page' });
const n = document.querySelector('#reader-notice');
const shown = getComputedStyle(n).display !== 'none' && n.textContent.includes('No article');
await new Promise((r) => setTimeout(r, 4300));
const hiddenLater = getComputedStyle(n).display === 'none';
return { onHttps, onData, onLocked, shown, hiddenLater, calls: window.__calls.filter((c) => c[0] === 'readerOpen') };
})()""")
        self.assertTrue(out["onHttps"])
        self.assertFalse(out["onData"])
        self.assertTrue(out["onLocked"], "the reader is the person's click")
        self.assertTrue(out["shown"])
        self.assertTrue(out["hiddenLater"])
        self.assertEqual(out["calls"], [["readerOpen", 1]])


if __name__ == "__main__":
    unittest.main()
