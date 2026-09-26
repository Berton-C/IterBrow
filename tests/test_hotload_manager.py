#!/usr/bin/env python3
import tempfile
import json
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT / "iter") not in sys.path:
    sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.hotload_manager import HotloadError, HotloadManager, IterHeartbeat
from iterbrow_runtime.pwq_protocol import PWQStore


BASE_TOOL = 'DESCRIPTION = "base"\n\ndef run():\n    return "base"\n'
CANDIDATE_TOOL = 'DESCRIPTION = "candidate"\n\ndef run():\n    return "candidate"\n'


class HotloadManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.iter_root = Path(self.temporary.name) / "iter"
        for name in ("tools", "transformations", "channels"):
            (self.iter_root / name).mkdir(parents=True)
        (self.iter_root / "tools" / "sample.py").write_text(BASE_TOOL, encoding="utf-8")
        self.store = PWQStore(
            self.iter_root / ".runtime" / "pwq",
            self.iter_root / ".runtime" / "pwq.json",
        )
        self.manager = HotloadManager(self.iter_root, pwq_store=self.store)
        self.base = self.manager.ensure_baseline()["generation_id"]
        self.parent_heartbeat = IterHeartbeat(self.iter_root, "parent", pid=os.getpid())
        self.parent_heartbeat.write(self.base, "cycle_complete", 0)

    def tearDown(self):
        self.temporary.cleanup()

    def _contract(self, path="tools/sample.py"):
        return {
            "module_id": "sample-tool",
            "version": "2",
            "purpose": "bounded test repair",
            "source_pressure": "test evidence",
            "atlas_slice": "HOT-1",
            "allowed_writes": [path],
            "allowed_effects": [],
            "tests": ["python_compile", "component_contract"],
            "rollback_target": self.manager.active()["generation_id"],
            "provenance": "unit-test",
        }

    def _approved(self, proposal_id="revision-test"):
        self.store.command(
            "propose", proposal_id, actor="iter",
            payload={
                "title": "Activate test revision",
                "ask": "Approve probation",
                "work_class": "build",
                "governance_refs": {
                    "atlas_slices": ["HOT-2", "REC-1"],
                    "invariants": ["INV-14", "INV-15"],
                },
            },
        )
        board = self.store.command(
            "approve", proposal_id, actor="human", expected_version=1,
        )
        item = next(entry for entry in board["items"] if entry["id"] == proposal_id)
        return proposal_id, item["dispatch_authorization"]

    def _validated_candidate(self):
        candidate = self.manager.stage(
            {"tools/sample.py": CANDIDATE_TOOL}, self._contract(),
        )
        candidate = self.manager.validate(candidate["candidate_id"])
        self.assertTrue(candidate["validation"]["passed"])
        self.assertFalse(candidate["validation"]["candidate_executed"])
        return candidate

    def test_candidate_is_inert_until_authorized_activation(self):
        candidate = self._validated_candidate()
        status = self.manager.status()
        self.assertEqual(status["candidate"]["candidate_id"], candidate["candidate_id"])
        self.assertEqual(status["actionable_candidate_ids"], [candidate["candidate_id"]])
        snapshot = self.manager.component_snapshot()
        self.assertEqual(snapshot["generation_id"], self.base)
        self.assertEqual(
            (snapshot["roots"]["tools"] / "sample.py").read_text(encoding="utf-8"),
            BASE_TOOL,
        )
        with self.assertRaises(HotloadError):
            self.manager.activate(candidate["candidate_id"], "missing", "not-a-token")
        proposal_id, token = self._approved()
        active = self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=2, heartbeat_timeout=60,
        )
        self.assertEqual(active["status"], "probation")
        item = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertEqual(item["status"], "in_progress")
        self.assertEqual(item["tracking"]["atlas_slice"], "REC-1")
        snapshot = self.manager.component_snapshot()
        self.assertEqual(snapshot["generation_id"], candidate["generation_id"])
        self.assertEqual(
            (snapshot["roots"]["tools"] / "sample.py").read_text(encoding="utf-8"),
            CANDIDATE_TOOL,
        )

    def test_staging_copies_only_managed_roots(self):
        parent = self.manager._generation_path(self.base)
        (parent / "chroma_db").mkdir()

        candidate = self.manager.stage(
            {"tools/sample.py": CANDIDATE_TOOL}, self._contract(),
        )

        generation = self.manager._generation_path(candidate["generation_id"])
        self.assertFalse((generation / "chroma_db").exists())
        self.assertTrue((generation / "tools" / "sample.py").is_file())

    def test_non_managed_generation_file_fails_validation(self):
        candidate = self.manager.stage(
            {"tools/sample.py": CANDIDATE_TOOL}, self._contract(),
        )
        generation = self.manager._generation_path(candidate["generation_id"])
        state_dir = generation / "chroma_db"
        state_dir.mkdir()
        (state_dir / "memories.json").write_text("[]\n", encoding="utf-8")

        with self.assertRaisesRegex(HotloadError, "non-managed file"):
            self.manager.validate(candidate["candidate_id"])

    def test_activation_requires_a_live_matching_parent_before_dispatch(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.heartbeat_path.unlink()
        with self.assertRaisesRegex(HotloadError, "live parent heartbeat"):
            self.manager.activate(candidate["candidate_id"], proposal_id, token)
        item = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertEqual(item["status"], "approved")
        self.assertEqual(candidate["status"], "validated")

        dead = IterHeartbeat(self.iter_root, "dead-parent", pid=99999999)
        dead.write(self.base, "cycle_complete", 1)
        with self.assertRaisesRegex(HotloadError, "not running"):
            self.manager.activate(candidate["candidate_id"], proposal_id, token)
        item = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertEqual(item["status"], "approved")

    def test_live_parent_cycle_may_finish_after_candidate_activation(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        parent = json.loads(self.manager.heartbeat_path.read_text(encoding="utf-8"))
        active = self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=1, heartbeat_timeout=60,
        )
        # The already-pinned parent may legitimately publish later phases
        # after the atomic pointer changes.  Only this exact session/PID/cycle
        # identity gets the transition allowance.
        self.parent_heartbeat.write(self.base, "model_wait", 0)
        waiting = self.manager.supervisor_check(
            True,
            now=active["activated_at"] + 11,
            iter_pid=os.getpid(),
            iter_started_at=parent["at"] - 1,
        )
        self.assertEqual(waiting["action"], "waiting")
        self.assertEqual(
            waiting["reason"],
            "activation-time parent cycle is still finishing",
        )
        candidate_heartbeat = IterHeartbeat(
            self.iter_root, "candidate", pid=os.getpid()
        )
        candidate_heartbeat.write(candidate["generation_id"], "cycle_complete", 1)
        promoted = self.manager.supervisor_check(True, iter_pid=os.getpid())
        self.assertEqual(promoted["action"], "promoted")

    def test_different_parent_cycle_after_activation_is_rejected(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(candidate["candidate_id"], proposal_id, token)
        self.parent_heartbeat.write(self.base, "cycle_start", 1)
        recovered = self.manager.supervisor_check(True, iter_pid=os.getpid())
        self.assertEqual(recovered["action"], "rolled_back")
        self.assertIn("wrong active generation", recovered["reason"])

    def test_split_control_requires_guardian_and_human_on_exact_candidate(self):
        candidate = self._validated_candidate()
        proposal_id = "split-revision"
        self.store.command(
            "propose", proposal_id, actor="iter",
            payload={
                "title": "Activate split-controlled revision",
                "ask": "Approve probation",
                "work_class": "build",
                "governance_refs": {
                    "atlas_slices": ["HOT-2", "REC-1"],
                    "invariants": ["INV-14", "INV-15", "INV-21"],
                },
                "approval_policy": self.manager.split_approval_policy(),
                "authorization_scope": self.manager.candidate_authorization_scope(candidate),
            },
        )
        witnessed = self.manager.attest_candidate(candidate["candidate_id"], proposal_id)
        item = next(entry for entry in witnessed["items"] if entry["id"] == proposal_id)
        self.assertEqual(item["approval_status"]["collected"], 1)
        self.assertFalse(item["approval_status"]["ready"])
        self.assertIsNone(item["dispatch_authorization"])
        approved = self.store.command(
            "approve", proposal_id, actor="human", expected_version=1,
        )
        item = next(entry for entry in approved["items"] if entry["id"] == proposal_id)
        self.assertTrue(item["approval_status"]["ready"])
        active = self.manager.activate(
            candidate["candidate_id"], proposal_id, item["dispatch_authorization"],
            required_heartbeats=2, heartbeat_timeout=60,
        )
        self.assertEqual(active["status"], "probation")

    def test_guardian_refuses_mismatched_candidate_scope(self):
        candidate = self._validated_candidate()
        scope = self.manager.candidate_authorization_scope(candidate)
        scope["candidate_tree_hash"] = "wrong"
        self.store.command(
            "propose", "scope-mismatch", actor="iter",
            payload={
                "title": "Wrong candidate binding",
                "ask": "Approve probation",
                "work_class": "build",
                "governance_refs": {
                    "atlas_slices": ["HOT-2", "REC-1"],
                    "invariants": ["INV-14", "INV-15", "INV-21"],
                },
                "approval_policy": self.manager.split_approval_policy(),
                "authorization_scope": scope,
            },
        )
        with self.assertRaises(HotloadError):
            self.manager.attest_candidate(candidate["candidate_id"], "scope-mismatch")

    def test_inert_candidate_can_be_superseded_with_evidence_retained(self):
        first = self._validated_candidate()
        second = self._validated_candidate()
        old_proposal_id = "hotload:" + first["candidate_id"]
        self.store.command(
            "propose", old_proposal_id, actor="iter",
            payload={"title": "Old candidate", "ask": "Approve old candidate?"},
        )
        retired = self.manager.supersede_candidate(
            first["candidate_id"], second["candidate_id"]
        )
        self.assertEqual(retired["status"], "superseded")
        self.assertEqual(retired["replacement_candidate_id"], second["candidate_id"])
        self.assertTrue(self.manager._generation_path(first["generation_id"]).is_dir())
        status = self.manager.status()
        self.assertEqual(status["candidate"]["candidate_id"], second["candidate_id"])
        self.assertEqual(status["actionable_candidate_ids"], [second["candidate_id"]])
        old_item = next(
            item for item in self.store.read()["items"]
            if item["id"] == old_proposal_id
        )
        self.assertEqual(old_item["status"], "superseded")
        self.assertEqual(
            old_item["superseded_by"], "hotload:" + second["candidate_id"]
        )

    def test_external_heartbeats_promote_probation(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=2, heartbeat_timeout=60,
        )
        heartbeat = IterHeartbeat(self.iter_root, "session")
        heartbeat.write(candidate["generation_id"], "cycle_complete", 1)
        first = self.manager.supervisor_check(True)
        self.assertEqual(first["action"], "waiting")
        tracked_first = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertIn("1 of 2", tracked_first["tracking"]["evidence_open_gaps"])
        heartbeat.write(candidate["generation_id"], "cycle_complete", 2)
        second = self.manager.supervisor_check(True)
        self.assertEqual(second["action"], "promoted")
        self.assertEqual(self.manager.active()["generation_id"], candidate["generation_id"])
        self.assertEqual(self.manager.active()["status"], "stable")
        tracked_final = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertEqual(tracked_final["tracking"]["atlas_slice"], "HOT-2")
        self.assertIn("All 2", tracked_final["tracking"]["evidence_open_gaps"])

    def test_completed_cycle_evidence_survives_latest_heartbeat_overwrite(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=2, heartbeat_timeout=60,
        )
        heartbeat = IterHeartbeat(self.iter_root, "lossless", pid=os.getpid())
        heartbeat.write(candidate["generation_id"], "cycle_complete", 1)
        heartbeat.write(candidate["generation_id"], "components_loaded", 2)
        first = self.manager.supervisor_check(True, iter_pid=os.getpid())
        self.assertEqual(first["action"], "waiting")
        record = self.manager._read_candidate(candidate["candidate_id"])
        self.assertEqual(record["observed_heartbeats"], ["lossless:1:cycle_complete"])
        self.assertEqual(
            record["completion_evidence"][0]["source"],
            "immutable_completion",
        )

        heartbeat.write(candidate["generation_id"], "cycle_complete", 2)
        heartbeat.write(candidate["generation_id"], "model_wait", 3)
        promoted = self.manager.supervisor_check(True, iter_pid=os.getpid())
        self.assertEqual(promoted["action"], "promoted")

    def test_successor_cycle_proves_completions_for_pre_upgrade_iter_process(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=2, heartbeat_timeout=60,
        )
        # Simulate an Iter process that started before immutable completion
        # files were available: its deterministic completion IDs were briefly
        # written to the latest-heartbeat file and then overwritten.
        self.parent_heartbeat.write(candidate["generation_id"], "cycle_complete", 1)
        self.parent_heartbeat.write(candidate["generation_id"], "cycle_complete", 2)
        for path in self.parent_heartbeat.completions_dir.glob("*.json"):
            path.unlink()
        self.parent_heartbeat.completions_dir.rmdir()
        self.parent_heartbeat.write(candidate["generation_id"], "components_loaded", 3)

        promoted = self.manager.supervisor_check(True, iter_pid=os.getpid())
        self.assertEqual(promoted["action"], "promoted")
        record = self.manager._read_candidate(candidate["candidate_id"])
        self.assertEqual(
            [entry["source"] for entry in record["completion_evidence"]],
            ["successor_cycle", "successor_cycle"],
        )

    def test_tampered_completed_cycle_evidence_rolls_back_probation(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=1, heartbeat_timeout=60,
        )
        heartbeat = IterHeartbeat(self.iter_root, "tampered", pid=os.getpid())
        heartbeat.write(candidate["generation_id"], "cycle_complete", 1)
        evidence_path = next(heartbeat.completions_dir.glob("*.json"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["cycle"] = 99
        evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

        recovered = self.manager.supervisor_check(True, iter_pid=os.getpid())
        self.assertEqual(recovered["action"], "rolled_back")
        self.assertIn("integrity verification", recovered["reason"])

    def test_process_exit_rolls_back_exact_parent(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        active = self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=2, heartbeat_timeout=60,
        )
        result = self.manager.supervisor_check(False, now=active["activated_at"] + 11)
        self.assertEqual(result["action"], "rolled_back")
        self.assertEqual(result["active"]["generation_id"], self.base)
        failed = self.manager.status()["candidate"]
        self.assertIsNone(failed)
        candidate_record = self.manager._read_candidate(candidate["candidate_id"])
        self.assertEqual(candidate_record["status"], "rolled_back")
        self.assertIn("exited", candidate_record["rollback_reason"])
        tracked = next(entry for entry in self.store.read()["items"] if entry["id"] == proposal_id)
        self.assertEqual(tracked["status"], "paused")
        self.assertEqual(tracked["tracking"]["atlas_slice"], "REC-1")
        self.assertIn("rollback completed", tracked["tracking"]["evidence_open_gaps"])

    def test_generation_tampering_blocks_activation_and_rolls_back_probation(self):
        candidate = self._validated_candidate()
        candidate_path = self.manager._generation_path(candidate["generation_id"]) / "tools" / "sample.py"
        candidate_path.write_text(CANDIDATE_TOOL + "# tampered\n", encoding="utf-8")
        proposal_id, token = self._approved()
        with self.assertRaises(HotloadError):
            self.manager.activate(candidate["candidate_id"], proposal_id, token)

        # A separately staged candidate that changes after activation is
        # rejected by the external supervisor before it can be promoted.
        fresh = self._validated_candidate()
        proposal_id_2, token_2 = self._approved("revision-test-2")
        self.manager.activate(fresh["candidate_id"], proposal_id_2, token_2)
        fresh_path = self.manager._generation_path(fresh["generation_id"]) / "tools" / "sample.py"
        fresh_path.write_text(CANDIDATE_TOOL + "# changed in probation\n", encoding="utf-8")
        recovered = self.manager.supervisor_check(True)
        self.assertEqual(recovered["action"], "rolled_back")
        self.assertIn("hash mismatch", recovered["reason"])

    def test_promoted_generation_corruption_recovers_exact_parent_on_startup(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=1, heartbeat_timeout=60,
        )
        heartbeat = IterHeartbeat(self.iter_root, "promote")
        heartbeat.write(candidate["generation_id"], "cycle_complete", 1)
        self.assertEqual(self.manager.supervisor_check(True)["action"], "promoted")
        active_path = self.manager._generation_path(candidate["generation_id"]) / "tools" / "sample.py"
        active_path.write_text(CANDIDATE_TOOL + "# corrupted after promotion\n", encoding="utf-8")
        recovered = self.manager.recover_on_startup()
        self.assertEqual(recovered["action"], "rolled_back")
        self.assertEqual(recovered["active"]["generation_id"], self.base)
        record = self.manager._read_candidate(candidate["candidate_id"])
        self.assertEqual(record["status"], "rolled_back_after_promotion")

    def test_event_ledger_tampering_fails_closed(self):
        events = self.manager.events_path.read_text(encoding="utf-8")
        self.manager.events_path.write_text(events.replace("baseline_created", "baseline_changed"), encoding="utf-8")
        with self.assertRaises(HotloadError):
            self.manager.status()

    def test_incomplete_final_ledger_write_is_repaired_and_audited(self):
        with self.manager.events_path.open("ab") as handle:
            handle.write(b'{"interrupted":')
        status = self.manager.status()
        self.assertTrue(status["ledger_tail_incomplete"])
        candidate = self._validated_candidate()
        self.assertEqual(candidate["status"], "validated")
        events = self.manager._events()
        recovery = next(event for event in events if event["kind"] == "ledger_tail_recovered")
        self.assertEqual(recovery["payload"]["recovered_event_count"], 1)
        self.assertFalse(self.manager.status()["ledger_tail_incomplete"])

    def test_progress_heartbeat_hard_floor_failure_rolls_back_without_promotion(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(
            candidate["candidate_id"], proposal_id, token,
            required_heartbeats=1, heartbeat_timeout=60,
        )
        heartbeat = IterHeartbeat(self.iter_root, "hard-floor")
        heartbeat.write(
            candidate["generation_id"], "components_loaded", 1,
            hard_floor_ok=False, detail="changed component failed to load",
        )
        result = self.manager.supervisor_check(True)
        self.assertEqual(result["action"], "rolled_back")
        self.assertEqual(result["active"]["generation_id"], self.base)
        record = self.manager._read_candidate(candidate["candidate_id"])
        self.assertEqual(record["status"], "rolled_back")
        self.assertEqual(record["observed_heartbeats"], [])

    def test_startup_never_resumes_abandoned_probation(self):
        candidate = self._validated_candidate()
        proposal_id, token = self._approved()
        self.manager.activate(candidate["candidate_id"], proposal_id, token)
        result = self.manager.recover_on_startup()
        self.assertEqual(result["action"], "rolled_back")
        self.assertEqual(self.manager.active()["generation_id"], self.base)

    def test_stable_generation_requests_restart_for_missing_or_stale_heartbeat(self):
        waiting = self.manager.supervisor_check(
            True, now=20, iter_pid=44, iter_started_at=0,
        )
        self.assertEqual(waiting["action"], "waiting")
        missing = self.manager.supervisor_check(
            True, now=31, iter_pid=44, iter_started_at=0,
        )
        self.assertEqual(missing["action"], "restart_required")
        heartbeat = IterHeartbeat(self.iter_root, "stable", pid=44)
        written = heartbeat.write(self.base, "cycle_start", 1)
        stale = self.manager.supervisor_check(
            True, now=written["at"] + 721, iter_pid=44,
            iter_started_at=written["at"] - 1,
        )
        self.assertEqual(stale["action"], "restart_required")
        self.assertIn("stale", stale["reason"])

    def test_core_paths_and_candidate_defined_tests_are_rejected(self):
        with self.assertRaises(HotloadError):
            self.manager.stage({"iter.py": "pass\n"}, self._contract("iter.py"))
        contract = self._contract()
        contract["tests"] = ["candidate_says_it_passed"]
        with self.assertRaises(HotloadError):
            self.manager.stage({"tools/sample.py": CANDIDATE_TOOL}, contract)
        nested = self._contract("tools/scratch/sample.py")
        with self.assertRaises(HotloadError):
            self.manager.stage({"tools/scratch/sample.py": CANDIDATE_TOOL}, nested)

    def test_broken_component_contract_fails_without_execution(self):
        candidate = self.manager.stage(
            {"tools/sample.py": "def not_run():\n    raise RuntimeError('must stay inert')\n"},
            self._contract(),
        )
        checked = self.manager.validate(candidate["candidate_id"])
        self.assertEqual(checked["status"], "validation_failed")
        self.assertFalse(checked["validation"]["passed"])
        self.assertFalse(checked["validation"]["candidate_executed"])


if __name__ == "__main__":
    unittest.main()
