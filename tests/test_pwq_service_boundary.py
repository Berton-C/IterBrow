#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "iter" / "pwq_service.py"


class PWQServiceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.iter_root = Path(self.temporary.name) / "iter"
        self.iter_root.mkdir()
        self.env = {
            **os.environ,
            "ITER_DIR": str(self.iter_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def tearDown(self):
        self.temporary.cleanup()

    def call(self, action, *, expect_ok=True, **request):
        payload = {"action": action, **request}
        result = subprocess.run(
            [os.environ.get("PYTHON", "python3"), str(SERVICE)],
            cwd=self.iter_root,
            env=self.env,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=10,
        )
        response = json.loads(result.stdout)
        if expect_ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(response["ok"], response)
            return response["result"]
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(response["ok"])
        return response

    @staticmethod
    def item(board, proposal_id):
        return next(value for value in board["items"] if value["id"] == proposal_id)

    def proposal(self, title):
        return {
            "title": title,
            "ask": "Exercise the isolated PWQ service boundary?",
            "proposed_shape": "No product or network side effect.",
            "options": [],
            "work_class": "build",
            "governance_refs": {
                "atlas_slices": ["PWQ-2"],
                "invariants": ["INV-09", "INV-10", "INV-16"],
            },
            "authorization_scope": {"kind": "isolated_pwq_acceptance"},
        }

    def test_full_lifecycle_and_human_decisions_cross_the_json_boundary(self):
        proposal_id = "service-lifecycle"
        board = self.call(
            "propose", actor="iter", proposal_id=proposal_id,
            payload=self.proposal("Service lifecycle"), command_id="propose-1",
        )
        item = self.item(board, proposal_id)
        self.assertEqual(item["status"], "proposed")
        self.assertEqual(item["proposal_version"], 1)

        board = self.call(
            "sign", actor="human", proposal_id=proposal_id, expected_version=1,
            command_id="sign-1", payload={
                "signer_id": "human:owner",
                "role": "human_owner",
                "proof": {"type": "trusted_local_session_v1", "value": "isolated-ui-proof"},
            },
        )
        item = self.item(board, proposal_id)
        self.assertEqual(item["status"], "approved")
        token = item["dispatch_authorization"]
        self.assertTrue(token)

        board = self.call(
            "start", actor="iter", proposal_id=proposal_id, expected_version=1,
            command_id="start-1", payload={"dispatch_authorization": token},
        )
        self.assertEqual(self.item(board, proposal_id)["status"], "in_progress")

        tracking = {
            "target": "PWQ subprocess lifecycle acceptance",
            "atlas_slice": "PWQ-2",
            "bounded_claim": "The JSON service preserves the canonical lifecycle.",
            "invariants": ["INV-09", "INV-10", "INV-16"],
            "evidence_open_gaps": "Isolated service events pass; visible UI remains separate.",
            "boundaries": "No live queue, owner decision, or product side effect.",
            "next_trigger": "Pause and resume under the same authorization.",
        }
        board = self.call(
            "track", actor="iter", proposal_id=proposal_id, expected_version=1,
            command_id="track-1", payload=tracking,
        )
        self.assertEqual(self.item(board, proposal_id)["tracking"]["target"], tracking["target"])

        board = self.call(
            "pause", actor="human", proposal_id=proposal_id, expected_version=1,
            command_id="pause-1", payload={"reason": "isolated acceptance"},
        )
        self.assertEqual(self.item(board, proposal_id)["status"], "paused")
        board = self.call(
            "resume", actor="human", proposal_id=proposal_id, expected_version=1,
            command_id="resume-1", payload={"dispatch_authorization": token},
        )
        self.assertEqual(self.item(board, proposal_id)["status"], "in_progress")
        board = self.call(
            "complete", actor="human", proposal_id=proposal_id, expected_version=1,
            command_id="complete-1", payload={"note": "isolated acceptance complete"},
        )
        self.assertEqual(self.item(board, proposal_id)["status"], "completed")

        rejected_id = "service-reorder-reject"
        board = self.call(
            "propose", actor="iter", proposal_id=rejected_id,
            payload=self.proposal("Reorder and reject"), command_id="propose-2",
        )
        board = self.call(
            "reorder", actor="human", proposal_id=rejected_id, expected_version=1,
            command_id="reorder-1", payload={"position": 0},
        )
        self.assertEqual(board["items"][0]["id"], rejected_id)
        board = self.call(
            "reject", actor="human", proposal_id=rejected_id, expected_version=1,
            command_id="reject-1", payload={"reason": "isolated acceptance"},
        )
        self.assertEqual(self.item(board, rejected_id)["status"], "rejected")

        self.assertTrue((self.iter_root / ".runtime" / "pwq" / "events.jsonl").is_file())
        self.assertTrue((self.iter_root / ".runtime" / "pwq.json").is_file())

    def test_untrusted_actor_cannot_issue_a_human_decision(self):
        proposal_id = "service-human-boundary"
        self.call(
            "propose", actor="iter", proposal_id=proposal_id,
            payload=self.proposal("Human boundary"), command_id="propose-human-boundary",
        )
        response = self.call(
            "approve", expect_ok=False, actor="iter", proposal_id=proposal_id,
            expected_version=1, command_id="forged-approval", payload={},
        )
        self.assertIn("human decision", response["error"])


if __name__ == "__main__":
    unittest.main()
