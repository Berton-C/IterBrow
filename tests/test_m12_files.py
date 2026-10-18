#!/usr/bin/env python3
"""M12-B1..B8: the hands — read_file, write_file, edit_file, list_files, grep_files, shell with cwd and
timeout, run_tests, and self_improve's honest refusal of non-Python targets.

Spec: docs/milestones/M12_builder_hands.md section B.
"""
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m12_support import pending, require_m12, m12_root, tool_text, ITER_SRC, REPO  # noqa: E402


class FileToolsTests(unittest.TestCase):
    """M12-B1..B5"""

    def setUp(self):
        self.r = m12_root("m12files", with_main_js=True)
        self.addCleanup(self.r.close)

    def test_read_file_pages_numbered_lines(self):
        require_m12()
        (self.r.root / "demo.txt").write_text("".join("line %d\n" % i for i in range(1, 501)), encoding="utf-8")
        out = tool_text(self.r, "read_file", path="demo.txt")
        lines = out.splitlines()
        self.assertEqual(lines[0], "demo.txt (lines 1–200 of 500)")
        self.assertEqual(lines[1], "    1| line 1")
        self.assertEqual(lines[-1], "  200| line 200")
        page = tool_text(self.r, "read_file", path="demo.txt", offset="490", limit="50")
        self.assertEqual(page.splitlines()[0], "demo.txt (lines 490–500 of 500)")
        self.assertEqual(page.splitlines()[-1], "  500| line 500")
        self.assertTrue(tool_text(self.r, "read_file", path="nope.txt").startswith("ERROR: no file at nope.txt"))
        self.assertTrue(tool_text(self.r, "read_file", path="tools").startswith("ERROR: tools is a directory"))
        (self.r.root / "big.txt").write_text("x" * 30000 + "\n" + "tail\n", encoding="utf-8")
        cut = tool_text(self.r, "read_file", path="big.txt")
        self.assertLessEqual(len(cut), 24500)
        self.assertIn("cut", cut.splitlines()[0])
        (self.r.root / "bin.dat").write_bytes(b"\xff\xfe\x00binary")
        self.assertTrue(tool_text(self.r, "read_file", path="bin.dat").startswith("ERROR"), "non-UTF-8 says so")

    def test_paths_stay_inside_the_repo_and_never_cross_a_symlink_out(self):
        # The parent holds main.js (m12_root with_main_js), so it is the repo root: ../main.js is readable.
        self.assertIn("repo root marker", tool_text(self.r, "read_file", path="../main.js"))
        self.assertTrue(tool_text(self.r, "read_file", path="../../etc/passwd").startswith("REFUSED:"))
        self.assertTrue(tool_text(self.r, "read_file", path="/etc/passwd").startswith("REFUSED:"))
        os.symlink("/", self.r.root / "escape")
        self.assertTrue(tool_text(self.r, "read_file", path="escape/etc/hostname").startswith("REFUSED:"))
        for forbidden in ("../.git/config", "../node_modules/x.js", ".venv/pyvenv.cfg"):
            self.assertTrue(tool_text(self.r, "write_file", path=forbidden, content="x").startswith("REFUSED:"), forbidden)
        self.assertFalse((self.r.root.parent / ".git").exists())

    def test_write_file_is_atomic_and_reports(self):
        out = tool_text(self.r, "write_file", path="apps-test/deep/index.html", content="<h1>hi</h1>\n")
        self.assertEqual(out, "WROTE apps-test/deep/index.html (12 bytes, 1 lines)")
        self.assertEqual((self.r.root / "apps-test" / "deep" / "index.html").read_text(encoding="utf-8"), "<h1>hi</h1>\n")
        self.assertEqual(tool_text(self.r, "write_file", path="apps-test/deep/index.html", content="<h1>hi</h1>\n"),
                         "WROTE apps-test/deep/index.html (unchanged)")
        self.assertEqual([p.name for p in (self.r.root / "apps-test" / "deep").iterdir()], ["index.html"], "no temp file left behind")
        script = self.r.root / "run.sh"
        script.write_text("#!/bin/sh\necho 1\n", encoding="utf-8"); script.chmod(0o755)
        tool_text(self.r, "write_file", path="run.sh", content="#!/bin/sh\necho 2\n")
        self.assertEqual(script.stat().st_mode & 0o777, 0o755, "mode kept")
        self.assertTrue(tool_text(self.r, "write_file", path="huge.txt", content="y" * (2 * 1024 * 1024 + 1)).startswith("REFUSED:"))

    def test_edit_file_replaces_exactly_one_occurrence(self):
        (self.r.root / "app.js").write_text("const a = 1;\nconst b = 2;\nconst c = a + b;\nconsole.log(c);\n", encoding="utf-8")
        out = tool_text(self.r, "edit_file", path="app.js", old="const b = 2;", new="const b = 20;\nconst b2 = 21;")
        self.assertEqual(out.splitlines()[0], "EDITED app.js (+2 −1 lines)")
        self.assertIn("    2| const b = 20;", out)
        self.assertIn("    3| const b2 = 21;", out)
        self.assertIn("    1| const a = 1;", out, "two lines of context")
        self.assertEqual((self.r.root / "app.js").read_text(encoding="utf-8"), "const a = 1;\nconst b = 20;\nconst b2 = 21;\nconst c = a + b;\nconsole.log(c);\n")
        before = (self.r.root / "app.js").read_text(encoding="utf-8")
        self.assertEqual(tool_text(self.r, "edit_file", path="app.js", old="const", new="let").splitlines()[0], "EDIT-FAILED: old text occurs 4 times in app.js")
        self.assertEqual(tool_text(self.r, "edit_file", path="app.js", old="nothing here", new="x").splitlines()[0], "EDIT-FAILED: old text occurs 0 times in app.js")
        self.assertEqual((self.r.root / "app.js").read_text(encoding="utf-8"), before, "a failed edit changes nothing")
        self.assertEqual(tool_text(self.r, "edit_file", path="app.js", old="console.log(c);\n", new="").splitlines()[0], "EDITED app.js (+0 −1 lines)")
        self.assertNotIn("console.log", (self.r.root / "app.js").read_text(encoding="utf-8"))

    def test_list_files_relative_sorted_and_skipping_noise(self):
        for rel in ("proj/a.py", "proj/sub/b.js", "proj/node_modules/x.js", "proj/__pycache__/a.pyc", "proj/.git/HEAD"):
            path = self.r.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x\n", encoding="utf-8")
        out = tool_text(self.r, "list_files", path="proj")
        self.assertEqual(out.splitlines(), ["proj/a.py  2", "proj/sub/"])
        deep = tool_text(self.r, "list_files", path="proj", glob="**/*.js")
        self.assertEqual(deep.splitlines(), ["proj/sub/b.js  2"])
        for i in range(5):
            (self.r.root / "proj" / ("f%d.txt" % i)).write_text("x", encoding="utf-8")
        capped = tool_text(self.r, "list_files", path="proj", glob="f*.txt", limit="3")
        self.assertEqual(len(capped.splitlines()), 4)
        self.assertEqual(capped.splitlines()[-1], "… and 2 more")

    def test_grep_files_reports_path_line_text(self):
        (self.r.root / "g1.py").write_text("def alpha():\n    return 'Alpha'\n", encoding="utf-8")
        (self.r.root / "g2.js").write_text("const alpha = 1;\n", encoding="utf-8")
        (self.r.root / "g3.bin").write_bytes(b"alpha\x00\xff")
        out = tool_text(self.r, "grep_files", pattern="alpha", path=".", glob="g*")
        self.assertEqual(sorted(out.splitlines()), ["g1.py:1: def alpha():", "g2.js:1: const alpha = 1;"])
        self.assertEqual(len(tool_text(self.r, "grep_files", pattern="(?i)alpha", glob="g*.py").splitlines()), 2)
        self.assertEqual(tool_text(self.r, "grep_files", pattern="omega", glob="g*"), "NO MATCHES")
        capped = tool_text(self.r, "grep_files", pattern="alpha", glob="g*", limit="1")
        self.assertEqual(capped.splitlines()[-1], "… and more")


