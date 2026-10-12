#!/usr/bin/env python3
"""Archive growth: batched log rotation, quota sees archives, cheap line counts (BUG-16)."""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_episodic_memory import EpisodicCase, load, system  # noqa: E402
from iterbrow_runtime import episodic_history  # noqa: E402


def record(i):
    return '("2026-10-01 10:%02d:%02d" "HUMAN_MESSAGE: line %d")\n' % ((i // 60) % 60, i % 60, i)


class ArchiveGrowthTests(EpisodicCase):
    def test_bug16_quota_guard_rotates_logs_in_batches(self):
        quota = load("transformations/zz_quota_guard.py")
        with open("history.metta", "w") as handle:
            handle.writelines(record(i) for i in range(quota.MAX_HISTORY_LINES))
        written = quota.MAX_HISTORY_LINES
        for _cycle in range(100):
            with open("history.metta", "a") as handle:
                handle.writelines(record(written + j) for j in range(3))
            written += 3
            quota.transform([system()], [])
        archives = list(Path("memory/archive/history.metta").glob("*.txt"))
        self.assertLessEqual(len(archives), 4, "one archive file per cycle instead of per batch")
        self.assertEqual(episodic_history.history_line_count("history.metta"), written)   # nothing lost

    def test_bug16_storage_quota_counts_the_archive(self):
        quota = load("transformations/zz_quota_guard.py")
        folder = Path("memory/archive/history.metta")
        folder.mkdir(parents=True)
        (folder / "1-rotation-a.txt").write_text("x" * 100000)
        self.assertGreaterEqual(quota._dir_size("."), 100000)

    def test_storage_warning_reaches_the_prompt_and_suggests_nothing_destructive(self):
        # Review 3 LOW-b: `import bridge` never exists, so the warning was never seen;
        # and it must not nudge the agent into deleting archived history.
        quota = load("transformations/zz_quota_guard.py")
        quota.STORAGE_QUOTA_BYTES = 10
        Path("notes.txt").write_text("x" * 1000)
        messages, _ = quota.transform([system()], [])
        content = messages[0]["content"]
        self.assertIn("STORAGE", content)
        self.assertIn("MB", content)
        for word in ("clean", "delete", "remove", "free up", "prune", "trim"):
            self.assertNotIn(word, content.lower())


    def test_bug16_line_count_matches_history_lines_without_rereading_archives(self):
        folder = Path("memory/archive/history.metta")
        folder.mkdir(parents=True)
        for n in range(5):
            (folder / ("%d-rotation-%d.txt" % (n + 1, n))).write_text("".join(record(n * 10 + i) for i in range(10)))
        Path("history.metta").write_text("".join(record(100 + i) for i in range(7)))
        expected = sum(1 for _ in episodic_history.history_lines("history.metta"))
        self.assertEqual(episodic_history.history_line_count("history.metta"), expected)
        reads = []
        real = Path.read_text

        def counting(path, *args, **kwargs):
            if "memory/archive" in str(path) and str(path).endswith(".txt"):
                reads.append(path)
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", counting):
            self.assertEqual(episodic_history.history_line_count("history.metta"), expected)
        self.assertEqual(reads, [])
        # Positions from a start point agree with the full chronological view.
        everything = list(enumerate(episodic_history.history_lines("history.metta"), 1))
        self.assertEqual(list(episodic_history.history_lines_from("history.metta", 23)), everything[22:])


if __name__ == "__main__":
    unittest.main()
