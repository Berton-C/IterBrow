#!/usr/bin/env python3
"""M10-A1..A5: the ally SDK — install and lens, cards, calibration, the optional model, the kernel export.

Spec: docs/milestones/M10_ally_sdk.md section A. The SDK is exercised in a real Chromium page with
fetch stubbed; the kernel JSON is compared with a fresh export from the running service.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m10_support import (pending, m10_root, require_m10, run_sdk, kernel_json, KERNEL_JSON, SDK, BRIEF, PATTERNS, PAIRS,  # noqa: E402
                         playwright_available, NODE, REPO, ITER_SRC)

PW = unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")


@PW
class InstallAndLensTests(unittest.TestCase):
    """M10-A1"""

    @pending("M10-A1")
    def test_lens_reads_the_kernel_data(self):
        require_m10()
        out = run_sdk("<h1>App</h1>", "0", """(async () => { await window.__installed; return {
  patterns: IterAlly.patterns(), pairs: IterAlly.pairs(), gapAB: IterAlly.gap('AgencyBalance'),
  moat: IterAlly.facet('AgencyBalance', 'moat'), pc1: IterAlly.paraconsistent('TimeCoherence', 'CreativeTranscendence'),
  pc2: IterAlly.paraconsistent('CreativeTranscendence', 'TimeCoherence'), pc3: IterAlly.paraconsistent('TimeCoherence', 'AgencyBalance'),
  brief: IterAlly.brief(), fetches: window.__fetches.length }; })()""")
        self.assertEqual(out["patterns"], PATTERNS)
        self.assertEqual(sorted(map(tuple, out["pairs"])), sorted(PAIRS))
        kernel = kernel_json()
        self.assertEqual(out["gapAB"], kernel["facets"]["AgencyBalance"]["gap"])
        self.assertIn("Capture is quiet", out["moat"])
        self.assertEqual((out["pc1"], out["pc2"], out["pc3"]), (True, True, False))
        self.assertEqual(out["brief"], BRIEF)
        self.assertEqual(out["fetches"], 0, "the kernel was given inline; nothing was fetched")

    @pending("M10-A1")
    def test_install_validates_the_brief_and_guards_early_calls(self):
        out = run_sdk("<h1>App</h1>", "0", """(async () => {
const r = {};
try { IterAlly.install({ brief: { for: 'x' }, kernel: window.__kernel }); r.bad = 'no throw'; } catch (e) { r.bad = e.message; }
try { IterAlly.install({ brief: { for: 'x'.repeat(201), flourishing: 'y' }, kernel: window.__kernel }); r.long = 'no throw'; } catch (e) { r.long = e.message; }
return r; })()""")
        self.assertEqual(out["bad"], 'IterAlly: a brief needs "for" and "flourishing"')
        self.assertEqual(out["long"], 'IterAlly: a brief needs "for" and "flourishing"')
        early = json.loads(__import__("m10_support").run_playwright("""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.set_content("<!doctype html><body></body>")
    pg.add_script_tag(path=%s)
    print(json.dumps(pg.evaluate("(() => { try { IterAlly.patterns(); return 'no throw'; } catch (e) { return e.message; } })()"))); b.close()
