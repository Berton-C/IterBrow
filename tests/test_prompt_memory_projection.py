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


class MemoryContextBounds(unittest.TestCase):
    """B3 (everything charged), B4 (nothing silently dropped), B8, B9."""

    def test_block_respects_limit_including_headers(self):
        items = [("memory/tasks/sub_%04d_with_a_long_descriptive_name.txt" % i, "x" * 40)
                 for i in range(400)]
        out = memory_context(items, LIMIT)
        self.assertLessEqual(len(out), LIMIT)

    def test_large_index_is_charged_and_bounded(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: hello")
            for i in range(2500):
                m.write("daily/%05d_unrelated_standup_log_entry.txt" % i, "ok")
            out = m.project([user("hi there")])
            self.assertLessEqual(len(out), LIMIT)
            self.assertIn("# Task Content: hello", out)
            self.assertIn("memory/index (request view only):", out)

    def test_files_after_an_oversized_one_are_named_not_vanished(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: deploy the invoice app")
            m.write("invoice_app_design.txt", "D" * 25000)
            m.write("invoice_deploy_credentials_location.txt", "creds in ~/.config/invoice/env")
            m.write("unrelated_garden.txt", "tomatoes")
            out = m.project([user("deploy the invoice app now")])
            self.assertLessEqual(len(out), LIMIT)
            self.assertIn("invoice_deploy_credentials_location", out)
            self.assertIn("unrelated_garden", out)
            self.assertIn("memory/index (request view only):", out)

    def test_names_every_file_that_did_not_fit(self):
        items = [("memory/standing_%d_preference.txt" % i, "p" * 9000) for i in range(6)]
        out = memory_context(items, LIMIT)
        self.assertLessEqual(len(out), LIMIT)
        for i in range(6):
            self.assertIn("memory/standing_%d_preference.txt" % i, out)

    def test_excerpt_keeps_newest_tail(self):
        content = "\n".join("old entry %d" % i for i in range(3000)) + "\nNEWEST ENTRY"
        out = memory_context([("memory/user_preferences.txt", content)], LIMIT)
        self.assertLessEqual(len(out), LIMIT)
        self.assertIn("old entry 0", out)
        self.assertIn("NEWEST ENTRY", out)

    def test_current_tasks_survives_large_sibling_in_tasks(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: migrate DB to postgres")
            m.write("tasks/backlog.txt", "- idea\n" * 3400)
            self.assertIn("migrate DB to postgres", m.project([user("continue")]))

    def test_many_matching_notes_do_not_block_request(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: hello")
            for i in range(3500):
                m.write("tasks/sub/%05d_standup_log_entry_for_the_daily_sync.txt" % i, "ok")
            mem = m.project([user("hi there")])
            cur = user("hi there")
            msgs = [{"role": "system", "content": "prompt.txt:\n...\n\n" + mem}, cur]
            try:
                project_request(msgs, [], working_input_limit(msgs, [], 45000, cur), cur, input_ceiling=45000)
            except RequestBudgetExceeded as error:
                self.fail("memory projection alone blocked the request: %s" % error)


if __name__ == "__main__":
    unittest.main()
