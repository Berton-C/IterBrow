#!/usr/bin/env python3
"""M7-B1..B3: the felt channel — a short note in Iter's own voice, rendered as a voice, absent when off.

Spec: docs/milestones/M7_soul_personality.md section B.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m7_support import (pending, m7_root, run_transformation, write_soul_settings, tool_entry, run_bridge,  # noqa: E402
                        playwright_available, run_playwright, sidebar_page_script, NODE, REPO, ITER_SRC, FEATURES)


class FeltToolTests(unittest.TestCase):
    """M7-B1"""

    def setUp(self):
        self.r = m7_root("m7felt")
        self.addCleanup(self.r.close)
        self.r.start()

    @pending("M7-B1")
    def test_felt_publishes_a_flagged_message_and_records_an_atom(self):
        write_soul_settings(self.r.root, "berton", {"felt": True})
        out = self.r.text("felt", text="The way the tab strip breathes when a pin lands — I liked building that.")
        self.assertTrue(out.startswith("FELT-SENT: iter-"), out)
        message_id = out.split()[1]
        message = json.loads((Path(self.r.root) / ".runtime" / "electron_ui" / "outbox" / (message_id + ".json")).read_text())
        self.assertEqual(message["role"], "iter")
        self.assertIs(message["felt"], True)
        self.assertNotIn("card", message)
        self.assertIn("tab strip breathes", message["content"])
        atoms = self.r.call("read_atoms", {"prefix": "state:soul_felt:"})["atoms"]
        self.assertEqual(atoms["state:soul_felt:%s" % message_id].split()[:2], ["(soul-felt", '"berton"'])

    @pending("M7-B1")
    def test_long_notes_are_refused(self):
        out = self.r.text("felt", text="x" * 281)
        self.assertEqual(out, "ERROR: keep a felt note under 280 characters")
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_felt:"})["atoms"], {})

    @pending("M7-B1")
    def test_felt_atoms_live_only_in_the_soul_view(self):
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_felt:iter-x",
                                                 "atom": '(soul-felt "berton" 1700000000000)'}],
                                 "actor": "iter", "source": "felt"})
        for view in ("current", "full", "kb"):
            self.assertNotIn("1700000000000", self.r.call("query", {"code": "!(match &self (soul-felt $p $at) $at)", "view": view}, timeout=60)["result"], view)
        self.assertIn("1700000000000", self.r.call("query", {"code": "!(match &self (soul-felt $p $at) $at)", "view": "soul"}, timeout=60)["result"])


@unittest.skipUnless(NODE, "needs node")
class FeltBridgeTests(unittest.TestCase):
    """M7-B1 (bridge side): `felt: true` survives the journal; other values are dropped, never fatal."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name

    @pending("M7-B1")
    def test_felt_flag_is_kept_and_junk_is_dropped(self):
        f1 = {"schema_version": 1, "id": "iter-f1", "role": "iter", "at": 1700000000000, "content": "a note", "felt": True}
        f2 = {"schema_version": 1, "id": "iter-f2", "role": "iter", "at": 1700000000001, "content": "plain", "felt": "yes"}
        out = run_bridge(self.root, """
for (const [n, m] of [['f1.json', %s], ['f2.json', %s]]) { const p = path.join(bridge.paths.outboxDir, n); fs.writeFileSync(p, m); settle(p); }
bridge.pollNow();
out = { received: received.map((m) => [m.id, m.felt === undefined ? null : m.felt, m.content]),
        history: bridge.history().map((m) => [m.id, m.felt === undefined ? null : m.felt]) };
""" % (json.dumps(json.dumps(f1)), json.dumps(json.dumps(f2))))
        self.assertEqual(out["received"], [["iter-f1", True, "a note"], ["iter-f2", None, "plain"]])
        self.assertEqual(out["history"], [["iter-f1", True], ["iter-f2", None]])


@unittest.skipUnless(NODE and playwright_available(), "needs node and system Playwright")
class FeltRenderTests(unittest.TestCase):
    """M7-B2"""

    def _page(self, message, probe):
        setup = "window.__incoming = %s; window.__deliver && window.__deliver(window.__incoming);" % json.dumps(message)
        api = ("{onChatIncoming:(cb)=>{window.__deliver=cb;},chatHistory:()=>Promise.resolve([]),"
               "iterStatus:()=>Promise.resolve({running:false}),recentLog:()=>Promise.resolve([]),"
               "onUiResume:()=>{},onIterStatus:()=>{},loadSettings:()=>Promise.resolve({})}")
        return json.loads(run_playwright(sidebar_page_script(setup, probe, api)).strip().splitlines()[-1])

    @pending("M7-B2")
    def test_felt_message_renders_as_a_voice(self):
        out = self._page({"schema_version": 1, "id": "iter-f1", "role": "iter", "at": 1700000000000,
                          "content": "I liked *that* one.", "felt": True}, """(() => {
const row = document.querySelector('.msg.row.iter.felt'); if (!row) return {missing: true};
return { mark: row.querySelector('.felt-mark') && row.querySelector('.felt-mark').textContent,
         body: row.querySelector('.body.markdown').innerHTML, buttons: row.querySelectorAll('button').length,
         plainRows: document.querySelectorAll('.msg.row.iter:not(.felt)').length };
})()""")
        self.assertNotIn("missing", out, "felt row not rendered")
        self.assertEqual(out["mark"], "✦")
        self.assertIn("<em>that</em>", out["body"])
        self.assertEqual(out["buttons"], 0)

    def test_plain_message_renders_exactly_as_before(self):
        out = self._page({"schema_version": 1, "id": "iter-p1", "role": "iter", "at": 1700000000000, "content": "hello"}, """(() => {
const row = document.querySelector('.msg.row.iter'); return { felt: row.classList.contains('felt'), mark: !!row.querySelector('.felt-mark') };
})()""")
        self.assertEqual(out, {"felt": False, "mark": False})


class FeltOffTests(unittest.TestCase):
    """M7-B3: off means the tool is not even offered; on names the frequency."""

    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="m7feltoff-")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp, ignore_errors=True))

    def _presence(self, features, **profile):
        write_soul_settings(self.temp, "bright", features, **profile)
        tools = [tool_entry("felt"), tool_entry("card"), tool_entry("shell")]
        return run_transformation(self.temp, "soul_presence.py", tools=tools, env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})

    @pending("M7-B3")
    def test_felt_off_removes_the_tool_and_leaves_others(self):
        msgs, tools = self._presence({"forks": True, "felt": False})
        self.assertEqual([t["function"]["name"] for t in tools], ["card", "shell"])
        self.assertNotIn("felt", msgs[-1]["content"])

    @pending("M7-B3")
    def test_all_off_still_removes_felt_and_adds_no_block(self):
        msgs, tools = self._presence({f: False for f in FEATURES})
        self.assertEqual([t["function"]["name"] for t in tools], ["card", "shell"])
        self.assertEqual(msgs, [{"role": "system", "content": "base"}])

    @pending("M7-B3")
    def test_felt_on_keeps_the_tool_and_names_the_frequency(self):
        msgs, tools = self._presence({"felt": True}, frequency="whisper")
        self.assertEqual([t["function"]["name"] for t in tools], ["felt", "card", "shell"])
        self.assertIn("felt (a short note on what you found interesting; rarely)", msgs[-1]["content"])


if __name__ == "__main__":
    unittest.main()
