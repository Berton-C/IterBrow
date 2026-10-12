#!/usr/bin/env python3
"""Milestone 1: a corrupt experience.json must never crash Iter at startup."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "iter") not in sys.path:
    sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.episodic_history import load_experience


class ExperienceLoadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.previous = os.getcwd()
        os.chdir(self.temporary.name)
        self.logged = []

    def tearDown(self):
        os.chdir(self.previous)
        self.temporary.cleanup()

    def test_missing_file_starts_empty(self):
        self.assertEqual(load_experience(log=self.logged.append), [])

    def test_valid_file_is_loaded(self):
        history = [{"role": "user", "content": "hello"}]
        Path("experience.json").write_text(json.dumps(history), encoding="utf-8")
        self.assertEqual(load_experience(log=self.logged.append), history)

    def test_truncated_file_is_quarantined_not_fatal(self):
        Path("experience.json").write_text('[{"role": "user", "content": "hel', encoding="utf-8")
        self.assertEqual(load_experience(log=self.logged.append), [])
        self.assertFalse(Path("experience.json").exists())
        quarantined = list(Path(".").glob("experience.json.corrupt-*"))
        self.assertEqual(len(quarantined), 1)
        self.assertIn('"hel', quarantined[0].read_text(encoding="utf-8"))
        self.assertTrue(self.logged and "unreadable" in self.logged[0])

    def test_empty_and_wrong_shape_files_are_quarantined(self):
        for payload in ("", "{}"):
            Path("experience.json").write_text(payload, encoding="utf-8")
            self.assertEqual(load_experience(log=self.logged.append), [])
            self.assertFalse(Path("experience.json").exists())

    def test_iter_startup_uses_the_safe_loader(self):
        source = (ROOT / "iter" / "iter.py").read_text(encoding="utf-8")
        self.assertIn("load_experience(", source)
        self.assertNotIn('open("experience.json", "r"', source)


if __name__ == "__main__":
    unittest.main()
