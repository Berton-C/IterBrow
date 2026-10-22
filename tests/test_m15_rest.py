#!/usr/bin/env python3
"""M15-F1..F2: build mode lasts until Iter rests (not 16 messages), and the bench recognises a passing probe
whichever tool returned it (Iter ran notes' probe through the python tool on 2026-10-22).

Spec: docs/milestones/M15_build_ledger.md section F.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import pending, REPO  # noqa: E402
from m14_support import transformation, system, user, assistant  # noqa: E402


class RestTests(unittest.TestCase):
    """M15-F1"""

    def test_a_build_lasts_until_iter_rests(self):
        mode = transformation("build_mode")
        rested = [system(), user("build me a todo app"), assistant(calls=[("c1", "nop", {"wait_seconds": "0"})]), user("thanks")]
        self.assertFalse(mode.active(rested), "after the rest, the build is over")
        paused = [system(), user("build me a todo app")] + [assistant(calls=[("c%d" % i, "browser_eval", {"expression": "1"})]) for i in range(20)]
        self.assertTrue(mode.active(paused), "twenty evals later the build is still on")
        timer = paused + [assistant(calls=[("t", "nop", {"wait_seconds": "60"})]), assistant(calls=[("e", "browser_eval", {"expression": "2"})])]
        self.assertTrue(mode.active(timer), "a positive wait is a pause inside the work, not a rest")
        self.assertTrue(mode.active(rested + [assistant(calls=[("o", "browser_open_app", {"app_id": "todo"})])]), "opening an app is a build signal")
        self.assertEqual(len(mode.window(rested)), 1, "the window is what came after the rest")

    def test_current_app_reads_the_same_window(self):
        mode = transformation("build_mode")
        messages = [system(), user("build me a todo app"), assistant(calls=[("n", "new_app", {"id": "todo", "title": "Todo"})])] \
            + [assistant(calls=[("c%d" % i, "browser_eval", {"expression": "1"})]) for i in range(20)]
        self.assertEqual(mode.current_app(messages), "todo")
        self.assertIsNone(mode.current_app(messages + [assistant(calls=[("r", "nop", {"wait_seconds": "0"})])]))

    def test_the_old_sixteen_message_rule_is_gone(self):
        src = (REPO / "iter" / "transformations" / "build_mode.py").read_text(encoding="utf-8")
        self.assertIn("def window(", src)
        self.assertNotIn("[-WINDOW:]", src)
        self.assertIn('"browser_open_app"', src[src.index("APP_TOOLS = "):src.index("APP_TOOLS = ") + 120])


class BenchProbeTests(unittest.TestCase):
    """M15-F2"""

    def test_a_probe_run_through_python_counts(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("m15_bench", REPO / "scripts" / "foundry_bench" / "bench.py")
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        root = Path(tempfile.mkdtemp(prefix="m15-rest-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        it = bench.Iter(root, socket_path="/nonexistent")
        call = lambda i, n, a: {"role": "assistant", "tool_calls": [{"id": i, "function": {"name": n, "arguments": json.dumps(a)}}]}  # noqa: E731
        res = lambda i, t: {"role": "tool", "tool_call_id": i, "content": t}  # noqa: E731
        (root / "experience.json").write_text(json.dumps([
            {"role": "user", "content": "Build me a notes app"},
            call("7", "python", {"code": "print(app_probe(app='notes'))"}), res("7", "Step 13:20:59: PROBE notes (probe.json): 17 passed, 0 failed\n✓ …"),
            call("8", "send", {"content": "Two results in."}), res("8", "SUCCESS")]), encoding="utf-8")
        self.assertTrue(it.probe_passed_then_reported(set(), "notes"))
        (root / "experience.json").write_text(json.dumps([
            {"role": "user", "content": "Build me a notes app"},
            call("9", "send", {"content": "PROBE notes (probe.json): 17 passed, 0 failed — I ran it"}), res("9", "SUCCESS"),
            call("10", "send", {"content": "done"}), res("10", "SUCCESS")]), encoding="utf-8")
        self.assertFalse(it.probe_passed_then_reported(set(), "notes"), "words in a send are still not a probe")


if __name__ == "__main__":
    unittest.main()
