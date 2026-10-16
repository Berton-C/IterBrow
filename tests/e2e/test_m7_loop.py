#!/usr/bin/env python3
"""M7-E1 invariant: two forks with patterns and museum ids go out through the real loop, the
picks come back, the reducer folds them into a taste belief (n=2) and casts the museum votes,
a felt note goes out as a voice, the learned line reaches the prompt, and nothing outside the
soul view moved.

Spec: docs/milestones/M7_soul_personality.md section E. The clicks are simulated the way the
sidebar does it (bridge sendChoice + soul_choice recordSoulChoice); the loop, the service and
the channel are real.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import IterRun, send, tool  # noqa: E402
from m7_support import pending, require_m7, museum_save, museum_get, stv, taste_n, NODE, REPO  # noqa: E402


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


class SoulPersonalityLoopTests(unittest.TestCase):
    def test_forks_become_taste_votes_and_a_learned_line(self):
        require_m7()
        script = [
            [tool("card", kind="fork", title="Header?", body="Two poles.",
                  choices=[{"id": "a", "label": "Playful", "pattern": "CreativeTranscendence", "museum_id": "{{museum_a}}"},
                           {"id": "b", "label": "On time", "pattern": "TimeCoherence", "museum_id": "{{museum_b}}"}])],
            [send("CARD-1-DONE")],
            # A send waits for input: each click below wakes exactly one request.
            [tool("card", kind="fork", title="Footer?", body="Two poles again.",
                  choices=[{"id": "a", "label": "Playful", "pattern": "CreativeTranscendence", "museum_id": "{{museum_c}}"},
                           {"id": "b", "label": "On time", "pattern": "TimeCoherence", "museum_id": "{{museum_d}}"}])],
            [send("CARD-2-DONE")],
            [tool("felt", text="Building both headers side by side was the fun part today.")],
            [send("FELT-DONE")],
            [send("LOOP-DONE")],
        ]
        run = IterRun(script, name="m7")
        ids = {name: museum_save(run.root, name) for name in ("museum_a", "museum_b", "museum_c", "museum_d")}
        text = json.dumps(script)
        for name, comp_id in ids.items():
            text = text.replace("{{%s}}" % name, comp_id)
        run.script_path.write_text(text, encoding="utf-8")
        runtime = run.root / ".runtime"
        (runtime / "soul_settings.json").write_text(json.dumps({"schema_version": 1, "person": "berton",
                                                                 "people": {"berton": {"features": {"forks": True, "felt": True}}}}))
        with run:
            kb_before = len(run.atoms("state:kb_statement:"))

            def card_id_after(marker):
                run.wait_for_reply(marker, timeout=300)
                sent = [m for m in run.experience() if m.get("role") == "tool" and "CARD-SENT" in m.get("content", "")]
                return re.search(r"CARD-SENT: (card-[0-9a-f]{12})", sent[-1]["content"]).group(1)

            first = card_id_after("CARD-1-DONE")
            self.assertEqual(sorted(run.atoms("state:soul_card_choice:%s:" % first)), ["state:soul_card_choice:%s:a" % first, "state:soul_card_choice:%s:b" % first])
            self.assertIn(ids["museum_a"], run.atoms("state:soul_card_choice:%s:" % first)["state:soul_card_choice:%s:a" % first])
            click(run, first, "a", "Playful")
            second = card_id_after("CARD-2-DONE")
            self.assertNotEqual(first, second)
            click(run, second, "a", "Playful")
            run.wait_for_reply("FELT-DONE", timeout=300)
            run.say("thanks")
            run.wait_for_reply("LOOP-DONE", timeout=300)
            run.stop()

            # Reducer: seen markers, taste n=2, votes cast.
            self.assertEqual(sorted(run.atoms("state:soul_taste_seen:")), sorted("state:soul_taste_seen:%s" % c for c in (first, second)))
            taste = run.atoms("state:soul_taste:berton:")["state:soul_taste:berton:CreativeTranscendence:TimeCoherence"]
            self.assertEqual(taste_n(taste), 2)
            f, c = stv(taste)
            self.assertEqual(f, 1.0)
            self.assertAlmostEqual(c, 2 / 3, places=2)
            self.assertEqual(museum_get(run.root, ids["museum_a"])["vote"], "keep")
            self.assertEqual(museum_get(run.root, ids["museum_b"])["vote"], "reject")
            self.assertEqual(museum_get(run.root, ids["museum_c"])["vote"], "keep")
            self.assertEqual(museum_get(run.root, ids["museum_d"])["vote"], "reject")

            # Felt: a flagged outbox message and its atom.
            felt_messages = [json.loads(p.read_text()) for p in run.outbox.glob("*.json")]
            felt_messages = [m for m in felt_messages if m.get("felt") is True]
            self.assertEqual(len(felt_messages), 1)
            self.assertIn("fun part", felt_messages[0]["content"])
            self.assertEqual(len(run.atoms("state:soul_felt:")), 1)

            # The learned line reached a later request (one-cycle lag allowed).
            systems = [r["system"] for r in run.requests()]
            self.assertTrue(any("Learned: you've leaned CreativeTranscendence over TimeCoherence (2 of 2 forks)" in s for s in systems),
                            "no learned line in any request:\n" + "\n---\n".join(s[-600:] for s in systems[-3:]))

            # Isolation: nothing outside the soul view moved; other views never see soul atoms.
            # NACE learns tool efficacy from the card/felt calls themselves (that is its job), so its
            # count may grow; what must hold is that no Soul atom lands outside state:soul_* and the
            # kb is untouched. (The reducer's own NACE/kb isolation is checked in test_m7_taste A2.)
            soul_heads = ("(soul-taste", "(soul-card", "(soul-felt", "(soul-dismissed", "(soul-choice")
            everything = {**run.atoms("state:"), **run.atoms("event:")}
            leaked = [key for key, atom in everything.items()
                      if not key.startswith("state:soul_") and atom.lstrip().startswith(soul_heads)]
            self.assertEqual(leaked, [])
            nace_atoms = run.atoms("state:nace_belief:")
            self.assertFalse([a for a in nace_atoms.values() if "soul" in a.lower()], "no Soul content in NACE beliefs")
            self.assertEqual(len(run.atoms("state:kb_statement:")), kb_before)
            from harness import atomspace_call
            for view in ("current", "full", "kb"):
                out = atomspace_call(run.sock, "query", {"code": "!(match &self (soul-taste $p $a $b $t $n) $a)", "view": view}, timeout=120)["result"]
                self.assertNotIn("CreativeTranscendence", out, view)


if __name__ == "__main__":
    unittest.main()
