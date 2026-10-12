#!/usr/bin/env python3
"""trajectory.py and stall_detect.py derive tool calls from messages (BUG-11)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_episodic_memory import EpisodicCase, load, roundtrip, system, user, send_exchange, tool_exchange  # noqa: E402


class ToolCallSourceTests(EpisodicCase):
    def _cycle(self, experience):
        messages = [system()] + experience
        for name in ("stall_detect", "trajectory", "transcript"):
            messages, _ = load("transformations/%s.py" % name).transform(roundtrip(messages), [])
        return messages[0]["content"]

    def test_bug11_trajectory_records_real_tool_calls(self):
        experience = [user("2026-10-01 09:00:00", "go")] + tool_exchange("t", "browser_click", "2026-10-01 09:00:01")
        self._cycle(experience)
        self._cycle(experience)
        snapshot = json.loads(Path(".trajectory/snap_0002.json").read_text())
        self.assertEqual(snapshot["calls"], ["browser_click"])
        self.assertFalse(snapshot["send"])

    def test_bug11_status_sends_and_user_messages_are_not_a_tool_loop(self):
        experience = [user("2026-10-01 09:00:00", "a"), user("2026-10-01 09:00:01", "b"),
                      user("2026-10-01 09:00:02", "c")]
        for i in range(3):
            experience += send_exchange("s%d" % i, "2026-10-01 09:00:1%d" % i, "status %d" % i)
        self._cycle(experience)
        content = self._cycle(experience)
        self.assertNotIn("STALL WARNING", content)

    def test_bug11_silent_tool_loop_is_detected(self):
        experience = [user("2026-10-01 09:00:00", "go")] + send_exchange("s0", "2026-10-01 09:00:01", "on it")
        for i in range(12):
            experience += tool_exchange("b%d" % i, "browser_click", "2026-10-01 09:01:%02d" % i)
        content = self._cycle(experience)
        self.assertIn("STALL WARNING: tool repeated", content)
        self.assertIn("STALL WARNING: 12 tool calls since last send()", content)


if __name__ == "__main__":
    unittest.main()
