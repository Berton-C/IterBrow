#!/usr/bin/env python3
"""Milestone 1: work already done in a turn must survive Stop, crash or error."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "iter") not in sys.path:
    sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.loop_continuity import complete_interrupted_turn, unanswered_tool_calls


def _call(call_id, name):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": "{}"}}


class InterruptedTurnTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {"role": "user", "content": "Step t0: [electron_ui] hello"},
            {"role": "assistant", "content": None,
             "tool_calls": [_call("c1", "send"), _call("c2", "shell"), _call("c3", "nop")]},
            {"role": "tool", "tool_call_id": "c1", "content": "Step t1: SENT",
             "_iter_execution": {"success": True, "state": "returned"}},
        ]

    def test_unanswered_calls_are_the_ones_without_results(self):
        self.assertEqual([c["id"] for c in unanswered_tool_calls(self.history)], ["c2", "c3"])

    def test_completed_turn_keeps_delivered_work_and_marks_the_rest(self):
        completed = complete_interrupted_turn(self.history, "interrupted by stop", "t2")
        self.assertEqual(completed[:3], self.history)
        self.assertEqual([m["tool_call_id"] for m in completed[3:]], ["c2", "c3"])
        for placeholder in completed[3:]:
            self.assertIn("NOT EXECUTED: interrupted by stop", placeholder["content"])
            self.assertEqual(placeholder["_iter_execution"]["state"], "not_executed")
        # every tool call now has exactly one result: a valid request transcript
        results = [m["tool_call_id"] for m in completed if m["role"] == "tool"]
        self.assertEqual(sorted(results), ["c1", "c2", "c3"])

    def test_nothing_pending_is_a_no_op(self):
        self.assertEqual(complete_interrupted_turn(self.history[:1], "x", "t"), self.history[:1])
        full = self.history + [
            {"role": "tool", "tool_call_id": "c2", "content": "ok"},
            {"role": "tool", "tool_call_id": "c3", "content": "ok"},
        ]
        self.assertEqual(complete_interrupted_turn(full, "x", "t"), full)

    def test_does_not_mutate_input(self):
        before = list(self.history)
        complete_interrupted_turn(self.history, "x", "t")
        self.assertEqual(self.history, before)


    def test_in_flight_call_is_uncertain_not_not_executed(self):
        completed = complete_interrupted_turn(self.history, "stop", "t2", in_flight_id="c2")
        by_id = {m["tool_call_id"]: m for m in completed if m["role"] == "tool"}
        self.assertIn("INTERRUPTED", by_id["c2"]["content"])
        self.assertIn("outcome unknown", by_id["c2"]["content"])
        self.assertEqual(by_id["c2"]["_iter_execution"]["state"], "uncertain")
        self.assertIn("NOT EXECUTED", by_id["c3"]["content"])
        self.assertEqual(by_id["c3"]["_iter_execution"]["state"], "not_executed")


if __name__ == "__main__":
    unittest.main()
