"""Shared helpers for the Milestone 11 (browser track II) tests. Spec: docs/milestones/M11_browser_track.md.

Not a test module. `pending(item)` = unittest.expectedFailure until the item is implemented
(remove the decorator to activate the test). `M11_IMPLEMENTED` is keyed on bridge/location.js.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import REPO, ITER_SRC, NODE, node, run_playwright, playwright_available  # noqa: E402,F401
from m9_support import toolbar_page_script  # noqa: E402,F401

BRIDGE = REPO / "bridge"
M11_IMPLEMENTED = (BRIDGE / "location.js").exists()


def pending(item):
    assert item.startswith("M11-"), item
    return unittest.expectedFailure


def require_m11():
    if not M11_IMPLEMENTED:
        raise AssertionError("Milestone 11 not implemented: bridge/location.js is missing")


def bridge_json(module, script):
    """Run `script` in node with `const M = require(bridge/<module>.js)`; return the last stdout line as JSON."""
    code, stdout, stderr = node("const M = require(%s);\n%s" % (json.dumps(str(BRIDGE / module)), script))
    assert code == 0, stderr
    return json.loads(stdout.strip().splitlines()[-1])


def main_js():
    return (REPO / "main.js").read_text(encoding="utf-8")


def preload_js():
    return (REPO / "preload.js").read_text(encoding="utf-8")


def section(text, marker, before=0, after=1500):
    """Slice of `text` around the first occurrence of `marker` (fails clearly when absent)."""
    assert marker in text, marker
    index = text.index(marker)
    return text[max(0, index - before):index + after]


# The toolbar stub for M11: the M9 API plus bookmark / history / reader handlers.
TOOLBAR_API = ("{onTabsUpdate:(cb)=>{window.__handlers.tabs=cb;},"
               "listTabs:()=>Promise.resolve([{id:1,active:true,url:'https://a.test/',canGoBack:false,canGoForward:false,locked:false}]),"
               "onFindOpen:(cb)=>{window.__handlers.findOpen=cb;},onFindResult:(cb)=>{window.__handlers.findResult=cb;},"
               "onAllySuggest:(cb)=>{window.__handlers.allySuggest=cb;},onCompassState:(cb)=>{window.__handlers.compass=cb;},"
               "onBookmarkState:(cb)=>{window.__handlers.bookmark=cb;},"
               "onHistoryOpen:(cb)=>{window.__handlers.historyOpen=cb;},"
               "historySearch:(q)=>{window.__calls.push(['historySearch',q]);return Promise.resolve(window.__historyResults||[]);},"
               "onReaderNotice:(cb)=>{window.__handlers.readerNotice=cb;}}")


def toolbar(setup, probe):
    return json.loads(run_playwright(toolbar_page_script(setup, probe, TOOLBAR_API)).strip().splitlines()[-1])


def page_script_eval(html, script_expr, probe_js, wait_ms=200):
    """Playwright: a static page from `html`; evaluate the bridge script expression (a JS string read
    from bridge/reader.js via node) then print the probe."""
    return """
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1000, "height": 800})
    pg.set_content(%s); pg.wait_for_timeout(%d)
    pg.evaluate("window.__out = " + %s)
    print(json.dumps(pg.evaluate(%s))); b.close()
""" % (json.dumps(html), wait_ms, json.dumps(script_expr), json.dumps(probe_js))


def reader_script(name):
    """The page-script string exported by bridge/reader.js (READER_SCRIPT or PIP_SCRIPT)."""
    return bridge_json("reader.js", "process.stdout.write(JSON.stringify(M.%s));" % name)


ARTICLE_HTML = """<!doctype html><html><head><title>Why the sky is blue — Example Journal</title>
<script>window.__tracked = 1;</script><style>body{color:red}</style></head><body>
<nav><a href="/">Home</a> <a href="/about">About us</a> <a href="/subscribe">Subscribe now</a></nav>
<aside>Trending: ten things you will not believe. Sign up for the newsletter today.</aside>
<main>
<article>
<h1>Why the sky is blue</h1>
<p class="byline">By Ada Example</p>
<p>%s</p>
<p>Rayleigh scattering is stronger at shorter wavelengths, so blue light is scattered more than red light. <a href="https://example.org/rayleigh" onclick="steal()">Read the derivation</a> or <a href="javascript:alert(1)">this</a>.</p>
<img src="https://example.org/sky.jpg" alt="A blue sky" onerror="steal()" style="width:1px">
<p style="color:green" onmouseover="steal()">%s</p>
<script>steal();</script>
<form><input name="email"><button>Subscribe</button></form>
</article>
</main>
<footer>Copyright Example Journal. Terms. Privacy. Careers. Do not sell my data.</footer>
</body></html>""" % ("Sunlight reaches the atmosphere and is scattered by molecules of air. " * 8,
                     "At sunset the light travels through more air, and the blues are scattered away before they reach you. " * 6)
