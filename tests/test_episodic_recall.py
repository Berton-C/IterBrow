#!/usr/bin/env python3
"""Recall tools: search_transcript nearest record (BUG-12), archived experience
reachable by search_transcript/episodes and truthful notices (BUG-13)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_episodic_memory import EpisodicCase, load, user, send_exchange  # noqa: E402


class SearchTranscriptNearestTests(EpisodicCase):
    def _write(self):
        Path("transcript.txt").write_text(
            "[2026-10-01 09:00:00][user] MORNING\n"
            "[2026-10-01 17:00:00][user] EVENING\n", encoding="utf-8")

    def test_bug12_returns_the_nearest_record_not_the_next_one(self):
        self._write()
        result = load("tools/search_transcript.py").run("2026-10-01 09:30:00", 0)
        self.assertIn("MORNING", result)
        self.assertNotIn("EVENING", result)

    def test_bug12_label_says_where_the_nearest_record_is(self):
        self._write()
        result = load("tools/search_transcript.py").run("2026-10-01 09:30:00", 0)
        self.assertIn("1800s before the requested time", result)
        result = load("tools/search_transcript.py").run("2026-10-01 16:45:00", 0)
        self.assertIn("EVENING", result)
        self.assertIn("900s after the requested time", result)

    def test_bug12_context_lines_surround_the_nearest_record(self):
        Path("transcript.txt").write_text("".join(
            "[2026-10-01 09:%02d:00][user] LINE-%d\n" % (i, i) for i in range(10)), encoding="utf-8")
        result = load("tools/search_transcript.py").run("2026-10-01 09:05:10", 1)
        self.assertEqual([l for l in result.splitlines() if "LINE-" in l],
                         ["[2026-10-01 09:04:00][user] LINE-4", "[2026-10-01 09:05:00][user] LINE-5",
                          "[2026-10-01 09:06:00][user] LINE-6"])


if __name__ == "__main__":
    unittest.main()
