#!/usr/bin/env python3
"""M6-C1..C3: the Soul kernel atoms as a seed in their own view, the lens, the reflection tool.

Spec: docs/milestones/M6_soul_base.md section C.
"""
import re
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import (pending, m6_root, soul_lens, PATTERNS, PAIRS, FACETS, reference_kernel,  # noqa: E402
                        count_atoms, read_manifest, ITER_SRC)

SEED = ITER_SRC / "seeds" / "soul_kernel.metta"


class SeedTests(unittest.TestCase):
    """M6-C1"""

    @pending("M6-C1")
    def test_seed_is_declared_and_holds_the_reference_atom_counts(self):
        self.assertTrue(SEED.exists(), SEED)
        entries = {e["path"]: e for e in read_manifest()["entries"]}
        self.assertEqual(entries["seeds/soul_kernel.metta"]["role"], "source_seed")
        self.assertEqual(entries["seeds/soul_kernel.metta"]["format"], "metta")
        text = SEED.read_text(encoding="utf-8")
        self.assertNotIn("add-atom", text, "plain atoms, not evaluated inserts")
        for facet in FACETS:
            self.assertEqual(count_atoms(text, facet), 9, facet)
        for head, n in (("priority", 5), ("soul-pattern-related", 7), ("soul-pattern-degrades-without", 6),
                        ("soul-paraconsistent-pair", 4), ("tension-vector", 5), ("threatens", 7),
                        ("soul-will-threshold", 9), ("soul-autonomy-component", 3), ("soul-causal", 33)):
            self.assertEqual(count_atoms(text, head), n, head)
        for a, b in PAIRS:
            self.assertIn("(soul-paraconsistent-pair %s %s)" % (a, b), text)
        for pattern in PATTERNS:
            self.assertRegex(text, r"\(soul-pattern-gap %s\s+\"" % pattern)
        # Nothing from the reference's gates comes along.
        for forbidden in ("output-verdict", "operation-risk", "soul-mutation", "aliveness", "soul-file-class"):
            self.assertNotIn(forbidden, text, forbidden)

    @pending("M6-C1")
    def test_facet_texts_are_verbatim_from_the_reference_when_available(self):
        reference = reference_kernel()
        if reference is None:
            self.skipTest("ClarityOmega checkout not present; verbatim comparison needs it")
        text = SEED.read_text(encoding="utf-8")

        def facets(source):
            out = {}
            for match in re.finditer(r"\((soul-pattern(?:-[a-z+-]+)?) (\w+)\s+\"((?:[^\"\\]|\\.)*)\"\)", source):
                out[(match.group(1), match.group(2))] = match.group(3)
            return out

        ours, theirs = facets(text), facets(reference)
        missing = sorted(set(theirs) - set(ours))
        self.assertEqual(missing, [], "facet atoms missing from the port")
        for key in theirs:
            self.assertEqual(ours[key], theirs[key], key)