class ShellTests(unittest.TestCase):
    """M12-B6"""

    def setUp(self):
        self.r = m12_root("m12shell", with_main_js=True)
        self.addCleanup(self.r.close)

    def test_cwd_timeout_and_stderr_section(self):
        require_m12()
        (self.r.root / "sub").mkdir()
        self.assertEqual(tool_text(self.r, "shell", cmd="basename \"$PWD\"", cwd="sub").strip(), "SUCCESS, RETURN: sub")
        self.assertEqual(tool_text(self.r, "shell", cmd="basename \"$PWD\"", cwd="..").strip(), "SUCCESS, RETURN: " + self.r.root.parent.name)
        self.assertTrue(tool_text(self.r, "shell", cmd="pwd", cwd="../..").startswith("REFUSED:"))
        out = tool_text(self.r, "shell", cmd="echo out; echo err 1>&2; exit 3")
        self.assertTrue(out.startswith("FAILED (exit 3), RETURN: out\n"), out)
        self.assertIn("--- stderr ---\nerr", out)
        self.assertNotIn("--- stderr ---", tool_text(self.r, "shell", cmd="echo only"))
        started = time.monotonic()
        out = tool_text(self.r, "shell", cmd="echo before; sleep 20; echo after", timeout="1")
        self.assertLess(time.monotonic() - started, 10)
        self.assertTrue(out.startswith("FAILED (timeout after 1s), RETURN: before"), out)
        venv = tool_text(self.r, "shell", cmd="python3 -c 'import sys; print(sys.prefix)'")
        self.assertIn(".venv", venv, "python3 in the shell is the venv")


