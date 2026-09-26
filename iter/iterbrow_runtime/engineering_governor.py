"""Constitutional adapter for the AtomSpace-native engineering governor.

The module is intentionally small. It validates a fixed input schema, writes
one durable ``engineering-work`` atom, submits ``engineering-next`` to the
authoritative Hyperon snapshot, and persists the exact native conclusion with
the evaluated commit identity. Active mode exposes one fixed, read-only action
and records only mechanical process observations. MeTTa owns test meaning,
comparison, outcome, Tracking, and PLN/NACE evidence revision.
"""

import hashlib
import re
import subprocess
import sys
import uuid
from pathlib import Path

from iterbrow_runtime.cognitive_events import (
    _call_atomspace,
    commit_batch,
    commit_event,
    metta_string,
)


ROOT = Path(__file__).resolve().parents[2]
ACTION_REGISTRY = {
    "qa.pwq_board_boundary": (
        sys.executable,
        str(ROOT / "tests" / "test_pwq_board_boundary.py"),
    ),
}


TEXT_FIELDS = (
    "work_id", "parent_id", "intention", "invariants", "current_state",
    "unresolved_gap", "selected_alternative", "counter_alternative",
    "predicted_effects", "risks", "test_obligations",
    "recovery_obligations", "authorization_ref", "observation",
)

ENUM_FIELDS = {
    "authorization": {"pending", "authorized"},
    "action_status": {"pending", "completed", "failed"},
    "test_result": {"pending", "passed", "failed"},
    "comparison": {"pending", "matched", "mismatched", "unknown"},
    "recovery_state": {"ready", "unavailable"},
    "execution_mode": {"active", "shadow"},
}

NATIVE_DECISIONS = {
    "request_authorization", "shadow_action_ready", "active_action_ready",
    "accept", "iterate", "rollback", "escalate",
}

_DECISION_RE = re.compile(
    r"\(engineering-decision\s+\"([^\"]+)\"\s+"
    r"([a-z_]+)\s+\"([^\"]+)\"\)"
)
_EVIDENCE_RE = re.compile(
    r"\(engineering-evidence-revision\s+\"([^\"]+)\"\s+"
    r"\"([^\"]+)\"\s+(positive|incomplete|negative|unavailable)\s+"
    r"\(stv\s+([-+\d.eE]+)\s+([-+\d.eE]+)\)\)"
)


def _normalise(work):
    if not isinstance(work, dict):
        raise ValueError("engineering work must be an object")
    expected = set(TEXT_FIELDS) | set(ENUM_FIELDS)
    missing = sorted(expected - set(work))
    extra = sorted(set(work) - expected)
    if missing:
        raise ValueError("engineering work is missing: %s" % ", ".join(missing))
    if extra:
        raise ValueError("engineering work has unknown fields: %s" % ", ".join(extra))
    result = {}
    for field in TEXT_FIELDS:
        value = str(work[field]).strip()
        if not value:
            raise ValueError("engineering work %s cannot be empty" % field)
        result[field] = value
    if result["selected_alternative"] == result["counter_alternative"]:
        raise ValueError("engineering work requires a distinct counter-alternative")
    for field, allowed in ENUM_FIELDS.items():
        value = str(work[field]).strip().lower()
        if value not in allowed:
            raise ValueError(
                "engineering work %s must be one of: %s"
                % (field, ", ".join(sorted(allowed)))
            )
        result[field] = value
    if result["authorization"] == "pending" and result["authorization_ref"] != "none":
        raise ValueError("pending work must use authorization_ref=none")
    if result["authorization"] == "authorized" and result["authorization_ref"] == "none":
        raise ValueError("authorized work requires a PWQ-bound authorization_ref")
    if result["execution_mode"] == "active":
        if result["authorization"] != "authorized":
            raise ValueError("active work requires authorization=authorized")
        if not result["authorization_ref"].startswith("pwq:"):
            raise ValueError("active work requires a PWQ-bound authorization_ref")
    return result


