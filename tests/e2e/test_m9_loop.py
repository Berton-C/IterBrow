#!/usr/bin/env python3
"""M9-E1 invariant: a kept idea comes back once as an offer, the pick folds it, and it never comes
back; the browsing block appears only with the ally on; nothing leaks outside state:soul_*.

Spec: docs/milestones/M9_soul_wonder_ally.md section E. The loop, the service and the channel are
real; the click is simulated the way the sidebar does it.
"""
import json
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import IterRun, send, tool, atomspace_call  # noqa: E402
from m9_support import pending, require_m9, make_app_dir, write_browsing_log, wonders, now_ms, NODE, REPO  # noqa: E402


def click(run, card_id, pick, label, person="berton"):
    node_script = """
const { makeChatBridge } = require(%s);
const { recordSoulChoice } = require(%s);
const bridge = makeChatBridge(%s, () => {}, { pollIntervalMs: 60000, settleMs: 0 });
bridge.pollNow();
const card = bridge.history().find((m) => m.card && m.card.id === %s);
if (!card) { process.stdout.write(JSON.stringify({ error: 'card not in journal' })); process.exit(0); }
bridge.sendChoice(card.card.id, %s, %s, %s);
bridge.stop();
recordSoulChoice({ socket: %s, iterDir: %s, person: %s, kind: card.card.kind, cardId: card.card.id, pick: %s, at: Date.now() })
  .then((r) => process.stdout.write(JSON.stringify(r)));
""" % tuple(json.dumps(x) for x in (str(REPO / "bridge" / "chat_bridge.js"), str(REPO / "bridge" / "soul_choice.js"),
                                     str(run.root), card_id, pick, person, label, str(run.sock), str(run.root), person, pick))
    proc = subprocess.run([NODE, "-e", node_script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result.get("written"), result
    return result


class WonderAllyLoopTests(unittest.TestCase):
    class _Wonders:
        def __init__(self, run):
            self.run = run

        def call(self, method, params):
            return atomspace_call(self.run.sock, method, params)

    @pending("M9-E1")
    def test_wonder_round_trip_and_browsing_block(self):
        require_m9()
        script = [
            [tool("wonder", action="add", app="crm", idea="a timeline of every conversation")],
            [send("KEPT")],
            [tool("card", kind="offer", title="One from the jar", body="A timeline of every conversation?", topic="wonder:{{wonder_id}}",
                  choices=[{"id": "take", "label": "Take it"}, {"id": "keep", "label": "Keep it"}, {"id": "let_go", "label": "Let it go"}])],
            [send("OFFERED")],
            [send("TAKEN-SEEN")],
            [send("BROWSE-SEEN")],
        ]
        run = IterRun(script, name="m9")
        make_app_dir(run.root, "crm")
        (run.root / ".runtime" / "soul_settings.json").write_text(json.dumps({
            "schema_version": 1, "person": "berton",
            "people": {"berton": {"features": {"forks": True, "wonder": True, "browsing_ally": False}, "frequency": "chatty"}}}))
        with run:
            run.say("keep this idea")
            run.wait_for_reply("KEPT", timeout=300)
            kept = [m["content"] for m in run.experience() if m.get("role") == "tool" and "WONDER-KEPT" in m.get("content", "")]
            self.assertTrue(kept)
            wid = re.search(r"WONDER-KEPT: (wonder-[0-9a-f]{8})", kept[-1]).group(1)  # the fake model fills {{wonder_id}} from this

            run.say("anything from the jar?")
            run.wait_for_reply("OFFERED", timeout=300)
            offered_requests = [r for r in run.requests() if "## Wonder" in r["system"]]
            self.assertTrue(offered_requests, "the offer never reached a request")
            self.assertIn("topic wonder:%s" % wid, offered_requests[0]["system"])
            sent = [m for m in run.experience() if m.get("role") == "tool" and "CARD-SENT" in m.get("content", "")]
            card_id = re.search(r"CARD-SENT: (card-[0-9a-f]{12})", sent[-1]["content"]).group(1)
            click(run, card_id, "take", "Take it")
            run.wait_for_reply("TAKEN-SEEN", timeout=300)
            deadline = time.time() + 120
            while time.time() < deadline and wonders(self._Wonders(run)).get(wid) != "taken":
                time.sleep(0.5)
            self.assertEqual(wonders(self._Wonders(run)).get(wid), "taken")
            self.assertIn("state:soul_topic_pick:wonder:%s" % wid, run.atoms("state:soul_topic_pick:"))

            # The browsing block needs the ally on; with it off there is no block and no log.
            self.assertFalse((run.root / ".runtime" / "browsing_log.jsonl").exists())
            (run.root / ".runtime" / "soul_settings.json").write_text(json.dumps({
                "schema_version": 1, "person": "berton",
                "people": {"berton": {"features": {"forks": True, "wonder": True, "browsing_ally": True}, "frequency": "chatty"}}}))
            write_browsing_log(run.root, [{"at": now_ms() - 3 * 60000, "tab": 1, "domain": "docs.python.org", "title": "asyncio"}])
            run.say("what am I doing?")
            run.wait_for_reply("BROWSE-SEEN", timeout=300)
            run.stop()
            last = run.requests()[-1]["system"]
            self.assertIn("## Browsing (ally)", last)
            self.assertIn("docs.python.org", last)
            self.assertNotIn("## Wonder", last, "a taken idea never comes back")
            heads = ("(soul-wonder", "(soul-topic-pick", "(soul-card-topic", "(soul-taste", "(soul-card", "(soul-choice")
            everything = {**run.atoms("state:"), **run.atoms("event:")}
            leaked = [k for k, a in everything.items() if not k.startswith("state:soul_") and a.lstrip().startswith(heads)]
            self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
