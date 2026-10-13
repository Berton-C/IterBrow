#!/usr/bin/env python3
"""Regression tests for the prompt-assembly audit (memory, tasks, handoff, alarms).

Each memory test mirrors iter.py's own projection path:
  _memory_projection.projection_contents -> relevant_memory -> memory_context
Bug IDs refer to the prompt audit (B1..B17).
"""
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
for p in (str(ITER), str(ITER / "tools"), str(ITER / "transformations")):
    if p not in sys.path:
        sys.path.insert(0, p)

from iterbrow_runtime.request_budget import (  # noqa: E402
    RequestBudgetExceeded, active_work_start, memory_context, project_request,
    relevant_memory, working_input_limit,
)
import _memory_projection  # noqa: E402

LIMIT = 20000


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def user(text, ts="2026-10-08 12:00:00", channel="electron_ui"):
    return {"role": "user", "content": "Step %s: [%s] %s" % (ts, channel, text)}


class MemoryDir:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "memory").mkdir()
        self._cwd = os.getcwd()
        os.chdir(self.root)
        return self

    def __exit__(self, *exc):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def write(self, rel, data):
        path = self.root / "memory" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.write_bytes if isinstance(data, bytes) else path.write_text)(data)
        return path

    def items(self):
        if not hasattr(_memory_projection, "projection_contents"):
            # Pre-fix iter.py path, so a failure shows the bug itself.
            return [(Path(p), Path(p).read_text(encoding="utf-8", errors="replace").strip())
                    for p in _memory_projection.projection_files("memory")]
        return [(Path(p), t) for p, t in _memory_projection.projection_contents("memory")]

    def project(self, experience):
        """The same calls iter.py makes each cycle."""
        return memory_context(relevant_memory(self.items(), experience), LIMIT)


class IterUsesProjectionContents(unittest.TestCase):
    def test_iter_reads_memory_only_through_projection_contents(self):
        source = (ITER / "iter.py").read_text()
        self.assertIn("_memory_projection.projection_contents(", source)
        self.assertNotIn("path.read_text(encoding=\"utf-8\", errors=\"replace\").strip()) for path in memory_paths",
                         source)


class ProjectionRobustness(unittest.TestCase):
    """B1, B6 and the per-file read cap."""

    def test_dangling_symlink_does_not_abort_projection(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: fix")
            os.symlink("/nonexistent/target", m.root / "memory" / "stale_link.txt")
            out = m.project([user("hello")])
            self.assertIn("# Task Content: fix", out)

    def test_fifo_is_skipped_not_blocking(self):
        with MemoryDir() as m:
            os.mkfifo(m.root / "memory" / "pipe.txt")
            m.write("tasks/current_tasks.txt", "# Task Content: fix")
            result = {}
            worker = threading.Thread(target=lambda: result.setdefault("items", m.items()), daemon=True)
            worker.start()
            worker.join(5)
            if worker.is_alive():
                # Unblock the reader so the test process can exit.
                fd = os.open(m.root / "memory" / "pipe.txt", os.O_WRONLY | os.O_NONBLOCK)
                os.close(fd)
                self.fail("projecting memory/ blocked on a FIFO")
            self.assertEqual([str(p) for p, _ in result["items"]],
                             [os.path.join("memory", "tasks", "current_tasks.txt")])

    def test_unreadable_file_is_skipped(self):
        if os.geteuid() == 0:
            self.skipTest("root reads mode-000 files")
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: fix")
            locked = m.write("locked.txt", "secret")
            locked.chmod(0)
            self.assertIn("# Task Content: fix", m.project([user("hello")]))

    def test_binary_capture_and_dotfiles_are_not_prompt_memory(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: take a photo")
            m.write("captures/capture_20261008_120000.png", bytes(range(256)) * 50)
            m.write("captures/notes.txt", "capture sidecar text")
            m.write("photo_notes.bin", b"\x89PNG\r\n\x1a\n\x00\x00")
            m.write(".improve_dismissed", "x" * 5000)
            m.write(".state/inner.txt", "hidden")
            rel = [os.path.relpath(p, "memory") for p in _memory_projection.projection_files("memory")]
            self.assertEqual(rel, [os.path.join("tasks", "current_tasks.txt")])
            self.assertNotIn("�", m.project([user("did the photo capture work?")]))
            self.assertEqual(_memory_projection.projection_chars("memory"),
                             len("# Task Content: take a photo"))

    def test_huge_file_is_read_bounded_with_head_and_tail(self):
        with MemoryDir() as m:
            m.write("bench.log", "OLDEST LINE\n" + "a" * 1_000_000 + "\nNEWEST LINE")
            (path, text), = _memory_projection.projection_contents("memory")
            self.assertLessEqual(len(text), _memory_projection.DEFAULT_READ_CHARS + 200)
            self.assertTrue(text.startswith("OLDEST LINE"))
            self.assertTrue(text.endswith("NEWEST LINE"))


class RelevanceSelection(unittest.TestCase):
    """B2: topic matching runs on the user's words, not the Step/channel wrapper."""

    def test_step_envelope_is_not_a_topic(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: toast")
            m.write("notes/2026-09-14_websearch_outage_postmortem.txt", "W" * 900)
            m.write("notes/electron_ipc_rewrite_plan.txt", "E" * 900)
            m.write("notes/step_counter_ideas.txt", "S" * 900)
            m.write("notes/wedding_toast_ideas.txt", "open with the canoe story")
            out = m.project([user("please help me with the wedding toast")])
            self.assertIn("canoe story", out)
            self.assertNotIn("websearch_outage_postmortem.txt:\n", out)
            self.assertNotIn("electron_ipc_rewrite_plan.txt:\n", out)
            self.assertNotIn("step_counter_ideas.txt:\n", out)

    def test_user_word_matching_still_selects_named_note(self):
        with MemoryDir() as m:
            m.write("notes/electron_ipc_rewrite_plan.txt", "plan body")
            out = m.project([user("how is the electron rewrite going?")])
            self.assertIn("electron_ipc_rewrite_plan.txt:\n", out)


if __name__ == "__main__":
    unittest.main()
