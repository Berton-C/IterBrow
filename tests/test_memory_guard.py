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


    # Review 3 M1 -----------------------------------------------------------
    def assert_episodes_intact(self, code):
        output = self.attempt(code)
        for i in range(1, 4):
            path = Path("memory/recap/episode_%04d.json" % i)
            self.assertTrue(path.exists(), "episode %d deleted by: %s\n%s" % (i, code, output))
        self.assertIn("BLOCKED", output, code)
        return output

    def test_rmtree_of_the_recap_folder_is_refused_before_anything_is_deleted(self):
        Path("memory/recap/notes.txt").write_text("unprotected neighbour")
        self.assert_episodes_intact("import shutil; shutil.rmtree('memory/recap')")
        self.assertTrue(Path("memory/recap/notes.txt").exists(), "rmtree deleted part of the tree first")
        self.assert_episodes_intact("import shutil; shutil.rmtree('memory')")

    def test_dir_fd_relative_unlink_and_rename_are_resolved(self):
        self.assert_episodes_intact(
            "import os; fd = os.open('memory/recap', os.O_RDONLY)\n"
            "os.unlink('episode_0001.json', dir_fd=fd)")
        self.assert_tier3_intact(
            "import os; fd = os.open('memory/tiers', os.O_RDONLY)\n"
            "os.close(os.open('tier3.txt', os.O_WRONLY | os.O_TRUNC, dir_fd=fd))")
        Path("evil.txt").write_text("REPLACED")
        self.assert_tier3_intact(
            "import os; fd = os.open('memory/tiers', os.O_RDONLY)\n"
            "os.replace('evil.txt', 'tier3.txt', dst_dir_fd=fd)")

    def test_rmdir_of_a_protected_folder_is_refused(self):
        output = self.attempt("import os; os.rmdir('memory/recap')")
        self.assertIn("BLOCKED", output)
        self.assertTrue(Path("memory/recap").is_dir())

    def test_unresolvable_dir_fd_refuses_only_protected_file_names(self):
        guard = load("tools/_memory_guard.py")
        guard._fd_path = lambda fd: None
        with self.assertRaises(PermissionError):
            guard.check_remove("episode_0001.json", dir_fd=99)
        with self.assertRaises(PermissionError):
            guard.check_remove("tier3.txt", dir_fd=99)
        guard.check_remove("notes.txt", dir_fd=99)  # not a protected name: allowed

    def test_same_file_names_outside_the_iter_root_layout_are_not_protected(self):
        output = self.attempt(
            "import os, shutil; os.makedirs('apps/demo/memory/recap', exist_ok=True)\n"
            "open('apps/demo/chat.txt','w').write('demo chat')\n"
            "open('apps/demo/transcript.txt','w').write('demo transcript')\n"
            "open('apps/demo/history.metta','w').write('demo')\n"
            "open('apps/demo/memory/recap/episode_0001.json','w').write('{}')\n"
            "open('apps/demo/memory/recap/episode_0001.json','w').write('{}')\n"
            "shutil.rmtree('apps/demo')\n"
            "print('DEMO-OK')")
        self.assertNotIn("BLOCKED", output)
        self.assertIn("DEMO-OK", output)
        self.assertFalse(Path("apps/demo").exists())

    def test_root_logs_stay_protected_by_any_spelling(self):
        Path("chat.txt").write_text("real chat\n")
        for spelling in ("chat.txt", os.path.abspath("chat.txt"),
                         "memory/../chat.txt", "../%s/chat.txt" % Path.cwd().name):
            output = self.attempt("open(%r, 'w').write('GONE')" % spelling)
            self.assertIn("BLOCKED", output, spelling)
        self.assertEqual(Path("chat.txt").read_text(), "real chat\n")


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
