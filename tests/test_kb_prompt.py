#!/usr/bin/env python3
"""M5-E1, M5-E2: derived conclusions reach the model through chroma_query and kb_query.

Spec: docs/milestones/M5_knowledge_base.md section E.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_memory_support import ITER_SRC  # noqa: E402
from kb_support import pending, kb_root, stv_of, close  # noqa: E402

SMOKES_RULE = "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))"


class _Seeded(unittest.TestCase):
    def setUp(self):
        self.r = kb_root("kbprompt")
        self.addCleanup(self.r.close)
        self.r.start()

    def seed(self):
        """Called first in every test body (setUp must not fail under @pending)."""
        self.anna = self.r.remember("Anna smokes a pack a day", mem_type="fact")
        self.rule = self.r.remember("smoking leads to cancer", mem_type="belief")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=self.anna, formalization="(--> anna ([] smokes))"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=self.rule, formalization=SMOKES_RULE))


class ChromaQueryTests(_Seeded):
    """M5-E1"""

    @pending("M5-E1")
    def test_result_block_lists_derived_conclusions_with_premises(self):
        self.seed()
        out = self.r.text("chroma_query", query="Anna smokes a pack a day", k=1)
        self.assertIn("ID: " + self.anna, out)
        self.assertIn("Formalization: (--> anna ([] smokes))", out)
        derived = [line for line in out.splitlines() if line.strip().startswith("[derived]")]
        self.assertEqual(len(derived), 1, out)
        self.assertIn("(--> anna ([] cancerous))", derived[0])
        # memory (1.0 0.5) and rule (1.0 0.5): deduction gives (1.0 0.25)
        self.assertTrue(close(stv_of(derived[0])[0], (1.0, 0.25)), derived[0])
        self.assertIn(SMOKES_RULE, derived[0])
        self.assertIn("(--> anna ([] smokes))", derived[0].split("⇐")[-1] if "⇐" in derived[0] else derived[0])

    @pending("M5-E1")
    def test_memory_without_formalization_has_no_derived_section(self):
        self.seed()
        plain = self.r.remember("the weather is mild today", mem_type="fact")
        out = self.r.text("chroma_query", query="the weather is mild today", k=1)
        self.assertIn("ID: " + plain, out)
        self.assertNotIn("[derived]", out)
        self.assertNotIn("Derived:", out)

    @pending("M5-E1")
    def test_derived_lines_are_capped_at_five_per_memory(self):
        self.seed()
        for i in range(8):
            rule = self.r.remember("smoking implies consequence %d" % i, mem_type="belief")
            self.assertIn("SUCCESS", self.r.text(
                "formalize_metta", LTM_item=rule,
                formalization="(==> (--> $1 ([] smokes)) (--> $1 ([] consequence_%d)))" % i))
        out = self.r.text("chroma_query", query="Anna smokes a pack a day", k=1)
        block = out.split("ID: " + self.anna, 1)[1].split("--- Result", 1)[0]
        derived = [line for line in block.splitlines() if line.strip().startswith("[derived]")]
        self.assertEqual(len(derived), 5, block)
        self.assertRegex(block, r"\(\+?\d+ more derived")


class KbQueryTests(_Seeded):
    """M5-E2"""

    @pending("M5-E2")
    def test_pattern_returns_stored_then_derived_matches(self):
        self.seed()
        out = self.r.text("kb_query", pattern="(--> $1 ([] cancerous))")
        self.assertIn("[derived] (--> anna ([] cancerous)) (stv 1.0 0.25)", out)
        out = self.r.text("kb_query", pattern="(--> anna $what)")
        stored = [line for line in out.splitlines() if line.strip().startswith("[stored]")]
        derived = [line for line in out.splitlines() if line.strip().startswith("[derived]")]
        self.assertEqual(len(stored), 1, out)
        self.assertIn("(--> anna ([] smokes)) (stv 1.0 0.5)", stored[0])
        self.assertIn(self.anna, stored[0], "stored matches name their evidence memories")
        self.assertEqual(len(derived), 1, out)
        self.assertLess(out.index("[stored]"), out.index("[derived]"))

    @pending("M5-E2")
    def test_bad_pattern_and_no_match_are_explicit(self):
        self.seed()
        out = self.r.text("kb_query", pattern="(--> anna")
        self.assertIn("ERROR", out.upper())
        out = self.r.text("kb_query", pattern="(--> nobody $what)")
        self.assertIn("no stored or derived statement matches", out.lower())

    @pending("M5-E2")
    def test_tool_descriptions_fit_the_prompt_budget(self):
        self.seed()
        sys.path.insert(0, str(ITER_SRC))
        from tools._metadata_static import static_tool_metadata
        for name in ("kb_query", "define_term", "merge_terms", "formalize_metta"):
            path = ITER_SRC / "tools" / (name + ".py")
            self.assertTrue(path.exists(), path)
            description = static_tool_metadata(path)["description"]
            self.assertLessEqual(len(description), 500, "%s DESCRIPTION is %d chars" % (name, len(description)))


if __name__ == "__main__":
    unittest.main()