class RunTestsTests(unittest.TestCase):
    """M12-B7"""

    def test_runs_a_target_from_the_repo_root_and_summarises(self):
        require_m12()
        r = m12_root("m12runtests", with_main_js=True)
        self.addCleanup(r.close)
        tests = r.root.parent / "tests"
        tests.mkdir()
        (tests / "test_m12_tiny.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n\ndef test_skip():\n    import unittest; raise unittest.SkipTest('x')\n", encoding="utf-8")
        out = tool_text(r, "run_tests", target="tests/test_m12_tiny.py")
        self.assertRegex(out.splitlines()[0], r"^RESULT: 1 passed, 1 skipped in [\d.]+s$")
        self.assertIn("--- output ---", out)
        (tests / "test_m12_bad.py").write_text("def test_no():\n    assert False, 'boom'\n", encoding="utf-8")
        out = tool_text(r, "run_tests", target="test_m12_bad")
        self.assertRegex(out.splitlines()[0], r"^RESULT: 1 failed")
        self.assertIn("boom", out)
        self.assertLessEqual(len(out.splitlines()), 64)
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertRegex(src, r'"run_tests":\s*900')
        self.assertIn("pytest", (REPO / "scripts" / "requirements-dev.txt").read_text(encoding="utf-8"))
        self.assertIn("requirements-dev.txt", (REPO / "scripts" / "setup_python_env.sh").read_text(encoding="utf-8"))


class SelfImproveTests(unittest.TestCase):
    """M12-B8"""

    def test_self_improve_refuses_non_python_targets_without_touching_them(self):
        require_m12()
        r = m12_root("m12selfimprove")
        self.addCleanup(r.close)
        page = r.root / "mapstation-test" / "index.html"
        page.parent.mkdir()
        page.write_text("<h1>before</h1>\n", encoding="utf-8")
        out = tool_text(r, "self_improve", action="apply", target="mapstation-test/index.html", content="<h1>after</h1>\n", description="x")
        self.assertIn("Python components only", out)
        self.assertIn("write_file", out)
        self.assertEqual(page.read_text(encoding="utf-8"), "<h1>before</h1>\n")


if __name__ == "__main__":
    unittest.main()
