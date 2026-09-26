#!/usr/bin/env python3
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))


def load_module(relative):
    path = ROOT / "iter" / relative
    name = "bridge_test_%s_%s" % (path.stem, uuid.uuid4().hex)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DomainBridgeTests(unittest.TestCase):
    def native_revision_fixture(self, module):
        def rpc(method, **kwargs):
            if method == 'read_atoms':
                return {'atoms': {'state:nace_belief:cap-efficacy:shell': '(cap-efficacy shell (stv 0.5 0.0))'}}
            self.assertEqual(method, 'query')
            self.assertIn('Truth_Revision', kwargs['code'])
            return {'result': '[[(nace-revised 0 (stv 0.5 0.0) (stv 1.0 0.1))]]'}
        module._call_atomspace = rpc

    def test_task_projection_advances_only_after_authoritative_commit(self):
        module = load_module("tools/task_state.py")
        with tempfile.TemporaryDirectory() as temp:
            projection = Path(temp) / "task_state.metta"
            module.PATH = str(projection)
            observed = []

            def commit(*_args, **_kwargs):
                observed.append("commit")
                self.assertFalse(projection.exists())
                return {"commit": 1}

            module.commit_event = commit
            self.assertIn("recorded", module.run("set", "atlas", "building", "test"))
            self.assertEqual(observed, ["commit"])
            self.assertIn("task-phase", projection.read_text(encoding="utf-8"))

            projection.unlink()
            module.commit_event = mock.Mock(side_effect=RuntimeError("authority down"))
            self.assertIn("error committing", module.run("set", "atlas", "building", "test"))
            self.assertFalse(projection.exists())

    def test_reliability_projection_follows_commit(self):
        module = load_module("transformations/tool_reliability_tracker.py")
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            projection = runtime / "tool_reliability.json"
            module.RUNTIME_DIR = str(runtime)
            module.RELIABILITY_FILE = str(projection)
            module.STATE_FILE = str(runtime / "state.txt")
            module.ISSUE_LOG = str(runtime / "issues.log")

            def commit(*_args, **_kwargs):
                self.assertFalse(projection.exists())
                return {"commit": 1}

            module.commit_event = commit
            self.assertTrue(module.update_reliability("shell", True, "call-1"))
            self.assertEqual(json.loads(projection.read_text())["shell"]["calls"], 1)

    def test_reliability_tracker_batches_backlog_and_persists_progress(self):
        module = load_module("transformations/tool_reliability_tracker.py")
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            module.RUNTIME_DIR = str(runtime)
            module.RELIABILITY_FILE = str(runtime / "tool_reliability.json")
            module.STATE_FILE = str(runtime / "state.txt")
            module.ISSUE_LOG = str(runtime / "issues.log")
            module.PENDING_BATCH_FILE = str(runtime / "pending.json")
            module.NACE_PENDING_FILE = str(Path(temp) / "nace_pending.metta")
            module.MAX_OUTCOMES_PER_BATCH = 3
            commits = []

            def commit(events, **kwargs):
                commits.append((events, kwargs))
                return {"commit": len(commits), "duplicate": False}

            module.commit_batch = commit
            messages = []
            for index in range(5):
                call_id = "call-%d" % index
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{"id": call_id, "function": {"name": "shell"}}],
                })
                messages.append({"role": "tool", "tool_call_id": call_id, "content": "ok",
                                 "_iter_execution": {"success": True, "scope": "invocation"}})

            module.transform(messages, [])
            self.assertEqual(len(commits[0][0]), 3)
            self.assertEqual(len(Path(module.STATE_FILE).read_text().splitlines()), 3)
            self.assertEqual(json.loads(Path(module.RELIABILITY_FILE).read_text())["shell"]["calls"], 3)
            self.assertFalse(Path(module.PENDING_BATCH_FILE).exists())

            module.transform(messages, [])
            self.assertEqual(len(commits[1][0]), 2)
            self.assertEqual(len(Path(module.STATE_FILE).read_text().splitlines()), 5)
            self.assertEqual(json.loads(Path(module.RELIABILITY_FILE).read_text())["shell"]["calls"], 5)
            nace = Path(module.NACE_PENDING_FILE).read_text()
            self.assertEqual(nace.count("(pending-revision tool shell confirmed)"), 5)
            self.assertEqual(nace.count(module.NACE_MARKER_PREFIX), 5)

    def test_reliability_pending_batch_recovery_is_projection_idempotent(self):
        module = load_module("transformations/tool_reliability_tracker.py")
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            module.RUNTIME_DIR = str(runtime)
            module.RELIABILITY_FILE = str(runtime / "tool_reliability.json")
            module.STATE_FILE = str(runtime / "state.txt")
            module.ISSUE_LOG = str(runtime / "issues.log")
            module.PENDING_BATCH_FILE = str(runtime / "pending.json")
            module.NACE_PENDING_FILE = str(Path(temp) / "nace_pending.metta")
            record = {
                "schema_version": 1,
                "transaction_id": "batch-1",
                "domain_events": [{
                    "event_id": "tool-outcome:call-1", "domain": "tool_reliability",
                    "entity_id": "shell", "event_type": "outcome_recorded", "payload": {},
                }],
                "state_atoms": {"tool_reliability:shell": "(tool-reliability shell (stv 1.0 0.5) 1 1 0)"},
                "scores_after": {"shell": {"f": 1.0, "c": 0.5, "calls": 1, "successes": 1, "failures": 0}},
                "processed_ids": ["call-1"],
                "nace_entries": [{"tool_call_id": "call-1", "line": "(pending-revision tool shell confirmed)"}],
            }
            module.commit_batch = mock.Mock(return_value={"commit": 1, "duplicate": True})
            module._finish_pending_batch(record)
            module._finish_pending_batch(record)
            self.assertEqual(json.loads(Path(module.RELIABILITY_FILE).read_text())["shell"]["calls"], 1)
            nace = Path(module.NACE_PENDING_FILE).read_text()
            self.assertEqual(nace.count("(pending-revision tool shell confirmed)"), 1)
            self.assertEqual(nace.count(module.NACE_MARKER_PREFIX + "call-1"), 1)

    def test_semantic_index_is_a_post_commit_projection(self):
        module = load_module("tools/_petta_db.py")
        with tempfile.TemporaryDirectory() as temp:
            module.DB_DIR = str(Path(temp) / "chroma_db")
            module.DB_FILE = str(Path(module.DB_DIR) / "memories.json")
            projection = Path(module.DB_FILE)
            commits = []

            def commit(*args, **_kwargs):
                commits.append(args)
                self.assertFalse(projection.exists())
                return {"commit": 1}

            module._commit_memory_change = commit
            module.Collection().add(["m1"], [[0.1, 0.2]], ["remember me"], [{"type": "fact"}])
            self.assertEqual(len(commits), 1)
            self.assertEqual(json.loads(projection.read_text())["ids"], ["m1"])

    def test_soul_registry_commits_before_projection(self):
        module = load_module("tools/soul_skill_registry.py")
        with tempfile.TemporaryDirectory() as temp:
            projection = Path(temp) / "soul_skills.json"
            module.SKILLS_PATH = str(projection)

            def commit(*_args, **_kwargs):
                self.assertFalse(projection.exists())
                return {"commit": 1}

            module.commit_event = commit
            result = json.loads(module.run("seed"))
            self.assertGreater(result["seeded"], 0)
            self.assertTrue(projection.exists())

    def test_nace_batch_commits_before_belief_and_queue_projections(self):
        module = load_module("transformations/nace_courier.py")
        self.native_revision_fixture(module)
        with tempfile.TemporaryDirectory() as temp:
            beliefs = Path(temp) / "nace_beliefs.metta"
            pending = Path(temp) / "nace_pending.metta"
            beliefs.write_text("(cap-efficacy shell (stv 0.5 0.0))\n", encoding="utf-8")
            original_pending = "(pending-revision tool shell confirmed)\n"
            pending.write_text(original_pending, encoding="utf-8")
            module.BELIEFS_PATH = str(beliefs)
            module.PENDING_PATH = str(pending)
            module.RECOVERY_PATH = str(Path(temp) / "nace_projection_recovery.json")
            commits = []

            def commit(events, **kwargs):
                commits.append((events, kwargs))
                self.assertEqual(pending.read_text(encoding="utf-8"), original_pending)
                self.assertIn("0.5 0.0", beliefs.read_text(encoding="utf-8"))
                return {"commit": 1}

            module.commit_batch = commit
            fake_lock = types.SimpleNamespace(
                run=lambda **_kwargs: json.dumps({"ok": True})
            )
            with mock.patch.dict(sys.modules, {"soul_lock": fake_lock}):
                summary, candidates = module.process_revisions()
            self.assertEqual(len(commits), 1)
            self.assertEqual(len(candidates), 1)
            self.assertIn("beliefs revised", summary)
            self.assertIn("Queue cleared", pending.read_text(encoding="utf-8"))
            self.assertNotIn("0.5 0.0", beliefs.read_text(encoding="utf-8"))
            self.assertFalse(Path(module.RECOVERY_PATH).exists())

    def test_nace_recovers_exact_projection_without_double_revision(self):
        module = load_module("transformations/nace_courier.py")
        self.native_revision_fixture(module)
        with tempfile.TemporaryDirectory() as temp:
            beliefs = Path(temp) / "nace_beliefs.metta"
            pending = Path(temp) / "nace_pending.metta"
            recovery = Path(temp) / "recovery.json"
            beliefs.write_text("(cap-efficacy shell (stv 0.5 0.0))\n", encoding="utf-8")
            pending.write_text("(pending-revision tool shell confirmed)\n", encoding="utf-8")
            module.BELIEFS_PATH = str(beliefs)
            module.PENDING_PATH = str(pending)
            module.RECOVERY_PATH = str(recovery)
            real_write = module._write_file
            failed = {"once": False}

            def fail_projection_once(path, content):
                if path == module.BELIEFS_PATH and not failed["once"]:
                    failed["once"] = True
                    raise OSError("simulated projection interruption")
                return real_write(path, content)

            module.commit_batch = mock.Mock(return_value={"commit": 1})
            module._write_file = fail_projection_once
            fake_lock = types.SimpleNamespace(run=lambda **_kwargs: json.dumps({"ok": True}))
            with mock.patch.dict(sys.modules, {"soul_lock": fake_lock}):
                with self.assertRaises(OSError):
                    module.process_revisions()
                self.assertTrue(recovery.exists())
                summary, _ = module.process_revisions()
            self.assertIn("recovered", summary)
            self.assertFalse(recovery.exists())
            self.assertIn("Queue cleared", pending.read_text(encoding="utf-8"))
            self.assertEqual(module.commit_batch.call_count, 2)

    def test_nace_consumes_adjacent_reliability_marker_with_revision(self):
        module = load_module("transformations/nace_courier.py")
        pending = (
            ";; NACE Pending\n"
            "(pending-revision tool shell confirmed)\n"
            ";; tool-reliability-event call-1\n"
            "(pending-revision tool send confirmed)\n"
            ";; tool-reliability-event call-2\n"
        )
        remaining = module._remove_consumed_pending(
            pending, "(pending-revision tool shell confirmed)\n"
        )
        self.assertNotIn("call-1", remaining)
        self.assertNotIn("tool shell confirmed", remaining)
        self.assertIn("call-2", remaining)
        self.assertIn("tool send confirmed", remaining)


if __name__ == "__main__":
    unittest.main()