def work_atom(work):
    work = _normalise(work)
    quote = metta_string
    observation = "none" if work["observation"] == "none" else quote(work["observation"])
    return " ".join((
        "(engineering-work", quote(work["work_id"]),
        "(parent %s)" % quote(work["parent_id"]),
        "(intention %s)" % quote(work["intention"]),
        "(invariants %s)" % quote(work["invariants"]),
        "(current-state %s)" % quote(work["current_state"]),
        "(unresolved-gap %s)" % quote(work["unresolved_gap"]),
        "(alternatives %s %s)" % (
            quote(work["selected_alternative"]),
            quote(work["counter_alternative"]),
        ),
        "(selected %s)" % quote(work["selected_alternative"]),
        "(predicted-effects %s)" % quote(work["predicted_effects"]),
        "(risks %s)" % quote(work["risks"]),
        "(test-obligations %s)" % quote(work["test_obligations"]),
        "(recovery-obligations %s)" % quote(work["recovery_obligations"]),
        "(authorization %s %s)" % (
            work["authorization"], quote(work["authorization_ref"]),
        ),
        "(action %s)" % work["action_status"],
        "(observation %s)" % observation,
        "(test-result %s)" % work["test_result"],
        "(comparison %s)" % work["comparison"],
        "(recovery-state %s)" % work["recovery_state"],
        "(execution-mode %s))" % work["execution_mode"],
    ))


def control_atom(work):
    """Return the compact ground control record committed with the full work."""
    work = _normalise(work)
    observation_state = "none" if work["observation"] == "none" else "observed"
    return " ".join((
        "(engineering-control-record", metta_string(work["work_id"]),
        metta_string(work["selected_alternative"]), work["authorization"],
        work["action_status"], observation_state, work["test_result"],
        work["comparison"], work["recovery_state"], work["execution_mode"] + ")",
    ))


def metadata_atom(work):
    """Return a work-keyed projection equation without semantic conclusions."""
    work = _normalise(work)
    return " ".join((
        "(= (engineering-metadata", metta_string(work["work_id"]), ")",
        "(work-metadata", metta_string(work["intention"]),
        metta_string(work["unresolved_gap"]),
        metta_string(work["selected_alternative"]), "))",
    ))


def context_id(work):
    """Return the stable identity of one authorized active-work capsule."""
    work = _normalise(work)
    authority = hashlib.sha256(
        work["authorization_ref"].encode("utf-8")
    ).hexdigest()
    return "engineering-context:%s:%s" % (work["work_id"], authority)


def record_work(work, actor="iter", transaction_id=None,
                commit_batch_fn=commit_batch):
    """Commit full work, ground control, and metadata in one transaction."""
    normalised = _normalise(work)
    event_id = str(uuid.uuid4())
    return commit_batch_fn(
        [{
            "event_id": event_id,
            "domain": "engineering_work",
            "entity_id": normalised["work_id"],
            "event_type": "work_recorded",
            "payload": {"work": normalised},
        }],
        state_atoms={
            "engineering_work:%s" % normalised["work_id"]: work_atom(normalised),
            "engineering_control:%s" % normalised["work_id"]: control_atom(normalised),
            "engineering_metadata:%s" % normalised["work_id"]: metadata_atom(normalised),
        },
        actor=actor,
        source="engineering_governor.%s" % normalised["execution_mode"],
        transaction_id=transaction_id or (
            "engineering-work:%s:%s" % (normalised["work_id"], uuid.uuid4())
        ),
    )


def _extract_native_decision(work_id, raw_result):
    matches = _DECISION_RE.findall(str(raw_result))
    if len(matches) != 1:
        raise RuntimeError(
            "native governor must return exactly one engineering-decision; got %d"
            % len(matches)
        )
    returned_work, decision, selected = matches[0]
    if returned_work != work_id:
        raise RuntimeError("native governor returned a decision for another work unit")
    if decision not in NATIVE_DECISIONS:
        raise RuntimeError("native governor returned an unknown decision: %s" % decision)
    return decision, selected


