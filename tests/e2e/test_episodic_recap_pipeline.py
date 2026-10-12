#!/usr/bin/env python3
"""Invariant: the episodic pipeline works end to end through the real loop.

history.metta grows past the recap threshold -> the Recap Request is in the
system prompt the model receives -> the agent records an episode the way the
request describes (record_episode) -> on the next request the cursor has
advanced, the request is gone, the tier files exist and the tier pyramid in
the system prompt contains the newest episode."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import IterRun, send, tool

# Each scripted turn makes three sends (6 history records), so request 4 is the
# first with >= 20 unsummarized records (1 user message + 6 per turn).
RECORD_TURN = 5


class EpisodicRecapPipelineTests(unittest.TestCase):
    def test_recap_request_reaches_model_and_recorded_episode_reaches_tier_pyramid(self):
        script = [[send("tick-%d-%s" % (i, part)) for part in "abc"] for i in range(RECORD_TURN)]
        script.append([tool("record_episode", summary="E2E-EPISODE-SUMMARY of the tick conversation")])
        script.append([send("after-episode")])
        with IterRun(script, name="recap") as run:
            run.say("count ticks for me")
            requests = run.wait_for_requests(RECORD_TURN + 2, timeout=420)
            run.wait_for_reply("after-episode", timeout=120)
            run.stop()
            log = run.read_log("iter.log")

            asked = [r["n"] for r in requests[:RECORD_TURN + 1] if "## Recap Request" in r["system"]]
            self.assertTrue(asked, "no Recap Request reached the model before the episode turn:\n" + log[-3000:])
            first = next(r for r in requests if r["n"] == asked[0])
            self.assertIn("record_episode(", first["system"])
            self.assertIn("episode_0001.json", first["system"])
            self.assertIn('episodes(time_string="', first["system"])
            self.assertIn("record_episode", first["tools"])

            results = {m["tool_call_id"]: m["content"] for m in run.experience() if m["role"] == "tool"}
            recorded = results.get("call_%d_0" % RECORD_TURN, "")
            self.assertIn("SUCCESS", recorded, recorded)

            episode = json.loads(run.read("memory/recap/episode_0001.json"))
            self.assertEqual(episode["e"], 1)
            self.assertIn("E2E-EPISODE-SUMMARY", episode["s"])
            self.assertEqual(episode["lines"][0], 1)
            self.assertEqual(int(run.read("memory/recap/.recap_state")), episode["lines"][1])
            self.assertGreaterEqual(episode["lines"][1], 20)

            after = next(r for r in requests if r["n"] == RECORD_TURN + 1)
            self.assertNotIn("## Recap Request", after["system"])
            self.assertFalse((run.root / "memory/recap/.recap_needed").exists())
            for name in ("tier3", "tier4", "tier5"):
                self.assertTrue((run.root / "memory/tiers" / (name + ".txt")).exists(), name)
            self.assertIn("## Tiered Memory Pyramid", after["system"])
            pyramid = after["system"][after["system"].rfind("## Tiered Memory Pyramid"):]
            self.assertIn("E1: E2E-EPISODE-SUMMARY", pyramid)
            self.assertIn("1 episodes recorded, E1 to E1.", pyramid)


if __name__ == "__main__":
    unittest.main()
