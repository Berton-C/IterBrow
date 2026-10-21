#!/usr/bin/env python3
"""M15-A1..A4: the request never wedges silently — a calibrated estimate, degrade before blocking, one
notice when blocked, a bench that sees it.

Spec: docs/milestones/M15_build_ledger.md section A.
"""
import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m15_support import pending, require_m15, runtime_module, openai_tools, ITER_SRC, REPO  # noqa: E402


class CalibrationTests(unittest.TestCase):
    """M15-A1"""

    def test_ratio_is_the_median_of_recent_pairs_clamped(self):
        budget = runtime_module("request_budget")
        self.assertEqual(budget.calibration([]), 1.0)
        self.assertEqual(budget.calibration([{"estimated": 44204, "actual": 25380}] * 2), 1.0, "fewer than 3 records: no calibration")
        records = [{"estimated": 44204, "actual": 25380}, {"estimated": 42831, "actual": 21891},
                   {"estimated": 44406, "actual": 24948}, {"estimated": 40000, "actual": 22000}]  # Berton's logs, 2026-10-19/20
        ratio = budget.calibration(records)
        self.assertAlmostEqual(ratio, 0.5559, places=3)  # median of 0.5111, 0.55, 0.5618, 0.5742
        self.assertEqual(budget.calibration([{"estimated": 100, "actual": 1}] * 5), 0.4, "clamped low")
        self.assertEqual(budget.calibration([{"estimated": 100, "actual": 500}] * 5), 1.2, "clamped high")
        self.assertEqual(budget.calibration([{"estimated": 0, "actual": 5}] * 5 + [{"estimated": 100, "actual": 60}] * 3), 0.6, "bad pairs ignored")
        self.assertEqual(budget.calibration([{"estimated": 100, "actual": 60}] * 40), 0.6)
        self.assertEqual(budget.DEFAULT_INPUT_TOKENS, 45000, "the ceiling is settled")

    def test_project_request_applies_the_ratio_and_reports_it(self):
        require_m15()
        budget = runtime_module("request_budget")
        src = (ITER_SRC / "iterbrow_runtime" / "request_budget.py").read_text(encoding="utf-8")
        self.assertIn("def calibration(", src)
        self.assertIn("calibrated_input_tokens", src)
        messages = [{"role": "system", "content": "s" * 60000}, {"role": "user", "content": "hi"}]  # ≈ 20k estimated
        tools = openai_tools(["send"])
        _messages, _tools, report = budget.project_request(messages, tools, 45000, messages[-1], calibration_ratio=0.55)
        # 60k chars ≈ 20k estimated: fits either way; at 0.55 it is ≈ 11k and the report says so.
        text = json.dumps(report)
        self.assertRegex(text, r'"calibration": 0\.55')
        self.assertRegex(text, r'"calibrated_input_tokens": \d+')

    def test_loop_records_estimate_and_actual_pairs(self):
        require_m15()
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn("model_usage_calibration.jsonl", src)
        self.assertIn("calibration(", src)
        manifest = json.loads((ITER_SRC / "state_manifest.json").read_text(encoding="utf-8"))
        entry = next((e for e in manifest["entries"] if e["path"] == ".runtime/model_usage_calibration.jsonl"), None)
        self.assertIsNotNone(entry)
        self.assertEqual((entry["role"], entry["reset"], entry["portable"]), ("cache", True, False))


class DegradeTests(unittest.TestCase):
    """M15-A2"""

    def test_degrade_order_and_fit(self):
        budget = runtime_module("request_budget")
        over = {"total": 47224, "tool_schemas_unprotected": 9000, "descriptions_excess": 3000, "observations_old": 6000}
        self.assertEqual(budget.degrade(over, 45000), ["tool_schemas"])
        self.assertEqual(budget.degrade(dict(over, tool_schemas_unprotected=1500), 45000), ["tool_schemas", "descriptions"])
        self.assertEqual(budget.degrade(dict(over, tool_schemas_unprotected=500, descriptions_excess=500), 45000),
                         ["tool_schemas", "descriptions", "observations"])
        self.assertIsNone(budget.degrade(dict(over, tool_schemas_unprotected=0, descriptions_excess=0, observations_old=0), 45000))
        self.assertEqual(budget.degrade(dict(over, total=44000), 45000), [], "nothing to do when it fits")

    def test_loop_applies_the_plan_before_blocking(self):
        require_m15()
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn("degrade(", src)
        self.assertIn('"degraded"', src)
        self.assertIn("PROTECTED_TOOL_NAMES", src[src.index("degrade("):src.index("degrade(") + 3000], "protected tools never leave the request")


class NoticeTests(unittest.TestCase):
    """M15-A3"""

    def test_notice_text_and_once(self):
        require_m15()
        src = (ITER_SRC / "iter.py").read_text(encoding="utf-8")
        self.assertIn("def blocked_notice(", src)
        start = src.index("def blocked_notice(")
        end = src.index("\ndef ", start + 10)
        namespace = {"re": re}
        exec(src[start:end], namespace)  # noqa: S102 — our own source
        notice = namespace["blocked_notice"]
        message = ("RequestBudgetExceeded: Protected input estimates 47224 tokens, above the 45000 input target. Over by 2224; "
                   "approximate components: {\"assistant_tool\": 0, \"images\": 1, \"runtime_observations\": 9176, \"system\": 19695, "
                   "\"tool_schemas\": 16993, \"user\": 1087}. Current user, latest tool exchange and stored memories were preserved; request was not sent.")
        text = notice(ValueError(message))
        self.assertTrue(text.startswith("I can't send this request: it is ~2,224 tokens over the 45,000 I work within"), text)
        self.assertIn("tool schemas 16,993", text)
        self.assertIn("system 19,695", text)
        self.assertIn("observations 9,176", text)
        self.assertIn("I'll retry as soon as anything changes", text)
        self.assertLess(len(text), 400)
        self.assertIn("blocked_notice(", src[src.index("def wait_for_request_change("):src.index("def wait_for_request_change(") + 1500])
        self.assertRegex(src, r"notified_block|block_notified|_blocked_notice_sent", "the same block is announced once")


class BenchSeesItTests(unittest.TestCase):
    """M15-A4"""

    def test_preflight_refuses_a_blocked_iter(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("m15_bench", REPO / "scripts" / "foundry_bench" / "bench.py")
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        root = Path(tempfile.mkdtemp(prefix="m15-bench-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / ".runtime" / "recovery").mkdir(parents=True)
        (root / ".runtime" / "recovery" / "iter_heartbeat.json").write_text(
            json.dumps({"at": time.time(), "phase": "request_blocked", "detail": "RequestBudgetExceeded: over"}), encoding="utf-8")
        self.assertIn("blocked", bench.Iter(root, socket_path="/nonexistent").preflight())

    def test_wait_report_ends_early_on_a_block(self):
        require_m15()
        src = (REPO / "scripts" / "foundry_bench" / "bench.py").read_text(encoding="utf-8")
        self.assertIn('"request_blocked"', src[src.index("def wait_report("):src.index("def wait_report(") + 2500])
        self.assertIn('record["reason"]', src)


if __name__ == "__main__":
    unittest.main()
