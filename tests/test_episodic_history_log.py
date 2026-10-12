#!/usr/bin/env python3
"""history.metta logging: event timestamps and never losing a record (BUG-8, BUG-9)."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_episodic_memory import EpisodicCase, load, roundtrip, system, user, send_exchange


class HistoryLogTests(EpisodicCase):
    def test_bug8_history_records_event_time_not_log_time(self):
        history = load("transformations/history.py")
        experience = [user("2026-10-01 09:00:00", "x")] + send_exchange("c1", "2026-10-01 09:00:05", "reply")
        history.transform(roundtrip([system()] + experience), [])
        text = Path("history.metta").read_text(encoding="utf-8")
        self.assertIn('("2026-10-01 09:00:00" "HUMAN_MESSAGE: Step 2026-10-01 09:00:00', text)
        self.assertIn('("2026-10-01 09:00:05" "TOOL_CALL: send', text)
        self.assertIn('("2026-10-01 09:00:05" "TOOL_RESULT: Step 2026-10-01 09:00:05', text)

    def _block_history_append(self):
        # A rotation marker that does not match history.metta makes
        # recover_rotation refuse to append (it preserves all copies).
        os.makedirs("memory/archive/history.metta")
        Path("memory/archive/history.metta/.rotation.json").write_text(json.dumps(
            {"before": "a", "after": "b", "prefix": "p", "archive": "1-rotation-x.txt"}))
        Path("history.metta").write_text("zzz\n")

    def test_bug9_failed_append_is_not_marked_logged(self):
        self._block_history_append()
        history = load("transformations/history.py")
        history.transform(roundtrip([system(), user("2026-10-01 09:00:00", "LOST")]), [])
        state = json.loads(Path(".history_state").read_text()) if Path(".history_state").exists() else []
        self.assertNotIn("u:Step 2026-10-01 09:00:00: [electron_ui] LOST", state)
        # Once the cause is repaired the record is appended on the next cycle.
        os.remove("memory/archive/history.metta/.rotation.json")
        history.transform(roundtrip([system(), user("2026-10-01 09:00:00", "LOST")]), [])
        self.assertIn("LOST", Path("history.metta").read_text())

    def test_bug9_append_failure_is_visible_in_the_system_message(self):
        self._block_history_append()
        messages, _ = load("transformations/history.py").transform(
            roundtrip([system(), user("2026-10-01 09:00:00", "LOST")]), [])
        self.assertIn("history.py: could not append 1 records", messages[0]["content"])

    def test_bug9_transcript_append_failure_is_visible_and_retried(self):
        os.makedirs("memory/archive/transcript.txt")
        Path("memory/archive/transcript.txt/.rotation.json").write_text(json.dumps(
            {"before": "a", "after": "b", "prefix": "p", "archive": "1-rotation-x.txt"}))
        Path("transcript.txt").write_text("zzz\n")
        transcript = load("transformations/transcript.py")
        messages, _ = transcript.transform(roundtrip([system(), user("2026-10-01 09:00:00", "HELLO")]), [])
        self.assertIn("transcript.py: could not update transcript.txt", messages[0]["content"])
        os.remove("memory/archive/transcript.txt/.rotation.json")
        transcript.transform(roundtrip([system(), user("2026-10-01 09:00:00", "HELLO")]), [])
        self.assertIn("HELLO", Path("transcript.txt").read_text())


if __name__ == "__main__":
    unittest.main()
