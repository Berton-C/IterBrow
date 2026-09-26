#!/usr/bin/env python3
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))
sys.path.insert(0, str(ROOT / "iter" / "tools"))

import _metta_gate as gate  # noqa: E402
import _metta_substrate as substrate  # noqa: E402


class _StopEvent:
    def set(self):
        return None


class GovernanceGateTests(unittest.TestCase):
    def test_substrate_queries_authority_without_legacy_projection(self):
        calls = []

        class FakeMetta:
            ENGINE_AVAILABLE = True

            @staticmethod
            def query(code, **kwargs):
                calls.append(code)
                return {
                    "result": "[[0.9]]", "epoch": "epoch-1", "commit": 7,
                    "state_hash": "hash-7",
                }

        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "nace_substrate.metta").write_text("(LEGACY_SUBSTRATE_SENTINEL)")
            Path(temp, "nace_beliefs.metta").write_text("(LEGACY_BELIEF_SENTINEL)")
            with mock.patch.object(substrate, "_import_metta_wrapper", return_value=FakeMetta), \
                 mock.patch.object(substrate, "try_setrlimit_as"), \
                 mock.patch.object(substrate, "start_memory_watchdog", return_value=_StopEvent()):
                result = substrate.run_query("!(governed-query)", root=temp)
        self.assertTrue(result["ok"])
        self.assertEqual(result["commit"], 7)
        self.assertEqual(result["authority"], "atomspace")
        self.assertNotIn("LEGACY_", calls[0])

    def test_removed_direct_write_detector_stays_removed(self):
        authoritative = {
            "ok": True, "result": "[[one_shape_one_writer]]",
            "epoch": "epoch-1", "commit": 8, "state_hash": "hash-8",
        }
        self.assertIsNone(gate._hard_policy_violation("shell", {"cmd": "printf x > tools/unsafe.py"}))
        self.assertIsNone(gate._hard_policy_violation("python", {"code": "open('tools/a.py','w').write('x')"}))

    def test_hard_policy_allows_read_only_managed_code_peek_with_stderr_redirect(self):
        violation = gate._hard_policy_violation(
            "shell",
            {
                "cmd": (
                    "pwd; sed -n '1,45p' tools/chroma_query.py "
                    "2>/dev/null || ls tools/ | head -20"
                )
            },
        )
        self.assertIsNone(violation)

    def test_shell_text_is_not_a_direct_write_veto(self):
        commands = (
            "printf x > tools/unsafe.py",
            "printf x | tee transformations/unsafe.py",
            "sed -i '' 's/x/y/' channels/terminal.py",
            "rm tools/unsafe.py",
            "printf x > .runtime/pwq.json",
        )
        for command in commands:
            with self.subTest(command=command):
                violation = gate._hard_policy_violation("shell", {"cmd": command})
                self.assertIsNone(violation)

    def test_human_pwq_decision_is_vetoed_before_tool(self):
        authoritative = {
            "ok": True, "result": "[[human_agency_before_dispatch]]",
            "epoch": "epoch-1", "commit": 4, "state_hash": "hash-4",
        }
        with mock.patch.object(gate._sub, "run_query", return_value=authoritative), \
             mock.patch.object(gate, "commit_event", return_value={"commit": 5}):
            verdict = gate.run("pwq_write", {"action": "approve", "proposal_id": "p"})
        self.assertTrue(verdict.startswith("enforce|VETO|"))
        self.assertIn("human", verdict.lower())

    def test_authoritative_nace_allow_records_evaluated_commit(self):
        authoritative = {
            "ok": True,
            "result": "[[(cap-evaluation 0.925 0.993 0.922025)]]",
            "epoch": "epoch-1", "commit": 12, "state_hash": "hash-12",
        }
        with mock.patch.object(gate._sub, "breaker_should_skip", return_value=False), \
             mock.patch.object(gate._sub, "breaker_record_result"), \
             mock.patch.object(gate._sub, "run_query", return_value=authoritative), \
             mock.patch.object(gate, "_load_lifecycle_and_priority", return_value=(None, "critical")), \
             mock.patch.object(gate, "commit_event", return_value={"commit": 13}) as commit:
            verdict = gate.run(
                "shell", {"cmd": "pwd"}, {"cycle": 3, "generation_id": "gen-1"}
            )
        self.assertTrue(verdict.startswith("enforce|ALLOW|"))
        self.assertIn("evaluated_state=12", verdict)
        payload = commit.call_args.kwargs["payload"]
        self.assertEqual(payload["evaluated_commit"], 12)
        self.assertEqual(payload["context"]["generation_id"], "gen-1")
        self.assertNotIn("pwd", json.dumps(payload))

    def test_decision_recording_failure_is_advisory_not_a_new_veto(self):
        authoritative = {
            "ok": True,
            "result": "[[(cap-evaluation 0.925 0.993 0.922025)]]",
            "epoch": "epoch-1", "commit": 12, "state_hash": "hash-12",
        }
        with mock.patch.object(gate._sub, "breaker_should_skip", return_value=False), \
             mock.patch.object(gate._sub, "breaker_record_result"), \
             mock.patch.object(gate._sub, "run_query", return_value=authoritative), \
             mock.patch.object(gate, "_load_lifecycle_and_priority", return_value=(None, "critical")), \
             mock.patch.object(gate, "commit_event", side_effect=RuntimeError("authority down")):
            verdict = gate.run("shell", {"cmd": "pwd"})
        self.assertTrue(verdict.startswith("enforce|ADVISE|"))
        self.assertIn("authority down", verdict)

    def test_iter_passes_arguments_and_generation_context_to_gate(self):
        source = (ROOT / "iter" / "iter.py").read_text(encoding="utf-8")
        self.assertIn("tool_name, tool_arguments", source)
        self.assertIn('"generation_id": ACTIVE_COMPONENT_SNAPSHOT.get("generation_id")', source)


if __name__ == "__main__":
    unittest.main()
