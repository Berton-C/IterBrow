#!/usr/bin/env python3
"""M5-A3, M5-A4: the term registry, vocabulary modes and term merges.

Runs the real tools (formalize_metta, define_term, merge_terms) in fresh
processes against the real AtomSpace service (semantic_memory_support).
Spec: docs/milestones/M5_knowledge_base.md section A.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_support import pending, kb_root, kb_atoms, memory_metadata  # noqa: E402


def term_rows(root):
    """{canonical: (status, definition, aliases)} from the authority."""
    from iterbrow_runtime.cognitive_events import read_metta_string
    out = {}
    for key, atom in kb_atoms(root, "term").items():
        body = atom[len("(kb-term "):]
        fields = []
        pos = 0
        for _ in range(4):
            while body[pos].isspace():
                pos += 1
            value, pos = read_metta_string(body, pos)
            fields.append(value)
        out[fields[0]] = (fields[1], fields[2], json.loads(fields[3]))
        assert key == "state:kb_term:" + fields[0], key
    return out


class RegistryTests(unittest.TestCase):
    """M5-A3"""

    def setUp(self):
        self.r = kb_root("kbreg")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_first_use_registers_provisional_terms_and_known_terms_stay_known(self):
        out = self.r.text("define_term", name="Bird", definition="A feathered vertebrate", aliases=["birds", "avian"])
        self.assertIn("SUCCESS", out)
        raven = self.r.remember("ravens are birds", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> Raven Birds)"))
        rows = term_rows(self.r)
        self.assertEqual(rows["bird"][0], "known")
        self.assertEqual(rows["raven"][0], "provisional")
        self.assertIn("birds", rows["bird"][2])
        # The alias resolved to the known term: the stored statement names `bird`, not `birds`.
        self.assertEqual(memory_metadata(self.r, raven)["formalization"], "(--> raven bird)")

    def test_define_term_upgrades_a_provisional_term_in_place(self):
        swan = self.r.remember("swans are white", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=swan, formalization="(--> swan ([] white))"))
        self.assertEqual(term_rows(self.r)["swan"][0], "provisional")
        self.assertIn("SUCCESS", self.r.text("define_term", name="swan", definition="A large waterbird"))
        rows = term_rows(self.r)
        self.assertEqual(rows["swan"][0], "known")
        self.assertEqual(rows["swan"][1], "A large waterbird")
        # The statement atom is untouched by the upgrade.
        self.assertEqual(len(kb_atoms(self.r, "statement")), 1)

    def test_defining_an_alias_of_a_known_term_is_refused_and_names_it(self):
        self.assertIn("SUCCESS", self.r.text("define_term", name="bird", definition="x", aliases=["avian"]))
        out = self.r.text("define_term", name="Avian", definition="y")
        self.assertIn("ERROR", out.upper())
        self.assertIn("bird", out)
        self.assertNotIn("avian", term_rows(self.r))

    def test_strict_mode_refuses_unknown_terms_and_writes_nothing(self):
        strict = {"ITER_KB_VOCABULARY": "strict"}
        self.assertIn("SUCCESS", self.r.text("define_term", name="bird", definition="x", env=strict))
        raven = self.r.remember("ravens are birds", mem_type="fact")
        out = self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)", env=strict)
        self.assertIn("raven", out)
        self.assertNotIn("SUCCESS", out)
        self.assertEqual(kb_atoms(self.r, "statement"), {})
        self.assertEqual(kb_atoms(self.r, "evidence"), {})
        self.assertNotIn("raven", term_rows(self.r))
        self.assertNotIn("formalization", memory_metadata(self.r, raven))
        # Known terms (or their aliases) pass in strict mode.
        self.assertIn("SUCCESS", self.r.text("define_term", name="raven", definition="y", env=strict))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)", env=strict))
        self.assertEqual(len(kb_atoms(self.r, "statement")), 1)

    def test_permissive_is_the_default_mode(self):
        # Neither term is in seeds/kb_terms.json (which the service loads as known on start).
        raven = self.r.remember("ravens are corvids", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven corvid)",
                                             env={"ITER_KB_VOCABULARY": None}))
        self.assertEqual({name: row[0] for name, row in term_rows(self.r).items() if name in ("raven", "corvid")},
                         {"raven": "provisional", "corvid": "provisional"})


class MergeTests(unittest.TestCase):
    """M5-A4: merge_terms rewrites statements and keeps evidence."""

    def setUp(self):
        self.r = kb_root("kbmerge")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_merge_rewrites_statements_and_carries_evidence(self):
        a = self.r.remember("Anna smokes", mem_type="fact")
        b = self.r.remember("smoking leads to cancer", mem_type="belief")
        c = self.r.remember("Bob is a smoker", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=a, formalization="(--> anna ([] smokes))"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=b,
                                             formalization="(==> (--> $1 ([] smokes)) (--> $1 ([] cancerous)))"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=c, formalization="(--> bob ([] smoker))"))
        self.assertEqual(len(kb_atoms(self.r, "statement")), 3)

        out = self.r.text("merge_terms", keep="smokes", drop="smoker")
        self.assertIn("SUCCESS", out)
        statements = sorted(kb_atoms(self.r, "statement").values())
        self.assertEqual(statements, sorted([
            "(kb (--> anna ([] smokes)) (stv 1.0 0.5))",
            "(kb (--> bob ([] smokes)) (stv 1.0 0.5))",
            "(kb (==> (--> $1 ([] smokes)) (--> $1 ([] cancerous))) (stv 1.0 0.5))",
        ]))
        self.assertNotIn("smoker", term_rows(self.r))
        self.assertIn("smoker", term_rows(self.r)["smokes"][2])
        self.assertEqual(memory_metadata(self.r, c)["formalization"], "(--> bob ([] smokes))")
        evidence = kb_atoms(self.r, "evidence")
        self.assertEqual(len(evidence), 3)
        self.assertTrue(any(key.endswith(":" + c) for key in evidence))
        # Idempotent: a second merge changes nothing and does not fail.
        before = self.r.call("status")["commit"]
        self.assertIn("SUCCESS", self.r.text("merge_terms", keep="smokes", drop="smoker"))
        self.assertEqual(self.r.call("status")["commit"], before)

    def test_merge_that_makes_two_statements_collide_revises_them_into_one(self):
        a = self.r.remember("Anna smokes", mem_type="fact")
        b = self.r.remember("Anna is a smoker", mem_type="fact")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=a, formalization="(--> anna ([] smokes))"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=b, formalization="(--> anna ([] smoker))"))
        self.assertIn("SUCCESS", self.r.text("merge_terms", keep="smokes", drop="smoker"))
        statements = list(kb_atoms(self.r, "statement").values())
        self.assertEqual(len(statements), 1)
        self.assertIn("(kb (--> anna ([] smokes)) (stv 1.0 0.666", statements[0])
        self.assertEqual(len(kb_atoms(self.r, "evidence")), 2)

    def test_merge_refuses_unknown_terms(self):
        out = self.r.text("merge_terms", keep="nothing_here", drop="nor_here")
        self.assertIn("ERROR", out.upper())


if __name__ == "__main__":
    unittest.main()
