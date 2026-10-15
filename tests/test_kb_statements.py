#!/usr/bin/env python3
"""M5-B1, M5-B2, M5-B3, M5-C2: formalizations as first-class statement atoms.

Real tools in fresh processes against the real AtomSpace service.
Spec: docs/milestones/M5_knowledge_base.md sections B and C.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_support import pending, kb_root, kb_atoms, query, stv_of, close, memory_metadata  # noqa: E402

SMOKES_RULE = "(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))"


def statement_hash(statement):
    return hashlib.sha256(statement.encode("utf-8")).hexdigest()[:24]


class StatementAtomTests(unittest.TestCase):
    """M5-B1"""

    def setUp(self):
        self.r = kb_root("kbstmt")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_formalize_writes_statement_evidence_and_terms_in_one_transaction(self):
        raven = self.r.remember("ravens are birds", mem_type="fact")
        before = self.r.call("status")["commit"]
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> Raven bird)"))
        self.assertEqual(self.r.call("status")["commit"], before + 1, "one transaction, not several")

        statement = "(--> raven bird)"
        key = "state:kb_statement:" + statement_hash(statement)
        statements = kb_atoms(self.r, "statement")
        self.assertEqual(statements, {key: "(kb %s (stv 1.0 0.5))" % statement})
        evidence = kb_atoms(self.r, "evidence")
        self.assertEqual(evidence, {"state:kb_evidence:%s:%s" % (statement_hash(statement), raven):
                                    '(kb-evidence "%s" "%s")' % (statement_hash(statement), raven)})
        terms = kb_atoms(self.r, "term")
        self.assertIn("state:kb_term:raven", terms)
        self.assertIn('"provisional"', terms["state:kb_term:raven"])
        self.assertIn("state:kb_term:bird", terms)  # a seed term (known since start); not duplicated
        metadata = memory_metadata(self.r, raven)
        self.assertEqual(metadata["formalization"], statement)
        self.assertEqual(metadata["formalization_hash"], statement_hash(statement))

    def test_statement_is_a_live_expression_the_engine_can_match(self):
        raven = self.r.remember("ravens are birds", mem_type="fact")
        rule = self.r.remember("smoking causes cancer", mem_type="belief")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=rule, formalization=SMOKES_RULE))
        found = query(self.r, "!(match &self (kb (--> $what bird) $tv) (found $what $tv))")
        self.assertIn("(found raven (stv 1.0 0.5))", found)
        # The stored variable is a real variable: a ground premise unifies with it.
        found = query(self.r, "!(match &self (kb (==> (--> anna ([] smokes)) $conclusion) $tv) $conclusion)")
        self.assertIn("(--> anna ([] cancerous))", found)

    def test_formalization_is_stored_canonical_not_as_typed(self):
        raven = self.r.remember("ravens are birds", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven,
                                             formalization="( ==>  (--> $x ([] Smokes))   (--> $x ([] Cancerous)) )"))
        self.assertEqual(memory_metadata(self.r, raven)["formalization"], SMOKES_RULE)
        self.assertEqual(list(kb_atoms(self.r, "statement").values()), ["(kb %s (stv 1.0 0.5))" % SMOKES_RULE])

    def test_invalid_statement_writes_nothing(self):
        raven = self.r.remember("ravens are birds", mem_type="fact")
        before = self.r.call("status")["commit"]
        for bad in ("((--> raven bird) (stv 1.0 0.5))", '(--> "raven" bird)', "(--> raven bird) (--> x y)"):
            out = self.r.text("formalize_metta", LTM_item=raven, formalization=bad)
            self.assertNotIn("SUCCESS", out, bad)
        self.assertEqual(self.r.call("status")["commit"], before)
        self.assertEqual(kb_atoms(self.r, "statement"), {})


class LifecycleTests(unittest.TestCase):
    """M5-B2: evidence follows the memory; statements live exactly as long as their evidence."""

    def setUp(self):
        self.r = kb_root("kblife")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_reformalizing_moves_evidence_and_drops_the_orphaned_statement(self):
        raven = self.r.remember("ravens are birds", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven ([] black))"))
        statements = list(kb_atoms(self.r, "statement").values())
        self.assertEqual(statements, ["(kb (--> raven ([] black)) (stv 1.0 0.5))"])
        evidence = kb_atoms(self.r, "evidence")
        self.assertEqual(len(evidence), 1)
        self.assertTrue(next(iter(evidence)).startswith("state:kb_evidence:" + statement_hash("(--> raven ([] black))")))

    def test_forget_removes_evidence_and_last_evidence_removes_statement(self):
        raven = self.r.remember("ravens are birds", mem_type="todo")
        crow = self.r.remember("crows are birds too", mem_type="todo")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=crow, formalization="(--> raven bird)"))
        self.assertEqual(len(kb_atoms(self.r, "statement")), 1)
        self.assertEqual(len(kb_atoms(self.r, "evidence")), 2)
        self.assertTrue(self.r.text("forget", item_id=crow).startswith("FORGET-SUCCESS"))
        self.assertEqual(len(kb_atoms(self.r, "evidence")), 1)
        self.assertEqual(list(kb_atoms(self.r, "statement").values()), ["(kb (--> raven bird) (stv 1.0 0.5))"],
                         "stv recomputed from the remaining evidence")
        self.assertTrue(self.r.text("forget", item_id=raven).startswith("FORGET-SUCCESS"))
        self.assertEqual(kb_atoms(self.r, "statement"), {})
        self.assertEqual(kb_atoms(self.r, "evidence"), {})
        # Terms outlive statements (the registry is vocabulary, not usage).
        self.assertIn("state:kb_term:raven", kb_atoms(self.r, "term"))

    def test_support_and_contradict_recompute_the_statement_truth(self):
        raven = self.r.remember("ravens are birds", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)"))
        self.assertIn("SUPPORT-SUCCESS", self.r.text("support", item_id=raven, episode_time="2026-10-15 10:00:00"))
        memory_stv = (memory_metadata(self.r, raven)["strength"], memory_metadata(self.r, raven)["confidence"])
        statement = list(kb_atoms(self.r, "statement").values())[0]
        self.assertTrue(close(stv_of(statement)[0], memory_stv), (statement, memory_stv))
        self.assertIn("CONTRADICT-SUCCESS", self.r.text("contradict", item_id=raven, episode_time="2026-10-15 11:00:00"))
        memory_stv = (memory_metadata(self.r, raven)["strength"], memory_metadata(self.r, raven)["confidence"])
        statement = list(kb_atoms(self.r, "statement").values())[0]
        self.assertTrue(close(stv_of(statement)[0], memory_stv), (statement, memory_stv))


class RevisionTests(unittest.TestCase):
    """M5-C2: the same statement from two memories is one atom with revised truth."""

    def setUp(self):
        self.r = kb_root("kbrev")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_second_memory_with_same_statement_revises_instead_of_duplicating(self):
        a = self.r.remember("ravens are birds", mem_type="fact")
        b = self.r.remember("a raven is a kind of bird", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=a, formalization="(--> raven bird)"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=b, formalization="(--> Raven  bird)"))
        statements = list(kb_atoms(self.r, "statement").values())
        self.assertEqual(len(statements), 1)
        self.assertTrue(close(stv_of(statements[0])[0], (1.0, 0.6667)), statements[0])
        self.assertEqual(len(kb_atoms(self.r, "evidence")), 2)

    def test_conflicting_evidence_revises_to_uncertain_not_two_statements(self):
        a = self.r.remember("ravens are birds", mem_type="fact")
        b = self.r.remember("ravens are not birds", mem_type="belief")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=a, formalization="(--> raven bird)"))
        # Memory b carries negative truth (strength 0) via contradict before it is formalized.
        self.assertIn("CONTRADICT-SUCCESS", self.r.text("contradict", item_id=b, episode_time="2026-10-15 09:00:00"))
        b_meta = memory_metadata(self.r, b)
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=b, formalization="(--> raven bird)"))
        statements = list(kb_atoms(self.r, "statement").values())
        self.assertEqual(len(statements), 1)
        from kb_support import nal_revision
        expected = nal_revision([(1.0, 0.5), (b_meta["strength"], b_meta["confidence"])])
        self.assertTrue(close(stv_of(statements[0])[0], expected), (statements[0], expected))
        self.assertLess(stv_of(statements[0])[0][0], 1.0)


class ProjectionTests(unittest.TestCase):
    """M5-B3: space.metta is regenerated from kb atoms, not from metadata."""

    TRANSFORM = ("import sys, json, importlib.util; spec = importlib.util.spec_from_file_location('t', sys.argv[1]);"
                 "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
                 "m.transform(json.loads(sys.argv[2]), [])")

    def setUp(self):
        self.r = kb_root("kbproj")
        self.addCleanup(self.r.close)
        self.r.start()

    def _space(self):
        subprocess.run([sys.executable, "-c", self.TRANSFORM,
                        str(self.r.root / "transformations" / "atom_space_update.py"), json.dumps([{"role": "user", "content": "x"}])],
                       cwd=str(self.r.root), env=self.r.env(), check=True)
        path = self.r.root / "transformations" / ".runtime" / "space.metta"
        return path.read_text() if path.exists() else ""

    def test_projection_mirrors_statement_atoms_including_revised_truth(self):
        a = self.r.remember("ravens are birds", mem_type="fact")
        b = self.r.remember("a raven is a bird", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=a, formalization="(--> raven bird)"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=b, formalization="(--> raven bird)"))
        space = self._space()
        lines = [line for line in space.splitlines() if line.startswith("(")]
        self.assertEqual(len(lines), 1, space)
        self.assertTrue(close(stv_of(lines[0])[0], (1.0, 0.6667)), lines[0])
        # A memory whose metadata says one thing while the kb atom says another: the atom wins.
        self.assertEqual(lines[0], list(kb_atoms(self.r, "statement").values())[0].replace("(kb ", "(", 1))


if __name__ == "__main__":
    unittest.main()
