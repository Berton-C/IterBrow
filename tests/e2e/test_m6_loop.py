#!/usr/bin/env python3
"""M6-E1 invariant: a card goes out through the real loop, a click comes back as a choice
Iter sees in its next request, and the choice is recorded as a soul-choice atom.

Spec: docs/milestones/M6_soul_base.md. The click is simulated the way the sidebar does it
(bridge/chat_bridge.js sendChoice + bridge/soul_choice.js recordSoulChoice) because there is
no Electron here; the loop, the AtomSpace service and the channel are real.
"""
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import IterRun, send, tool, atomspace_call  # noqa: E402
from m6_support import pending, require_m6, NODE, REPO  # noqa: E402


class SoulBaseLoopTests(unittest.TestCase):
    def test_card_out_choice_in_atom_recorded(self):
        require_m6()
        script = [
            [tool("card", kind="fork", title="Which way?", body="Two poles.",
                  choices=[{"id": "a", "label": "Keep it playful"}, {"id": "b", "label": "Keep it obvious"}])],
            [send("CARD-DONE")],
            [send("LOOP-DONE")],
        ]
        with IterRun(script, name="m6") as run:
            run.say("show me a fork")
            run.wait_for_reply("CARD-DONE", timeout=300)
            outbox_entries = [m for m in run.experience() if m.get("role") == "tool" and "CARD-SENT" in m.get("content", "")]
            self.assertTrue(outbox_entries, "card tool did not report CARD-SENT")
            card_id = outbox_entries[0]["content"].split()[-1]

            # Simulate the sidebar: the bridge journals the choice and writes the inbox line; main.js records the atom.
            node_script = """
const { makeChatBridge } = require(%s);
const { recordSoulChoice } = require(%s);
const bridge = makeChatBridge(%s, () => {}, { pollIntervalMs: 60000, settleMs: 0 });
bridge.pollNow();
const card = bridge.history().find((m) => m.card && m.card.id === %s);
if (!card) { process.stdout.write(JSON.stringify({ error: 'card not in journal' })); process.exit(0); }
bridge.sendChoice(card.card.id, 'b', 'berton', 'Keep it obvious');
bridge.stop();
recordSoulChoice({ socket: %s, iterDir: %s, person: 'berton', kind: card.card.kind, cardId: card.card.id, pick: 'b', at: Date.now() })
  .then((r) => process.stdout.write(JSON.stringify(r)));
""" % tuple(json.dumps(x) for x in (str(REPO / "bridge" / "chat_bridge.js"), str(REPO / "bridge" / "soul_choice.js"),
                                     str(run.root), card_id, str(run.sock), str(run.root)))
            proc = subprocess.run([NODE, "-e", node_script], capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            result = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertTrue(result.get("written"), result)

            run.wait_for_reply("LOOP-DONE", timeout=300)
            # The loop may have woken for another reason and replied before reading the click;
            # the inbox line still wakes it again, so wait for it to land rather than racing it.
            line = "[choice card=%s pick=b by=berton] Keep it obvious" % card_id
            deadline = time.time() + 120
            while time.time() < deadline:
                seen = [m for m in run.experience() if m.get("role") == "user" and line in str(m.get("content", ""))]
                if seen:
                    break
                time.sleep(0.5)
            self.assertTrue(seen, "the choice line never reached the loop as a user message:\n" + run.read_log("iter.log")[-3000:])
            run.stop()
            requests = run.requests()
            atoms = run.atoms("state:soul_choice:")
            self.assertEqual(list(atoms), ["state:soul_choice:" + card_id])
            self.assertIn('"berton" "fork" "%s" "b"' % card_id, atoms["state:soul_choice:" + card_id])
            self.assertIn("## Soul (", requests[-1]["system"], "presence block is in the prompt with default features")


if __name__ == "__main__":
    unittest.main()
