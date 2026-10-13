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
        self.assertGreater(len(out), LIMIT * 0.9, "a lone oversized file should use the room nobody else needs")
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


class TaskBoundary(unittest.TestCase):
    """B5: advisory prefixes and retained-output envelopes hide a new task."""

    def _experience(self, result_text, new_msg):
        call = {"id": "c1", "type": "function", "function": {"name": "start_new_task", "arguments": json.dumps({
            "person": "B", "requestchannel": "electron_ui", "taskcontent": "x",
            "completionsendcriterium": "y", "originalUserMessage": new_msg, "new_work": "true"})}}
        return [user("build me a garden planner", "2026-10-01 09:00:00"),
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c0", "type": "function", "function": {"name": "send", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c0", "content": "Step 2026-10-01 09:00:01: SUCCESS"},
                user(new_msg),
                {"role": "assistant", "content": "", "tool_calls": [call]},
                {"role": "tool", "tool_call_id": "c1", "content": "Step 2026-10-08 12:00:01: " + result_text}]

    def test_plain_result_advances_boundary(self):
        msg = "now write the invoice parser"
        result = "SUCCESS, RETURN: New task started at 2026-10-08 12:00:01.\n  Person: B"
        self.assertEqual(active_work_start(self._experience(result, msg)), 3)

    def test_nace_advisory_prefix_does_not_hide_new_task(self):
        msg = "now write the invoice parser"
        result = ("[NACE advisory: capability 'start_new_task' is trust_stage=candidate (no "
                  "cap-efficacy belief data yet) -- always surfaced] "
                  "SUCCESS, RETURN: New task started at 2026-10-08 12:00:01.\n  Person: B")
        self.assertEqual(active_work_start(self._experience(result, msg)), 3)

    def test_retained_long_result_does_not_hide_new_task(self):
        from iterbrow_runtime.tool_results import capture_tool_output
        msg = "spec:\n" + "field: value\n" * 400
        raw = ("[NACE advisory: low confidence] SUCCESS, RETURN: New task started at "
               "2026-10-08 12:00:01.\n  Original message: " + msg)
        with tempfile.TemporaryDirectory() as tmp:
            text = capture_tool_output(tmp, raw, tool_call_id="c1", tool_name="start_new_task",
                                       generation_id="g", raw_result=raw, max_chars=4500)
        self.assertNotEqual(text, raw)  # really retained
        self.assertEqual(active_work_start(self._experience(text, msg)), 3)