def load_recorded_work(work_id, through_commit=None, call_fn=_call_atomspace):
    """Load the latest authoritative work event visible to one evaluation."""
    work_id = str(work_id).strip()
    if not work_id:
        raise ValueError("work_id cannot be empty")
    status = call_fn("status")
    current_commit = int((status or {}).get("commit", 0))
    if through_commit is not None:
        through_commit = int(through_commit)
        if through_commit < 0:
            raise ValueError("through_commit cannot be negative")
        if through_commit > current_commit:
            raise RuntimeError(
                "authoritative work snapshot is ahead of the AtomSpace"
            )
        current_commit = through_commit
    after = 0
    recorded = None
    recorded_commit = -1
    while after < current_commit:
        page = call_fn("subscribe", after_commit=after, limit=1000)
        transactions = list((page or {}).get("events") or [])
        if not transactions:
            break
        for transaction in transactions:
            transaction_commit = int(transaction.get("commit", 0))
            if transaction_commit > current_commit:
                continue
            for event in (transaction.get("metadata") or {}).get(
                    "domain_events", []):
                if (event.get("domain") != "engineering_work"
                        or event.get("event_type") != "work_recorded"
                        or str(event.get("entity_id", "")) != work_id):
                    continue
                candidate = (event.get("payload") or {}).get("work")
                if isinstance(candidate, dict) and transaction_commit >= recorded_commit:
                    recorded = candidate
                    recorded_commit = transaction_commit
        next_after = max(int(item.get("commit", 0)) for item in transactions)
        if next_after <= after:
            break
        after = next_after
    if recorded is None:
        raise RuntimeError("authoritative engineering work event is missing")
    normalised = _normalise(recorded)
    if normalised["work_id"] != work_id:
        raise RuntimeError("authoritative engineering work identity is inconsistent")
    return normalised


def _shadow_query(function_name, work):
    """Build a native call around exact ground work/control capsules."""
    normalised = _normalise(work)
    control = control_atom(normalised)
    if function_name == "engineering-shadow-next":
        return "!(%s %s)" % (function_name, control)
    if function_name == "engineering-shadow-tracking":
        return "!(%s %s %s)" % (
            function_name, work_atom(normalised), control,
        )
    raise ValueError("unknown engineering shadow function")


def evaluate_shadow(work_id, query_fn=None, commit_fn=commit_event,
                    transaction_id=None, work_loader_fn=None):
    """Evaluate and durably bind one native decision; never dispatch an action."""
    work_id = str(work_id).strip()
    if not work_id:
        raise ValueError("work_id cannot be empty")
    if query_fn is None:
        from iterbrow_runtime import engineering_query
        query_fn = engineering_query.run_query
    loader = work_loader_fn or load_recorded_work
    requested_work = _normalise(loader(work_id))
    if requested_work["work_id"] != work_id:
        raise RuntimeError("authoritative engineering work identity is inconsistent")
    requested_control = control_atom(requested_work)
    evaluated = query_fn(_shadow_query("engineering-shadow-next", requested_work))
    if not isinstance(evaluated, dict) or not evaluated.get("ok"):
        raise RuntimeError(
            "native governor unavailable: %s"
            % ((evaluated or {}).get("error") if isinstance(evaluated, dict) else evaluated)
        )
    for field in ("epoch", "commit", "state_hash"):
        if evaluated.get(field) in (None, ""):
            raise RuntimeError("native governor omitted evaluated %s" % field)
    decision, selected = _extract_native_decision(work_id, evaluated.get("result"))
    if decision == "active_action_ready":
        raise RuntimeError("shadow evaluation cannot authorize active dispatch")
    authoritative_work = _normalise(loader(
        work_id, through_commit=int(evaluated["commit"]),
    ))
    if authoritative_work["work_id"] != work_id:
        raise RuntimeError("authoritative engineering work identity is inconsistent")
    if control_atom(authoritative_work) != requested_control:
        raise RuntimeError(
            "authoritative engineering work changed during native evaluation"
        )
    if selected != authoritative_work["selected_alternative"]:
        raise RuntimeError(
            "native selected alternative does not match authoritative work"
        )
    decision_atom = " ".join((
        "(engineering-shadow-decision", metta_string(work_id), decision,
        metta_string(selected), metta_string(evaluated["epoch"]),
        str(int(evaluated["commit"])), metta_string(evaluated["state_hash"]), ")",
    ))
    committed = commit_fn(
        "engineering_decision",
        work_id,
        "shadow_decision",
        payload={
            "decision": decision,
            "selected_alternative": selected,
            "evaluated_epoch": evaluated["epoch"],
            "evaluated_commit": evaluated["commit"],
            "evaluated_state_hash": evaluated["state_hash"],
            "native_result": str(evaluated["result"]),
            "dispatch_authority": False,
        },
        state_atom=decision_atom,
        actor="iter",
        source="engineering_governor.shadow",
        transaction_id=transaction_id or (
            "engineering-decision:%s:%s:%s"
            % (work_id, evaluated["epoch"], evaluated["commit"])
        ),
    )
    return {
        "work_id": work_id,
        "decision": decision,
        "selected_alternative": selected,
        "evaluated_epoch": evaluated["epoch"],
        "evaluated_commit": evaluated["commit"],
        "evaluated_state_hash": evaluated["state_hash"],
        "decision_commit": committed.get("commit") if isinstance(committed, dict) else None,
        "dispatch_authority": False,
        "native_result": str(evaluated["result"]),
    }


