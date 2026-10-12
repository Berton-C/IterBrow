#!/usr/bin/env python3
"""Invariant: anything Iter sent to the user is in the saved history, even if the
cycle was stopped (SIGTERM from the Stop button) before its later tools finished."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import IterRun, send, shell, nop


class StopPreservesDeliveredReplyTests(unittest.TestCase):
    def test_reply_delivered_before_stop_is_saved_with_interrupted_calls_marked(self):
        script = [[send("DELIVERED-REPLY-0"), shell("sleep 60"), nop(0)]]
        with IterRun(script, name="stop") as run:
            run.say("what is the codeword?")
            run.wait_for_reply("DELIVERED-REPLY-0")
            run.wait_for_tool_result("SUCCESS", call_id="call_0_0")  # send returned; shell is sleeping
            # The shell tool is now sleeping: the Stop button arrives mid-cycle.
            run.stop("sigterm")
            history = run.experience()
            roles = [m["role"] for m in history]
            self.assertIn("assistant", roles, "assistant turn lost on Stop:\n" + run.read_log("iter.log"))
            tools = [m for m in history if m["role"] == "tool"]
            self.assertIn("SUCCESS", tools[0]["content"], "send result missing: %r" % tools)
            assistant = next(m for m in history if m["role"] == "assistant")
            call_ids = [c["id"] for c in assistant["tool_calls"]]
            answered = [m["tool_call_id"] for m in tools]
            self.assertEqual(sorted(call_ids), sorted(answered), "every tool call has exactly one result")
            by_id = {m["tool_call_id"]: m for m in tools}
            # shell was running when Stop arrived: its outcome is unknown, never "did not run"
            self.assertIn("INTERRUPTED", by_id["call_0_1"]["content"])
            self.assertEqual(by_id["call_0_1"]["_iter_execution"]["state"], "uncertain")
            # nop never started
            self.assertIn("NOT EXECUTED", by_id["call_0_2"]["content"])
            self.assertEqual(by_id["call_0_2"]["_iter_execution"]["state"], "not_executed")


if __name__ == "__main__":
    unittest.main()
