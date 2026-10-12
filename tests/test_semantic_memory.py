#!/usr/bin/env python3
"""Semantic (fact) memory: AtomSpace authority + chroma_db search index.

Every test drives the real tools in fresh processes against the real AtomSpace
service (see semantic_memory_support.py); the bug each class guards is named in
its docstring (B1..B15, S1 from the semantic-memory audit).
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_memory_support import SemanticRoot, ITER_SRC  # noqa: E402

MEMORY_TOOLS = ["remember", "chroma_query", "forget", "memory_update", "support", "contradict",
                "link_episode", "unlink_episode", "formalize_metta"]


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.r = SemanticRoot(self.id().rsplit(".", 1)[-1][:20])
        self.addCleanup(self.r.close)
        self.r.start()


class ToolImportPathTests(ServiceTestCase):
    """B9: hot-loaded tools must import _petta_db from their own generation, and
    B14: the memory journal belongs to ITER_DIR, not to the worker's cwd."""

    def test_every_memory_tool_imports_petta_db_from_its_own_directory(self):
        generation = self.r.root / ".runtime" / "hotload" / "generations" / "cand-1" / "tools"
        shutil.copytree(self.r.root / "tools", generation)
        for tool in MEMORY_TOOLS:
            for variant in (tool, "_" + tool):
                if not (generation / (variant + ".py")).exists():
                    continue
                kwargs = {
                    "remember": {"text": "generation probe"}, "chroma_query": {"query": "x"},
                    "forget": {"item_id": "nope"}, "memory_update": {"item_id": "nope", "text": "x"},
                    "support": {"item_id": "nope", "episode_time": "E"},
                    "contradict": {"item_id": "nope", "episode_time": "E"},
                    "link_episode": {"item_id": "nope", "linked_time": "E"},
                    "unlink_episode": {"item_id": "nope", "linked_time": "E"},
                    "formalize_metta": {"LTM_item": "nope", "formalization": "(--> a b)"},
                }[tool]
                result = self.r.tool(variant, tool_dir=generation, **kwargs)
                self.assertEqual(result.get("petta_file"), str(generation / "_petta_db.py"),
                                 "%s loaded the wrong _petta_db: %r" % (variant, result))

    def test_journal_is_written_under_iter_dir_whatever_the_cwd(self):
        elsewhere = Path(tempfile.mkdtemp(prefix="iterbrow-cwd-"))
        self.addCleanup(shutil.rmtree, elsewhere, True)
        result = self.r.text("remember", text="journal location probe", cwd=elsewhere)
        self.assertTrue(result.startswith("REMEMBER-SUCCESS"), result)
        self.assertTrue((self.r.root / "memory" / "journal.jsonl").exists())
        self.assertFalse((elsewhere / "memory" / "journal.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