class HandoffOnTimedWakeup(unittest.TestCase):
    """B10: the working handoff must reach timed/alarm wake-ups."""

    OK = {"success": True, "state": "returned", "scope": "invocation", "task_fulfillment": "unverified"}

    def _experience(self, with_pin=True):
        exp = [user("run the benchmark and report")]
        if with_pin:
            exp += [{"role": "assistant", "content": "", "tool_calls": [
                        {"id": "p1", "type": "function", "function": {"name": "pin", "arguments": json.dumps(
                            {"message": "benchmark PID 4242 running; next read /tmp/bench.log",
                             "handoff": "true"})}}]},
                    {"role": "tool", "tool_call_id": "p1", "content": "Step 2026-10-08 12:00:01: SUCCESS",
                     "_iter_execution": self.OK}]
        exp += [{"role": "assistant", "content": "", "tool_calls": [
                    {"id": "n1", "type": "function", "function": {"name": "nop", "arguments": '{"wait_seconds": 3600}'}}]},
                {"role": "tool", "tool_call_id": "n1", "content": "Step 2026-10-08 12:00:02: SUCCESS",
                 "_iter_execution": self.OK}]
        return exp

    def _send(self, call_id, text, ts="2026-10-08 12:00:03"):
        return [{"role": "assistant", "content": "", "tool_calls": [
                    {"id": call_id, "type": "function", "function": {"name": "send", "arguments": json.dumps(
                        {"channel": "electron_ui", "content": text})}}]},
                {"role": "tool", "tool_call_id": call_id, "content": "Step %s: SUCCESS" % ts,
                 "_iter_execution": self.OK}]

    def test_ordinary_cycle_after_a_send_has_no_handoff(self):
        # Review finding 1: the latest send stood in for a working account, so
        # the handoff was added to nearly every cycle (~13K chars each).
        import iterbrow_runtime.working_handoff as wh
        exp = [user("fix the tab strip")] + self._send("s1", "working on it") + [
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "sh1", "type": "function", "function": {"name": "shell", "arguments": '{"cmd": "ls"}'}}]},
            {"role": "tool", "tool_call_id": "sh1", "content": "Step 2026-10-08 12:00:04: main.js",
             "_iter_execution": self.OK}]
        self.assertEqual(wh.cycle_handoff(exp, ""), ("", ()))

    def test_handoff_injected_on_timed_wakeup(self):
        from iterbrow_runtime.work_inquiry import question_context
        import iterbrow_runtime.working_handoff as wh
        exp = self._experience()
        inquiry = question_context(exp, new_input=False, resumed=False)
        self.assertEqual(inquiry, "")  # a timed wake-up has no question cue
        text, evidence = wh.cycle_handoff(exp, inquiry, wakeup=True)
        self.assertIn("benchmark PID 4242", text)

    def test_wakeup_never_presents_a_completion_send_as_the_account(self):
        import iterbrow_runtime.working_handoff as wh
        exp = [user("run the benchmark")] + self._send("s1", "Done! Benchmark finished.") + \
            self._experience(with_pin=False)[1:]
        text, _ = wh.cycle_handoff(exp, "", wakeup=True)
        self.assertNotIn("Done! Benchmark finished.", text)

    def test_iter_passes_an_explicit_wakeup_flag(self):
        source = (ITER / "iter.py").read_text()
        self.assertIn("cycle_handoff(experience, inquiry, wakeup=", source)

    def test_no_account_and_no_cue_adds_nothing(self):
        import iterbrow_runtime.working_handoff as wh
        self.assertEqual(wh.cycle_handoff(self._experience(with_pin=False), "", wakeup=True), ("", ()))


class StartNewTaskPreservesHistory(unittest.TestCase):
    """B11: an update must not erase the original request, start time or prior account."""

    def _run_in(self, tmp, calls):
        cwd = os.getcwd()
        os.chdir(tmp)
        try:
            module = _load("start_new_task_under_test", ITER / "tools" / "start_new_task.py")
            module.commit_event = lambda *a, **k: {"ok": True}
            texts = []
            for args in calls:
                module.run(*args)
                texts.append(Path("memory/tasks/current_tasks.txt").read_text())
                time.sleep(1.05)
            archived = sorted(Path("memory/tasks/archive").glob("*")) if Path("memory/tasks/archive").exists() else []
            return texts, [p.read_text() for p in archived], _memory_projection.projection_files("memory")
        finally:
            os.chdir(cwd)

    def test_update_keeps_original_request_and_start_and_archives_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            (first, second), archived, projected = self._run_in(tmp, [
                ("B", "nochannel", "Build garden planner", "send link",
                 "Please build a garden planner\nwith Seattle frost dates", "true"),
                ("B", "nochannel", "Garden planner: add dark mode", "send screenshot"),
            ])
            self.assertIn("with Seattle frost dates", second)
            self.assertIn("add dark mode", second)
            self.assertEqual(first.splitlines()[0], second.splitlines()[0])  # start time kept
            self.assertEqual(archived, [first])
            self.assertFalse(any("archive" in p for p in projected))

    def test_new_work_starts_fresh_but_archives_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            (first, second), archived, _ = self._run_in(tmp, [
                ("B", "nochannel", "Build garden planner", "send link", "garden planner please", "true"),
                ("B", "nochannel", "Write invoice parser", "send file", "now the invoice parser", "true"),
            ])
            self.assertNotIn("garden planner please", second)
            self.assertNotEqual(first.splitlines()[0], second.splitlines()[0])
            self.assertEqual(archived, [first])