def _snapshot_identity(value, label="snapshot"):
    if not isinstance(value, dict):
        raise ValueError("%s must be an object" % label)
    result = {}
    for field in ("epoch", "commit", "state_hash"):
        if value.get(field) in (None, ""):
            raise ValueError("%s requires %s" % (label, field))
        result[field] = int(value[field]) if field == "commit" else str(value[field])
    return result


def _require_exact_snapshot(evaluated, expected):
    actual = _snapshot_identity(evaluated, "native evaluation")
    expected = _snapshot_identity(expected, "expected snapshot")
    if actual != expected:
        raise RuntimeError(
            "native governor snapshot is stale: expected %s/%s/%s, got %s/%s/%s"
            % (
                expected["epoch"], expected["commit"], expected["state_hash"],
                actual["epoch"], actual["commit"], actual["state_hash"],
            )
        )
    return actual


def _action_fingerprint(action_key):
    argv = ACTION_REGISTRY[action_key]
    return hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()


def _run_fixed_action(action_key, timeout=120):
    """Run one registered argv directly. There is deliberately no shell path."""
    if action_key not in ACTION_REGISTRY:
        raise ValueError("unknown governed action: %s" % action_key)
    return subprocess.run(
        list(ACTION_REGISTRY[action_key]),
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
        timeout=timeout,
    )


def _as_bytes(value):
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8", errors="replace")


def _observation_atom(observation):
    return " ".join((
        "(engineering-observation", metta_string(observation["work_id"]),
        metta_string(observation["action_key"]), observation["process_state"],
        str(int(observation["exit_code"])),
        metta_string(observation["stdout_sha256"]),
        metta_string(observation["stderr_sha256"]),
        str(int(observation["output_bytes"])), ")",
    ))


