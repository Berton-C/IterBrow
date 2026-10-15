#!/usr/bin/env python3
"""M5-G1: the AtomSpace dashboard reports what the authority holds, not spelling coincidences.

Spec: docs/milestones/M5_knowledge_base.md section G.
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_memory_support import ITER_SRC  # noqa: E402
from kb_support import pending, kb_root, transact  # noqa: E402


def load_dashboard():
    spec = importlib.util.spec_from_file_location(
        "dashboard_atomspace_under_test", ITER_SRC / "transformations" / "dashboard_atomspace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def statement_op(statement, f=1.0, c=0.5):
    key = "state:kb_statement:" + hashlib.sha256(statement.encode()).hexdigest()[:24]
    return {"op": "upsert", "key": key, "atom": "(kb %s (stv %s %s))" % (statement, f, c)}


class CountTests(unittest.TestCase):
    """M5-G1"""

    @pending("M5-G1")
    def test_counts_come_from_authority_atoms(self):
        atoms = {
            "state:kb_statement:aaa": "(kb (--> raven bird) (stv 1.0 0.5))",
            "state:kb_statement:bbb": "(kb (--> swan bird) (stv 1.0 0.5))",
            "state:kb_statement:ccc": "(kb (--> bird ([] flies)) (stv 1.0 0.5))",
            "state:kb_term:raven": '(kb-term "raven" "provisional" "" "[]")',
            "state:kb_term:bird": '(kb-term "bird" "known" "A feathered vertebrate" "[\\"birds\\"]")',
            "state:kb_evidence:aaa:m1": '(kb-evidence "aaa" "m1")',
            "state:nace_belief:cap-efficacy:shell": "(cap-efficacy shell (stv 0.9 0.8))",
            "state:semantic_memory:m1": '(semantic-memory "m1" "ravens are birds" "{}")',
        }

        def read_atoms(prefix):
            return {k: v for k, v in atoms.items() if k.startswith(prefix)}

        counts = load_dashboard().authority_counts(read_atoms, derive=lambda: [{"statement": "x"}] * 4)
        self.assertEqual(counts["status"], "ok")
        self.assertTrue(counts["loaded"])
        # "bird" appears in all three statements; that is NOT three links. Evidence atoms are.
        self.assertEqual({k: counts[k] for k in ("statements", "terms_known", "terms_provisional", "evidence",
                                                  "derived", "nace_beliefs")},
                         {"statements": 3, "terms_known": 1, "terms_provisional": 1, "evidence": 1,
                          "derived": 4, "nace_beliefs": 1})

    @pending("M5-G1")
    def test_unreachable_authority_shows_no_numbers(self):
        def read_atoms(_prefix):
            raise ConnectionRefusedError("no service")

        counts = load_dashboard().authority_counts(read_atoms, derive=lambda: [])
        self.assertEqual(counts["status"], "authority unreachable")
        self.assertFalse(counts["loaded"])
        for key in ("statements", "terms_known", "terms_provisional", "evidence", "derived", "nace_beliefs"):
            self.assertIsNone(counts[key], key)


class RenderedTests(unittest.TestCase):
    """M5-G1: the rendered page carries the honest numbers and the loaded/unloaded distinction."""

    TRANSFORM = ("import sys, json, importlib.util; spec = importlib.util.spec_from_file_location('t', sys.argv[1]);"
                 "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m);"
                 "m.transform(json.loads(sys.argv[2]), [])")

    def setUp(self):
        self.r = kb_root("kbdash")
        self.addCleanup(self.r.close)
        self.r.start()

    def _render(self, env=None):
        subprocess.run([sys.executable, "-c", self.TRANSFORM,
                        str(self.r.root / "transformations" / "dashboard_atomspace.py"),
                        json.dumps([{"role": "user", "content": "x"}])],
                       cwd=str(self.r.root), env=self.r.env(env), check=True, timeout=120)
        return (self.r.root / "dashboard_atomspace.html").read_text(encoding="utf-8")

    @pending("M5-G1")
    def test_page_shows_authority_counts_commit_and_projection_label(self):
        transact(self.r, [
            statement_op("(--> raven bird)"), statement_op("(--> swan bird)"),
            statement_op("(==> (--> $1 bird) (--> $1 ([] flies)))", 1.0, 0.9),
            {"op": "upsert", "key": "state:kb_evidence:x:m1", "atom": '(kb-evidence "x" "m1")'},
        ])
        commit = self.r.call("status")["commit"]
        html = self._render()
        self.assertIn("loaded in engine", html)
        self.assertIn("commit %d" % commit, html)
        self.assertIn("projection (not loaded)", html)
        data = json.loads(html.split("<!--counts:", 1)[1].split("-->", 1)[0])
        self.assertEqual(data["statements"], 3)
        self.assertEqual(data["evidence"], 1)
        self.assertEqual(data["derived"], 2, "raven flies, swan flies at depth 1")
        self.assertEqual(data["terms_known"] + data["terms_provisional"], len(self.r.atoms("state:kb_term:")))

    @pending("M5-G1")
    def test_page_without_authority_says_so_and_shows_no_numbers(self):
        html = self._render(env={"ITER_METTA_SOCKET": str(self.r.sock.parent / "nowhere.sock")})
        self.assertIn("authority unreachable", html)
        self.assertNotIn("loaded in engine", html)
        data = json.loads(html.split("<!--counts:", 1)[1].split("-->", 1)[0])
        self.assertIsNone(data["statements"])

    @pending("M5-G1")
    def test_graph_nodes_are_registry_terms_and_derived_statements_are_distinct(self):
        transact(self.r, [
            statement_op("(--> raven bird)"), statement_op("(--> swan bird)"),
            statement_op("(==> (--> $1 bird) (--> $1 ([] flies)))", 1.0, 0.9),
            {"op": "upsert", "key": "state:kb_term:bird", "atom": '(kb-term "bird" "known" "" "[]")'},
            {"op": "upsert", "key": "state:kb_term:raven", "atom": '(kb-term "raven" "provisional" "" "[]")'},
            {"op": "upsert", "key": "state:kb_term:swan", "atom": '(kb-term "swan" "provisional" "" "[]")'},
            {"op": "upsert", "key": "state:kb_term:flies", "atom": '(kb-term "flies" "provisional" "" "[]")'},
        ])
        html = self._render()
        graph = json.loads(html.split("<!--graph:", 1)[1].split("-->", 1)[0])
        kinds = {}
        for node in graph["nodes"]:
            kinds.setdefault(node["kind"], []).append(node)
        self.assertEqual(len(kinds.get("statement", [])), 3)
        self.assertEqual(len(kinds.get("derived", [])), 2)
        terms = {node["label"]: node for node in kinds.get("term", [])}
        self.assertEqual(set(terms), {"bird", "raven", "swan", "flies"})
        self.assertEqual(terms["bird"]["status"], "known")
        self.assertEqual(terms["raven"]["status"], "provisional")
        # statement -> term edges exist only for terms in the statement's canonical term list
        edges = {(link["source"], link["target"]) for link in graph["links"] if link["type"] == "mentions"}
        raven_statement = next(n for n in kinds["statement"] if n["label"] == "(--> raven bird)")
        self.assertIn((raven_statement["id"], terms["raven"]["id"]), edges)
        self.assertIn((raven_statement["id"], terms["bird"]["id"]), edges)
        self.assertNotIn((raven_statement["id"], terms["swan"]["id"]), edges)


if __name__ == "__main__":
    unittest.main()
