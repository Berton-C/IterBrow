#!/usr/bin/env python3
"""experience.json rotation into the exact archive (BUG-6)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_episodic_memory import EpisodicCase, user, send_exchange  # noqa: E402  (sets sys.path)
from iterbrow_runtime.request_budget import rotate_experience  # noqa: E402


def stamp(c):
    return "2026-10-01 %02d:%02d:%02d" % (c // 3600, (c // 60) % 60, c % 60)


def start_task(call_id, ts, original):
    return [{"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function", "function": {"name": "start_new_task", "arguments": json.dumps(
                    {"new_work": True, "originalUserMessage": original})}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "Step %s: SUCCESS, RETURN: New task started at x" % ts}]


class RotateExperienceTests(EpisodicCase):
    def test_bug6_ordinary_conversation_rotates(self):
        experience, archived = [], []
        for c in range(300):
            experience = rotate_experience(experience, 100, 80, archive=archived.append)
            experience.append(user(stamp(c), "unrelated question %d" % c))
            experience += send_exchange("c%d" % c, stamp(c), "answer %d" % c)
        self.assertLess(len(experience), 103)
        self.assertTrue(archived)
        kept_and_archived = sum(len(batch) for batch in archived) + len(experience)
        self.assertEqual(kept_and_archived, 900)   # nothing lost: every message archived or kept

    def test_bug6_rotation_is_batched_to_the_retain_size(self):
        experience, archived = [], []
        for c in range(300):
            experience = rotate_experience(experience, 100, 80, archive=archived.append)
            experience.append(user(stamp(c), "q%d" % c))
            experience += send_exchange("c%d" % c, stamp(c), "a")
        self.assertTrue(archived)
        # One archive batch per ~20 messages (cap 100 -> retain 80), not one per cycle.
        self.assertTrue(all(len(batch) >= 15 for batch in archived), [len(b) for b in archived])

    def test_bug6_paraphrased_task_anchor_matches_casefolded_and_whitespace_normalised(self):
        experience = []
        for c in range(200):
            experience = rotate_experience(experience, 100, 80, archive=lambda m: None)
            experience.append(user(stamp(c), "Please  fix tab %d" % c))
            experience += start_task("t%d" % c, stamp(c), "please fix\ntab %d" % c)
        self.assertLess(len(experience), 103)

    def test_bug6_active_task_since_its_anchor_is_never_rotated(self):
        experience = [user(stamp(0), "Build the importer")] + start_task("t0", stamp(0), "build the importer")
        for c in range(1, 120):   # long-running task with clarifications
            experience = rotate_experience(experience, 100, 80, archive=lambda m: None)
            experience += send_exchange("c%d" % c, stamp(c), "progress %d" % c)
            if c % 40 == 0:
                experience.append(user(stamp(c), "also handle case %d" % c))
        self.assertIn("Build the importer", experience[0]["content"])


    # Review 3 M2 -----------------------------------------------------------
    def runner(self, ts, text):
        return {"role": "user", "content": "Step %s: (autonomous) %s" % (ts, text), "_iter_runner": True}

    def test_retained_history_starts_with_the_user_message_of_a_turn(self):
        from iterbrow_runtime.request_budget import is_user_input
        experience = []
        for c in range(140):  # the reviewer's shape: a request every 10 cycles, autonomous continuations between
            experience.append(user(stamp(c), "user request %d" % c) if c % 10 == 0 else self.runner(stamp(c), "go on"))
            experience += send_exchange("c%d" % c, stamp(c), "msg %d" % c)
        archived = []
        kept = rotate_experience(experience, 100, 80, archive=archived.append)
        self.assertLess(len(kept), len(experience))
        self.assertTrue(is_user_input(kept[0]), kept[0])
        self.assertEqual(archived[0] + kept, experience)
        self.assertIn("user request 130", json.dumps(kept))

    def test_start_new_task_request_is_kept_until_the_hard_maximum(self):
        experience = [user(stamp(0), "Build the importer")] + start_task("t0", stamp(0), "build the importer")
        for c in range(1, 200):
            experience += send_exchange("c%d" % c, stamp(c), "progress %d" % c)
            if c % 40 == 0:
                experience.append(user(stamp(c), "also handle case %d" % c))
        kept = rotate_experience(experience, 100, 80, archive=lambda m: None, hard_maximum=500)
        self.assertEqual(kept, experience, "below the hard maximum the task's request stays")
        for c in range(200, 400):
            experience += send_exchange("c%d" % c, stamp(c), "progress %d" % c)
            if c % 40 == 0:
                experience.append(user(stamp(c), "also handle case %d" % c))
        archived = []
        kept = rotate_experience(experience, 100, 80, archive=archived.append, hard_maximum=500)
        self.assertLessEqual(len(kept), 500)
        self.assertEqual(kept[0]["role"], "user")
        self.assertNotIn("_iter_runner", kept[0])
        self.assertEqual(archived[0] + kept, experience)


if __name__ == "__main__":
    unittest.main()