class AlarmsAreDurableInput(unittest.TestCase):
    """B12: due alarms must survive retries/rollbacks; same-second reminders must not collide."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_same_second_reminders_do_not_overwrite(self):
        reminder = _load("reminder_under_test", ITER / "tools" / "reminder.py")
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 5))
        first = reminder.run(when, "electron_ui", "Submit paper")
        second = reminder.run(when, "electron_ui", "Call the bank")
        self.assertTrue(first.startswith("SUCCESS") and second.startswith("SUCCESS"))
        bodies = sorted(Path("memory/alarms", n).read_text() for n in os.listdir("memory/alarms"))
        self.assertEqual(bodies, ["electron_ui\nCall the bank", "electron_ui\nSubmit paper"])

    def test_alarm_transformation_does_not_consume_due_alarm(self):
        # The transformation edits one attempt's request copy; consuming the
        # file there loses the alarm on retry or rollback.
        Path("memory/alarms").mkdir(parents=True)
        due = Path("memory/alarms", str(int(time.time()) - 5))
        due.write_text("electron_ui\nSubmit paper")
        alarms = _load("alarms_under_test", ITER / "transformations" / "alarms.py")
        alarms.transform([{"role": "system", "content": "x"}], [])
        self.assertTrue(due.exists(), "the alarm transformation deleted a due alarm from a request copy")

    def _alarms(self, now):
        Path("memory/alarms").mkdir(parents=True)
        Path("memory/alarms", str(int(now) - 5)).write_text("electron_ui\nSubmit paper")
        Path("memory/alarms", str(int(now) - 5) + ".001").write_text("electron_ui\nCall the bank")
        Path("memory/alarms", str(int(now) + 3600)).write_text("electron_ui\nLater")

    def test_due_alarms_are_read_without_deleting_until_saved(self):
        # Review finding 12: the file was deleted before save_experience.
        import iterbrow_runtime.alarm_inbox as inbox
        now = time.time()
        self._alarms(now)
        if not hasattr(inbox, "pending_alarms"):
            inbox.take_due_alarms("memory/alarms", now=now)
            self.assertEqual(len(os.listdir("memory/alarms")), 3, "alarms deleted before they were saved")
        text, ids = inbox.pending_alarms("memory/alarms", (), now=now)
        self.assertEqual(text, "[electron_ui] [ALARM] Submit paper\n[electron_ui] [ALARM] Call the bank")
        self.assertEqual(len(os.listdir("memory/alarms")), 3)
        inbox.acknowledge_alarms("memory/alarms", ids)
        self.assertEqual(os.listdir("memory/alarms"), [str(int(now) + 3600)])

    def test_crash_between_save_and_delete_does_not_deliver_twice(self):
        import iterbrow_runtime.alarm_inbox as inbox
        now = time.time()
        self._alarms(now)
        text, ids = inbox.pending_alarms("memory/alarms", (), now=now)
        saved = [{"role": "user", "content": "Step x: " + text, "_iter_alarm": True, "_iter_alarm_ids": ids}]
        # ... crash here: files still on disk; the restarted loop reads them again.
        again, more = inbox.pending_alarms("memory/alarms", inbox.delivered_alarm_ids(saved), now=now)
        self.assertEqual((again, more), ("", []))
        self.assertEqual(os.listdir("memory/alarms"), [str(int(now) + 3600)])

    def test_iter_deletes_alarms_only_after_saving(self):
        source = (ITER / "iter.py").read_text()
        receive_at = source.index("event_append = pending_event_append or receive()")
        window = source[receive_at:receive_at + 2500]
        self.assertIn("pending_alarms(", window)
        self.assertIn('"_iter_alarm_ids": alarm_ids', window)
        self.assertLess(window.index("save_experience(experience)"), window.index("acknowledge_alarms("))


class PressureSignals(unittest.TestCase):
    """B13: one measure of what the prompt carries; never advise deleting memory."""

    def _fill(self, m):
        m.write("tasks/current_tasks.txt", "# Task Content: tune scheduler")
        for i in range(30):
            m.write("old/unrelated_%d.txt" % i, "z" * 1000)
        return [{"role": "system", "content": "prompt"}, user("tune the scheduler")]

    def test_auto_improve_and_tool_budget_use_the_selected_measure(self):
        with MemoryDir() as m:
            messages = self._fill(m)
            self.assertGreater(_memory_projection.projection_chars("memory"), LIMIT)
            auto = _load("auto_improve_under_test", ITER / "transformations" / "auto_improve.py")
            budget = _load("dynamic_tool_budget_under_test", ITER / "transformations" / "dynamic_tool_budget.py")
            try:
                _, _, auto_size, _ = auto._compute_pain(messages)
            except TypeError:
                _, _, auto_size, _ = auto._compute_pain()
            budget_size, _ = budget._memory_chars(messages)
            expected = len("# Task Content: tune scheduler")
            self.assertEqual(auto_size, expected, "auto_improve counts files the prompt does not carry")
            self.assertEqual(budget_size, expected, "dynamic_tool_budget counts the omission index")
            self.assertEqual(_memory_projection.selected_chars("memory", messages), expected)

    def test_proposal_never_suggests_deleting_or_archiving_memory(self):
        auto = _load("auto_improve_under_test", ITER / "transformations" / "auto_improve.py")
        text = auto._build_proposal(10.0, ["memory: 30000 chars"], 30000, {}).lower()
        for word in ("archive", "delete", "remove", "consolidate", "trim"):
            self.assertNotIn(word, text)


class DocsMatchCode(unittest.TestCase):
    """B14: prompt.txt, AGENTS.md and the omission index must describe the code."""

    def _tool_inventory(self):
        text = (ITER / "AGENTS.md").read_text()
        section = text.split("\n## Tool Inventory", 1)[1].split("\n## ", 1)[0]
        import re
        return re.findall(r"^\|\s*`([A-Za-z0-9_]+)`\s*\|", section, re.M)

    def test_every_tool_agents_md_lists_exists(self):
        names = self._tool_inventory()
        self.assertGreater(len(names), 10)
        missing = [n for n in names if not (ITER / "tools" / (n + ".py")).is_file()]
        self.assertEqual(missing, [], "AGENTS.md lists tools that do not exist in iter/tools/")

    def test_agents_md_describes_the_semantic_store_and_tools_correctly(self):
        text = (ITER / "AGENTS.md").read_text()
        self.assertNotIn("ChromaDB", text)
        rows = {line.split("|")[1].strip().strip("`"): line for line in text.splitlines()
                if line.startswith("| `")}
        self.assertNotIn("Overwrite", rows["start_new_task"])
        self.assertIn("archive", rows["start_new_task"])
        self.assertIn("recap cursor", rows["record_episode"])
        self.assertIn("remember", rows["chroma_query"])

    def test_prompt_txt_does_not_promise_every_memory_file(self):
        text = (ITER / "prompt.txt").read_text()
        self.assertNotIn("The included files are automatically included in your context", text)
        self.assertIn("name", text.split("./memory/", 1)[1].split("\n", 1)[0])

    def test_omission_index_does_not_point_at_chroma(self):
        with MemoryDir() as m:
            m.write("garden.txt", "tomatoes")
            out = m.project([user("deploy invoices")])
            index = out.split("memory/index (request view only):", 1)[1]
            self.assertIn("garden.txt", index)
            self.assertNotIn("available through chroma_query", index)


class ToolDescriptionsFitTheCap(unittest.TestCase):
    """B17: iter.py truncates DESCRIPTIONs over MAX_TOOL_DESCRIPTION_CHARS."""

    @staticmethod
    def _imported_description(path):
        """DESCRIPTION computed at import time: load the module the way
        iter.py's tool runner does, in a throwaway ITER_DIR."""
        import subprocess
        code = ("import importlib.util,sys,json;sys.path.insert(0,%r);sys.path.insert(0,%r);"
                "s=importlib.util.spec_from_file_location('t',%r);m=importlib.util.module_from_spec(s);"
                "s.loader.exec_module(m);print(json.dumps(str(m.DESCRIPTION)))"
                % (str(path.parent), str(ITER), str(path)))
        with tempfile.TemporaryDirectory() as tmp:
            out = subprocess.run([sys.executable, "-c", code], cwd=tmp, capture_output=True, text=True,
                                 env={**os.environ, "ITER_DIR": tmp}, timeout=60)
        if out.returncode:
            raise AssertionError("cannot read DESCRIPTION of %s: %s" % (path.name, out.stderr[-500:]))
        return json.loads(out.stdout.strip().splitlines()[-1])

    def test_no_public_tool_description_exceeds_the_cap(self):
        import re
        from _metadata_static import static_description
        cap = int(re.search(r"^MAX_TOOL_DESCRIPTION_CHARS = (\d+)", (ITER / "iter.py").read_text(), re.M).group(1))
        over = {}
        for path in sorted((ITER / "tools").glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                description = static_description(path)
            except Exception:
                description = self._imported_description(path)
            if len(description) > cap:
                over[path.stem] = len(description)
        self.assertEqual(over, {}, "these tools lose the end of their DESCRIPTION in the prompt")

    def test_device_capture_keeps_close_tab_instruction(self):
        from _metadata_static import static_description
        text = static_description(ITER / "tools" / "device_capture.py")[:500]  # what the prompt shows
        self.assertIn("action='close' with that tab_id", text)


class AlarmInputIsNotUserInput(unittest.TestCase):
    """Review finding 3: an alarm saved as input is marked and is not a user turn."""

    OK = {"success": True, "state": "returned", "scope": "invocation", "task_fulfillment": "unverified"}

    def _alarm(self, text="Submit paper"):
        return {"role": "user", "content": "Step 2026-10-08 13:00:00: [electron_ui] [ALARM] " + text,
                "_iter_alarm": True, "_iter_alarm_ids": ["1760000000:1"]}

    def _work(self):
        return [user("run the benchmark"),
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "p1", "type": "function", "function": {"name": "pin", "arguments": json.dumps(
                        {"message": "benchmark running", "handoff": "true"})}}]},
                {"role": "tool", "tool_call_id": "p1", "content": "Step 2026-10-08 12:00:01: SUCCESS",
                 "_iter_execution": self.OK}]

    def test_rotation_start_ignores_alarms(self):
        from iterbrow_runtime.request_budget import rotation_start
        exp = self._work() + [self._alarm()]
        self.assertEqual(rotation_start(exp), 0)

    def test_handoff_does_not_list_alarms_as_user_updates(self):
        from iterbrow_runtime.working_handoff import working_record
        record = working_record(self._work() + [self._alarm()])
        self.assertFalse(record["newer_user_input"])
        self.assertEqual(record["latest_user_updates"], [])

    def test_alarm_marker_never_reaches_the_provider(self):
        msgs = [{"role": "system", "content": "sys"}] + self._work() + [self._alarm()]
        out, _, _ = project_request(msgs, [], 45000, msgs[1], input_ceiling=45000)
        self.assertFalse(any(key.startswith("_iter_alarm") for m in out for key in m))
        self.assertTrue(any("[ALARM] Submit paper" in str(m.get("content")) for m in out))

    def test_iter_saves_alarms_marked_and_separately_from_user_input(self):
        source = (ITER / "iter.py").read_text()
        self.assertIn('"_iter_alarm": True', source)
        self.assertNotIn('event_append = (event_append + "\\n" if event_append else "") + due_alarms', source)


