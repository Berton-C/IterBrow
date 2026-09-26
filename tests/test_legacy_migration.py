#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.atomspace_store import AtomspaceStore  # noqa: E402
from iterbrow_runtime.legacy_migration import (  # noqa: E402
    MIGRATION_KEY,
    migrate_legacy_state,
)


class LegacyMigrationTests(unittest.TestCase):
    def _fixture(self, root):
        (root / "chroma_db").mkdir(parents=True)
        (root / "memory").mkdir()
        (root / "transformations" / ".runtime").mkdir(parents=True)
        (root / "nace_beliefs.metta").write_text(
            ";; projection\n(cap-efficacy shell (stv 0.9 0.8))\n",
            encoding="utf-8",
        )
        (root / "task_state.metta").write_text(
            '(task-phase "atlas" building "first")\n'
            '(task-phase "atlas" verifying "latest")\n',
            encoding="utf-8",
        )
        (root / "chroma_db" / "memories.json").write_text(json.dumps({
            "ids": ["memory-1"],
            "documents": ["remember this"],
            "metadatas": [{"kind": "fact"}],
            "embeddings": [[1, 2, 3]],
        }), encoding="utf-8")
        (root / "memory" / "soul_state.json").write_text(
            json.dumps({"eval_count": 7}), encoding="utf-8"
        )
        (root / "memory" / "soul_skills.json").write_text(
            json.dumps({"skills": [{"name": "care"}], "self_authored": []}),
            encoding="utf-8",
        )
        (root / "transformations" / ".runtime" / "tool_reliability.json").write_text(
            json.dumps({
                "shell": {"f": 0.9, "c": 0.8, "calls": 4, "successes": 3, "failures": 1}
            }),
            encoding="utf-8",
        )

    def test_migrates_principal_state_once_using_future_writer_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            store = AtomspaceStore(root / ".runtime" / "atomspace")
            rebuilt = []
            result = migrate_legacy_state(store, lambda atoms: rebuilt.append(dict(atoms)), root)
            self.assertEqual(result["status"], "migrated")
            self.assertEqual(result["commit"], 1)
            self.assertEqual(result["summary"]["semantic_memories"], 1)
            self.assertIn(MIGRATION_KEY, store.atoms)
            self.assertIn("state:nace_belief:cap-efficacy:shell", store.atoms)
            self.assertIn("state:task:atlas", store.atoms)
            self.assertIn("verifying", store.atoms["state:task:atlas"])
            self.assertIn("state:semantic_memory:memory-1", store.atoms)
            self.assertIn("state:soul:evaluation", store.atoms)
            self.assertIn("state:soul_skill:registry", store.atoms)
            self.assertIn("state:tool_reliability:shell", store.atoms)
            self.assertEqual(len(rebuilt), 1)

            repeated = migrate_legacy_state(store, lambda _atoms: self.fail("rebuilt twice"), root)
            self.assertEqual(repeated["status"], "already_migrated")
            self.assertEqual(store.commit, 1)
            replayed = AtomspaceStore(root / ".runtime" / "atomspace")
            self.assertEqual(replayed.atoms, store.atoms)

    def test_malformed_semantic_projection_fails_before_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._fixture(root)
            memory_path = root / "chroma_db" / "memories.json"
            memory_path.write_text(json.dumps({
                "ids": ["one", "two"],
                "documents": ["only one"],
                "metadatas": [{}, {}],
                "embeddings": [[], []],
            }), encoding="utf-8")
            store = AtomspaceStore(root / ".runtime" / "atomspace")
            with self.assertRaises(RuntimeError):
                migrate_legacy_state(store, lambda _atoms: None, root)
            self.assertEqual(store.commit, 0)
            self.assertEqual(store.atoms, {})


if __name__ == "__main__":
    unittest.main()