def context_atom(work, observation):
    """Build one versioned ground capsule from work and raw process facts.

    The capsule is the higher-order reasoning boundary. It contains both the
    Atlas-scale claim and the exact observation, but no semantic conclusion.
    """
    work = _normalise(work)
    if work["execution_mode"] != "active":
        raise ValueError("engineering context requires execution_mode=active")
    if work["authorization"] != "authorized":
        raise ValueError("engineering context requires authorized work")
    if observation.get("work_id") != work["work_id"]:
        raise ValueError("engineering context observation belongs to another work unit")
    if observation.get("action_key") != work["selected_alternative"]:
        raise ValueError("engineering context observation belongs to another action")
    process_state = str(observation.get("process_state", "")).strip()
    if process_state not in {"exited", "spawn_failed"}:
        raise ValueError("engineering context has an unknown process state")
    try:
        exit_code = int(observation["exit_code"])
        output_bytes = int(observation["output_bytes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("engineering context requires numeric raw observations") from exc
    if output_bytes < 0:
        raise ValueError("engineering context output bytes cannot be negative")
    for field in ("stdout_sha256", "stderr_sha256"):
        value = str(observation.get(field, ""))
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("engineering context %s must be a SHA-256 digest" % field)

    quote = metta_string
    return " ".join((
        "(engineering-context-v1", quote(context_id(work)),
        "(identity %s %s)" % (
            quote(work["work_id"]), quote(work["parent_id"]),
        ),
        "(authorization authorized %s)" % quote(work["authorization_ref"]),
        "(claim %s %s %s %s)" % (
            quote(work["intention"]), quote(work["invariants"]),
            quote(work["current_state"]), quote(work["unresolved_gap"]),
        ),
        "(alternatives %s %s)" % (
            quote(work["selected_alternative"]),
            quote(work["counter_alternative"]),
        ),
        "(prediction %s %s)" % (
            quote(work["predicted_effects"]), quote(work["risks"]),
        ),
        "(obligations %s %s)" % (
            quote(work["test_obligations"]),
            quote(work["recovery_obligations"]),
        ),
        "(observation %s %s %s %s %s)" % (
            process_state, exit_code,
            quote(observation["stdout_sha256"]),
            quote(observation["stderr_sha256"]), output_bytes,
        ),
        "(recovery %s))" % work["recovery_state"],
    ))


def observation_state_atoms(observation):
    """Return the raw observation atom; no semantic result is encoded here."""
    return {
        "engineering_observation:%s" % observation["work_id"]: (
            _observation_atom(observation)
        ),
    }


def _extract_native_evidence(work_id, action_key, raw_result):
    matches = _EVIDENCE_RE.findall(str(raw_result))
    if len(matches) != 1:
        raise RuntimeError(
            "native governor must return exactly one evidence revision; got %d"
            % len(matches)
        )
    returned_work, returned_action, label, frequency, confidence = matches[0]
    if returned_work != work_id or returned_action != action_key:
        raise RuntimeError("native governor returned evidence for another action")
    return {
        "label": label,
        "frequency": frequency,
        "confidence": confidence,
    }


def _context_query(function_name, capsule):
    if function_name not in {
        "engineering-context-next",
        "engineering-context-evidence",
        "engineering-context-tracking",
    }:
        raise ValueError("unknown engineering context function")
    return "!(%s %s)" % (function_name, capsule)


def record_active_context(work, observation, actor="iter", transaction_id=None,
                          commit_batch_fn=commit_batch):
    """Persist an exact active context without dispatching or classifying it."""
    normalised = _normalise(work)
    capsule = context_atom(normalised, observation)
    identity = context_id(normalised)
    authority = hashlib.sha256(
        normalised["authorization_ref"].encode("utf-8")
    ).hexdigest()
    event_id = "engineering-context:%s:%s" % (
        normalised["work_id"], authority,
    )
    return commit_batch_fn(
        [{
            "event_id": event_id,
            "domain": "engineering_context",
            "entity_id": normalised["work_id"],
            "event_type": "context_recorded",
            "payload": {
                "context_id": identity,
                "schema": "engineering-context-v1",
                "work_id": normalised["work_id"],
                "action_key": normalised["selected_alternative"],
                "observation": dict(observation),
            },
        }],
        state_atoms={"engineering_context:%s" % identity: capsule},
        actor=actor,
        source="engineering_governor.active",
        transaction_id=transaction_id or event_id,
    )


def finalize_active(work, observation, query_fn=None, commit_fn=commit_event):
    """Derive and persist native outcome/evidence from an existing context.

    This path never claims or dispatches an action. It is therefore safe to
    retry after an interruption once the raw observation capsule is durable.
    """
    normalised = _normalise(work)
    if normalised["execution_mode"] != "active":
        raise ValueError("finalize_active requires execution_mode=active")
    action_key = normalised["selected_alternative"]
    if action_key not in ACTION_REGISTRY:
        raise ValueError("unknown governed action: %s" % action_key)
    capsule = context_atom(normalised, observation)
    identity = context_id(normalised)
    if query_fn is None:
        from iterbrow_runtime import engineering_query
        query_fn = engineering_query.run_query

    outcome_query = query_fn(_context_query("engineering-context-next", capsule))
    if not isinstance(outcome_query, dict) or not outcome_query.get("ok"):
        raise RuntimeError("native active outcome unavailable from context")
    outcome_identity = _snapshot_identity(outcome_query, "native outcome")
    outcome, outcome_selected = _extract_native_decision(
        normalised["work_id"], outcome_query.get("result")
    )
    if outcome not in {"accept", "iterate", "rollback", "escalate"}:
        raise RuntimeError("native governor returned a non-terminal active outcome")
    if outcome_selected != action_key:
        raise RuntimeError("native governor changed the selected action")

    authority = hashlib.sha256(
        normalised["authorization_ref"].encode("utf-8")
    ).hexdigest()
    decision_transaction = "engineering-active-decision:%s:%s" % (
        normalised["work_id"], authority,
    )
    decision_atom = " ".join((
        "(engineering-active-decision", metta_string(identity),
        metta_string(normalised["work_id"]), outcome, metta_string(action_key),
        metta_string(outcome_identity["epoch"]),
        str(outcome_identity["commit"]),
        metta_string(outcome_identity["state_hash"]), ")",
    ))
    decision_commit = commit_fn(
        "engineering_decision", normalised["work_id"], "active_decision",
        payload={
            "context_id": identity,
            "decision": outcome,
            "selected_alternative": action_key,
            "evaluated_epoch": outcome_identity["epoch"],
            "evaluated_commit": outcome_identity["commit"],
            "evaluated_state_hash": outcome_identity["state_hash"],
            "native_result": str(outcome_query.get("result")),
            "dispatch_authority": True,
        },
        state_atom=decision_atom,
        actor="iter",
        source="engineering_governor.active",
        event_id=decision_transaction,
        transaction_id=decision_transaction,
    )

    evidence_query = query_fn(
        _context_query("engineering-context-evidence", capsule)
    )
    if not isinstance(evidence_query, dict) or not evidence_query.get("ok"):
        raise RuntimeError("native evidence revision unavailable from context")
    evidence_identity = _snapshot_identity(evidence_query, "native evidence")
    evidence = _extract_native_evidence(
        normalised["work_id"], action_key, evidence_query.get("result")
    )
    evidence_transaction = "engineering-evidence:%s:%s" % (
        normalised["work_id"], authority,
    )
    evidence_atom = " ".join((
        "(engineering-capability-evidence", metta_string(identity),
        metta_string(normalised["work_id"]), metta_string(action_key),
        evidence["label"], "(stv", evidence["frequency"],
        evidence["confidence"] + ")", metta_string(evidence_identity["epoch"]),
        str(evidence_identity["commit"]),
        metta_string(evidence_identity["state_hash"]), ")",
    ))
    evidence_commit = commit_fn(
        "engineering_evidence", normalised["work_id"], "native_revision",
        payload={
            **evidence,
            "context_id": identity,
            "action_key": action_key,
            "evaluated_epoch": evidence_identity["epoch"],
            "evaluated_commit": evidence_identity["commit"],
            "evaluated_state_hash": evidence_identity["state_hash"],
            "native_result": str(evidence_query.get("result")),
        },
        state_atom=evidence_atom,
        actor="iter",
        source="engineering_governor.active",
        event_id=evidence_transaction,
        transaction_id=evidence_transaction,
    )
    return {
        "work_id": normalised["work_id"],
        "context_id": identity,
        "action_key": action_key,
        "decision": outcome,
        "decision_commit": (
            decision_commit.get("commit")
            if isinstance(decision_commit, dict) else None
        ),
        "evidence_revision": evidence,
        "evidence_commit": (
            evidence_commit.get("commit")
            if isinstance(evidence_commit, dict) else None
        ),
        "python_semantic_classification": False,
    }


def execute_active(work, expected_snapshot, query_fn=None,
                   commit_fn=commit_event, commit_batch_fn=commit_batch,
                   runner_fn=None):
    """Execute the sole allowlisted action and bind its native outcome.

    The caller must name the exact AtomSpace snapshot produced by recording
    ``work``. A durable dispatch claim is written before execution. Replaying
    the claim returns ``already_claimed`` and never invokes the runner again.
    """
    normalised = _normalise(work)
    if normalised["execution_mode"] != "active":
        raise ValueError("execute_active requires execution_mode=active")
    if normalised["action_status"] != "pending":
        raise ValueError("active dispatch requires action_status=pending")
    if normalised["observation"] != "none":
        raise ValueError("active dispatch requires observation=none")
    action_key = normalised["selected_alternative"]
    if action_key not in ACTION_REGISTRY:
        raise ValueError("unknown governed action: %s" % action_key)
    if query_fn is None:
        from iterbrow_runtime import engineering_query
        query_fn = engineering_query.run_query
    evaluated = query_fn(
        "!(engineering-next %s)" % metta_string(normalised["work_id"])
    )
    if not isinstance(evaluated, dict) or not evaluated.get("ok"):
        raise RuntimeError("native active governor unavailable")
    evaluated_identity = _require_exact_snapshot(evaluated, expected_snapshot)
    decision, selected = _extract_native_decision(
        normalised["work_id"], evaluated.get("result")
    )
    if decision != "active_action_ready" or selected != action_key:
        raise RuntimeError("native governor did not authorize the selected action")

    authorization_hash = hashlib.sha256(
        normalised["authorization_ref"].encode("utf-8")
    ).hexdigest()
    claim_transaction = "engineering-dispatch:%s:%s" % (
        normalised["work_id"], authorization_hash,
    )
    claim_atom = " ".join((
        "(engineering-dispatch-claim", metta_string(normalised["work_id"]),
        metta_string(action_key), metta_string(normalised["authorization_ref"]),
        metta_string(evaluated_identity["epoch"]),
        str(evaluated_identity["commit"]),
        metta_string(evaluated_identity["state_hash"]), ")",
    ))
    claim = commit_fn(
        "engineering_dispatch", normalised["work_id"], "dispatch_claimed",
        payload={
            "action_key": action_key,
            "authorization_ref": normalised["authorization_ref"],
            "argv_sha256": _action_fingerprint(action_key),
            "evaluated_epoch": evaluated_identity["epoch"],
            "evaluated_commit": evaluated_identity["commit"],
            "evaluated_state_hash": evaluated_identity["state_hash"],
        },
        state_atom=claim_atom,
        actor="iter",
        source="engineering_governor.active",
        event_id=claim_transaction,
        transaction_id=claim_transaction,
    )
    if isinstance(claim, dict) and claim.get("duplicate"):
        return {
            "work_id": normalised["work_id"],
            "action_key": action_key,
            "status": "already_claimed",
            "dispatched": False,
        }

    process_state = "exited"
    try:
        completed = (runner_fn or _run_fixed_action)(action_key)
        exit_code = int(completed.returncode)
        stdout = _as_bytes(completed.stdout)
        stderr = _as_bytes(completed.stderr)
    except Exception as exc:
        process_state = "spawn_failed"
        exit_code = -1
        stdout = b""
        stderr = ("%s: %s" % (type(exc).__name__, exc)).encode(
            "utf-8", errors="replace"
        )
    observation = {
        "work_id": normalised["work_id"],
        "action_key": action_key,
        "process_state": process_state,
        "exit_code": exit_code,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "output_bytes": len(stdout) + len(stderr),
    }
    updated = dict(normalised)
    updated["action_status"] = (
        "completed" if process_state == "exited" else "failed"
    )
    updated["observation"] = (
        "%s:exit=%s:stdout=%s:stderr=%s:bytes=%s"
        % (
            process_state, exit_code, observation["stdout_sha256"],
            observation["stderr_sha256"], observation["output_bytes"],
        )
    )
    observation_transaction = "engineering-observation:%s:%s" % (
        normalised["work_id"], authorization_hash,
    )
    observation_commit = commit_batch_fn(
        [{
            "event_id": observation_transaction,
            "domain": "engineering_observation",
            "entity_id": normalised["work_id"],
            "event_type": "raw_process_observed",
            "payload": observation,
        }],
        state_atoms={
            "engineering_work:%s" % normalised["work_id"]: work_atom(updated),
            "engineering_control:%s" % normalised["work_id"]: control_atom(updated),
            **observation_state_atoms(observation),
            "engineering_context:%s" % context_id(updated): (
                context_atom(updated, observation)
            ),
        },
        actor="iter",
        source="engineering_governor.active",
        transaction_id=observation_transaction,
    )
    final = finalize_active(
        updated, observation, query_fn=query_fn, commit_fn=commit_fn,
    )
    return {
        **final,
        "status": "observed",
        "dispatched": True,
        "observation": observation,
        "observation_commit": (
            observation_commit.get("commit")
            if isinstance(observation_commit, dict) else None
        ),
    }


def load_active_context(work_id, call_fn=_call_atomspace):
    """Rehydrate raw work/observation facts from authoritative domain events."""
    work_id = str(work_id).strip()
    if not work_id:
        raise ValueError("work_id cannot be empty")
    status = call_fn("status")
    current_commit = int((status or {}).get("commit", 0))
    after = 0
    work = None
    observation = None
    while after < current_commit:
        page = call_fn("subscribe", after_commit=after, limit=1000)
        events = list((page or {}).get("events") or [])
        if not events:
            break
        for transaction in events:
            for event in (transaction.get("metadata") or {}).get(
                    "domain_events", []):
                if str(event.get("entity_id", "")) != work_id:
                    continue
                if (event.get("domain") == "engineering_work"
                        and event.get("event_type") == "work_recorded"):
                    candidate = (event.get("payload") or {}).get("work")
                    if isinstance(candidate, dict):
                        work = candidate
                if (event.get("domain") == "engineering_observation"
                        and event.get("event_type") == "raw_process_observed"):
                    candidate = event.get("payload")
                    if isinstance(candidate, dict):
                        observation = candidate
        next_after = max(int(item.get("commit", 0)) for item in events)
        if next_after <= after:
            break
        after = next_after
    if work is None or observation is None:
        raise RuntimeError("authoritative active context events are incomplete")
    return _normalise(work), dict(observation)


def recover_active(work_id, query_fn=None, work=None, observation=None,
                   context_loader_fn=None):
    """Reconstruct active Tracking from durable facts without dispatching."""
    if work is None or observation is None:
        loader = context_loader_fn or load_active_context
        work, observation = loader(work_id)
    projection = tracking_projection(
        work_id, query_fn=query_fn, work=work, observation=observation,
    )
    decision, selected = _extract_native_decision(work_id, projection["projection"])
    if decision not in {"accept", "iterate", "rollback", "escalate"}:
        raise RuntimeError("active work has no completed native outcome")
    evidence = _extract_native_evidence(
        work_id, selected, projection["projection"]
    )
    return {
        **projection,
        "decision": decision,
        "selected_alternative": selected,
        "evidence_revision": evidence,
        "dispatched": False,
        "authority": "atomspace_reconstruction",
    }


def tracking_projection(work_id, query_fn=None, work=None, observation=None,
                        work_loader_fn=None):
    """Return the native Tracking projection with its exact state identity."""
    work_id = str(work_id).strip()
    if not work_id:
        raise ValueError("work_id cannot be empty")
    if query_fn is None:
        from iterbrow_runtime import engineering_query
        query_fn = engineering_query.run_query
    if work is None and observation is None:
        loader = work_loader_fn or load_recorded_work
        shadow_work = _normalise(loader(work_id))
        if shadow_work["work_id"] != work_id:
            raise RuntimeError(
                "authoritative engineering work identity is inconsistent"
            )
        code = _shadow_query("engineering-shadow-tracking", shadow_work)
    elif work is None or observation is None:
        raise ValueError("active Tracking requires both work and observation")
    else:
        normalised = _normalise(work)
        if normalised["work_id"] != work_id:
            raise ValueError("active Tracking context belongs to another work unit")
        code = _context_query(
            "engineering-context-tracking",
            context_atom(normalised, observation),
        )
    result = query_fn(code)
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError("native Tracking projection unavailable")
    return {
        "work_id": work_id,
        "projection": str(result.get("result")),
        "epoch": result.get("epoch"),
        "commit": result.get("commit"),
        "state_hash": result.get("state_hash"),
        "authority": "atomspace_projection",
    }
