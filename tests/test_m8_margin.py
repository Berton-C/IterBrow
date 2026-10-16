#!/usr/bin/env python3
"""M8-D1..D4: the margin — the Soul in the tab.

Spec: docs/milestones/M8_soul_presence.md section D. D1 is tested in a real Chromium page with a
stubbed api (bridge/margin.js is pure DOM); D2 by reading main.js / app_preload.js; D3 through the
real chat bridge in node and the sidebar in Chromium; D4 through the presence transformation.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m8_support import (pending, m8_root, require_m8, write_soul_settings, run_transformation, run_bridge,  # noqa: E402
                        margin_page_script, run_playwright, playwright_available, ENABLED_API, DISABLED_API,
                        NODE, REPO)
from m6_support import sidebar_page_script  # noqa: E402


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class MarginPageTests(unittest.TestCase):
    """M8-D1"""

    def _page(self, api, setup, probe, body=None):
        kwargs = {"body": body} if body else {}
        return json.loads(run_playwright(margin_page_script(api, setup, probe, **kwargs)).strip().splitlines()[-1])

    @pending("M8-D1")
    def test_disabled_adds_nothing(self):
        require_m8()
        out = self._page(DISABLED_API, "0", "({root: !!document.querySelector('#iter-margin-root'), glyph: !!document.querySelector('#iter-margin-glyph')})")
        self.assertEqual(out, {"root": False, "glyph": False})

    @pending("M8-D1")
    def test_glyph_is_quiet_and_opens_the_panel(self):
        out = self._page(ENABLED_API, "0", """(() => {
const g = document.querySelector('#iter-margin-glyph'); if (!g) return {missing: true};
const cs = getComputedStyle(g);
const before = !!document.querySelector('#iter-margin');
g.click();
const panel = document.querySelector('#iter-margin');
return { text: g.textContent, label: g.getAttribute('aria-label'), title: g.title, position: cs.position,
         opacity: Number(cs.opacity), before, after: !!panel,
         controls: ['#iter-margin-target', '#iter-margin-text', '#iter-margin-ask', '#iter-margin-jam', '#iter-margin-close', '#iter-margin-status']
           .map((s) => !!document.querySelector(s)),
         askLabel: document.querySelector('#iter-margin-ask').textContent, jamLabel: document.querySelector('#iter-margin-jam').textContent,
         styleTags: document.querySelectorAll('style, link[rel=stylesheet]').length, rootChildren: document.querySelectorAll('#iter-margin-root > *').length };
})()""")
        self.assertNotIn("missing", out)
        self.assertEqual(out["text"], "✦")
        self.assertEqual(out["label"], "Iter")
        self.assertEqual(out["title"], "Ask Iter about this page")
        self.assertEqual(out["position"], "fixed")
        self.assertLessEqual(out["opacity"], 0.4)
        self.assertEqual((out["before"], out["after"]), (False, True))
        self.assertTrue(all(out["controls"]), out["controls"])
        self.assertEqual((out["askLabel"], out["jamLabel"]), ("Ask about this", "Jam on this"))
        self.assertEqual(out["styleTags"], 0, "no stylesheet injected into the page")

    @pending("M8-D1")
    def test_pointing_is_remembered_and_sent_with_the_text(self):
        out = self._page(ENABLED_API, """