""" % json.dumps(str(SDK))).strip().splitlines()[-1])
        self.assertEqual(early, "IterAlly: not installed yet")

    @pending("M10-A1")
    def test_sdk_has_no_pattern_text_and_no_dependencies(self):
        source = SDK.read_text(encoding="utf-8")
        for needle in ("Capture is quiet", "AgencyBalance", "WonderPreservation"):
            self.assertNotIn(needle, source, "pattern names and text live in soul_kernel.json only")
        self.assertNotIn("require(", source.replace("module.exports", ""))
        self.assertNotIn("import ", source)
        self.assertIn("window.IterAlly", source)
        self.assertIn("module.exports", source)


@PW
class CardTests(unittest.TestCase):
    """M10-A2"""

    @pending("M10-A2")
    def test_card_renders_records_the_pick_and_queues(self):
        require_m10()
        out = run_sdk("<h1>App</h1>", "0", """(async () => {
await window.__installed;
const first = IterAlly.card({ kind: 'offer', title: 'A thought', body: 'Try the *other* order?', topic: 'order', choices: ['Sure', 'Not now'] });
const second = IterAlly.card({ kind: 'read', title: 'Pace', body: '', choices: [{ id: 'slow', label: 'Slower' }, { id: 'fast', label: 'Faster' }] });
await new Promise((r) => setTimeout(r, 50));
const root = document.querySelector('#iter-ally-root');
const cards = document.querySelectorAll('.iter-ally-card').length;
const title = document.querySelector('.iter-ally-title').textContent;
const bodyHtml = document.querySelector('.iter-ally-body').innerHTML;
const buttons = [...document.querySelectorAll('button.iter-ally-choice')].map((b) => [b.dataset.choice, b.textContent]);
document.querySelector('button.iter-ally-choice[data-choice="a"]').click();
const pick1 = await first;
await new Promise((r) => setTimeout(r, 50));
const title2 = document.querySelector('.iter-ally-title').textContent;
document.querySelector('button.iter-ally-dismiss').click();
const pick2 = await second;
await new Promise((r) => setTimeout(r, 50));
return { rootFixed: getComputedStyle(root).position, cards, title, bodyHtml, buttons, pick1, title2, pick2,
         left: document.querySelectorAll('.iter-ally-card').length, styleTags: document.querySelectorAll('style, link[rel=stylesheet]').length,
         calibration: IterAlly.calibration().map((c) => [c.kind, c.topic, c.pick, c.person, typeof c.at]) }; })()""")
        self.assertEqual(out["rootFixed"], "fixed")
        self.assertEqual(out["cards"], 1, "one card at a time; the second is queued")
        self.assertEqual(out["title"], "A thought")
        self.assertIn("<em>other</em>", out["bodyHtml"])
        self.assertEqual(out["buttons"], [["a", "Sure"], ["b", "Not now"]])
        self.assertEqual(out["pick1"], "a")
        self.assertEqual(out["title2"], "Pace")
        self.assertEqual(out["pick2"], "dismiss")
        self.assertEqual(out["left"], 0)
        self.assertEqual(out["styleTags"], 0)
        self.assertEqual(out["calibration"], [["offer", "order", "a", "bright", "number"], ["read", None, "dismiss", "bright", "number"]])

    @pending("M10-A2")
    def test_fork_requires_a_declared_pair_and_adds_the_line(self):
        out = run_sdk("<h1>App</h1>", "0", """(async () => {
await window.__installed;
const r = {};
try { IterAlly.fork({ title: 'x', a: { label: 'A', pattern: 'TimeCoherence' }, b: { label: 'B', pattern: 'AgencyBalance' } }); r.bad = 'no throw'; } catch (e) { r.bad = e.message; }
const p = IterAlly.fork({ title: 'Header', body: 'Two ways.', a: { label: 'Playful', pattern: 'CreativeTranscendence' }, b: { label: 'On time', pattern: 'TimeCoherence' }, topic: 'header' });
await new Promise((res) => setTimeout(res, 50));
r.body = document.querySelector('.iter-ally-body').textContent;
r.cls = document.querySelector('.iter-ally-card').className;
document.querySelector('button.iter-ally-choice[data-choice="b"]').click();
r.pick = await p;
r.cal = IterAlly.calibration().map((c) => [c.kind, c.topic, c.pick]);
try { IterAlly.card({ kind: 'offer', title: 't', choices: [{ id: 'a', label: 'A', pattern: 'Velocity' }] }); r.badPattern = 'no throw'; } catch (e) { r.badPattern = e.message; }
return r; })()""")
        self.assertEqual(out["bad"], "IterAlly: TimeCoherence and AgencyBalance are not a declared pair")
        self.assertIn("Both can be true at once; this is yours to choose.", out["body"])
        self.assertIn("iter-ally-card", out["cls"])
        self.assertEqual(out["pick"], "b")
        self.assertEqual(out["cal"], [["fork", "header", "b"]])
        self.assertTrue(out["badPattern"].startswith("IterAlly: unknown pattern"), out["badPattern"])

    @pending("M10-A2")
    def test_notice_is_a_passing_line_that_records_nothing(self):
        out = run_sdk("<h1>App</h1>", "IterAlly.__afterInstall = window.__installed.then(() => IterAlly.notice('that was a nice turn'));", """(async () => {
await IterAlly.__afterInstall; await new Promise((r) => setTimeout(r, 50));
const n = document.querySelector('.iter-ally-notice');
return { text: n && n.textContent, buttons: document.querySelectorAll('#iter-ally-root button').length, cal: IterAlly.calibration().length }; })()""")
        self.assertIn("that was a nice turn", out["text"])
        self.assertIn("✦", out["text"])
        self.assertEqual(out["buttons"], 0)
        self.assertEqual(out["cal"], 0)


@PW
class CalibrationTests(unittest.TestCase):
    """M10-A3"""

    @pending("M10-A3")
    def test_calibration_persists_forgets_and_exports(self):
        require_m10()
        out = json.loads(__import__("m10_support").run_playwright("""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(); pg = ctx.new_page()
    pg.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body="<!doctype html><title>Little Orbit</title><body></body>"))
    pg.goto("http://app.test/index.html")
    pg.add_script_tag(path=%s)
    pg.evaluate("window.__kernel = " + %s)
    pg.evaluate("window.__brief = " + %s)
    pg.evaluate("window.IterAlly.install({ brief: window.__brief, person: 'bright', kernel: window.__kernel })")
    pg.wait_for_timeout(100)
    pg.evaluate("(async () => { const p = IterAlly.card({ kind: 'offer', title: 't', choices: ['x', 'y'], topic: 'first' }); await new Promise((r) => setTimeout(r, 30)); document.querySelector('button.iter-ally-choice[data-choice=\\"b\\"]').click(); await p; })()")
    pg.wait_for_timeout(100)
    pg.reload(); pg.add_script_tag(path=%s)
    pg.evaluate("window.IterAlly.install({ brief: %s, person: 'bright', kernel: %s })")
    pg.wait_for_timeout(100)
    out = pg.evaluate("(() => { const after = IterAlly.calibration().map((c) => [c.topic, c.pick]); const exp = IterAlly.calibrationExport(); IterAlly.forget(); return { after, exp, gone: IterAlly.calibration().length }; })()")
    print(json.dumps(out)); b.close()