class ViewTests(unittest.TestCase):
    """M6-C2: the soul view sees the seed and the choices; other views never do; NACE unaffected."""

    def setUp(self):
        self.r = m6_root("m6view")
        self.addCleanup(self.r.close)
        self.r.start()

    def _q(self, code, view):
        return self.r.call("query", {"code": code, "view": view}, timeout=60)["result"]

    @pending("M6-C2")
    def test_soul_view_answers_pair_and_pattern_queries(self):
        self.assertIn("True", self._q("!(soul-paraconsistent? TimeCoherence CreativeTranscendence)", "soul"))
        self.assertIn("False", self._q("!(soul-paraconsistent? TimeCoherence AgencyBalance)", "soul"))
        out = self._q("!(match &self (soul-pattern $p $d) $p)", "soul")
        for pattern in PATTERNS:
            self.assertIn(pattern, out)
        self.assertIn("Capture is quiet", self._q("!(match &self (soul-pattern-moat AgencyBalance $t) $t)", "soul"))

    @pending("M6-C2")
    def test_other_views_do_not_see_soul_atoms_and_soul_view_does_not_see_nace(self):
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:nace_belief:cap-efficacy:shell",
                                                 "atom": "(cap-efficacy shell (stv 0.9 0.8))"}],
                                 "actor": "test", "source": "test"})
        for view in ("current", "full", "kb"):
            self.assertNotIn("AgencyBalance", self._q("!(match &self (soul-pattern $p $d) $p)", view), view)
            self.assertNotIn("True", self._q("!(soul-paraconsistent? Safety Helpfulness)", view), view)
        for view in ("current", "full"):
            self.assertIn("(stv 0.9 0.8)", self._q("!(match &self (cap-efficacy shell $v) $v)", view), view)
        self.assertNotIn("0.9 0.8", self._q("!(match &self (cap-efficacy shell $v) $v)", "soul"))

    @pending("M6-C2")
    def test_soul_choices_are_visible_in_the_soul_view(self):
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_choice:card-1",
                                                 "atom": '(soul-choice "berton" "fork" "card-1" "a" 1700000000123)'}],
                                 "actor": "person", "source": "sidebar"})
        self.assertIn("card-1", self._q('!(match &self (soul-choice $p $k $c $pick $at) $c)', "soul"))
        self.assertNotIn("card-1", self._q('!(match &self (soul-choice $p $k $c $pick $at) $c)', "kb"))


class LensTests(unittest.TestCase):
    """M6-C3: pattern text enters Python only through the lens, read from the atoms."""

    def setUp(self):
        self.r = m6_root("m6lens")
        self.addCleanup(self.r.close)
        self.r.start()

    @pending("M6-C3")
    def test_lens_text_holds_every_pattern_and_gap_signature_verbatim(self):
        import os
        with unittest.mock.patch.dict(os.environ, {"ITER_DIR": str(self.r.root), "ITER_METTA_SOCKET": str(self.r.sock)}):
            text = soul_lens().lens_text()
        seed = SEED.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            self.assertIn(pattern, text)
            gap = re.search(r"\(soul-pattern-gap %s\s+\"((?:[^\"\\]|\\.)*)\"\)" % pattern, seed).group(1)
            self.assertIn(gap, text, pattern)
        self.assertNotIn("(soul-pattern", text, "prose for a prompt, not atoms")
        with unittest.mock.patch.dict(os.environ, {"ITER_DIR": str(self.r.root), "ITER_METTA_SOCKET": str(self.r.sock)}):
            only = soul_lens().lens_text(patterns=["WonderPreservation"])
        self.assertIn("WonderPreservation", only)
        self.assertNotIn("AgencyBalance", only)

    def test_no_pattern_text_lives_in_python_source(self):
        """The seed is the only home of the facet texts."""
        needle = "Capture is quiet"  # from the AgencyBalance moat
        for path in (ITER_SRC / "iterbrow_runtime").glob("*.py"):
            self.assertNotIn(needle, path.read_text(encoding="utf-8"), path.name)
        for path in (ITER_SRC / "tools").glob("*.py"):
            self.assertNotIn(needle, path.read_text(encoding="utf-8"), path.name)
        for path in (ITER_SRC / "transformations").glob("*.py"):
            self.assertNotIn(needle, path.read_text(encoding="utf-8"), path.name)

    @pending("M6-C3")
    def test_reflect_tool_returns_lens_text_for_named_patterns_and_declared_pairs(self):
        out = self.r.text("soul_reflect", situation="urgency pressure while deciding between TimeCoherence and CreativeTranscendence")
        self.assertIn("TimeCoherence", out)
        self.assertIn("CreativeTranscendence", out)
        self.assertIn("declared pair", out.lower())
        self.assertIn("urgency-narrows-thought", out, "tension vectors are matched by name")
        for forbidden in ("VERDICT", "gate", "block", "halt"):
            self.assertNotIn(forbidden, out, forbidden)
        from tools._metadata_static import static_tool_metadata
        self.assertLessEqual(len(static_tool_metadata(ITER_SRC / "tools" / "soul_reflect.py")["description"]), 500)
        self.assertFalse((ITER_SRC / "tools" / "soul_eval.py").exists(), "soul_eval is replaced, not kept beside")


if __name__ == "__main__":
    unittest.main()
