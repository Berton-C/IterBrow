#!/usr/bin/env python3
"""M5-A1, M5-A2, M5-C1: canonicalization and statement truth (pure Python, no service).

Spec: docs/milestones/M5_knowledge_base.md sections A and C.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_support import pending, kb_terms, nal_revision, close  # noqa: E402


class CanonicalizeTests(unittest.TestCase):
    """M5-A1: one spelling per concept."""

    @pending("M5-A1")
    def test_tokens_normalize_to_lowercase_snake_case(self):
        canonicalize = kb_terms().canonicalize
        self.assertEqual(canonicalize("Channel People"), "channel_people")
        self.assertEqual(canonicalize("channel-people"), "channel_people")
        self.assertEqual(canonicalize("  Channel__People  "), "channel_people")
        self.assertEqual(canonicalize("iterAgent"), "iteragent")  # no camel splitting: deterministic, not clever
        self.assertEqual(canonicalize("Ｂird"), "bird")  # NFKC
        self.assertEqual(canonicalize("tool/reliability"), "tool_reliability")

    @pending("M5-A1")
    def test_structural_symbols_variables_and_numbers_pass_through(self):
        canonicalize = kb_terms().canonicalize
        for symbol in ("-->", "<->", "==>", "[]", "stv", "$1", "$x", "0.7", "3", "-1.5"):
            self.assertEqual(canonicalize(symbol), symbol, symbol)

    @pending("M5-A1")
    def test_variables_are_renamed_positionally(self):
        canonical_statement = kb_terms().canonical_statement
        statement, _ = canonical_statement("(==> (--> $x ([] smokes)) (--> $x ([] cancerous)))")
        self.assertEqual(statement, "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))")
        statement, _ = canonical_statement("(==> (--> $b $a) (--> $a $b))")
        self.assertEqual(statement, "(==> (--> $1 $2) (--> $2 $1))")

    @pending("M5-A1")
    def test_hyperon_decorated_variables_are_plain_variables(self):
        canonical_statement = kb_terms().canonical_statement
        statement, _ = canonical_statement("(--> $1#385 ([] needs_doctor))")
        self.assertEqual(statement, "(--> $1 ([] needs_doctor))")


class CanonicalStatementTests(unittest.TestCase):
    """M5-A2: parse, serialize, list terms, reject what cannot be a statement."""

    @pending("M5-A2")
    def test_serialization_is_single_spaced_and_terms_are_ordered_unique(self):
        canonical_statement = kb_terms().canonical_statement
        statement, terms = canonical_statement("( -->   Raven   ( []  Black-Bird ) )")
        self.assertEqual(statement, "(--> raven ([] black_bird))")
        self.assertEqual(terms, ["raven", "black_bird"])
        statement, terms = canonical_statement("(==> (--> $1 ([] smokes)) (--> $1 ([] smokes)))")
        self.assertEqual(terms, ["smokes"])

    @pending("M5-A2")
    def test_numbers_and_variables_are_not_terms(self):
        canonical_statement = kb_terms().canonical_statement
        _, terms = canonical_statement("(--> 0.7 ([] gate_go_threshold))")
        self.assertEqual(terms, ["gate_go_threshold"])
        _, terms = canonical_statement("(--> $x ([] mortal))")
        self.assertEqual(terms, ["mortal"])

    @pending("M5-A2")
    def test_rejections(self):
        canonical_statement = kb_terms().canonical_statement
        for bad in ("(--> a b", "(--> a b) (--> c d)", "((--> a b) (stv 1.0 0.5))",
                    '(--> "a string" b)', "", "raven"):
            with self.assertRaises(ValueError, msg=bad):
                canonical_statement(bad)

    @pending("M5-A2")
    def test_canonical_form_is_a_fixed_point(self):
        canonical_statement = kb_terms().canonical_statement
        first, _ = canonical_statement("(==> (--> $ctx ([] Urgency)) (--> $ctx ([] reduces reasoning-quality)))")
        second, _ = canonical_statement(first)
        self.assertEqual(first, second)


class TruthTests(unittest.TestCase):
    """M5-C1: a statement's stv is the NAL revision fold over its evidence."""

    @pending("M5-C1")
    def test_reference_values(self):
        statement_truth = kb_terms().statement_truth
        self.assertTrue(close(statement_truth([(1.0, 0.5)]), (1.0, 0.5)))
        self.assertTrue(close(statement_truth([(1.0, 0.5), (1.0, 0.5)]), (1.0, 0.6667)))
        self.assertTrue(close(statement_truth([(1.0, 0.5), (0.0, 0.5)]), (0.5, 0.6667)))
        self.assertTrue(close(statement_truth([(1.0, 0.9), (1.0, 0.5)]), (1.0, 0.9091)))

    @pending("M5-C1")
    def test_matches_reference_fold_and_is_order_independent(self):
        statement_truth = kb_terms().statement_truth
        pairs = [(0.8, 0.6), (0.2, 0.4), (1.0, 0.9)]
        self.assertTrue(close(statement_truth(pairs), nal_revision(pairs)))
        self.assertTrue(close(statement_truth(list(reversed(pairs))), nal_revision(pairs)))

    @pending("M5-C1")
    def test_confidence_is_capped_and_no_other_clamp_applies(self):
        statement_truth = kb_terms().statement_truth
        _, confidence = statement_truth([(1.0, 0.99)] * 5)
        self.assertLessEqual(confidence, 0.99)
        # Pure NAL: strong negative evidence pulls strength DOWN (the legacy
        # _support.truth_revision clamp never lets confidence fall; this must not inherit it).
        strength, confidence = statement_truth([(1.0, 0.5), (0.0, 0.9)])
        self.assertLess(strength, 0.2)
        self.assertTrue(close((strength, confidence), nal_revision([(1.0, 0.5), (0.0, 0.9)])))

    @pending("M5-C1")
    def test_no_evidence_has_no_truth(self):
        with self.assertRaises(ValueError):
            kb_terms().statement_truth([])


if __name__ == "__main__":
    unittest.main()