class MemoryContextProperty(unittest.TestCase):
    """Review finding 4: every selected file is shown or named; the block fits."""

    def test_every_selected_file_is_shown_or_named_fuzz(self):
        import random
        rng = random.Random(20261013)
        failures = []
        for case in range(1500):
            count = rng.choice([1, 3, 10, 40, 60, 90])
            items = []
            for i in range(count):
                name = "memory/%s/%s_%03d.txt" % (rng.choice(["tasks", "notes", "standing", "x" * rng.randint(1, 40)]),
                                                  "n" * rng.randint(1, 30), i)
                size = rng.choice([0, 10, 500, 3000, 9000, 25000])
                items.append((name, "c" * size))
            if rng.random() < 0.6:
                omitted = ["memory/old/other_%04d.txt" % j for j in range(rng.choice([1, 50, 400]))]
                items.append(("memory/index (request view only)", "Other memory files:\n" + "\n".join(omitted)))
            out = memory_context(items, LIMIT)
            body_paths = [p for p, _ in items if not p.startswith("memory/index")]
            missing = [p for p in body_paths if p not in out]
            if len(out) > LIMIT or missing:
                failures.append((case, len(out), len(missing)))
        self.assertEqual(failures[:10], [], "%d of 1500 cases broke the property" % len(failures))


