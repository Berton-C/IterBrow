"""Additive foundry adapter for Iter's existing managed Python repair lane.

Only the existing tools/transformations/channels generation surface is managed
here. This is an artifact type, not the universe of code Iter may author. No
memory, state, source authority, heartbeat writer or supervisor is introduced.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .hotload_manager import HotloadManager, HotloadError, MANAGED_ROOTS


RUNTIME_ACTIONS = (
    "runtime.status", "runtime.stage", "runtime.validate", "runtime.propose",
    "runtime.activate", "runtime.rollback",
)
RUNTIME_ACTION_REGISTRY = {
    "runtime.status": {"required": (), "optional": ()},
    "runtime.stage": {"required": ("changes", "contract"), "optional": ()},
    "runtime.validate": {"required": ("candidate_id",), "optional": ()},
    "runtime.propose": {"required": ("candidate_id",), "optional": ("proposal_id",)},
    "runtime.activate": {"required": ("candidate_id", "proposal_id", "dispatch_authorization"),
                         "optional": ("required_heartbeats", "heartbeat_timeout")},
    "runtime.rollback": {"required": ("reason",), "optional": ()},
}


class FoundryRuntime:
    def __init__(self, iter_root, *, manager=None):
        self.iter_root = Path(iter_root).resolve()
        # A relocated component must not silently fork canonical authority by
        # following a generation-local or aliased runtime directory.
        for path in (self.iter_root / ".runtime", self.iter_root / ".runtime" / "hotload"):
            if path.is_symlink():
                raise HotloadError("managed runtime authority path cannot be a symlink")
        self.manager = manager or HotloadManager(self.iter_root)
        if self.manager.iter_root != self.iter_root:
            raise HotloadError("managed runtime adapter root differs from canonical Iter root")
        expected = self.iter_root / ".runtime" / "hotload"
        if Path(self.manager.runtime_dir).resolve() != expected.resolve():
            raise HotloadError("managed runtime adapter must use the canonical hotload authority")

    @staticmethod
    def _payload(action_type, payload):
        if action_type not in RUNTIME_ACTION_REGISTRY:
            raise HotloadError("unknown managed-runtime action")
        if not isinstance(payload, dict):
            raise HotloadError("managed-runtime payload must be an object")
        spec = RUNTIME_ACTION_REGISTRY[action_type]
        if set(spec["required"]) - set(payload):
            raise HotloadError("managed-runtime payload is missing required fields")
        if set(payload) - set(spec["required"] + spec["optional"]):
            raise HotloadError("managed-runtime payload contains unrecognized fields")
        if "candidate_id" in payload and not re.fullmatch(r"candidate-[a-f0-9]{32}", str(payload["candidate_id"])):
            raise HotloadError("invalid managed-runtime candidate identity")
        return json.loads(json.dumps(payload, allow_nan=False))

    def _propose(self, candidate_id, proposal_id=None):
        # Read candidate only through its existing manager after exact ID
        # validation. The guardian rechecks hashes, parent, and fixed tests.
        candidate = self.manager._read_candidate(candidate_id)
        if candidate.get("status") != "validated" or not (candidate.get("validation") or {}).get("passed"):
            raise HotloadError("managed runtime candidate must pass fixed validation before proposal")
        proposal_id = proposal_id or "hotload:" + candidate_id
        self.manager.pwq_store.command(
            "propose", proposal_id, actor="iter", command_id="foundry-runtime-propose:" + candidate_id,
            payload={
                "title": "Activate managed runtime revision: " + str(candidate["contract"]["module_id"]),
                "ask": str(candidate["contract"]["purpose"]), "work_class": "build",
                "governance_refs": {"atlas_slices": ["HOT-2", "REC-1", "BUILD-LOOP-1"],
                                    "invariants": ["INV-14", "INV-15"]},
                "approval_policy": self.manager.split_approval_policy(),
                "authorization_scope": self.manager.candidate_authorization_scope(candidate),
            },
        )
        board = self.manager.attest_candidate(candidate_id, proposal_id)
        item = next(entry for entry in board["items"] if entry["id"] == proposal_id)
        return {"proposal": item, "candidate_id": candidate_id,
                "candidate_tree_hash": candidate["tree_hash"]}

    def execute(self, action_type, payload, provenance=None):
        payload = self._payload(action_type, payload)
        pending = False
        proofs = {}
        if action_type == "runtime.status":
            result = self.manager.status()
            postcondition = "runtime-status"
            pending = result["active"].get("status") == "probation"
        elif action_type == "runtime.stage":
            contract = dict(payload["contract"])
            # The caller injects actual work/action provenance, not candidate code.
            contract["provenance"] = json.loads(json.dumps(provenance, allow_nan=False))
            result = self.manager.stage(payload["changes"], contract)
            postcondition = "runtime-staged"
        elif action_type == "runtime.validate":
            result = self.manager.validate(payload["candidate_id"])
            passed = result["validation"]["passed"]
            proofs["runtime-static"] = "passed" if passed else "failed"
            postcondition = "runtime-validated" if passed else "runtime-validation-failed"
        elif action_type == "runtime.propose":
            result = self._propose(payload["candidate_id"], payload.get("proposal_id"))
            postcondition = "runtime-awaiting-approval"
            pending = True
        elif action_type == "runtime.activate":
            result = self.manager.activate(**payload)
            postcondition = "runtime-probation-pending"
            pending = True  # A successful pointer update is NOT recovery proof.
        else:
            result = self.manager.rollback_probation(payload["reason"])
            postcondition = "runtime-rolled-back" if result.get("action") == "rolled_back" else "runtime-rollback-noop"
        return {"result": result, "postcondition": postcondition, "proofs": proofs,
                "pending": pending, "artifact_type": "managed-python-runtime",
                "managed_roots": list(MANAGED_ROOTS)}
