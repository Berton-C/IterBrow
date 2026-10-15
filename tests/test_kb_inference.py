#!/usr/bin/env python3
"""M5-D1, M5-D2: bounded forward chaining over stored statements, in the real engine.

Statement atoms are seeded straight into the authority (transact) so these
tests do not depend on the formalize tool; they depend on the inference seed
(iter/seeds/kb_inference.metta) being declared in state_manifest.json and on
iterbrow_runtime.kb_inference.derive.
Spec: docs/milestones/M5_knowledge_base.md section D.
"""
import hashlib
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_support import pending, kb_root, kb_inference, kb_atoms, query, transact, close  # noqa: E402


def seed(root, statements):
    """statements: {canonical statement: (f, c)} -> kb atoms in the authority."""
    operations = []
    for statement, (f, c) in statements.items():
        key = "state:kb_statement:" + hashlib.sha256(statement.encode()).hexdigest()[:24]
        operations.append({"op": "upsert", "key": key, "atom": "(kb %s (stv %s %s))" % (statement, f, c)})
    return transact(root, operations)


def by_statement(derivations):
    return {d["statement"]: d for d in derivations}


class DeductionTests(unittest.TestCase):
    """M5-D1"""

    def setUp(self):
        self.r = kb_root("kbinf")
        self.addCleanup(self.r.close)
        self.r.start()
        self.run_query = lambda code: query(self.r, code)

    @pending("M5-D1")
    def test_modus_ponens_with_nal_deduction_truth(self):
        seed(self.r, {
            "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))": (1.0, 0.9),
            "(--> anna ([] smokes))": (1.0, 0.5),
        })
        derived = by_statement(kb_inference().derive(self.run_query, depth=1))
        self.assertIn("(--> anna ([] cancerous))", derived)
        d = derived["(--> anna ([] cancerous))"]
        self.assertTrue(close(tuple(d["stv"]), (1.0, 0.45)), d)
        self.assertEqual(d["depth"], 1)
        self.assertEqual(sorted(d["premises"]),
                         sorted(["(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))", "(--> anna ([] smokes))"]))

    @pending("M5-D1")
    def test_implication_chaining_value_and_canonical_variables(self):
        seed(self.r, {
            "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))": (1.0, 0.9),
            "(==> (--> $1 ([] cancerous)) (--> $1 ([] needs_doctor)))": (0.9, 0.9),
        })
        derived = by_statement(kb_inference().derive(self.run_query, depth=1))
        chained = "(==> (--> $1 ([] smokes)) (--> $1 ([] needs_doctor)))"
        self.assertIn(chained, derived, "Hyperon's $1#NNN must come back as $1: %s" % list(derived))
        self.assertTrue(close(tuple(derived[chained]["stv"]), (0.9, 0.729)), derived[chained])

    @pending("M5-D1")
    def test_depth_two_reaches_what_depth_one_cannot(self):
        seed(self.r, {
            "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))": (1.0, 0.9),
            "(==> (--> $1 ([] cancerous)) (--> $1 ([] needs_doctor)))": (1.0, 0.9),
            "(--> anna ([] smokes))": (1.0, 0.5),
        })
        one = by_statement(kb_inference().derive(self.run_query, depth=1))
        two = by_statement(kb_inference().derive(self.run_query, depth=2))
        self.assertIn("(--> anna ([] cancerous))", one)
        # anna needs_doctor is reachable at depth 1 only through the chained rule (depth-1 derivation
        # of the rule, then applying it is depth 2) or by applying the second rule to a depth-1 fact.
        self.assertNotIn("(--> anna ([] needs_doctor))", one)
        self.assertIn("(--> anna ([] needs_doctor))", two)
        d = two["(--> anna ([] needs_doctor))"]
        self.assertEqual(d["depth"], 2)
        # Both routes give the same value: 1.0 * 0.9 * 0.9 * 0.5 chain of deductions.
        self.assertTrue(close(tuple(d["stv"]), (1.0, 0.45 * 0.9)), d)

    @pending("M5-D1")
    def test_universal_fact_unifies_with_everything(self):
        seed(self.r, {
            "(--> $1 ([] mortal))": (1.0, 0.9),
            "(==> (--> $1 ([] mortal)) (--> $1 ([] finite)))": (1.0, 0.9),
            "(--> socrates ([] human))": (1.0, 0.5),
        })
        derived = by_statement(kb_inference().derive(self.run_query, depth=1))
        self.assertIn("(--> $1 ([] finite))", derived)


