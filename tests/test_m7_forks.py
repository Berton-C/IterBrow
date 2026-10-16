#!/usr/bin/env python3
"""M7-D1..D2: forks as variants — a pick casts the museum votes; the recipe is in the prompt,
the mechanics in the tool.

Spec: docs/milestones/M7_soul_personality.md section D.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m7_support import (pending, m7_root, seed_choice, run_transformation, write_soul_settings,  # noqa: E402
                        museum_save, museum_get, ITER_SRC)


class VoteTests(unittest.TestCase):
    """M7-D1"""

    def setUp(self):
        self.r = m7_root("m7vote")
        self.addCleanup(self.r.close)
        self.r.start()

    def _reduce(self):
        return run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})

    @pending("M7-D1")
    def test_pick_keeps_the_picked_variant_and_rejects_the_other(self):
        a, b = museum_save(self.r.root, "playful header"), museum_save(self.r.root, "plain header")
        seed_choice(self.r, "berton", "fork", "card-1", "b",
                    [("a", "CreativeTranscendence", a), ("b", "TimeCoherence", b)])
        self._reduce()
        self.assertEqual(museum_get(self.r.root, b)["vote"], "keep")
        self.assertEqual(museum_get(self.r.root, a)["vote"], "reject")
        self.assertIsNotNone(museum_get(self.r.root, a), "reject is a vote, not a delete")
        # Taste was folded in the same pass.
        tastes = self.r.call("read_atoms", {"prefix": "state:soul_taste:berton:"})["atoms"]
        self.assertIn("state:soul_taste:berton:TimeCoherence:CreativeTranscendence", tastes)

    @pending("M7-D1")
    def test_dismiss_casts_nothing(self):
        a, b = museum_save(self.r.root, "x"), museum_save(self.r.root, "y")
        seed_choice(self.r, "berton", "fork", "card-2", "dismiss", [("a", None, a), ("b", None, b)])
        self._reduce()
        self.assertIsNone(museum_get(self.r.root, a)["vote"])
        self.assertIsNone(museum_get(self.r.root, b)["vote"])

    @pending("M7-D1")
    def test_missing_museum_id_is_skipped_not_fatal(self):
        a = museum_save(self.r.root, "only one exists")
        seed_choice(self.r, "berton", "fork", "card-3", "a", [("a", None, a), ("b", None, "comp-000000000000")])
        self._reduce()
        self.assertEqual(museum_get(self.r.root, a)["vote"], "keep")
        self.assertIn("state:soul_taste_seen:card-3", self.r.call("read_atoms", {"prefix": "state:soul_taste_seen:"})["atoms"])

    @pending("M7-D1")
    def test_votes_are_cast_once(self):
        a, b = museum_save(self.r.root, "x"), museum_save(self.r.root, "y")
        seed_choice(self.r, "berton", "fork", "card-4", "a", [("a", None, a), ("b", None, b)])
        self._reduce()
        # A later manual reversal must survive the next reduce (no re-vote on a seen choice).
        import subprocess
        code = ("import sys, os; sys.path.insert(0, os.path.join(sys.argv[1], 'tools')); import _component_museum as m;"
                "m.update_vote(sys.argv[2], 'reject')")
        subprocess.run([sys.executable, "-c", code, str(self.r.root), a], cwd=str(self.r.root),
                       env=dict(os.environ, ITER_DIR=str(self.r.root)), check=True, timeout=60)
        self._reduce()
        self.assertEqual(museum_get(self.r.root, a)["vote"], "reject")


class RecipeTests(unittest.TestCase):
    """M7-D2"""

    @pending("M7-D2")
    def test_presence_gives_the_recipe_only_when_forks_is_on(self):
        temp = tempfile.mkdtemp(prefix="m7recipe-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        write_soul_settings(temp, "berton", {"forks": True})
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        content = msgs[-1]["content"]
        for word in ("browser_tab_variants", "pattern", "museum_id", "links"):
            self.assertIn(word, content, word)
        self.assertLess(len(content) - len("base"), 900)
        write_soul_settings(temp, "berton", {"forks": False, "brief": True})
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        self.assertNotIn("browser_tab_variants", msgs[-1]["content"])

    @pending("M7-D2")
    def test_card_tool_description_mentions_the_metadata_and_stays_short(self):
        from tools._metadata_static import static_tool_metadata
        description = static_tool_metadata(ITER_SRC / "tools" / "card.py")["description"]
        self.assertIn("pattern", description)
        self.assertIn("museum_id", description)
        self.assertLessEqual(len(description), 500)


if __name__ == "__main__":
    unittest.main()
