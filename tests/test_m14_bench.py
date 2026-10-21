#!/usr/bin/env python3
"""M14-G1..G3: the five-app benchmark — the briefs validate, `score` and the table are pure, the docs exist.

Spec: docs/milestones/M14_vault_and_foundry_loop.md section G.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m14_support import pending, require_m14, node, NODE, BRIDGE, REPO  # noqa: E402

BENCH = REPO / "scripts" / "foundry_bench"
FIVE = ["todo", "pomodoro", "notes", "convert", "kanban"]


def bench_module():
    path = BENCH / "bench.py"
    if not path.exists():
        raise AssertionError("missing " + str(path))
    spec = importlib.util.spec_from_file_location("m14_bench", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BriefsTests(unittest.TestCase):
    """M14-G1"""

    @unittest.skipUnless(NODE, "needs node")
    def test_five_briefs_each_with_a_valid_probe(self):
        require_m14()
        briefs = json.loads((BENCH / "briefs.json").read_text(encoding="utf-8"))
        self.assertEqual([b["id"] for b in briefs], FIVE)
        for brief in briefs:
            self.assertTrue(brief["ask"].strip(), brief["id"])
            self.assertTrue(brief["main_action"].strip(), brief["id"])
            self.assertGreaterEqual(len(brief["probe"]["assertions"]), 3, brief["id"])
            code, out, err = node("const F = require(%s); process.stdout.write(JSON.stringify(F.validateProbeSpec(%s)));"
                                  % (json.dumps(str(BRIDGE / "foundry_apps.js")),
                                     json.dumps(dict(brief["probe"], appId=brief["id"]))))
            self.assertEqual(code, 0, (brief["id"], err))
        for brief in briefs:
            self.assertIn("iterate", brief, "each brief carries its iteration ask")
        self.assertIn("persist", briefs[0]["ask"].lower())


class ScoreTests(unittest.TestCase):
    """M14-G2"""

    RECORD = {"app": "todo", "model": "gpt-6-luna", "cycles": 14, "tool_calls": 11, "sends_before_report": 1,
              "sends_without_tool_result": 0, "cards": 2, "probe_passed": True, "elapsed_s": 412.5,
              "iteration_kept_working": True, "baseline": False}

    def test_score_and_table(self):
        bench = bench_module()
        self.assertEqual(bench.score(self.RECORD), {"built": True, "kept": True, "theatre": 0})
        theatre = dict(self.RECORD, probe_passed=False, sends_without_tool_result=7, iteration_kept_working=None)
        self.assertEqual(bench.score(theatre), {"built": False, "kept": None, "theatre": 7})
        table = bench.table([self.RECORD, dict(theatre, app="kanban")])
        lines = table.splitlines()
        self.assertTrue(lines[0].startswith("app"))
        self.assertTrue(any(line.startswith("todo") and "yes" in line for line in lines), table)
        self.assertTrue(any(line.startswith("kanban") and "no" in line for line in lines), table)
        self.assertIn("gpt-6-luna", table)

    def test_replies_are_read_from_the_durable_log(self):
        """M14-G2 (2026-10-19 run: every app 'unreported' for 20 min because the outbox is emptied by the sidebar)."""
        import tempfile, time, os
        bench = bench_module()
        root = Path(tempfile.mkdtemp(prefix="m14-benchlog-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        ui = root / ".runtime" / "electron_ui"
        ui.mkdir(parents=True)
        now = time.time()
        (ui / "messages.jsonl").write_text("\n".join(json.dumps(r) for r in [
            {"role": "user", "content": "Build me a todo app", "at": int((now - 100) * 1000)},
            {"role": "iter", "content": "old reply", "at": int((now - 50) * 1000)},
            {"role": "iter", "content": "Todo is built; the probe passed 4/4", "at": int((now + 5) * 1000)}]) + "\n", encoding="utf-8")
        it = bench.Iter(root, socket_path="/nonexistent")
        self.assertEqual(it.replies_since(now), ["Todo is built; the probe passed 4/4"])
        # A report is evidence in Iter's own record (a passing probe, then a reply), not words in a message.
        self.assertIsNone(it.wait_report("todo", now, timeout=1, idle=1), "words alone are not a report (2026-10-20 run)")
        call = lambda i, n, a: {"role": "assistant", "tool_calls": [{"id": i, "function": {"name": n, "arguments": json.dumps(a)}}]}  # noqa: E731
        res = lambda i, t: {"role": "tool", "tool_call_id": i, "content": t}  # noqa: E731
        (root / "experience.json").write_text(json.dumps([
            {"role": "user", "content": "Build me a todo app"},
            call("1", "app_probe", {"app": "todo"}), res("1", "PROBE todo (probe.json): 2 passed, 1 failed"),
            call("2", "send", {"content": "adding the workflow probe"}), res("2", "SUCCESS"),
            call("3", "app_probe", {"app": "todo"}), res("3", "Step 12:00: [NACE advisory] PROBE todo (probe.json): 3 passed, 0 failed"),
            call("4", "send", {"content": "Todo is built; the probe passed 4/4"}), res("4", "SUCCESS")]), encoding="utf-8")
        self.assertEqual(it.wait_report("todo", now, timeout=1, idle=1), "Todo is built; the probe passed 4/4")
        self.assertFalse(it.probe_passed_then_reported(set(), "kanban"))
        self.assertFalse(it.probe_passed_then_reported({"1", "2", "3", "4"}, "todo"), "the passing probe must come after the ask")
        # Counting by tool-call ids survives the loop rotating experience.json (2026-10-20: "0 cycles").
        mark = it.experience_mark()
        self.assertEqual(mark, {"1", "2", "3", "4"})
        rotated = [call("3", "app_probe", {"app": "todo"}), res("3", "PROBE todo (probe.json): 3 passed, 0 failed"),
                   call("4", "send", {"content": "x"}), res("4", "SUCCESS"),
                   call("5", "edit_file", {"path": "vault/todo/index.html"}), res("5", "EDITED vault/todo/index.html (+1 −1 lines)"),
                   call("6", "send", {"content": "y"}), res("6", "SUCCESS")]
        (root / "experience.json").write_text(json.dumps(rotated), encoding="utf-8")
        self.assertEqual([m.get("tool_call_id") or m["tool_calls"][0]["id"] for m in it.experience_since(mark)], ["5", "5", "6", "6"])
        self.assertEqual(bench.count_loop(it.experience_since(mark))["cycles"], 2)
        # Preflight refuses to start without a live Iter, with asks waiting, or with the app folders present.
        self.assertIn("heartbeat", it.preflight())
        (root / ".runtime" / "recovery").mkdir(parents=True)
        (root / ".runtime" / "recovery" / "iter_heartbeat.json").write_text(json.dumps({"at": now, "phase": "request_blocked", "detail": "RequestBudgetExceeded: over"}), encoding="utf-8")
        self.assertIn("blocked", it.preflight(), "a blocked Iter is not a live Iter (2026-10-21)")
        (root / ".runtime" / "recovery" / "iter_heartbeat.json").write_text(json.dumps({"at": now, "phase": "idle_wait"}), encoding="utf-8")
        (ui / "inbox").mkdir()
        (ui / "inbox" / "1.txt").write_text("hi", encoding="utf-8")
        self.assertIn("inbox", it.preflight())
        (ui / "inbox" / "1.txt").unlink()
        self.assertIn("apps folder", it.preflight())
        vault = root / "vault"
        (vault / "todo").mkdir(parents=True)
        (root / ".runtime" / "settings.json").write_text(json.dumps({"vault": str(vault)}), encoding="utf-8")
        self.assertIn("todo", it.preflight())
        (vault / "todo").rmdir()
        self.assertIsNone(it.preflight())

    def test_bench_shape(self):
        src = (BENCH / "bench.py").read_text(encoding="utf-8")
        for word in ("--app", "--baseline", "ITER_DIR", "inbox", "probe", "experience.json", "docs/bench/", "iteration_kept_working", "IDLE_TIMEOUT"):
            self.assertIn(word, src, word)
        self.assertIn("def score(", src)
        self.assertIn("def table(", src)


class DocsTests(unittest.TestCase):
    """M14-G3"""

    def test_docs(self):
        require_m14()
        readme = (REPO / "docs" / "bench" / "README.md").read_text(encoding="utf-8")
        for word in ("bench.py", "built", "kept", "theatre", "--baseline"):
            self.assertIn(word, readme, word)
        roadmap = (REPO / "docs" / "soul" / "SOUL_IN_THE_FOUNDRY.md").read_text(encoding="utf-8")
        self.assertIn("M14_vault_and_foundry_loop.md", roadmap)
        spec = (REPO / "docs" / "milestones" / "M14_vault_and_foundry_loop.md").read_text(encoding="utf-8")
        self.assertIn("Implementation notes", spec)
        self.assertNotIn("not implemented", spec.splitlines()[2])


if __name__ == "__main__":
    unittest.main()