class BoundsTests(unittest.TestCase):
    """M5-D2: derivations are bounded, deduplicated, never written, and labelled."""

    def setUp(self):
        self.r = kb_root("kbbnd")
        self.addCleanup(self.r.close)
        self.r.start()
        self.run_query = lambda code: query(self.r, code)

    def _chain(self, length):
        statements = {"(--> a0 ([] p0))": (1.0, 0.5)}
        for i in range(length):
            statements["(==> (--> $1 ([] p%d)) (--> $1 ([] p%d)))" % (i, i + 1)] = (1.0, 0.9)
        seed(self.r, statements)

    @pending("M5-D2")
    def test_depth_is_capped_at_three(self):
        self._chain(6)
        derived = by_statement(kb_inference().derive(self.run_query, depth=10))
        self.assertTrue(all(d["depth"] <= 3 for d in derived.values()), {k: d["depth"] for k, d in derived.items()})
        self.assertIn("(--> a0 ([] p3))", derived)

    @pending("M5-D2")
    def test_stored_statements_are_not_reported_as_derived_and_dedupe_keeps_highest_confidence(self):
        seed(self.r, {
            "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))": (1.0, 0.9),
            "(==> (--> $1 ([] vapes)) (--> $1 ([] cancerous)))": (1.0, 0.5),
            "(--> anna ([] smokes))": (1.0, 0.5),
            "(--> anna ([] vapes))": (1.0, 0.5),
            "(--> anna ([] cancerous))": (1.0, 0.5),  # already stored
            "(--> bob ([] smokes))": (1.0, 0.9),
            "(--> bob ([] vapes))": (1.0, 0.9),
        })
        derived = by_statement(kb_inference().derive(self.run_query, depth=2))
        self.assertNotIn("(--> anna ([] cancerous))", derived)
        self.assertIn("(--> bob ([] cancerous))", derived)
        self.assertTrue(close(tuple(derived["(--> bob ([] cancerous))"]["stv"]), (1.0, 0.81)),
                        "highest-confidence derivation wins: %s" % derived["(--> bob ([] cancerous))"])
        self.assertEqual(len([d for d in derived.values() if d["statement"] == "(--> bob ([] cancerous))"]), 1)

    @pending("M5-D2")
    def test_nothing_is_written_to_the_authority(self):
        self._chain(3)
        before = self.r.call("status")
        kb_inference().derive(self.run_query, depth=3)
        after = self.r.call("status")
        self.assertEqual(after["commit"], before["commit"])
        self.assertEqual(after["state_hash"], before["state_hash"])
        self.assertEqual(len(kb_atoms(self.r, "statement")), 4)
        self.assertNotIn("derived", "".join(self.r.atoms("state:")))

    @pending("M5-D2")
    def test_limit_and_budget_truncate_honestly(self):
        self._chain(3)
        full = kb_inference().derive(self.run_query, depth=3)
        self.assertFalse(full.truncated)
        result = kb_inference().derive(self.run_query, depth=3, limit=1)
        self.assertEqual(len(result), 1)
        self.assertTrue(result.truncated, "a truncated result must say so")
        started = time.monotonic()
        result = kb_inference().derive(self.run_query, depth=3, budget_s=0.0)
        self.assertLess(time.monotonic() - started, 5.0)
        self.assertTrue(result.truncated, "a zero budget returns at most what one round found, marked truncated")

    @pending("M5-D2")
    def test_engine_failure_is_reported_not_swallowed(self):
        def broken(_code):
            raise RuntimeError("isolated Hyperon query worker exited 1")
        with self.assertRaises(RuntimeError):
            kb_inference().derive(broken, depth=1)


if __name__ == "__main__":
    unittest.main()
