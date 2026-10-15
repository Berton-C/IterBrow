#!/usr/bin/env python3
"""M6-A1..A5: interactive sidebar cards and the choice round trip.

Spec: docs/milestones/M6_soul_base.md section A. The chat bridge tests drive the REAL
bridge/chat_bridge.js under node in a throwaway ITER_DIR; the render tests load the real
sidebar page in headless Chromium (system Python + Playwright) with window.iterApi stubbed.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import (pending, m6_root, require_m6, run_bridge, card, outbox_message, NODE,  # noqa: E402
                        playwright_available, run_playwright, sidebar_page_script, ITER_SRC, REPO)


@unittest.skipUnless(NODE, "needs node")
class CardMessageTests(unittest.TestCase):
    """M6-A1: the bridge accepts, journals and forwards a card; text messages are unchanged."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    def _deliver(self, message, name="m.json"):
        return run_bridge(self.root, """
const p = path.join(bridge.paths.outboxDir, %s);
fs.writeFileSync(p, %s); settle(p); bridge.pollNow();
out = { received, history: bridge.history(), logs,
        journal: fs.readFileSync(bridge.paths.journalPath, 'utf8').trim().split('\\n').map((l) => JSON.parse(l)) };
""" % (json.dumps(name), json.dumps(json.dumps(message))))

    @pending("M6-A1")
    def test_card_message_is_accepted_journaled_and_forwarded_with_its_card(self):
        out = self._deliver(outbox_message(card()))
        self.assertEqual(len(out["received"]), 1)
        received = out["received"][0]
        self.assertEqual(received["role"], "iter")
        self.assertEqual(received["card"]["id"], "card-test-1")
        self.assertEqual([c["id"] for c in received["card"]["choices"]], ["a", "b"])
        self.assertEqual(received["content"], "**Which way?**\n\nTwo poles.")
        self.assertEqual(out["journal"][-1]["card"]["kind"], "fork")
        self.assertEqual(out["history"][-1]["card"]["title"], "Which way?")

    @pending("M6-A1")
    def test_malformed_card_is_dropped_but_the_text_still_arrives(self):
        bad = outbox_message({"id": "card-x", "kind": "fork", "title": "t", "body": "b",
                              "choices": [{"id": "a", "label": "1"}, {"id": "b", "label": "2"},
                                          {"id": "c", "label": "3"}, {"id": "d", "label": "4"}]})
        out = self._deliver(bad)
        self.assertEqual(len(out["received"]), 1)
        self.assertNotIn("card", out["received"][0])
        self.assertEqual(out["received"][0]["content"], "**t**\n\nb")
        self.assertTrue(any("card" in line and "drop" in line for line in out["logs"]), out["logs"])
        for shape in ({"id": "card-y", "kind": "unknown", "title": "t", "body": "b", "choices": [{"id": "a", "label": "1"}]},
                      {"id": "card-z", "kind": "fork", "title": "", "body": "b", "choices": [{"id": "a", "label": "1"}]},
                      {"id": "card-w", "kind": "fork", "title": "t", "body": "b", "choices": []}):
            out = self._deliver(outbox_message(shape, message_id="iter-" + shape["id"]), name=shape["id"] + ".json")
            self.assertNotIn("card", out["received"][-1], shape)

    def test_plain_text_messages_are_unchanged(self):
        out = self._deliver({"schema_version": 1, "id": "iter-plain", "role": "iter", "content": "hello", "at": 5})
        self.assertEqual(out["received"][0], {"schema_version": 1, "id": "iter-plain", "role": "iter", "content": "hello", "at": 5})


@unittest.skipUnless(NODE, "needs node")
class ChoiceRoundTripTests(unittest.TestCase):
    """M6-A3: a click becomes an inbox line Iter receives like a message, and a journal entry."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    @pending("M6-A3")
    def test_send_choice_writes_the_inbox_line_and_journals_the_pick(self):
        out = run_bridge(self.root, """
const m = bridge.sendChoice('card-test-1', 'a', 'berton', 'Keep it playful');
const names = fs.readdirSync(bridge.paths.inboxDir);
out = { message: m, inbox: fs.readFileSync(path.join(bridge.paths.inboxDir, names[0]), 'utf8'),
        journal: fs.readFileSync(bridge.paths.journalPath, 'utf8').trim().split('\\n').map((l) => JSON.parse(l)) };
""")
        self.assertEqual(out["inbox"], "[choice card=card-test-1 pick=a by=berton] Keep it playful")
        self.assertEqual(out["message"]["role"], "user")
        self.assertEqual(out["message"]["choice"], {"card": "card-test-1", "pick": "a", "by": "berton"})
        self.assertEqual(out["journal"][-1]["choice"]["pick"], "a")
        self.assertEqual(out["journal"][-1]["content"], out["inbox"])

    @pending("M6-A3")
    def test_dismissal_has_no_label(self):
        out = run_bridge(self.root, """
