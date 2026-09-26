#!/usr/bin/env python3
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "iter"))

from iterbrow_runtime.pwq_protocol import PWQError, PWQStore  # noqa: E402


def proposal(status="proposed", **updates):
    value = {
        "id": "p1",
        "title": "Build durable cognition",
        "ask": "May Iter proceed?",
        "proposed_shape": "Journal then reason",
        "options": [{"label": "Yes", "desc": "Proceed"}],
        "selected_option": None,
        "user_input": "",
        "alarm": None,
        "negotiation_log": [],
        "status": status,
        "orders_given": status in ("approved", "orders given", "in_progress"),
        "created": "2026-09-21 12:00:00",
    }
    value.update(updates)
    return value


def split_policy():
    return {
        "scheme": "role_threshold_v1",
        "threshold": 2,
        "required_roles": ["human_owner", "runtime_guardian"],
        "distinct_signers": True,
        "eligible_signers": [
            {
                "signer_id": "human:owner",
                "role": "human_owner",
                "actors": ["human"],
                "proof_types": ["trusted_local_session_v1"],
            },
            {
                "signer_id": "platform:hotload_guardian",
                "role": "runtime_guardian",
                "actors": ["platform.hotload_guardian"],
                "proof_types": ["hotload_validation_v1"],
            },
        ],
    }


