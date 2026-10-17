#!/usr/bin/env python3
"""M8-E1 invariant: quiet leaves no Soul in the request; a mode switch shows up next request; a
margin message goes through the real bridge into Iter's experience; the soul-absent walk records
and changes nothing; museum night reads the votes; no Soul atom lands outside state:soul_*.

Spec: docs/milestones/M8_soul_presence.md section E. The loop, the service and the channel are
real; the margin is simulated the way main.js does it (bridge sendMargin + recordSoulMargin).
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
from m8_support import pending, require_m8, museum_save, museum_get, dir_digest, make_app_dir, NODE, REPO  # noqa: E402

MOMENTS = [{"where": "the empty-state screen", "what": "a blank table", "pattern": "WonderPreservation"},
           {"where": "the save button", "what": "it saves silently", "pattern": "ConnectionDepth"}]


def margin(run, payload, person="berton"):
    node_script = """
const { makeChatBridge } = require(%s);
const { recordSoulMargin } = require(%s);
const bridge = makeChatBridge(%s, () => {}, { pollIntervalMs: 60000, settleMs: 0 });
const message = bridge.sendMargin(%s);
bridge.stop();
recordSoulMargin({ socket: %s, person: %s, app: message.margin.app, intent: message.margin.intent, messageId: message.id, at: message.at })
  .then((r) => process.stdout.write(JSON.stringify({ ...r, content: message.content })));
""" % tuple(json.dumps(x) for x in (str(REPO / "bridge" / "chat_bridge.js"), str(REPO / "bridge" / "soul_choice.js"),
                                     str(run.root), payload, str(run.sock), person))
    proc = subprocess.run([NODE, "-e", node_script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


class SoulPresenceLoopTests(unittest.TestCase):
    def test_quiet_modes_margin_critique_and_museum_through_the_real_loop(self):
        require_m8()
        script = [
            [send("QUIET-SEEN")],
            [tool("soul_mode", mode="jam")],
            [send("JAM-SET")],
            [send("MARGIN-SEEN")],
            [tool("soul_absent_test", app="crm", moments=MOMENTS)],
            [tool("museum_night")],
            [send("WALK-DONE")],
        ]
        run = IterRun(script, name="m8")
        kept, rejected = museum_save(run.root, "playful header"), museum_save(run.root, "plain header")
        app = make_app_dir(run.root, "crm")
        app_before = dir_digest(app)
        (run.root / ".runtime" / "soul_settings.json").write_text(json.dumps({
            "schema_version": 1, "person": "berton",
            "people": {"berton": {"features": {"forks": True, "felt": True, "margin": True, "brief": True}, "mode": "quiet"}}}))
        with run:
            # Seed one M7-style fork so museum night has a kept and a rejected piece.
            atomspace_call(run.sock, "transact", {"operations": [
                {"op": "upsert", "key": "state:soul_card:card-1", "atom": '(soul-card "card-1" "fork" "berton" 1700000000000)'},
                {"op": "upsert", "key": "state:soul_card_choice:card-1:a", "atom": '(soul-card-choice "card-1" "a" CreativeTranscendence "%s")' % kept},
                {"op": "upsert", "key": "state:soul_card_choice:card-1:b", "atom": '(soul-card-choice "card-1" "b" TimeCoherence "%s")' % rejected},
                {"op": "upsert", "key": "state:soul_choice:card-1", "atom": '(soul-choice "berton" "fork" "card-1" "a" 1700000000001)'},
            ], "actor": "test", "source": "test"})
            run.say("hello")
            run.wait_for_reply("QUIET-SEEN", timeout=300)
            first = run.requests()[0]
            self.assertNotIn("## Soul (", first["system"], "quiet: no Soul block")
            self.assertNotIn('"name": "felt"', json.dumps(first.get("tools", [])), "quiet: no felt tool")

            run.say("let's jam")
            run.wait_for_reply("JAM-SET", timeout=300)
            self.assertIn("Mode: jam", run.requests()[-1]["system"])
            saved = json.loads((run.root / ".runtime" / "soul_settings.json").read_text())
            self.assertEqual(saved["people"]["berton"]["mode"], "jam")

            sent = margin(run, {"app": "crm", "tab": 3, "intent": "ask", "text": "why is this grey?",
                                "element": {"selector": "p.note", "tag": "p", "text": "hello"}})
            self.assertTrue(sent["written"], sent)
            run.wait_for_reply("MARGIN-SEEN", timeout=300)
            # The loop may wake and reply before it reads the inbox line; the line still wakes it
            # again, so wait for it to land rather than racing the reply (as the M6 test does).
            line = "[margin app=crm tab=3 intent=ask element=p.note] why is this grey?"
            deadline = time.time() + 120
            while time.time() < deadline:
                seen = [m for m in run.experience() if m.get("role") == "user" and line in str(m.get("content", ""))]
                if seen:
                    break
                time.sleep(0.5)
            self.assertTrue(seen, "the margin line never reached the loop:\n" + run.read_log("iter.log")[-3000:])
            self.assertEqual(len(run.atoms("state:soul_margin:")), 1)

            run.say("walk it")
            run.wait_for_reply("WALK-DONE", timeout=300)
            run.stop()
            results = [m["content"] for m in run.experience() if m.get("role") == "tool"]
            walk = next(c for c in results if "Soul-absent walk of crm" in c)
            self.assertIn("gap (WonderPreservation):", walk)
            self.assertTrue(walk.rstrip().endswith("Nothing was changed."))
            self.assertEqual(dir_digest(app), app_before)
            critiques = run.atoms("state:soul_critique:")
            self.assertEqual(len(critiques), 1)
            self.assertIn('"crm" "berton" 2 ', list(critiques.values())[0])
            night = next(c for c in results if "Museum night (" in c)
            self.assertIn("%s playful header" % kept, night[night.index("Kept:"):night.index("Rejected:")])
            self.assertIn("%s plain header" % rejected, night[night.index("Rejected:"):])
            # The reducer ran on the seeded fork during the loop, so the votes are real; museum night
            # must not have changed them.
            self.assertEqual(museum_get(run.root, kept)["vote"], "keep")
            self.assertEqual(museum_get(run.root, rejected)["vote"], "reject")
            # Isolation: no Soul atom outside state:soul_*.
            heads = ("(soul-margin", "(soul-critique", "(soul-taste", "(soul-card", "(soul-choice", "(soul-felt", "(soul-dismissed")
            everything = {**run.atoms("state:"), **run.atoms("event:")}
            leaked = [k for k, a in everything.items() if not k.startswith("state:soul_") and a.lstrip().startswith(heads)]
            self.assertEqual(leaked, [])
            for view in ("current", "full", "kb"):
                out = atomspace_call(run.sock, "query", {"code": "!(match &self (soul-critique $a $p $n $at) $a)", "view": view}, timeout=120)["result"]
                self.assertNotIn("crm", out, view)


if __name__ == "__main__":
    unittest.main()
