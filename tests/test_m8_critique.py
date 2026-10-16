#!/usr/bin/env python3
"""M8-B1..C1: the soul-absent walk (critique) and museum night.

Spec: docs/milestones/M8_soul_presence.md sections B and C.
"""
import json
import os
import re
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m8_support import (pending, m8_root, write_soul_settings, dir_digest, make_app_dir, museum_save, museum_get,  # noqa: E402
                        seed_choice, run_transformation, ITER_SRC)

MOMENTS = [{"where": "the empty-state screen", "what": "a blank table with no invitation to add the first row",
            "pattern": "WonderPreservation"},
           {"where": "the save button", "what": "it saves silently; nothing acknowledges the person", "pattern": "ConnectionDepth"}]


class SoulAbsentTests(unittest.TestCase):
    """M8-B1"""

    def setUp(self):
        self.r = m8_root("m8critique")
        self.addCleanup(self.r.close)
        self.r.start()

    @pending("M8-B1")
    def test_walk_cites_gap_signatures_from_the_lens_and_changes_nothing(self):
        write_soul_settings(self.r.root, "berton", {"brief": True}, mode="critique")
        app = make_app_dir(self.r.root, "crm")
        self.r.text("brief", app="crm", for_whom="Berton, keeping track of people he cares about", flourishing="he reaches out")
        before = dir_digest(app)
        out = self.r.text("soul_absent_test", app="crm", moments=MOMENTS)
        self.assertTrue(out.startswith("Soul-absent walk of crm (as: Berton, keeping track of people he cares about)"), out)
        self.assertIn("1. the empty-state screen — a blank table with no invitation to add the first row", out)
        self.assertIn("2. the save button — it saves silently; nothing acknowledges the person", out)
        self.assertIn("gap (WonderPreservation):", out)
        self.assertIn("gap (ConnectionDepth):", out)
        seed = (ITER_SRC / "seeds" / "soul_kernel.metta").read_text(encoding="utf-8")
        for pattern in ("WonderPreservation", "ConnectionDepth"):
            gap = re.search(r"\(soul-pattern-gap %s\s+\"((?:[^\"\\]|\\.)*)\"\)" % pattern, seed).group(1)
            self.assertIn(gap, out, "gap text comes verbatim from the atoms")
        self.assertTrue(out.rstrip().endswith("Nothing was changed."), out)
        self.assertEqual(dir_digest(app), before, "the walk never touches the app")
        atoms = self.r.call("read_atoms", {"prefix": "state:soul_critique:"})["atoms"]
        self.assertEqual(len(atoms), 1)
        self.assertTrue(list(atoms.values())[0].startswith('(soul-critique "crm" "berton" 2 '), atoms)

    @pending("M8-B1")
    def test_no_brief_is_said_plainly_and_unknown_patterns_are_refused(self):
        write_soul_settings(self.r.root, "berton", {"brief": True})
        make_app_dir(self.r.root, "music")
        out = self.r.text("soul_absent_test", app="music", moments=json.dumps(MOMENTS[:1]))
        self.assertTrue(out.startswith("Soul-absent walk of music (no brief; walked as a first-time user)"), out)
        bad = self.r.text("soul_absent_test", app="music", moments=[{"where": "x", "what": "y", "pattern": "Velocity"}])
        self.assertTrue(bad.startswith("ERROR: unknown pattern"), bad)
        self.assertEqual(len(self.r.call("read_atoms", {"prefix": "state:soul_critique:"})["atoms"]), 1, "the bad call recorded nothing")
        self.assertTrue(self.r.text("soul_absent_test", app="music", moments=[]).startswith("ERROR:"))
        self.assertTrue(self.r.text("soul_absent_test", app="music", moments=[MOMENTS[0]] * 9).startswith("ERROR:"))
        source = (ITER_SRC / "tools" / "soul_absent_test.py").read_text(encoding="utf-8")
        self.assertNotIn("AgencyBalance", source, "pattern names come from the lens, not the tool")

    @pending("M8-B1")
    def test_critique_atoms_live_only_in_the_soul_view(self):
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_critique:c1",
                                                 "atom": '(soul-critique "crm" "berton" 2 1700000000000)'}],
                                 "actor": "iter", "source": "soul_absent_test"})
        for view in ("current", "full", "kb"):
            self.assertNotIn("1700000000000", self.r.call("query", {"code": "!(match &self (soul-critique $a $p $n $at) $at)", "view": view}, timeout=60)["result"], view)
        self.assertIn("1700000000000", self.r.call("query", {"code": "!(match &self (soul-critique $a $p $n $at) $at)", "view": "soul"}, timeout=60)["result"])