class PWQProtocolTests(unittest.TestCase):
    def make_store(self, temp):
        root = Path(temp)
        return PWQStore(root / "pwq", root / "pwq.json")

    def test_sync_migrates_legacy_status_and_mints_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            board = store.sync_board({"version": 1, "items": [proposal("orders given")]})
            item = board["items"][0]
            self.assertEqual(item["status"], "approved")
            self.assertTrue(item["dispatch_authorization"])
            self.assertTrue(item["orders_given"])
            self.assertGreaterEqual(board["sequence"], 2)

    def test_modify_invalidates_approval_and_stale_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            approved = store.command("approve", "p1", actor="human", expected_version=1)
            token = approved["items"][0]["dispatch_authorization"]
            modified = store.command(
                "modify", "p1", actor="human",
                payload={"user_input": "Use snapshots too"}, expected_version=1,
            )
            item = modified["items"][0]
            self.assertEqual(item["status"], "modified")
            self.assertIsNone(item["dispatch_authorization"])
            self.assertNotEqual(token, item["dispatch_authorization"])
            with self.assertRaises(PWQError):
                store.command("approve", "p1", actor="human", expected_version=1)

    def test_pause_resume_requires_current_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            approved = store.command("approve", "p1", actor="human")
            token = approved["items"][0]["dispatch_authorization"]
            started = store.command(
                "start", "p1", payload={"dispatch_authorization": token},
            )
            self.assertEqual(started["items"][0]["status"], "in_progress")
            paused = store.command("pause", "p1", actor="human")
            self.assertEqual(paused["items"][0]["status"], "paused")
            with self.assertRaises(PWQError):
                store.command(
                    "resume", "p1", actor="human",
                    payload={"dispatch_authorization": "wrong"},
                )
            resumed = store.command(
                "resume", "p1", actor="human",
                payload={"dispatch_authorization": token},
            )
            self.assertEqual(resumed["items"][0]["status"], "in_progress")

            store.command("pause", "p1", actor="human")
            store.command("complete", "p1", actor="human")

    def test_pause_before_dispatch_resumes_to_approved(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            approved = store.command("approve", "p1", actor="human")
            token = approved["items"][0]["dispatch_authorization"]
            paused = store.command("pause", "p1", actor="human")
            self.assertEqual(paused["items"][0]["status"], "paused")
            resumed = store.command(
                "resume", "p1", actor="human",
                payload={"dispatch_authorization": token},
            )
            self.assertEqual(resumed["items"][0]["status"], "approved")

    def test_in_progress_work_must_pause_before_modification(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            approved = store.command("approve", "p1", actor="human")
            token = approved["items"][0]["dispatch_authorization"]
            store.command("start", "p1", payload={"dispatch_authorization": token})
            with self.assertRaisesRegex(PWQError, "must be paused"):
                store.command(
                    "modify", "p1", actor="human",
                    payload={"user_input": "unsafe live edit"},
                )
            with self.assertRaisesRegex(PWQError, "must be paused"):
                store.command("reject", "p1", actor="human")
            store.command("pause", "p1", actor="human")
            modified = store.command(
                "modify", "p1", actor="human",
                payload={"user_input": "bounded paused edit"},
            )
            item = modified["items"][0]
            self.assertEqual(item["status"], "modified")
            self.assertEqual(item["user_input"], "bounded paused edit")
            self.assertIsNone(item["dispatch_authorization"])

    def test_dispatch_requires_current_approval_token(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            with self.assertRaises(PWQError):
                store.command("start", "p1", payload={"dispatch_authorization": "none"})
            approved = store.command("approve", "p1", actor="human", expected_version=1)
            item = approved["items"][0]
            with self.assertRaises(PWQError):
                store.command("start", "p1", payload={"dispatch_authorization": "wrong"})
            started = store.command(
                "start", "p1", payload={"dispatch_authorization": item["dispatch_authorization"]},
                expected_version=item["proposal_version"],
            )
            self.assertEqual(started["items"][0]["status"], "in_progress")

    def test_agent_cannot_mint_human_decisions(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            for decision in ("approve", "reject", "reorder"):
                with self.subTest(decision=decision), self.assertRaises(PWQError):
                    store.command(decision, "p1", actor="iter", payload={"position": 0})

    def test_split_role_threshold_binds_exact_version_before_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            created = store.command(
                "propose", "p1", payload=proposal(
                    approval_policy=split_policy(),
                    authorization_scope={
                        "action": "hotload.activate",
                        "candidate_id": "candidate-1",
                        "candidate_tree_hash": "abc",
                        "rollback_target": "base-1",
                    },
                ),
            )
            original_digest = created["items"][0]["proposal_digest"]
            witnessed = store.command(
                "sign", "p1", actor="platform.hotload_guardian",
                payload={
                    "signer_id": "platform:hotload_guardian",
                    "role": "runtime_guardian",
                    "proof": {"type": "hotload_validation_v1", "value": "evidence"},
                },
                expected_version=1,
            )
            item = witnessed["items"][0]
            self.assertEqual(item["status"], "proposed")
            self.assertIsNone(item["dispatch_authorization"])
            self.assertEqual(item["approval_status"]["collected"], 1)
            self.assertFalse(item["approval_status"]["ready"])
            with self.assertRaises(PWQError):
                store.command(
                    "sign", "p1", actor="iter",
                    payload={
                        "signer_id": "human:owner",
                        "role": "human_owner",
                        "proof": {"type": "trusted_local_session_v1", "value": "fake"},
                    },
                )
            approved = store.command("approve", "p1", actor="human", expected_version=1)
            item = approved["items"][0]
            self.assertEqual(item["status"], "approved")
            self.assertTrue(item["dispatch_authorization"])
            self.assertTrue(item["authorization_evidence_digest"])
            self.assertTrue(item["approval_status"]["ready"])
            self.assertEqual(item["proposal_digest"], original_digest)

            modified = store.command(
                "modify", "p1", actor="human",
                payload={"user_input": "new scope"}, expected_version=1,
            )
            item = modified["items"][0]
            self.assertNotEqual(item["proposal_digest"], original_digest)
            self.assertEqual(item["approval_signatures"], [])
            self.assertIsNone(item["dispatch_authorization"])
            self.assertFalse(item["approval_status"]["ready"])

    def test_uninstalled_wallet_proof_cannot_be_treated_as_a_signature(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            policy = split_policy()
            policy["eligible_signers"][0]["proof_types"].append("eip712")
            store.command("propose", "p1", payload=proposal(approval_policy=policy))
            with self.assertRaises(PWQError):
                store.command(
                    "sign", "p1", actor="human",
                    payload={
                        "signer_id": "human:owner",
                        "role": "human_owner",
                        "proof": {"type": "eip712", "value": "unverified"},
                    },
                )

    def test_command_id_is_idempotent_and_cannot_be_repurposed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            first = store.command(
                "propose", "p1", payload=proposal(), command_id="cmd-propose-1"
            )
            retried = store.command(
                "propose", "p1", payload=proposal(), command_id="cmd-propose-1"
            )
            self.assertEqual(first, retried)
            self.assertEqual(retried["sequence"], 1)
            with self.assertRaises(PWQError):
                store.command(
                    "modify", "p1", payload={"user_input": "changed"},
                    command_id="cmd-propose-1",
                )

    def test_incomplete_final_ledger_write_is_repaired_and_audited(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            torn = b'{"interrupted":'
            with store.events_path.open("ab") as handle:
                handle.write(torn)

            modified = store.command(
                "modify", "p1", actor="human",
                payload={"user_input": "recovered"},
            )
            self.assertEqual(modified["items"][0]["status"], "modified")
            self.assertEqual(modified["items"][0]["user_input"], "recovered")
            events = store._events()
            recovery = next(
                event for event in events if event["kind"] == "ledger_tail_recovered"
            )
            self.assertEqual(
                recovery["payload"]["discarded_tail_sha256"],
                hashlib.sha256(torn).hexdigest(),
            )
            self.assertTrue(store.events_path.read_bytes().endswith(b"\n"))

    def test_complete_malformed_ledger_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            with store.events_path.open("ab") as handle:
                handle.write(b"not-json\n")
            with self.assertRaisesRegex(PWQError, "ledger corruption"):
                store.read()

    def test_reorder_reject_and_hash_chain_recovery(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            store.command("propose", "p2", payload={**proposal(), "id": "p2", "title": "Second"})
            reordered = store.command("reorder", "p2", actor="human", payload={"position": 0})
            self.assertEqual([item["id"] for item in reordered["items"]], ["p2", "p1"])
            rejected = store.command("reject", "p2", actor="human")
            self.assertEqual(rejected["items"][0]["status"], "rejected")
            recovered = self.make_store(temp).read()
            self.assertEqual(recovered, rejected)

    def test_only_runtime_guardian_can_terminally_supersede_a_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            approved = store.command("approve", "p1", actor="human")
            self.assertTrue(approved["items"][0]["dispatch_authorization"])
            with self.assertRaises(PWQError):
                store.command(
                    "supersede", "p1", actor="iter",
                    payload={"replacement_proposal_id": "p2"},
                )
            retired = store.command(
                "supersede", "p1", actor="platform.hotload_guardian",
                payload={"replacement_proposal_id": "p2"},
            )
            item = retired["items"][0]
            self.assertEqual(item["status"], "superseded")
            self.assertEqual(item["superseded_by"], "p2")
            self.assertIsNone(item["dispatch_authorization"])
            with self.assertRaises(PWQError):
                store.command("sign", "p1", actor="human")

    def test_tracking_labels_are_descriptive_not_runtime_prerequisites(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            build = proposal(
                work_class="build",
                governance_refs={
                    "atlas_slices": ["HOT-2", "REC-1"],
                    "invariants": ["INV-14", "INV-15"],
                },
            )
            store.command("propose", "p1", payload=build)
            tracking = {
                "target": "Recoverable self-extension",
                "atlas_slice": "HOT-2",
                "bounded_claim": "One cycle uses one immutable generation",
                "invariants": ["INV-14"],
                "evidence_open_gaps": "Pointer tests pass; live Electron drill remains",
                "boundaries": "Candidate cannot approve or promote itself",
                "next_trigger": "Run the external-supervisor failure drill",
                "source_revision": "test-revision",
            }
            with self.assertRaises(PWQError):
                store.command("track", "p1", payload=tracking)
            approved = store.command("approve", "p1", actor="human", expected_version=1)
            token = approved["items"][0]["dispatch_authorization"]
            started = store.command(
                "start", "p1", payload={"dispatch_authorization": token},
                expected_version=1,
            )
            tracked = store.command(
                "track", "p1", payload=tracking, expected_version=1,
                command_id="track-1",
            )
            item = tracked["items"][0]
            self.assertEqual(item["status"], "in_progress")
            self.assertEqual(item["dispatch_authorization"], token)
            self.assertEqual(item["proposal_version"], 1)
            self.assertEqual(item["tracking_sequence"], 1)
            self.assertEqual(item["tracking"]["atlas_slice"], "HOT-2")
            self.assertEqual(item["tracking"]["invariants"], ["INV-14"])
            replayed = self.make_store(temp).read()["items"][0]
            self.assertEqual(replayed["tracking"], item["tracking"])
            retried = store.command(
                "track", "p1", payload=tracking, expected_version=1,
                command_id="track-1",
            )
            self.assertEqual(retried["sequence"], tracked["sequence"])
            changed = store.command(
                    "track", "p1",
                    payload={**tracking, "atlas_slice": "AS-1"},
                    expected_version=1,
                )
            self.assertEqual(changed['items'][0]['tracking']['atlas_slice'], 'AS-1')
            changed = store.command(
                    "track", "p1",
                    payload={**tracking, "invariants": ["INV-01"]},
                    expected_version=1,
                )
            self.assertEqual(changed['items'][0]['dispatch_authorization'], token)
            store.command("pause", "p1", actor="human", expected_version=1)
            modified = store.command(
                "modify", "p1", actor="human",
                payload={"user_input": "Change the approved build scope"},
                expected_version=1,
            )
            self.assertIsNone(modified["items"][0]["tracking"])
            self.assertIsNone(modified["items"][0]["dispatch_authorization"])

    def test_general_work_tracking_labels_do_not_grant_new_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.make_store(temp)
            store.command("propose", "p1", payload=proposal())
            approved = store.command("approve", "p1", actor="human", expected_version=1)
            token = approved["items"][0]["dispatch_authorization"]
            store.command("start", "p1", payload={"dispatch_authorization": token})
            tracked = store.command("track", "p1", payload={
                    "target": "General work",
                    "atlas_slice": "HOT-2",
                    "bounded_claim": "Do the work",
                    "invariants": [],
                    "evidence_open_gaps": "Open",
                    "boundaries": "Approved scope",
                    "next_trigger": "Continue",
                })
            self.assertEqual(tracked['items'][0]['dispatch_authorization'], token)


if __name__ == "__main__":
    unittest.main()