class LessonsAndCompoundWords(unittest.TestCase):
    """Review finding 5: lesson notes are always selected; compound names match split words."""

    def test_lesson_notes_are_always_selected(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: fix the tab strip pin bug")
            m.write("notes/lesson_cdp_click_needs_scroll.txt", "LESSON-CDP body")
            m.write("notes/2026-09-20_soul_gate_lessons.txt", "LESSON-DATED-SOUL body")
            m.write("notes/step_budget_lessons.txt", "LESSON-STEP body")
            m.write("notes/misc_topic_01.txt", "MISC body")
            out = m.project([user("can you continue fixing the pin bug?")])
            for marker in ("LESSON-CDP", "LESSON-DATED-SOUL", "LESSON-STEP"):
                self.assertIn(marker, out)
            self.assertNotIn("MISC body", out)

    def test_compound_file_name_matches_split_request_words(self):
        with MemoryDir() as m:
            m.write("notes/2026-09-15_tabstrip_fix.txt", "TABSTRIP-NOTE")
            m.write("notes/address_bar_quirks.txt", "ADDRESSBAR-NOTE")
            out = m.project([user("the tab strip pins are broken again")])
            self.assertIn("TABSTRIP-NOTE", out)
            out = m.project([user("the addressbar loses focus")])
            self.assertIn("ADDRESSBAR-NOTE", out)


class SkippedFilesAreNamed(unittest.TestCase):
    """Review finding 6: files skipped as binary, non-UTF-8 or unreadable stay
    visible by name in the index, marked as not shown."""

    def _view(self, m, experience):
        skipped = _memory_projection.projection_skipped("memory")
        return memory_context(relevant_memory(m.items(), experience, skipped=skipped), LIMIT)

    def test_binary_utf16_and_unreadable_files_are_listed_as_not_shown(self):
        with MemoryDir() as m:
            m.write("tasks/current_tasks.txt", "# Task Content: x")
            m.write("notes/diagram.png", b"\x89PNG\r\n\x1a\n\x00\x00" + bytes(range(256)))
            m.write("notes/windows_export.txt", "hello from notepad".encode("utf-16"))
            m.write("notes/latin1_note.txt", "caf\xe9 cr\xe8me".encode("latin-1") * 10)
            os.symlink("/nonexistent/target", m.root / "memory" / "notes" / "stale_link.txt")
            os.mkfifo(m.root / "memory" / "notes" / "pipe.txt")
            m.write(".stall_state.json", "{}")
            m.write("captures/capture_1.png", b"\x00" * 50)
            skipped = dict(_memory_projection.projection_skipped("memory"))
            for name in ("diagram.png", "windows_export.txt", "latin1_note.txt", "stale_link.txt", "pipe.txt"):
                self.assertIn(os.path.join("memory", "notes", name), skipped)
            out = self._view(m, [user("hello")])
            index = out.split("memory/index (request view only):", 1)[1]
            for name in ("diagram.png", "windows_export.txt", "latin1_note.txt", "stale_link.txt", "pipe.txt"):
                self.assertIn("memory/notes/" + name, index)
            self.assertIn("not shown", index)
            self.assertNotIn("\ufffd", out)
            # Documented: dot-files are runtime bookkeeping and captures/ is
            # media storage; neither is listed (see _memory_projection).
            self.assertNotIn(".stall_state.json", out)
            self.assertNotIn("capture_1.png", out)

    def test_iter_passes_skipped_files_to_the_view(self):
        source = (ITER / "iter.py").read_text()
        self.assertIn("projection_skipped(", source)


class AutoImproveLogsMeasurementErrors(unittest.TestCase):
    """Review finding 7: a failing memory measurement must be logged, not
    silently disable the pain signal."""

    def test_selected_chars_failure_is_logged_and_other_signals_survive(self):
        with MemoryDir() as m:
            auto = _load("auto_improve_under_test", ITER / "transformations" / "auto_improve.py")

            def broken(*args, **kwargs):
                raise RuntimeError("relevant_memory exploded (test)")
            auto._projection = type(sys)("_broken_projection")
            auto._projection.selected_chars = broken
            messages = [{"role": "system", "content": "prompt"}, user("hello")]
            auto.transform(messages, [])
            log = m.root / "transformations" / ".runtime" / "auto_improve_issues.log"
            self.assertTrue(log.exists(), "the failure was swallowed without a trace")
            self.assertIn("relevant_memory exploded", log.read_text())
            pain, signals, mem_size, _ = auto._compute_pain(messages)
            self.assertEqual(mem_size, 0)


class PromptMemoryDocsAreReachable(unittest.TestCase):
    """Review finding 9: the memory wording is exactly true and actually reaches the model."""

    def test_prompt_txt_states_the_real_selection_rules(self):
        text = (ITER / "prompt.txt").read_text()
        line = next(l for l in text.splitlines() if "./memory/" in l)
        for fact in ("lesson", "excerpt", "listed by path", "never listed", "cannot be shown"):
            self.assertIn(fact, line)

    def test_agents_md_prompt_memory_section_is_inside_the_injected_window(self):
        inject = _load("agents_md_inject_under_test", ITER / "transformations" / "agents_md_inject.py")
        cwd = os.getcwd()
        os.chdir(ITER)
        try:
            out, _ = inject.transform([{"role": "system", "content": "x"}], [])
        finally:
            os.chdir(cwd)
        injected = out[0]["content"]
        self.assertIn("## Prompt memory (memory/ files)", injected)
        section = (ITER / "AGENTS.md").read_text().split("## Prompt memory (memory/ files)", 1)[1].split("\n## ", 1)[0]
        self.assertIn(section.strip()[-120:], injected, "the section is cut by the auto-include window")


class StartNewTaskArchiveSafety(unittest.TestCase):
    """Review finding 10: an archive failure never reports 'not committed';
    tasks/archive/ is bounded."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.module = _load("start_new_task_archive_test", ITER / "tools" / "start_new_task.py")
        self.commits = []
        self.module.commit_event = lambda *a, **k: self.commits.append(a) or {"ok": True}

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_archive_failure_is_reported_as_committed(self):
        self.module.run("B", "nochannel", "first task", "done", "first", "true")
        Path("memory/tasks/archive").write_text("not a directory")  # archiving must fail
        result = self.module.run("B", "nochannel", "second task", "done", "second", "true")
        self.assertTrue(result.startswith("SUCCESS"), result)
        self.assertIn("archive failed", result)
        self.assertIn("second task", Path("memory/tasks/current_tasks.txt").read_text())
        self.assertEqual(len(self.commits), 2)

    def test_archive_keeps_the_newest_200(self):
        for i in range(206):
            self.module.run("B", "nochannel", "task %03d" % i, "done", "msg %03d" % i, "true")
        names = sorted(os.listdir("memory/tasks/archive"))
        self.assertEqual(len(names), 200)
        self.assertIn("task 204", Path("memory/tasks/archive", names[-1]).read_text())


if __name__ == "__main__":
    unittest.main()
