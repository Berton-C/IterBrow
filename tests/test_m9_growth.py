#!/usr/bin/env python3
"""M9-B1..B3: service before growth, with a voice — the deferral asks, the answer is honored,
and without the flag nothing changes.

Spec: docs/milestones/M9_soul_wonder_ally.md section B. auto_improve.py uses paths relative to the
cwd (ITER_DIR), so each test runs it in a subprocess from a fresh root with a tool_reliability.json
that scores enough pain (three tools at f=0.1, c=0.9, 5 calls -> 4.05 >= 3.0).
"""
import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m9_support import pending, m9_root, require_m9, run_transformation, seed_topic_card, seed_pick  # noqa: E402

PAINFUL = {"shell": {"f": 0.1, "c": 0.9, "calls": 5, "failures": 4},
           "browser_click": {"f": 0.1, "c": 0.9, "calls": 5, "failures": 4},
           "remember": {"f": 0.1, "c": 0.9, "calls": 5, "failures": 4}}


class GrowthVoiceTests(unittest.TestCase):
    def setUp(self):
        self.r = m9_root("m9growth")
        self.addCleanup(self.r.close)
        self.r.start()

    def _prepare(self, pain=True, deferred=True):
        root = Path(self.r.root)
        (root / "memory").mkdir(exist_ok=True)
        runtime = root / "transformations" / ".runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "tool_reliability.json").write_text(json.dumps(PAINFUL if pain else {}))
        for name in (".improve_needed", ".improve_pending", ".improve_cooldown", ".growth_asked"):
            (root / "memory" / name).unlink(missing_ok=True)
        flag = root / "memory" / ".service_before_growth_flag.json"
        if deferred:
            flag.write_text(json.dumps({"expires_at": time.time() + 3600, "reason": "send discipline"}))
        else:
            flag.unlink(missing_ok=True)
        return root

    def _run(self):
        msgs, _ = run_transformation(self.r.root, "auto_improve.py",
                                     messages=[{"role": "system", "content": "base"}, {"role": "user", "content": "hi"}],
                                     env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        return msgs[0]["content"]

    def test_deferred_pain_becomes_a_question_asked_once_a_day(self):
        root = self._prepare()
        content = self._run()
        self.assertTrue((root / "memory" / ".improve_pending").exists(), "the proposal waits in .improve_pending")
        self.assertFalse((root / "memory" / ".improve_needed").exists(), "deferred: never .improve_needed")
        self.assertIn("topic growth", content)
        self.assertIn("now / later", content)
        self.assertIn("I'd like to work on", content)
        self.assertTrue((root / "memory" / ".growth_asked").exists())
        second = self._run()
        self.assertNotIn("I'd like to work on", second, "asked once per 24 h")
        self.assertIn("deferred", second.lower(), "the plain deferral note still stands")
        # An outstanding growth card also silences the ask, even after the day.
        (root / "memory" / ".growth_asked").write_text(str(time.time() - 25 * 3600))
        seed_topic_card(self.r, "card-g1", "growth", choices=("now", "later"))
        self.assertNotIn("I'd like to work on", self._run())

    def test_now_lets_the_proposal_through_and_later_keeps_the_deferral(self):
        root = self._prepare()
        self._run()
        flag_mtime = (root / "memory" / ".service_before_growth_flag.json").stat().st_mtime
        seed_topic_card(self.r, "card-g2", "growth", choices=("now", "later"))
        # Just after the deferral began (a real click is never in the future; +5 s here would still
        # postdate the flag the "later" half below rewrites a moment later).
        seed_pick(self.r, "card-g2", "now", at=int(flag_mtime * 1000) + 1)
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        content = self._run()
        self.assertTrue((root / "memory" / ".improve_needed").exists(), "now: the proposal goes through")
        self.assertFalse((root / "memory" / ".improve_pending").exists())
        self.assertTrue((root / "memory" / ".improve_cooldown").exists())
        self.assertIn("Pain score", content)
        self.assertTrue((root / "memory" / ".service_before_growth_flag.json").exists(), "the flag is not auto_improve's to touch")
        # later: deferred stays, no re-ask inside the day.
        root = self._prepare()
        self._run()
        seed_topic_card(self.r, "card-g3", "growth", choices=("now", "later"), at=int(time.time() * 1000))
        seed_pick(self.r, "card-g3", "later", at=int(time.time() * 1000) + 1)
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        content = self._run()
        self.assertFalse((root / "memory" / ".improve_needed").exists())
        self.assertNotIn("I'd like to work on", content)
        self.assertIn("deferred", content.lower())

    def test_a_stale_now_from_before_this_deferral_does_not_count(self):
        root = self._prepare()
        seed_topic_card(self.r, "card-g4", "growth", choices=("now", "later"), at=1)
        seed_pick(self.r, "card-g4", "now", at=2)  # long before the flag was written
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        self._run()
        self.assertFalse((root / "memory" / ".improve_needed").exists())
        self.assertTrue((root / "memory" / ".improve_pending").exists())

    def test_without_the_flag_the_old_path_is_unchanged(self):
        root = self._prepare(deferred=False)
        content = self._run()
        self.assertTrue((root / "memory" / ".improve_needed").exists())
        self.assertFalse((root / "memory" / ".improve_pending").exists())
        self.assertFalse((root / "memory" / ".growth_asked").exists())
        self.assertIn("Pain score", content)
        self.assertNotIn("topic growth", content)
        root = self._prepare(pain=False, deferred=False)
        content = self._run()
        self.assertFalse((root / "memory" / ".improve_needed").exists())
        self.assertEqual(content, "base")


if __name__ == "__main__":
    unittest.main()