class CritiqueCountTests(unittest.TestCase):
    """M8-B2 and M8-D5: honest counts."""

    @pending("M8-B2")
    def test_authority_counts_include_critiques_and_margin_asks(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dash", ITER_SRC / "transformations" / "dashboard_atomspace.py")
        dash = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dash)
        atoms = {"state:soul_critique:c1": '(soul-critique "crm" "berton" 2 1700000000000)',
                 "state:soul_margin:m1": '(soul-margin "berton" "crm" "ask" 1700000000001)',
                 "state:soul_margin:m2": '(soul-margin "berton" "crm" "jam" 1700000000002)'}
        temp = tempfile.mkdtemp(prefix="m8dash-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        with unittest.mock.patch.dict(os.environ, {"ITER_DIR": temp}):
            counts = dash.authority_counts(lambda prefix: {k: v for k, v in atoms.items() if k.startswith(prefix)}, derive=lambda: [])
            empty = dash.authority_counts(lambda prefix: {}, derive=lambda: [])
        self.assertEqual((counts["soul_critiques"], counts["soul_margin"]), (1, 2))
        self.assertEqual((empty["soul_critiques"], empty["soul_margin"]), (0, 0))


class MuseumNightTests(unittest.TestCase):
    """M8-C1"""

    def setUp(self):
        self.r = m8_root("m8museum")
        self.addCleanup(self.r.close)
        self.r.start()

    @pending("M8-C1")
    def test_walk_groups_votes_joins_forks_and_reads_only(self):
        write_soul_settings(self.r.root, "berton", {"forks": True}, mode="museum")
        kept = museum_save(self.r.root, "playful header")
        rejected = museum_save(self.r.root, "plain header")
        unvoted = museum_save(self.r.root, "footer idea")
        seed_choice(self.r, "berton", "fork", "card-1", "a", [("a", "CreativeTranscendence", kept), ("b", "TimeCoherence", rejected)])
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        self.assertEqual(museum_get(self.r.root, kept)["vote"], "keep")
        museum_before = {c: museum_get(self.r.root, c) for c in (kept, rejected, unvoted)}
        status_before = self.r.call("status")["commit"]
        out = self.r.text("museum_night")
        self.assertTrue(out.startswith("Museum night (3 pieces)"), out)
        kept_section = out[out.index("Kept:"):out.index("Rejected:")]
        rejected_section = out[out.index("Rejected:"):out.index("Unvoted:")]
        unvoted_section = out[out.index("Unvoted:"):out.index("Leans:")]
        self.assertIn("%s playful header" % kept, kept_section)
        self.assertIn("fork card-1: CreativeTranscendence, picked", kept_section)
        self.assertIn("%s plain header" % rejected, rejected_section)
        self.assertIn("fork card-1: TimeCoherence, passed over", rejected_section)
        self.assertIn("%s footer idea" % unvoted, unvoted_section)
        self.assertIn("Leans: none yet", out, "one fork is not yet a lean")
        self.assertEqual({c: museum_get(self.r.root, c) for c in (kept, rejected, unvoted)}, museum_before, "reading only")
        self.assertEqual(self.r.call("status")["commit"], status_before, "no atom changes")

    @pending("M8-C1")
    def test_filter_and_limit(self):
        write_soul_settings(self.r.root, "berton", {"forks": True})
        for index in range(4):
            museum_save(self.r.root, "orbit widget %d" % index)
        museum_save(self.r.root, "crm row")
        out = self.r.text("museum_night", app="orbit", limit=2)
        self.assertTrue(out.startswith("Museum night (2 pieces)"), out)
        self.assertNotIn("crm row", out)
        self.assertEqual(out.count("orbit widget"), 2)


if __name__ == "__main__":
    unittest.main()