""" % (json.dumps(str(SDK)), json.dumps(json.dumps(kernel_json())), json.dumps(json.dumps(BRIEF)), json.dumps(str(SDK)),
       json.dumps(BRIEF), json.dumps(kernel_json()))).strip().splitlines()[-1])
        self.assertEqual(out["after"], [["first", "b"]], "picks survive a reload")
        self.assertEqual(out["exp"]["app"], "Little Orbit")
        self.assertEqual(out["exp"]["person"], "bright")
        self.assertEqual(out["exp"]["brief"], BRIEF)
        self.assertEqual([p["pick"] for p in out["exp"]["picks"]], ["b"])
        self.assertEqual(out["gone"], 0)


@PW
class ModelTests(unittest.TestCase):
    """M10-A4"""

    @pending("M10-A4")
    def test_ask_sends_brief_and_lens_with_the_owners_key_or_refuses_without_a_model(self):
        require_m10()
        fetch = ("(url, init) => { window.__fetches.push([url, init]); return Promise.resolve({ ok: true, status: 200, "
                 "json: () => Promise.resolve({ choices: [{ message: { content: 'a reply' } }] }) }); }")
        out = run_sdk("<h1>App</h1>", "0", """(async () => {
await window.__installed;
const r = {};
try { await IterAlly.ask('hello'); r.none = 'no reject'; } catch (e) { r.none = e.message; }
r.fetchesBefore = window.__fetches.length;
await IterAlly.install({ brief: window.__brief, person: 'bright', kernel: window.__kernel, model: { baseUrl: 'https://openrouter.ai/api/v1', apiKey: 'sk-test', model: 'openai/gpt-4o-mini' } });
r.reply = await IterAlly.ask('what should I try next?');
const [url, init] = window.__fetches[0];
r.url = url; r.auth = init.headers.Authorization || init.headers.authorization; r.method = init.method;
const body = JSON.parse(init.body); r.model = body.model; r.system = body.messages[0].content; r.user = body.messages[1].content;
return r; })()""", fetch_js=fetch)
        self.assertEqual(out["none"], "IterAlly: no model configured")
        self.assertEqual(out["fetchesBefore"], 0, "no network without a model")
        self.assertEqual(out["reply"], "a reply")
        self.assertEqual(out["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(out["auth"], "Bearer sk-test")
        self.assertEqual(out["method"], "POST")
        self.assertEqual(out["model"], "openai/gpt-4o-mini")
        self.assertIn(BRIEF["for"], out["system"])
        self.assertIn(BRIEF["flourishing"], out["system"])
        kernel = kernel_json()
        self.assertIn(kernel["facets"]["WonderPreservation"]["gap"], out["system"], "the lens is in the system prompt")
        self.assertEqual(out["user"], "what should I try next?")


class KernelExportTests(unittest.TestCase):
    """M10-A5"""

    @pending("M10-A5")
    def test_committed_kernel_json_equals_a_fresh_export(self):
        r = m10_root("m10kernel")
        self.addCleanup(r.close)
        r.start()
        out = Path(r.root) / "fresh_kernel.json"
        proc = subprocess.run([sys.executable, str(REPO / "scripts" / "export_soul_kernel.py"), "--out", str(out)],
                              env=r.env(), capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertEqual(out.read_bytes(), KERNEL_JSON.read_bytes(), "run scripts/export_soul_kernel.py and commit the result")
        check = subprocess.run([sys.executable, str(REPO / "scripts" / "export_soul_kernel.py"), "--check"],
                               env=r.env(), capture_output=True, text=True, timeout=300)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        kernel = kernel_json()
        self.assertEqual(kernel["generated_from"], "seeds/soul_kernel.metta")
        self.assertEqual(kernel["patterns"], PATTERNS)
        self.assertEqual(set(kernel["facets"]["AgencyBalance"]), {"description", "flourishing", "captured", "signal", "felt", "moat", "anti", "proxy", "gap"})
        seed = (ITER_SRC / "seeds" / "soul_kernel.metta").read_text(encoding="utf-8").replace('\\"', '"')
        for pattern, facets in kernel["facets"].items():
            for text in facets.values():
                self.assertIn(text, seed, "every facet text is in the seed: %s" % pattern)
        self.assertTrue(KERNEL_JSON.read_text().endswith("\n"))


if __name__ == "__main__":
    unittest.main()
