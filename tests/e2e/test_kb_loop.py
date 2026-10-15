#!/usr/bin/env python3
"""M5-H1 invariant: the knowledge base works through the real loop.

The scripted model remembers a fact and a rule, formalizes both, remembers a
second phrasing of the fact and formalizes it to the same statement, then asks
kb_query. The saved tool results must show one revised statement and a
derived conclusion, and the authority must hold exactly those atoms.
Spec: docs/milestones/M5_knowledge_base.md section H.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import IterRun, send, tool  # noqa: E402
from kb_support import pending, require_m5  # noqa: E402

RULE = "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))"


class KnowledgeBaseLoopTests(unittest.TestCase):
    def test_formalize_revise_and_derive_through_the_real_loop(self):
        require_m5()
        script = [
            [tool("remember", text="Anna smokes a pack a day", mem_type="fact", provenance_type="observed")],
            [tool("formalize_metta", LTM_item="{{memory_id}}", formalization="(--> Anna ([] Smokes))")],
            [tool("remember", text="smoking leads to cancer", mem_type="belief", provenance_type="inferred")],
            [tool("formalize_metta", LTM_item="{{memory_id}}", formalization=RULE)],
            [tool("remember", text="Anna is a smoker, she told me", mem_type="fact", provenance_type="observed")],
            [tool("formalize_metta", LTM_item="{{memory_id}}", formalization="(--> anna ([] smokes))")],
            [tool("kb_query", pattern="(--> anna $what)")],
            [send("KB-DONE")],
        ]
        with IterRun(script, name="kb") as run:
            run.say("learn about Anna")
            run.wait_for_reply("KB-DONE", timeout=420)
            run.stop()

            results = {m["tool_call_id"]: m["content"] for m in run.experience() if m["role"] == "tool"}
            for turn in (1, 3, 5):
                self.assertIn("SUCCESS", results.get("call_%d_0" % turn, ""), results.get("call_%d_0" % turn))
            answer = results.get("call_6_0", "")
            self.assertIn("[stored] (--> anna ([] smokes)) (stv 1.0 0.666", answer)
            self.assertIn("[derived] (--> anna ([] cancerous))", answer)

            statements = run.atoms("state:kb_statement:")
            self.assertEqual(sorted(statements.values()), sorted([
                "(kb (--> anna ([] smokes)) (stv 1.0 0.666667))",
                "(kb %s (stv 1.0 0.5))" % RULE,
            ]))
            self.assertEqual(len(run.atoms("state:kb_evidence:")), 3)
            self.assertNotIn("derived", "".join(run.atoms("state:").values()))
            # The model was offered the new tools.
            offered = run.requests()[-1]["tools"]
            for name in ("kb_query", "define_term", "merge_terms"):
                self.assertIn(name, offered)


if __name__ == "__main__":
    unittest.main()
