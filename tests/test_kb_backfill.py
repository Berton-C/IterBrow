#!/usr/bin/env python3
"""M5-F1: memories formalized before Milestone 5 become statement atoms on service start.

Legacy memory atoms (formalization only in metadata) are written straight into
the authority, the service is restarted, and the backfill that runs on
readiness must create the kb atoms exactly once.
Spec: docs/milestones/M5_knowledge_base.md section F.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_memory_support import ITER_SRC  # noqa: E402
from kb_support import pending, kb_root, kb_atoms, transact, legacy_memory_atom, stv_of, close  # noqa: E402


def legacy(root, memories):
    """memories: [(id, document, metadata)] -> semantic-memory atoms as the old code wrote them."""
    return transact(root, [{"op": "upsert", "key": "state:semantic_memory:" + item_id,
                            "atom": legacy_memory_atom(item_id, document, metadata)}
                           for item_id, document, metadata in memories])


class BackfillTests(unittest.TestCase):
    """M5-F1"""

    def setUp(self):
        self.r = kb_root("kbfill")
        self.addCleanup(self.r.close)
        self.r.start()

    def _restart(self):
        self.r.stop()
        return self.r.start()

    @pending("M5-F1")
    def test_legacy_formalizations_become_atoms_once(self):
        legacy(self.r, [
            ("m1", "ravens are birds", {"time": "2026-10-01 10:00:00", "formalization": "(--> Raven  bird)",
                                        "strength": 1.0, "confidence": 0.5}),
            ("m2", "a raven is a bird", {"time": "2026-10-02 10:00:00", "formalization": "(--> raven bird)",
                                        "strength": 1.0, "confidence": 0.9}),
            ("m3", "smoking causes cancer", {"time": "2026-10-03 10:00:00", "strength": 1.0, "confidence": 0.5,
                                            "formalization": "(==> (--> $x ([] smokes)) (--> $x ([] cancerous)))"}),
            ("m4", "no formalization here", {"time": "2026-10-04 10:00:00"}),
            ("m5", "broken", {"time": "2026-10-05 10:00:00", "formalization": "(--> broken"}),
        ])
        self.assertEqual(kb_atoms(self.r, "statement"), {}, "nothing happens until the service restarts")
        status = self._restart()
        self.assertTrue(status["ready"])

        statements = kb_atoms(self.r, "statement")
        self.assertEqual(len(statements), 2, statements)
        raven_key = "state:kb_statement:" + hashlib.sha256(b"(--> raven bird)").hexdigest()[:24]
        self.assertIn(raven_key, statements)
        self.assertTrue(close(stv_of(statements[raven_key])[0], (1.0, 0.9091)), statements[raven_key])
        self.assertIn("(kb (==> (--> $1 ([] smokes)) (--> $1 ([] cancerous))) (stv 1.0 0.5))", statements.values())
        evidence = kb_atoms(self.r, "evidence")
        self.assertEqual(sorted(key.split(":")[-1] for key in evidence), ["m1", "m2", "m3"])
        memories = self.r.memories()
        self.assertEqual(memories["m1"][1]["formalization"], "(--> raven bird)")
        self.assertEqual(memories["m1"][1]["formalization_hash"], raven_key.split(":")[-1])
        self.assertNotIn("formalization_hash", memories["m4"][1])
        self.assertEqual(memories["m5"][1]["formalization"], "(--> broken", "unparseable text is kept as it was")
        self.assertIn("formalization_error", memories["m5"][1])
        terms = kb_atoms(self.r, "term")
        for name in ("raven", "bird", "smokes", "cancerous"):
            self.assertIn("state:kb_term:" + name, terms)
        log = self.r.service_log.read_text()
        self.assertRegex(log, r"kb backfill: 2 statements, \d+ terms \(\d+ provisional\), 1 skipped")

        before = self.r.call("status")["commit"]
        self._restart()
        self.assertEqual(self.r.call("status")["commit"], before, "a second start performs no transaction")

    @pending("M5-F1")
    def test_seed_vocabulary_is_known_and_never_downgraded(self):
        seed_path = ITER_SRC / "seeds" / "kb_terms.json"
        self.assertTrue(seed_path.exists(), seed_path)
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        self.assertIsInstance(seed, list)
        self.assertTrue(all({"name", "definition"} <= set(entry) for entry in seed), seed[:3])
        names = [entry["name"] for entry in seed]
        self.assertIn("bird", names)
        self.assertIn("threat_pattern", names, "names already used by kb_substrate.metta are known")
        manifest = json.loads((ITER_SRC / "state_manifest.json").read_text())
        self.assertIn("seeds/kb_terms.json", [entry["path"] for entry in manifest["entries"]])

        status = self._restart()
        self.assertTrue(status["ready"])
        terms = kb_atoms(self.r, "term")
        for name in names:
            self.assertIn("state:kb_term:" + name, terms, name)
            self.assertIn('"known"', terms["state:kb_term:" + name])
        # A memory that uses a seed term does not make it provisional.
        legacy(self.r, [("m1", "ravens are birds", {"time": "2026-10-01 10:00:00", "formalization": "(--> raven bird)"})])
        self._restart()
        self.assertIn('"known"', kb_atoms(self.r, "term")["state:kb_term:bird"])
        self.assertIn('"provisional"', kb_atoms(self.r, "term")["state:kb_term:raven"])

    @pending("M5-F1")
    def test_reconcile_also_backfills_when_the_service_was_already_up(self):
        legacy(self.r, [("m1", "ravens are birds", {"time": "2026-10-01 10:00:00", "formalization": "(--> raven bird)"})])
        out = self.r.text("chroma_query", query="ravens are birds")  # chroma_query reconciles the index first
        self.assertIn("ID: m1", out)
        self.assertEqual(len(kb_atoms(self.r, "statement")), 1)


if __name__ == "__main__":
    unittest.main()