bridge.sendChoice('card-test-1', 'dismiss', 'haley');
const names = fs.readdirSync(bridge.paths.inboxDir);
out = { inbox: fs.readFileSync(path.join(bridge.paths.inboxDir, names[0]), 'utf8') };
""")
        self.assertEqual(out["inbox"], "[choice card=card-test-1 pick=dismiss by=haley]")

    @pending("M6-A3")
    def test_iter_channel_receives_the_choice_line_verbatim(self):
        """channels/electron_ui.py receive() returns the line as a user message."""
        run_bridge(self.root, "bridge.sendChoice('card-7', 'b', 'bright', 'Keep it obvious'); out = {};")
        env = dict(os.environ, ITER_DIR=self.root)
        import subprocess
        proc = subprocess.run([sys.executable, "-c",
                               "import sys; sys.path.insert(0, %r); import electron_ui; print(electron_ui.receive())"
                               % str(ITER_SRC / "channels")], env=env, capture_output=True, text=True, cwd=self.root)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "[choice card=card-7 pick=b by=bright] Keep it obvious")


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class CardRenderTests(unittest.TestCase):
    """M6-A2: the sidebar renders a card and a click sends exactly one choice."""

    def _page(self, message, probe):
        setup = "window.__incoming = %s; window.__deliver && window.__deliver(window.__incoming);" % json.dumps(message)
        # The renderer subscribes with iterApi.onChatIncoming(cb); the stub keeps the callback.
        api = ("{onChatIncoming:(cb)=>{window.__deliver=cb;},chatHistory:()=>Promise.resolve([]),"
               "iterStatus:()=>Promise.resolve({running:false}),recentLog:()=>Promise.resolve([]),"
               "onUiResume:()=>{},onIterStatus:()=>{},loadSettings:()=>Promise.resolve({}),"
               "sendChoice:(...a)=>{window.__calls.push(['sendChoice',...a]);return Promise.resolve(true);}}")
        return json.loads(run_playwright(sidebar_page_script(setup, probe, api)).strip().splitlines()[-1])

    @pending("M6-A2")
    def test_card_shows_title_body_buttons_and_links(self):
        message = outbox_message(card(links=[{"label": "Variant A", "url": "https://example.com/a"}]))
        out = self._page(message, """(() => {
const c = document.querySelector('.card'); if (!c) return {missing: true};
return { title: c.querySelector('.card-title').textContent, body: c.querySelector('.card-body').innerHTML,
         buttons: [...c.querySelectorAll('button.choice')].map((b) => [b.dataset.choice, b.textContent, b.title]),
         links: [...c.querySelectorAll('a')].map((a) => a.getAttribute('href')),
         fallbackShown: !!c.closest('.row').querySelector('.body.markdown') };
})()""")
        self.assertNotIn("missing", out, "no .card rendered")
        self.assertEqual(out["title"], "Which way?")
        self.assertIn("Two poles.", out["body"])
        self.assertEqual([b[0] for b in out["buttons"]], ["a", "b"])
        self.assertEqual(out["buttons"][0][2], "wonder")
        self.assertEqual(out["links"], ["https://example.com/a"])
        self.assertFalse(out["fallbackShown"], "the markdown fallback is for old sidebars; a card renders as a card")

    @pending("M6-A2")
    def test_click_sends_one_choice_and_locks_the_card(self):
        out = self._page(outbox_message(card()), """(async () => {
const c = document.querySelector('.card');
c.querySelector('button.choice[data-choice="b"]').click();
await new Promise((r) => setTimeout(r, 100));
c.querySelector('button.choice[data-choice="a"]').click();
await new Promise((r) => setTimeout(r, 100));
return { calls: window.__calls.filter((x) => x[0] === 'sendChoice'),
         disabled: [...c.querySelectorAll('button.choice')].map((b) => b.disabled),
         picked: c.querySelector('button.choice.picked') && c.querySelector('button.choice.picked').dataset.choice };
})()""")
        self.assertEqual(out["calls"], [["sendChoice", "card-test-1", "b", "Keep it obvious"]])
        self.assertEqual(out["disabled"], [True, True])
        self.assertEqual(out["picked"], "b")

    @pending("M6-A2")
    def test_dismiss_sends_dismiss(self):
        out = self._page(outbox_message(card()), """(async () => {
document.querySelector('.card .dismiss').click();
await new Promise((r) => setTimeout(r, 100));
return { calls: window.__calls.filter((x) => x[0] === 'sendChoice') };
})()""")
        self.assertEqual(out["calls"], [["sendChoice", "card-test-1", "dismiss", ""]])

    @pending("M6-A2")
    def test_card_body_is_rendered_through_the_markdown_renderer_and_escaped(self):
        message = outbox_message(card(body="**bold** <script>alert(1)</script>"))
        out = self._page(message, "document.querySelector('.card .card-body').innerHTML")
        self.assertIn("<strong>bold</strong>", out)
        self.assertNotIn("<script>", out)


class CardToolTests(unittest.TestCase):
    """M6-A5: the `card` tool Iter calls."""

    def setUp(self):
        self.r = m6_root("m6card")
        self.addCleanup(self.r.close)
        self.r.start()

    def _outbox(self):
        outbox = Path(self.r.root) / ".runtime" / "electron_ui" / "outbox"
        return [json.loads(p.read_text()) for p in sorted(outbox.glob("*.json"))]

    @pending("M6-A5")
    def test_card_tool_writes_a_card_with_markdown_fallback(self):
        out = self.r.text("card", kind="fork", title="Which way?", body="Two poles.",
                          choices=[{"id": "a", "label": "Keep it playful", "hint": "wonder"},
                                   {"id": "b", "label": "Keep it obvious"}])
        self.assertTrue(out.startswith("CARD-SENT: card-"), out)
        message = self._outbox()[-1]
        self.assertEqual(message["card"]["kind"], "fork")
        self.assertEqual(message["content"], "**Which way?**\n\nTwo poles.\n\n1. Keep it playful — wonder\n2. Keep it obvious")
        self.assertEqual(message["card"]["id"], out.split()[-1])

    @pending("M6-A5")
    def test_choices_may_be_plain_labels_and_get_letter_ids(self):
        self.assertIn("CARD-SENT", self.r.text("card", kind="offer", title="Now?", body="x", choices=["Now", "Later", "Never"]))
        self.assertEqual([c["id"] for c in self._outbox()[-1]["card"]["choices"]], ["a", "b", "c"])

    @pending("M6-A5")
    def test_validation_and_description(self):
        for bad in (dict(kind="fork", title="", body="b", choices=["x"]),
                    dict(kind="verdict", title="t", body="b", choices=["x"]),
                    dict(kind="fork", title="t", body="b", choices=[]),
                    dict(kind="fork", title="t", body="b", choices=["1", "2", "3", "4"])):
            self.assertTrue(self.r.text("card", **bad).startswith("ERROR"), bad)
        self.assertEqual(self._outbox(), [])
        from tools._metadata_static import static_tool_metadata
        self.assertLessEqual(len(static_tool_metadata(ITER_SRC / "tools" / "card.py")["description"]), 500)


class CalibrationAtomTests(unittest.TestCase):
    """M6-A4: a pick becomes one soul-choice atom in the AtomSpace (written by main.js)."""

    def setUp(self):
        self.r = m6_root("m6atom")
        self.addCleanup(self.r.close)
        self.r.start()

    def _record(self, card_id, pick, person="berton", kind="fork", socket=None):
        """Call main.js's recorder the way the sidebar IPC does (through the node harness)."""
        import subprocess
        script = """
const path = require('path');
const { recordSoulChoice } = require(%s);
recordSoulChoice({ socket: %s, iterDir: %s, person: %s, kind: %s, cardId: %s, pick: %s, at: 1700000000123 })
  .then((r) => process.stdout.write(JSON.stringify(r) + '\\n'));
""" % tuple(json.dumps(x) for x in (str(REPO / "bridge" / "soul_choice.js"), socket or str(self.r.sock),
                                     str(self.r.root), person, kind, card_id, pick))
        proc = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(proc.stdout.strip().splitlines()[-1])

    @pending("M6-A4")
    def test_pick_writes_exactly_one_atom_with_the_pinned_shape(self):
        self.assertTrue(self._record("card-1", "a")["written"])
        atoms = self.r.call("read_atoms", {"prefix": "state:soul_choice:"})["atoms"]
        self.assertEqual(atoms, {"state:soul_choice:card-1": '(soul-choice "berton" "fork" "card-1" "a" 1700000000123)'})
        # A second click on the same card cannot happen in the UI; the recorder refuses it too.
        self.assertFalse(self._record("card-1", "b")["written"])
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_choice:"})["atoms"], atoms)
        # A dismissal after a pick is ignored; a dismissal of a fresh card is recorded.
        self.assertFalse(self._record("card-1", "dismiss")["written"])
        self.assertTrue(self._record("card-2", "dismiss", person="haley", kind="read")["written"])
        self.assertIn('(soul-choice "haley" "read" "card-2" "dismiss" 1700000000123)',
                      self.r.call("read_atoms", {"prefix": "state:soul_choice:"})["atoms"].values())

    @pending("M6-A4")
    def test_unreachable_service_queues_the_atom_and_the_next_event_flushes_it(self):
        pending_file = Path(self.r.root) / ".runtime" / "soul_choice_pending.jsonl"
        out = self._record("card-9", "a", socket=str(Path(self.r.sock).parent / "nowhere.sock"))
        self.assertFalse(out["written"])
        self.assertTrue(out["queued"])
        self.assertTrue(pending_file.exists())
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_choice:"})["atoms"], {})
        self.assertTrue(self._record("card-10", "b")["written"])
        atoms = self.r.call("read_atoms", {"prefix": "state:soul_choice:"})["atoms"]
        self.assertEqual(sorted(k.split(":")[-1] for k in atoms), ["card-10", "card-9"])
        self.assertFalse(pending_file.exists() and pending_file.read_text().strip())


if __name__ == "__main__":
    unittest.main()