const p = document.querySelector('p.note.lead');
p.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));
document.querySelector('#iter-margin-glyph').click();
""", """(async () => {
const target = document.querySelector('#iter-margin-target').textContent;
document.querySelector('#iter-margin-text').value = 'why is this grey?';
document.querySelector('#iter-margin-ask').click();
await new Promise((r) => setTimeout(r, 100));
return { target, sent: window.__sent, status: document.querySelector('#iter-margin-status').textContent,
         cleared: document.querySelector('#iter-margin-text').value,
         enabled: !document.querySelector('#iter-margin-ask').disabled };
})()""")
        self.assertEqual(out["target"], "pointing at: p.note.lead")
        self.assertEqual(len(out["sent"]), 1)
        sent = out["sent"][0]
        self.assertEqual(sent["intent"], "ask")
        self.assertEqual(sent["text"], "why is this grey?")
        self.assertEqual(sent["element"]["selector"], "p.note.lead")
        self.assertEqual(sent["element"]["tag"], "p")
        self.assertEqual(sent["element"]["text"], "hello")
        self.assertEqual(out["status"], "sent")
        self.assertEqual(out["cleared"], "")
        self.assertTrue(out["enabled"])

    @pending("M8-D1")
    def test_selector_prefers_id_then_classes_then_a_short_path(self):
        out = self._page(ENABLED_API, "0", """(async () => {
const results = [];
for (const sel of ['#title', 'p.note.lead', 'li']) {
  const el = document.querySelector(sel);
  el.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));
  if (!document.querySelector('#iter-margin')) document.querySelector('#iter-margin-glyph').click();
  document.querySelector('#iter-margin-jam').click();
  await new Promise((r) => setTimeout(r, 50));
}
return window.__sent.map((s) => [s.intent, s.text, s.element.selector]);
})()""", body="<h1 id='title'>App</h1><p class='note lead'>hello</p><ul><li>one</li><li>two</li></ul>")
        self.assertEqual(out[0], ["jam", "", "#title"])
        self.assertEqual(out[1], ["jam", "", "p.note.lead"])
        self.assertRegex(out[2][2], r"^(body > )?ul(:nth-of-type\(1\))? > li(:nth-of-type\(1\))?$")

    @pending("M8-D1")
    def test_empty_ask_is_refused_in_place_and_state_false_removes_everything(self):
        out = self._page(ENABLED_API, "document.querySelector('#iter-margin-glyph').click();", """(async () => {
document.querySelector('#iter-margin-ask').click();
await new Promise((r) => setTimeout(r, 50));
const refused = document.querySelector('#iter-margin-status').textContent;
const sentCount = (window.__sent || []).length;
window.__state({enabled: false});
await new Promise((r) => setTimeout(r, 50));
const gone = !document.querySelector('#iter-margin-root');
window.__state({enabled: true});
await new Promise((r) => setTimeout(r, 50));
return { refused, sentCount, gone, back: !!document.querySelector('#iter-margin-glyph') };
})()""")
        self.assertEqual(out["refused"], "say what you'd like to ask")
        self.assertEqual(out["sentCount"], 0)
        self.assertTrue(out["gone"])
        self.assertTrue(out["back"])

    @pending("M8-D1")
    def test_rejected_send_shows_the_error_and_re_enables(self):
        api = ("({enabled: () => Promise.resolve({enabled: true, app: 'orbit'}),"
               " send: () => Promise.reject(new Error('This tab is locked')), onState: () => {}})")
        out = self._page(api, "document.querySelector('#iter-margin-glyph').click();", """(async () => {
document.querySelector('#iter-margin-text').value = 'hi';
document.querySelector('#iter-margin-ask').click();
await new Promise((r) => setTimeout(r, 50));
return { status: document.querySelector('#iter-margin-status').textContent, enabled: !document.querySelector('#iter-margin-ask').disabled,
         kept: document.querySelector('#iter-margin-text').value };
})()""")
        self.assertIn("This tab is locked", out["status"])
        self.assertTrue(out["enabled"])
        self.assertEqual(out["kept"], "hi")


class WiringTests(unittest.TestCase):
    """M8-D2: preload installs it; main.js decides from the tab and the person, never from the page."""

    @pending("M8-D2")
    def test_preload_installs_the_margin_with_an_ipc_api(self):
        preload = (REPO / "bridge" / "app_preload.js").read_text(encoding="utf-8")
        self.assertIn("require('./margin')", preload)
        for channel in ("margin:enabled", "margin:send", "margin:state"):
            self.assertIn(channel, preload, channel)
        self.assertIn("DOMContentLoaded", preload)

    @pending("M8-D2")
    def test_main_checks_app_scope_lock_and_feature_for_both_handlers(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        for handler in ("margin:enabled", "margin:send"):
            start = main.index("ipcMain.handle('%s'" % handler)
            body = main[start:start + 1800]
            self.assertIn("event.sender", body, handler)
            self.assertIn("locked", body, handler)
            self.assertIn("appScope", body, handler)
            self.assertIn("loadSoulSettings()", body, handler)
        send = main[main.index("ipcMain.handle('margin:send'"):][:1800]
        for message in ("This tab is locked", "Not an app tab", "Margin is off"):
            self.assertIn(message, send, message)
        self.assertIn("chatBridge.sendMargin(", send)
        self.assertIn("recordSoulMargin(", send)
        self.assertNotIn("payload.person", send, "the page never names the person")
        self.assertIn("margin:state", main[main.index("onTabsChanged"):][:3000], "lock toggles push the state to app tabs")

    @pending("M8-D2")
    def test_soul_save_pushes_margin_state(self):
        main = (REPO / "main.js").read_text(encoding="utf-8")
        save = main[main.index("ipcMain.handle('soul:save'"):][:1500]
        self.assertIn("margin:state", save)


@unittest.skipUnless(NODE, "needs node")
class BridgeTests(unittest.TestCase):
    """M8-D3 (bridge): the line Iter reads and the journal entry the sidebar replays."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    @pending("M8-D3")
    def test_send_margin_writes_the_line_and_journals_the_structure(self):
        require_m8()
        out = run_bridge(self.root, """
const m = bridge.sendMargin({ app: 'orbit', tab: 7, intent: 'ask', text: 'why is this grey?', element: { selector: 'p.note', tag: 'p', text: 'hello' } });
const j = bridge.sendMargin({ app: 'orbit', tab: 7, intent: 'jam', text: '', element: { selector: '#title', tag: 'h1', text: 'App' } });
const inbox = fs.readdirSync(bridge.paths.inboxDir).sort().map((n) => fs.readFileSync(path.join(bridge.paths.inboxDir, n), 'utf8'));
out = { first: m, second: j, inbox, history: bridge.history().map((x) => [x.role, x.content, x.margin || null]) };
""")
        self.assertEqual(out["first"]["role"], "user")
        self.assertEqual(out["first"]["content"], "[margin app=orbit tab=7 intent=ask element=p.note] why is this grey?")
        self.assertEqual(out["first"]["margin"], {"app": "orbit", "tab": 7, "intent": "ask", "element": {"selector": "p.note", "tag": "p", "text": "hello"}})
        self.assertEqual(out["second"]["content"], "[margin app=orbit tab=7 intent=jam element=#title]")
        self.assertEqual(sorted(out["inbox"]), sorted([out["first"]["content"], out["second"]["content"]]))
        self.assertEqual(len(out["history"]), 2)
        self.assertEqual(out["history"][0][2]["intent"], "ask")

    @pending("M8-D3")
    def test_send_margin_validates(self):
        code, stdout, stderr = __import__("m8_support").node("""
const { makeChatBridge, marginLine } = require(%s);
const bridge = makeChatBridge(%s, () => {}, { pollIntervalMs: 60000, settleMs: 0 });
const bad = [];
for (const p of [ { app: 'orbit', tab: 7, intent: 'shout', text: 'x' }, { app: '../x', tab: 7, intent: 'ask', text: 'x' },
                  { app: 'orbit', tab: 'seven', intent: 'ask', text: 'x' }, { app: 'orbit', tab: 7, intent: 'ask', text: '' },
                  { app: 'orbit', tab: 7, intent: 'ask', text: 'x', element: { selector: 'a'.repeat(201) } } ]) {
  try { bridge.sendMargin(p); bad.push('accepted'); } catch (e) { bad.push('refused'); }
}
bridge.stop();
process.stdout.write(JSON.stringify({ bad, line: marginLine({ app: 'orbit', tab: 3, intent: 'ask', text: 'hi', element: { selector: 'p' } }),
  noElement: marginLine({ app: 'orbit', tab: 3, intent: 'jam', text: '' }) }));
""" % (json.dumps(str(REPO / "bridge" / "chat_bridge.js")), json.dumps(self.root)))
        self.assertEqual(code, 0, stderr)
        out = json.loads(stdout.strip().splitlines()[-1])
        self.assertEqual(out["bad"], ["refused"] * 5)
        self.assertEqual(out["line"], "[margin app=orbit tab=3 intent=ask element=p] hi")
        self.assertEqual(out["noElement"], "[margin app=orbit tab=3 intent=jam element=page]")

    @pending("M8-D3")
    def test_record_soul_margin_writes_one_atom(self):
        r = m8_root("m8marginatom")
        self.addCleanup(r.close)
        r.start()
        code, stdout, stderr = __import__("m8_support").node("""
const { recordSoulMargin } = require(%s);
recordSoulMargin({ socket: %s, person: 'berton', app: 'orbit', intent: 'ask', messageId: 'user-1', at: 1700000000000 })
  .then((res) => process.stdout.write(JSON.stringify(res)));
""" % (json.dumps(str(REPO / "bridge" / "soul_choice.js")), json.dumps(str(r.sock))))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout.strip().splitlines()[-1]), {"written": True})
        atoms = r.call("read_atoms", {"prefix": "state:soul_margin:"})["atoms"]
        self.assertEqual(atoms, {"state:soul_margin:user-1": '(soul-margin "berton" "orbit" "ask" 1700000000000)'})


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class SidebarTests(unittest.TestCase):
    """M8-D3 (sidebar): a margin message shows where it came from."""

    def _page(self, message, probe):
        setup = "window.__incoming = %s; window.__deliver && window.__deliver(window.__incoming);" % json.dumps(message)
        api = ("{onChatIncoming:(cb)=>{window.__deliver=cb;},chatHistory:()=>Promise.resolve([]),"
               "iterStatus:()=>Promise.resolve({running:false}),recentLog:()=>Promise.resolve([]),"
               "onUiResume:()=>{},onIterStatus:()=>{},loadSettings:()=>Promise.resolve({})}")
        return json.loads(run_playwright(sidebar_page_script(setup, probe, api)).strip().splitlines()[-1])

    @pending("M8-D3")
    def test_margin_rows_carry_a_note(self):
        require_m8()
        out = self._page({"schema_version": 1, "id": "user-m1", "role": "user", "at": 1700000000000,
                          "content": "[margin app=orbit tab=7 intent=ask element=p.note] why is this grey?",
                          "margin": {"app": "orbit", "tab": 7, "intent": "ask", "element": {"selector": "p.note", "tag": "p", "text": "hello"}}}, """(() => {
const row = document.querySelector('.msg.row.user'); if (!row) return {missing: true};
return { note: row.querySelector('.margin-note') && row.querySelector('.margin-note').textContent, body: row.querySelector('.body').textContent };
})()""")
        self.assertEqual(out["note"], "from orbit · p.note")
        self.assertEqual(out["body"].strip(), "why is this grey?")
        out = self._page({"schema_version": 1, "id": "user-m2", "role": "user", "at": 1700000000001,
                          "content": "[margin app=orbit tab=7 intent=jam element=page]",
                          "margin": {"app": "orbit", "tab": 7, "intent": "jam", "element": None}}, """(() => {
const row = document.querySelector('.msg.row.user');
return { note: row.querySelector('.margin-note').textContent, body: row.querySelector('.body').textContent.trim(), italic: !!row.querySelector('.body em') };
})()""")
        self.assertEqual(out["note"], "from orbit")
        self.assertEqual(out["body"], "jam on this")
        self.assertTrue(out["italic"])


class RecipeTests(unittest.TestCase):
    """M8-D4"""

    @pending("M8-D4")
    def test_presence_margin_line_names_the_riffs(self):
        temp = tempfile.mkdtemp(prefix="m8recipe-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        write_soul_settings(temp, "berton", {"margin": True})
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        content = msgs[-1]["content"]
        for word in ("[margin", "jam on this", "three riffs", "browser_tab_variants", "fork card"):
            self.assertIn(word, content, word)
        write_soul_settings(temp, "berton", {"margin": False, "forks": True})
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        self.assertNotIn("[margin", msgs[-1]["content"])


if __name__ == "__main__":
    unittest.main()
