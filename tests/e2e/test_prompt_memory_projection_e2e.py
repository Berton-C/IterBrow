#!/usr/bin/env python3
"""Invariant: whatever sits in memory/, the loop keeps cycling and the system
prompt carries a bounded, readable memory view (prompt audit B1-B9, B12).

memory/ holds a dangling symlink, a binary capture, a dated note that does not
match the request, and a large appended log that does. Over a few real cycles
the system prompt must keep current_tasks.txt and the newest tail of the log,
contain no U+FFFD, and keep the memory block within MAX_MEMORY_CHARS. A due
alarm must become saved input."""
import os
import re
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import IterRun, send, nop

MAX_MEMORY_CHARS = 20000
MEMORY_START = re.compile(r"\[(?:\d+ CHARACTERS BELOW MAXIMUM|PROMPT MEMORY EXCERPT:[^\]]*)\]\n\./memory/:\n")


def memory_block(system):
    """The memory view iter.py builds: from its notice to the first block a
    transformation appends after it."""
    match = MEMORY_START.search(system)
    assert match, "no memory block in the system prompt"
    rest = system[match.end():]
    ends = [i for i in (rest.find(marker) for marker in ("\n\n--- ", "\n\n## ", "\n\n[")) if i >= 0]
    return system[match.start():match.end() + (min(ends) if ends else len(rest))]


class PromptMemoryProjectionTests(unittest.TestCase):
    def test_bad_entries_do_not_stop_the_loop_and_the_view_stays_bounded(self):
        script = [[send("ack-1")], [send("ack-2")], [send("ack-3")], [nop(0)]]
        run = IterRun(script, name="promptmem")
        memory = run.root / "memory"
        (memory / "tasks").mkdir(parents=True)
        (memory / "tasks" / "current_tasks.txt").write_text(
            "# Current Task (started 2026-10-13 09:00:00)\n# Task Content: E2E-TASK-MARKER benchmark\n")
        os.symlink("/nonexistent/iterbrow-e2e-target", memory / "stale_link.txt")
        (memory / "captures").mkdir()
        (memory / "captures" / "capture_20261013_090000.png").write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00" + bytes(range(256)) * 200)
        (memory / "notes").mkdir()
        (memory / "notes" / "2026-10-01_unrelated_status.txt").write_text("DATED-NOTE-BODY " * 200)
        log = "".join("benchmark entry %06d: ok\n" % i for i in range(12000))  # ~300 KB
        (memory / "benchmark_log.txt").write_text("OLDEST-BENCH-ENTRY\n" + log + "NEWEST-BENCH-ENTRY\n")
        (memory / "alarms").mkdir()
        (memory / "alarms" / str(int(time.time()) - 60)).write_text("electron_ui\nE2E-ALARM-DUE")
        with run:
            run.say("how is the benchmark going?")
            run.wait_for_reply("ack-3")
            requests = run.wait_for_requests(4)
            run.stop()
            log_text = run.read_log("iter.log")
            self.assertNotIn("FileNotFoundError", log_text)
            for request in requests[:4]:
                system = request["system"]
                self.assertNotIn("�", system)
                self.assertIn("E2E-TASK-MARKER", system)
                self.assertIn("NEWEST-BENCH-ENTRY", system)
                self.assertNotIn("DATED-NOTE-BODY", system)
                block = memory_block(system)
                self.assertIn("E2E-TASK-MARKER", block)
                self.assertIn("NEWEST-BENCH-ENTRY", block)
                self.assertIn("2026-10-01_unrelated_status.txt", block)  # indexed, not shown
                self.assertNotIn("capture_20261013_090000.png", block)
                self.assertLessEqual(len(block), MAX_MEMORY_CHARS)
            inputs = [m["content"] for m in run.experience() if m["role"] == "user"]
            self.assertTrue(any("[electron_ui] [ALARM] E2E-ALARM-DUE" in text for text in inputs), inputs)
            self.assertFalse((run.root / "memory" / "alarms").exists()
                             and any((run.root / "memory" / "alarms").iterdir()))


if __name__ == "__main__":
    unittest.main()
