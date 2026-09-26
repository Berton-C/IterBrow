"""Durable PWQ human-agency protocol and board materializer."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import time
import uuid
from pathlib import Path


SCHEMA_VERSION = 1
CANONICAL_STATUSES = {
    "proposed", "modified", "approved", "in_progress",
    "paused", "completed", "rejected", "superseded", "archived",
}
LEGACY_STATUS = {
    "waiting": "proposed",
    "proposed": "proposed",
    "negotiating": "modified",
    "modified": "modified",
    "orders given": "approved",
    "approved": "approved",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "paused": "paused",
    "done": "completed",
    "completed": "completed",
    "rejected": "rejected",
}
TERMINAL = {"completed", "rejected", "superseded"}
HUMAN_DECISIONS = {"approve", "reject", "reorder"}
TRUSTED_HUMAN_ACTORS = {"human", "migration"}
WORK_CLASSES = {"general", "build"}
APPROVAL_SCHEME = "role_threshold_v1"
LOCAL_HUMAN_PROOF = "trusted_local_session_v1"
HOTLOAD_GUARDIAN_PROOF = "hotload_validation_v1"


def _default_approval_policy():
    return {
        "scheme": APPROVAL_SCHEME,
        "threshold": 1,
        "required_roles": ["human_owner"],
        "distinct_signers": True,
        "eligible_signers": [
            {
                "signer_id": "human:owner",
                "role": "human_owner",
                "actors": ["human", "migration"],
                "proof_types": [LOCAL_HUMAN_PROOF],
            },
        ],
    }


class PWQError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fsync_directory(path):
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    _fsync_directory(path.parent)


def _atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))
    _fsync_directory(path.parent)


def _normalise_status(item):
    status = str(item.get("status", "proposed")).strip().lower()
    if item.get("orders_given") and status not in ("completed", "done", "rejected"):
        status = "approved"
    status = LEGACY_STATUS.get(status, status)
    if status not in CANONICAL_STATUSES:
        raise PWQError("unknown PWQ status: %s" % status)
    return status


def _normalise_approval_policy(raw):
    if raw in (None, {}):
        return _default_approval_policy()
    if not isinstance(raw, dict):
        raise PWQError("approval_policy must be an object")
    if raw.get("scheme", APPROVAL_SCHEME) != APPROVAL_SCHEME:
        raise PWQError("unsupported approval policy scheme")
    eligible = raw.get("eligible_signers")
    if not isinstance(eligible, list) or not eligible:
        raise PWQError("approval_policy requires eligible_signers")
    signers = []
    signer_ids = set()
    for value in eligible:
        if not isinstance(value, dict):
            raise PWQError("eligible signer entries must be objects")
        signer_id = str(value.get("signer_id", "")).strip()
        role = str(value.get("role", "")).strip()
        actors = value.get("actors") or []
        proof_types = value.get("proof_types") or []
        if not signer_id or not role:
            raise PWQError("eligible signers require signer_id and role")
        if signer_id in signer_ids:
            raise PWQError("eligible signer ids must be distinct")
        if not isinstance(actors, list) or not actors or not all(
            isinstance(actor, str) and actor.strip() for actor in actors
        ):
            raise PWQError("eligible signer actors must be a non-empty string list")
        if not isinstance(proof_types, list) or not proof_types or not all(
            isinstance(proof, str) and proof.strip() for proof in proof_types
        ):
            raise PWQError("eligible signer proof_types must be a non-empty string list")
        signer_ids.add(signer_id)
        signers.append({
            "signer_id": signer_id,
            "role": role,
            "actors": list(dict.fromkeys(actor.strip() for actor in actors)),
            "proof_types": list(dict.fromkeys(proof.strip() for proof in proof_types)),
        })
    try:
        threshold = int(raw.get("threshold", 1))
    except (TypeError, ValueError) as exc:
        raise PWQError("approval threshold must be an integer") from exc
    if threshold < 1 or threshold > len(signers):
        raise PWQError("approval threshold must fit the eligible signer set")
    required_roles = raw.get("required_roles") or []
    if not isinstance(required_roles, list) or not all(
        isinstance(role, str) and role.strip() for role in required_roles
    ):
        raise PWQError("required_roles must be a string list")
    required_roles = list(dict.fromkeys(role.strip() for role in required_roles))
    eligible_roles = {signer["role"] for signer in signers}
    if not set(required_roles).issubset(eligible_roles):
        raise PWQError("required approval roles must have eligible signers")
    if len(required_roles) > threshold:
        raise PWQError("approval threshold cannot be lower than required role count")
    if raw.get("distinct_signers", True) is not True:
        raise PWQError("role_threshold_v1 requires distinct signers")
    return {
        "scheme": APPROVAL_SCHEME,
        "threshold": threshold,
        "required_roles": required_roles,
        "distinct_signers": True,
        "eligible_signers": signers,
    }


def _proposal_fields(item):
    options = item.get("options") or []
    if not isinstance(options, list) or not all(
        isinstance(option, dict)
        and isinstance(option.get("label"), str)
        and isinstance(option.get("desc", ""), str)
        for option in options
    ):
        raise PWQError("options must be objects with label and desc")
    negotiation = item.get("negotiation_log") or []
    if not isinstance(negotiation, list):
        raise PWQError("negotiation_log must be a list")
    work_class = str(item.get("work_class", "general")).strip().lower()
    if work_class not in WORK_CLASSES:
        raise PWQError("work_class must be general or build")
    raw_refs = item.get("governance_refs") or {}
    if not isinstance(raw_refs, dict):
        raise PWQError("governance_refs must be an object")
    atlas_slices = raw_refs.get("atlas_slices") or []
    invariants = raw_refs.get("invariants") or []
    if not isinstance(atlas_slices, list) or not isinstance(invariants, list):
        raise PWQError("governance_refs lists are required")
    if not all(isinstance(value, str) and value.strip() for value in atlas_slices + invariants):
        raise PWQError("governance references must be non-empty strings")
    governance_refs = {
        "atlas_slices": list(dict.fromkeys(value.strip() for value in atlas_slices)),
        "invariants": list(dict.fromkeys(value.strip() for value in invariants)),
    }
    # Documentation references are descriptive metadata, not execution scope.
    authorization_scope = item.get("authorization_scope") or {}
    if not isinstance(authorization_scope, dict):
        raise PWQError("authorization_scope must be an object")
    try:
        json.dumps(authorization_scope, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise PWQError("authorization_scope must be JSON serializable") from exc
    return {
        "title": str(item.get("title", "")),
        "ask": str(item.get("ask", "")),
        "proposed_shape": str(item.get("proposed_shape", "")),
        "options": options,
        "selected_option": item.get("selected_option"),
        "user_input": str(item.get("user_input", "")),
        "alarm": item.get("alarm"),
        "negotiation_log": negotiation,
        "created": item.get("created") or time.strftime("%Y-%m-%d %H:%M:%S"),
        "work_class": work_class,
        "governance_refs": governance_refs,
        "approval_policy": _normalise_approval_policy(item.get("approval_policy")),
        "authorization_scope": authorization_scope,
    }


def _proposal_digest(proposal_id, proposal_version, item):
    proposal = _proposal_fields(item)
    value = {
        "proposal_id": proposal_id,
        "proposal_version": int(proposal_version),
        "proposal": proposal,
    }
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _approval_summary(item):
    policy = item.get("approval_policy") or _default_approval_policy()
    signatures = item.get("approval_signatures") or []
    distinct = {signature.get("signer_id") for signature in signatures}
    roles = {signature.get("role") for signature in signatures}
    required = set(policy.get("required_roles") or [])
    ready = (
        len(distinct) >= int(policy.get("threshold", 1))
        and required.issubset(roles)
    )
    if item.get("legacy_approval") and item.get("dispatch_authorization"):
        ready = True
    return {
        "scheme": policy.get("scheme", APPROVAL_SCHEME),
        "collected": len(distinct),
        "threshold": int(policy.get("threshold", 1)),
        "roles_collected": sorted(role for role in roles if role),
        "required_roles": list(policy.get("required_roles") or []),
        "required_roles_satisfied": required.issubset(roles),
        "ready": ready,
        "legacy": bool(item.get("legacy_approval")),
    }


def _authorization_evidence_digest(proposal_digest, signatures):
    evidence = {
        "proposal_digest": proposal_digest,
        "attestation_ids": sorted(signature["attestation_id"] for signature in signatures),
    }
    return hashlib.sha256(_canonical(evidence).encode("utf-8")).hexdigest()


def _tracking_fields(payload, current):
    if not isinstance(payload, dict):
        raise PWQError("tracking payload must be an object")
    required = (
        "target", "bounded_claim",
        "evidence_open_gaps", "boundaries", "next_trigger",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise PWQError("tracking update is missing: %s" % ", ".join(missing))
    tracking = {
        "target": str(payload["target"]).strip(),
        "atlas_slice": str(payload.get("atlas_slice", "")).strip(),
        "bounded_claim": str(payload["bounded_claim"]).strip(),
        "invariants": payload.get("invariants", []),
        "evidence_open_gaps": str(payload["evidence_open_gaps"]).strip(),
        "boundaries": str(payload["boundaries"]).strip(),
        "next_trigger": str(payload["next_trigger"]).strip(),
        "source_revision": str(payload.get("source_revision", "")).strip(),
    }
    if any(not tracking[field] for field in (
        "target", "bounded_claim", "evidence_open_gaps", "boundaries", "next_trigger"
    )):
        raise PWQError("tracking text fields cannot be empty")
    if not isinstance(tracking["invariants"], list) or not all(
        isinstance(value, str) and value.strip() for value in tracking["invariants"]
    ):
        raise PWQError("tracking invariants must be a non-empty string list")
    tracking["invariants"] = list(dict.fromkeys(value.strip() for value in tracking["invariants"]))
    # Progress reporting cannot expand authorization_scope or grant consent.
    # Labels may change without renegotiating the approved work.
    return tracking


class PWQStore:
    def __init__(self, runtime_dir, projection_path=None):
        self.runtime_dir = Path(runtime_dir)
        self.events_path = self.runtime_dir / "events.jsonl"
        self.lock_path = self.runtime_dir / "writer.lock"
        self.projection_path = Path(projection_path) if projection_path else self.runtime_dir.parent / "pwq.json"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def _locked(self):
        handle = self.lock_path.open("a+")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle

    def _events(self, repair_tail=False):
        self._last_ledger_tail_incomplete = False
        self._last_ledger_tail_hash = None
        if not self.events_path.exists():
            return []
        events = []
        previous_hash = "GENESIS"
        raw = self.events_path.read_bytes()
        ended_with_newline = raw.endswith(b"\n")
        lines = raw.split(b"\n")
        if ended_with_newline:
            lines = lines[:-1]
        for index, raw_line in enumerate(lines):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                if index == len(lines) - 1 and not ended_with_newline:
                    self._last_ledger_tail_incomplete = True
                    self._last_ledger_tail_hash = hashlib.sha256(raw_line).hexdigest()
                    break
                raise PWQError("PWQ ledger corruption at line %d" % (index + 1)) from exc
            supplied_hash = event.pop("event_hash", None)
            actual_hash = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
            if supplied_hash != actual_hash or event.get("previous_hash") != previous_hash:
                raise PWQError("PWQ ledger hash chain mismatch at sequence %s" % event.get("sequence"))
            event["event_hash"] = supplied_hash
            events.append(event)
            previous_hash = supplied_hash
        if repair_tail and (self._last_ledger_tail_incomplete or not ended_with_newline):
            canonical_ledger = "".join(_canonical(event) + "\n" for event in events)
            _atomic_text(self.events_path, canonical_ledger)
        return events

    @staticmethod
    def _build_event(events, kind, proposal_id, actor, payload,
                     proposal_version=None, event_id=None):
        previous_hash = events[-1]["event_hash"] if events else "GENESIS"
        event = {
            "schema_version": SCHEMA_VERSION,
            "sequence": len(events) + 1,
            "event_id": str(event_id or uuid.uuid4()),
            "proposal_id": proposal_id,
            "proposal_version": proposal_version,
            "actor": actor,
            "kind": kind,
            "at": time.time(),
            "payload": payload or {},
            "previous_event_id": events[-1]["event_id"] if events else None,
            "previous_hash": previous_hash,
        }
        event["event_hash"] = hashlib.sha256(_canonical(event).encode("utf-8")).hexdigest()
        return event

    def _append_event_line(self, event):
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(event) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(self.events_path.parent)

    def _append(self, kind, proposal_id, actor, payload, proposal_version=None,
                event_id=None):
        events = self._events(repair_tail=True)
        if self._last_ledger_tail_incomplete:
            recovery = self._build_event(
                events, "ledger_tail_recovered", "__pwq_ledger__", "platform.recovery",
                {
                    "discarded_tail_sha256": self._last_ledger_tail_hash,
                    "recovered_event_count": len(events),
                },
            )
            self._append_event_line(recovery)
            events.append(recovery)
        event = self._build_event(
            events, kind, proposal_id, actor, payload, proposal_version, event_id
        )
        self._append_event_line(event)
        return event

    def _materialize(self, events=None):
        events = events if events is not None else self._events()
        proposals = {}
        order = []
        for event in events:
            proposal_id = event["proposal_id"]
            kind = event["kind"]
            payload = event.get("payload") or {}
            if kind == "ledger_tail_recovered":
                continue
            if kind == "proposed":
                if proposal_id in proposals:
                    raise PWQError("duplicate proposed event for %s" % proposal_id)
                proposals[proposal_id] = {
                    "id": proposal_id,
                    **payload["proposal"],
                    "status": "proposed",
                    "proposal_version": 1,
                    "dispatch_authorization": None,
                    "authorization_evidence_digest": None,
                    "approval_signatures": [],
                    "legacy_approval": False,
                    "last_event_id": event["event_id"],
                    "updated_at": event["at"],
                    "tracking": None,
                    "tracking_sequence": 0,
                }
                proposals[proposal_id]["proposal_digest"] = _proposal_digest(
                    proposal_id, 1, proposals[proposal_id]
                )
                order.append(proposal_id)
                continue
            current = proposals.get(proposal_id)
            if not current:
                raise PWQError("event for unknown proposal: %s" % proposal_id)
            if event.get("proposal_version") not in (None, current["proposal_version"]):
                raise PWQError("stale proposal version in ledger for %s" % proposal_id)
            if kind == "modified":
                current.update(payload.get("changes") or {})
                current["proposal_version"] += 1
                current["status"] = "modified"
                current.pop("paused_from", None)
                current["dispatch_authorization"] = None
                current["authorization_evidence_digest"] = None
                current["approval_signatures"] = []
                current["legacy_approval"] = False
                current["tracking"] = None
                current["proposal_digest"] = _proposal_digest(
                    proposal_id, current["proposal_version"], current
                )
            elif kind == "approval_signed":
                attestation = payload.get("attestation") or {}
                if attestation.get("proposal_digest") != current.get("proposal_digest"):
                    raise PWQError("approval attestation does not bind the current proposal digest")
                if any(
                    signature.get("signer_id") == attestation.get("signer_id")
                    for signature in current.get("approval_signatures", [])
                ):
                    raise PWQError("approval signer is duplicated in the ledger")
                current.setdefault("approval_signatures", []).append(attestation)
                summary = _approval_summary(current)
                supplied_authorization = payload.get("dispatch_authorization")
                if summary["ready"]:
                    if not supplied_authorization:
                        raise PWQError("threshold approval event is missing dispatch authorization")
                    expected_evidence = _authorization_evidence_digest(
                        current["proposal_digest"], current["approval_signatures"]
                    )
                    if payload.get("authorization_evidence_digest") != expected_evidence:
                        raise PWQError("threshold approval evidence digest mismatch")
                    current["status"] = "approved"
                    current["dispatch_authorization"] = supplied_authorization
                    current["authorization_evidence_digest"] = expected_evidence
                elif supplied_authorization:
                    raise PWQError("dispatch authorization was minted before threshold approval")
            elif kind == "approved":
                # Replay compatibility for the pre-threshold PWQ v1 ledger.
                current["status"] = "approved"
                current["dispatch_authorization"] = payload["dispatch_authorization"]
                current["legacy_approval"] = True
            elif kind == "rejected":
                current["status"] = "rejected"
                current.pop("paused_from", None)
                current["dispatch_authorization"] = None
            elif kind == "superseded":
                current["status"] = "superseded"
                current["dispatch_authorization"] = None
                current["authorization_evidence_digest"] = None
                current["superseded_by"] = payload["replacement_proposal_id"]
            elif kind == "started":
                if payload.get("dispatch_authorization") != current.get("dispatch_authorization"):
                    raise PWQError("invalid dispatch authorization for %s" % proposal_id)
                current["status"] = "in_progress"
                current.pop("paused_from", None)
            elif kind == "paused":
                current["paused_from"] = current["status"]
                current["status"] = "paused"
            elif kind == "resumed":
                if payload.get("dispatch_authorization") != current.get("dispatch_authorization"):
                    raise PWQError("invalid resume authorization for %s" % proposal_id)
                resume_status = current.pop("paused_from", "in_progress")
                if resume_status not in ("approved", "in_progress"):
                    raise PWQError("invalid paused origin for %s" % proposal_id)
                current["status"] = resume_status
            elif kind == "completed":
                current["status"] = "completed"
            elif kind == "archived":
                current["archived_from"] = payload["previous_status"]
                if payload.get("paused_from") is not None:
                    current["archived_paused_from"] = payload["paused_from"]
                current["status"] = "archived"
            elif kind == "unarchived":
                restored = payload["previous_status"]
                if restored != current.get("archived_from"):
                    raise PWQError("archive restore does not match the recorded prior status")
                current["status"] = restored
                if restored == "paused" and current.get("archived_paused_from"):
                    current["paused_from"] = current["archived_paused_from"]
                current.pop("archived_from", None)
                current.pop("archived_paused_from", None)
            elif kind == "reordered":
                if proposal_id in order:
                    order.remove(proposal_id)
                position = max(0, min(int(payload.get("position", len(order))), len(order)))
                order.insert(position, proposal_id)
            elif kind == "tracking_updated":
                current["tracking_sequence"] = int(current.get("tracking_sequence", 0)) + 1
                current["tracking"] = {
                    **payload["tracking"],
                    "actor": event["actor"],
                    "at": event["at"],
                    "event_id": event["event_id"],
                    "sequence": current["tracking_sequence"],
                }
            else:
                raise PWQError("unknown event kind: %s" % kind)
            current["last_event_id"] = event["event_id"]
            current["updated_at"] = event["at"]

        items = []
        for proposal_id in order:
            item = dict(proposals[proposal_id])
            item["approval_status"] = _approval_summary(item)
            item["orders_given"] = item["status"] in ("approved", "in_progress")
            items.append(item)
        return {
            "version": 3,
            "protocol": "pwq_v2",
            "sequence": len(events),
            "items": items,
        }

    def read(self):
        with self._locked() as lock_handle:
            try:
                if not self.events_path.exists() and self.projection_path.exists():
                    legacy = json.loads(self.projection_path.read_text(encoding="utf-8"))
                    self._sync_locked(legacy, actor="migration")
                board = self._materialize()
                _atomic_json(self.projection_path, board)
                return board
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _command_locked(self, kind, proposal_id, actor, payload=None,
                        expected_version=None, command_id=None):
        event_kind = {
            "propose": "proposed", "modify": "modified",
            "approve": "approval_signed", "sign": "approval_signed",
            "reject": "rejected", "start": "started", "pause": "paused",
            "resume": "resumed", "complete": "completed", "reorder": "reordered",
            "archive": "archived", "restore": "unarchived",
            "track": "tracking_updated", "supersede": "superseded",
        }.get(kind)
        if command_id:
            existing = next(
                (event for event in self._events() if event["event_id"] == command_id),
                None,
            )
            if existing:
                if existing["proposal_id"] != proposal_id or existing["kind"] != event_kind:
                    raise PWQError("command_id was already used for a different command")
                return self._materialize()
        if kind in HUMAN_DECISIONS and actor not in TRUSTED_HUMAN_ACTORS:
            raise PWQError("%s is a human decision and cannot be issued by %s" % (kind, actor))
        board = self._materialize()
        current = next((item for item in board["items"] if item["id"] == proposal_id), None)
        if kind == "propose":
            if current:
                raise PWQError("proposal already exists: %s" % proposal_id)
            self._append(
                "proposed", proposal_id, actor,
                {"proposal": _proposal_fields(payload or {})}, 1,
                event_id=command_id,
            )
        else:
            if not current:
                raise PWQError("unknown proposal: %s" % proposal_id)
            version = current["proposal_version"]
            if expected_version is not None and int(expected_version) != version:
                raise PWQError("stale proposal version: expected %s, current %s" % (expected_version, version))
            status = current["status"]
            if kind == "modify":
                if status in TERMINAL:
                    raise PWQError("cannot modify terminal proposal")
                if status == "in_progress":
                    raise PWQError("in-progress work must be paused before modification")
                changes = _proposal_fields({**current, **(payload or {})})
                self._append(
                    "modified", proposal_id, actor, {"changes": changes}, version,
                    event_id=command_id,
                )
            elif kind in ("approve", "sign"):
                if kind == "approve" and actor not in TRUSTED_HUMAN_ACTORS:
                    raise PWQError("approve is a human decision and cannot be issued by %s" % actor)
                if status not in ("proposed", "modified"):
                    raise PWQError("cannot sign approval from %s" % status)
                supplied = payload or {}
                signer_id = str(supplied.get("signer_id") or "human:owner").strip()
                role = str(supplied.get("role") or "human_owner").strip()
                policy = current.get("approval_policy") or _default_approval_policy()
                eligible = next(
                    (entry for entry in policy["eligible_signers"]
                     if entry["signer_id"] == signer_id and entry["role"] == role),
                    None,
                )
                if not eligible:
                    raise PWQError("signer and role are not eligible for this proposal")
                if actor not in eligible["actors"]:
                    raise PWQError("actor cannot attest for signer role %s" % role)
                if any(
                    signature.get("signer_id") == signer_id
                    for signature in current.get("approval_signatures", [])
                ):
                    raise PWQError("signer has already attested to this proposal version")
                proof = supplied.get("proof") or {}
                if not isinstance(proof, dict):
                    raise PWQError("approval proof must be an object")
                proof_type = str(proof.get("type") or (
                    LOCAL_HUMAN_PROOF if actor in TRUSTED_HUMAN_ACTORS else ""
                )).strip()
                if proof_type not in eligible["proof_types"]:
                    raise PWQError("proof type is not allowed for this signer")
                if proof_type == LOCAL_HUMAN_PROOF and actor not in TRUSTED_HUMAN_ACTORS:
                    raise PWQError("local human proof requires the trusted human boundary")
                if proof_type == HOTLOAD_GUARDIAN_PROOF and actor != "platform.hotload_guardian":
                    raise PWQError("hot-load validation proof requires the platform guardian")
                if proof_type not in (LOCAL_HUMAN_PROOF, HOTLOAD_GUARDIAN_PROOF):
                    raise PWQError("proof verifier is not installed for %s" % proof_type)
                proof_value = str(proof.get("value") or uuid.uuid4()).strip()
                attestation = {
                    "attestation_id": str(uuid.uuid4()),
                    "signer_id": signer_id,
                    "role": role,
                    "actor": actor,
                    "decision": "approve",
                    "proposal_digest": current["proposal_digest"],
                    "proof": {"type": proof_type, "value": proof_value},
                }
                prospective = {
                    **current,
                    "approval_signatures": [
                        *(current.get("approval_signatures") or []), attestation,
                    ],
                }
                ready = _approval_summary(prospective)["ready"]
                token = str(uuid.uuid4()) if ready else None
                evidence_digest = (
                    _authorization_evidence_digest(
                        current["proposal_digest"], prospective["approval_signatures"]
                    )
                    if ready else None
                )
                self._append(
                    "approval_signed", proposal_id, actor,
                    {
                        "attestation": attestation,
                        "dispatch_authorization": token,
                        "authorization_evidence_digest": evidence_digest,
                    }, version,
                    event_id=command_id,
                )
            elif kind == "reject":
                if status in TERMINAL:
                    raise PWQError("proposal is already terminal")
                if status == "in_progress":
                    raise PWQError("in-progress work must be paused before rejection")
                self._append(
                    "rejected", proposal_id, actor, payload or {}, version,
                    event_id=command_id,
                )
            elif kind == "supersede":
                if actor != "platform.hotload_guardian":
                    raise PWQError("only the runtime guardian can supersede a hot-load proposal")
                if status in TERMINAL:
                    raise PWQError("proposal is already terminal")
                if status == "in_progress":
                    raise PWQError("dispatched work must be paused or rolled back before supersession")
                replacement = str((payload or {}).get("replacement_proposal_id") or "").strip()
                if not replacement:
                    raise PWQError("supersession requires a replacement proposal id")
                self._append(
                    "superseded", proposal_id, actor,
                    {"replacement_proposal_id": replacement}, version,
                    event_id=command_id,
                )
            elif kind == "start":
                if status != "approved":
                    raise PWQError("proposal must be approved before dispatch")
                token = (payload or {}).get("dispatch_authorization")
                if token != current.get("dispatch_authorization"):
                    raise PWQError("valid current dispatch_authorization is required")
                self._append(
                    "started", proposal_id, actor,
                    {"dispatch_authorization": token}, version,
                    event_id=command_id,
                )
            elif kind == "pause":
                if status not in ("approved", "in_progress"):
                    raise PWQError("cannot pause from %s" % status)
                self._append(
                    "paused", proposal_id, actor, payload or {}, version,
                    event_id=command_id,
                )
            elif kind == "resume":
                if status != "paused":
                    raise PWQError("cannot resume from %s" % status)
                token = (payload or {}).get("dispatch_authorization")
                if token != current.get("dispatch_authorization"):
                    raise PWQError("valid current dispatch_authorization is required")
                self._append(
                    "resumed", proposal_id, actor,
                    {"dispatch_authorization": token}, version,
                    event_id=command_id,
                )
            elif kind == "complete":
                if status not in ("approved", "in_progress", "paused"):
                    raise PWQError("cannot complete from %s" % status)
                self._append(
                    "completed", proposal_id, actor, payload or {}, version,
                    event_id=command_id,
                )
            elif kind == "archive":
                if status not in ("proposed", "modified", "paused"):
                    raise PWQError("only waiting proposals can be archived")
                prior_pause = current.get("paused_from") if status == "paused" else None
                self._append(
                    "archived", proposal_id, actor,
                    {"previous_status": status, "paused_from": prior_pause},
                    version, event_id=command_id,
                )
            elif kind == "restore":
                if status != "archived":
                    raise PWQError("only archived proposals can be restored")
                previous = current.get("archived_from")
                if previous not in ("proposed", "modified", "paused"):
                    raise PWQError("archived proposal has no valid prior waiting status")
                self._append(
                    "unarchived", proposal_id, actor,
                    {"previous_status": previous}, version, event_id=command_id,
                )
            elif kind == "reorder":
                self._append(
                    "reordered", proposal_id, actor,
                    {"position": int((payload or {}).get("position", 0))}, version,
                    event_id=command_id,
                )
            elif kind == "track":
                if status not in ("in_progress", "paused"):
                    raise PWQError("tracking requires dispatched or paused work")
                tracking = _tracking_fields(payload or {}, current)
                self._append(
                    "tracking_updated", proposal_id, actor,
                    {"tracking": tracking}, version,
                    event_id=command_id,
                )
            else:
                raise PWQError("unknown command: %s" % kind)
        board = self._materialize()
        _atomic_json(self.projection_path, board)
        return board

    def command(self, kind, proposal_id, actor="iter", payload=None,
                expected_version=None, command_id=None):
        if not isinstance(proposal_id, str) or not proposal_id:
            raise PWQError("proposal_id is required")
        with self._locked() as lock_handle:
            try:
                return self._command_locked(
                    kind, proposal_id, actor, payload, expected_version, command_id
                )
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _sync_locked(self, incoming, actor="human"):
        if not isinstance(incoming, dict) or not isinstance(incoming.get("items"), list):
            raise PWQError("board payload must contain items")
        board = self._materialize()
        current_by_id = {item["id"]: item for item in board["items"]}
        incoming_ids = []
        for position, raw in enumerate(incoming["items"]):
            proposal_id = raw.get("id")
            if not isinstance(proposal_id, str) or not proposal_id:
                raise PWQError("every proposal requires a non-empty id")
            incoming_ids.append(proposal_id)
            target_status = _normalise_status(raw)
            current = current_by_id.get(proposal_id)
            if not current:
                self._command_locked("propose", proposal_id, actor, raw)
                current = next(item for item in self._materialize()["items"] if item["id"] == proposal_id)
            target_fields = _proposal_fields(raw)
            changes = {key: value for key, value in target_fields.items() if current.get(key) != value}
            if changes:
                self._command_locked("modify", proposal_id, actor, changes, current["proposal_version"])
                current = next(item for item in self._materialize()["items"] if item["id"] == proposal_id)
            if target_status == "modified" and current["status"] == "proposed" and not changes:
                self._command_locked("modify", proposal_id, actor, {}, current["proposal_version"])
            elif target_status == "approved" and current["status"] != "approved":
                self._command_locked("approve", proposal_id, actor, {}, current["proposal_version"])
            elif target_status == "in_progress" and current["status"] != "in_progress":
                if current["status"] != "approved":
                    self._command_locked("approve", proposal_id, actor, {}, current["proposal_version"])
                    current = next(item for item in self._materialize()["items"] if item["id"] == proposal_id)
                self._command_locked(
                    "start", proposal_id, actor,
                    {"dispatch_authorization": current["dispatch_authorization"]},
                    current["proposal_version"],
                )
            elif target_status == "rejected" and current["status"] != "rejected":
                self._command_locked("reject", proposal_id, actor, {}, current["proposal_version"])
            elif target_status == "completed" and current["status"] != "completed":
                if current["status"] in ("proposed", "modified"):
                    self._command_locked("approve", proposal_id, actor, {}, current["proposal_version"])
                    current = next(item for item in self._materialize()["items"] if item["id"] == proposal_id)
                self._command_locked("complete", proposal_id, actor, {}, current["proposal_version"])
            elif target_status == "paused" and current["status"] != "paused":
                if current["status"] in ("proposed", "modified"):
                    self._command_locked("approve", proposal_id, actor, {}, current["proposal_version"])
                    current = next(item for item in self._materialize()["items"] if item["id"] == proposal_id)
                self._command_locked("pause", proposal_id, actor, {}, current["proposal_version"])

            materialized = self._materialize()
            actual_position = next(i for i, item in enumerate(materialized["items"]) if item["id"] == proposal_id)
            if actual_position != position:
                latest = next(item for item in materialized["items"] if item["id"] == proposal_id)
                self._command_locked("reorder", proposal_id, actor, {"position": position}, latest["proposal_version"])

        board = self._materialize()
        _atomic_json(self.projection_path, board)
        return board

    def sync_board(self, incoming, actor="human"):
        with self._locked() as lock_handle:
            try:
                return self._sync_locked(incoming, actor)
            finally:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
