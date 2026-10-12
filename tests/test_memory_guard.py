#!/usr/bin/env python3
"""Tier/episode write guard in the python tool, shell tool and rollup_helper (BUG-7)."""
import builtins
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_episodic_memory import EpisodicCase, ITER, load  # noqa: E402


class PythonToolGuardTests(EpisodicCase):
    def setUp(self):
        super().setUp()
        self.write_episodes(range(1, 4))
        load("tools/rebuild_tiers.py").rebuild()
        self.python = load("tools/python.py")
        self.original = self.tier("tier3")

    def attempt(self, code):
        output = str(self.python.run(code))
        return output

    def assert_tier3_intact(self, code):
        output = self.attempt(code)
        self.assertTrue(Path("memory/tiers/tier3.txt").exists(), "tier3 deleted by: " + code)
        self.assertEqual(self.tier("tier3"), self.original, "tier3 changed by: %s\n%s" % (code, output))
        self.assertIn("BLOCKED", output, code)

    def test_bug7_pathlib_write_text_is_blocked(self):
        self.assert_tier3_intact("import pathlib; pathlib.Path('memory/tiers/tier3.txt').write_text('X')")

    def test_bug7_io_open_and_plus_modes_are_blocked(self):
        self.assert_tier3_intact("import io; io.open('memory/tiers/tier3.txt','w').write('IO')")
        self.assert_tier3_intact("f=open('memory/tiers/tier3.txt','r+'); f.write('RPLUS'); f.close()")
        self.assert_tier3_intact("open('memory/tiers/tier3.txt','a').write('APPEND')")

    def test_bug7_low_level_and_module_imports_are_blocked(self):
        self.assert_tier3_intact("import os; os.remove('memory/tiers/tier3.txt')")
        self.assert_tier3_intact("from os import unlink; unlink('memory/tiers/tier3.txt')")
        self.assert_tier3_intact("import os; os.close(os.open('memory/tiers/tier3.txt', os.O_WRONLY | os.O_TRUNC))")
        self.assert_tier3_intact("import pathlib; pathlib.Path('memory/tiers/tier3.txt').unlink()")

    def test_bug7_rename_or_replace_onto_a_protected_destination_is_blocked(self):
        Path("evil.txt").write_text("REPLACED")
        self.assert_tier3_intact("import os; os.replace('evil.txt', 'memory/tiers/tier3.txt')")
        Path("evil2.json").write_text('{"e": 2, "s": "FORGED"}')
        output = self.attempt("import os; os.rename('evil2.json', 'memory/recap/episode_0002.json')")
        self.assertIn("BLOCKED", output)
        self.assertEqual(json.loads(Path("memory/recap/episode_0002.json").read_text())["s"], "ep 2")

    def test_bug7_existing_episode_cannot_be_overwritten_in_place(self):
        output = self.attempt("f=open('memory/recap/episode_0001.json','r+'); f.write('{\"e\":1,\"s\":\"FORGED\"}   '); f.close()")
        self.assertIn("BLOCKED", output)
        self.assertEqual(json.loads(Path("memory/recap/episode_0001.json").read_text())["s"], "ep 1")

    def test_bug7_sanctioned_and_harmless_writes_still_work(self):
        output = self.attempt(
            "open('memory/recap/episode_0004.json','x').write('{\"e\": 4, \"s\": \"new\"}')\n"
            "open('history.metta','a').write('(\"2026-10-01 09:00:00\" \"HUMAN_MESSAGE: hi\")\\n')\n"
            "open('notes.txt','w').write('ok')\n"
            "print(rebuild_tiers())\n"
            "print(open('memory/tiers/tier3.txt').read())")
        self.assertNotIn("BLOCKED", output)
        self.assertIn("E4: new", output)
        self.assertEqual(Path("notes.txt").read_text(), "ok")

    def test_bug7_guard_is_removed_after_the_python_tool_returns(self):
        real_open, real_io_open, real_remove = builtins.open, io.open, os.remove
        self.attempt("x = 1")
        self.assertIs(builtins.open, real_open)
        self.assertIs(io.open, real_io_open)
        self.assertIs(os.remove, real_remove)


class ShellAndHelperGuardTests(EpisodicCase):
    def setUp(self):
        super().setUp()
        self.write_episodes(range(1, 4))
        load("tools/rebuild_tiers.py").rebuild()
        self.original = self.tier("tier3")

    def test_bug7_shell_python_one_liner_on_a_tier_is_blocked_best_effort(self):
        output = str(load("tools/shell.py").run("python3 -c \"open('memory/tiers/tier3.txt','w').write('SHELLPY')\""))
        self.assertIn("BLOCKED", output)
        self.assertEqual(self.tier("tier3"), self.original)
        self.assertIn("E3", str(load("tools/shell.py").run("cat memory/tiers/tier3.txt")))

    def test_bug7_rollup_helper_no_longer_trims_or_appends_tiers(self):
        for args in (["trim", "tier3", "5"], ["append", "tier4", "hand-written era"]):
            result = subprocess.run([sys.executable, str(ITER / "rollup_helper.py")] + args,
                                    capture_output=True, text=True, cwd=str(self.dir))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rebuild_tiers", result.stdout + result.stderr)
        self.assertEqual(self.tier("tier3"), self.original)
        self.assertEqual(self.tier("tier4"), "")


if __name__ == "__main__":
    unittest.main()
