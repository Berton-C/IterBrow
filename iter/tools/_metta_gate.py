"""Internal: MeTTa-based dispatch gate. NOT an LLM-facing tool (underscore-
prefixed). Called by iter.py just before dispatching a tool call, to check
the capability's current efficacy expectation in nace_beliefs.metta against
nace_substrate.metta's should-dispatch threshold (efficacy-expectation >= 0.3).

QUERY DESIGN NOTE (found while empirically testing against the real engine,
not assumed): nace_substrate.metta defines current-efficacy/should-dispatch
with TWO overlapping equations each -- one that matches a real belief via
`match &self`, and one generic fallback `(stv 0.5 0.0)` for capabilities with
no belief entry. Because MeTTa returns every equation that matches rather
than "first match wins", calling `!(should-dispatch websearch)` directly
returns BOTH results at once, e.g. `[Grounded(False), Grounded(True)]` --
ambiguous, and a naive substring check on the text would misread it. This
module instead queries `(match &self (cap-efficacy $cap $stv) ...)` directly,
which returns exactly one value when a belief exists and an empty list when
it doesn't -- unambiguous, and it also gives us a clean, safe default (no
calibration data yet for this capability -> ALLOW, don't veto something
that's never been measured).

CAPABILITY REGISTRY PIPELINE (added 2026-09-14, proven against real
nace_beliefs.metta data before being wired in -- see gate_simulation.py in
the project notes): instead of one flat threshold for every capability, this
now runs an ordered pipeline per call:
  1. lifecycle check    -- capability_lifecycle.metta's `cap-lifecycle`. A
     capability marked `quarantined` (confirmed f=0.0 across repeated real
     attempts, not just low-confidence/no-data) is always flagged, full stop,
     regardless of any expectation number. Recovery is a conscious edit to
     that file, not automatic -- this is a manual circuit breaker.
  1b. TRUST LIFECYCLE (Stage 3, 2026-09-14) -- a capability that ISN'T
     quarantined still gets one of 4 trust stages, derived from real
     evidence rather than a static label that never changes:
       candidate      -- manually declared in capability_lifecycle.metta, OR
                         no cap-efficacy belief atom exists at all yet.
                         Always ADVISE, in both advisory and enforce mode --
                         never a silent fail-open ALLOW just because nobody
                         has looked. This is the concrete fix for the gap
                         where 4 capabilities were declared lifecycle=new
                         but the gate never actually treated them
                         differently.
       probe_eligible -- has some real cap-efficacy confidence (c) but below
                         0.4 -- not enough evidence yet to earn the critical
                         floor discount, so the flat 0.3 threshold applies
                         even for a capability declared cap-priority=
                         critical.
       authoritative  -- 0.4 <= c < 0.8 -- normal behavior, same floor logic
                         as the old single "active" stage.
       durable        -- c >= 0.8 -- sustained, well-evidenced track record;
                         gets a small extra floor discount (0.05, never
                         below an absolute 0.10 floor).
     Every probe (a real dispatch of a candidate/probe_eligible capability)
     is also appended to a lightweight, size-capped probe log (see
     `_log_probe` / PROBE_LOG_PATH) purely for visibility -- something a
     human (or a future capability) can read to see "here's what happened
     the first N times this ran", without turning into an unbounded audit
     trail.
  2. efficacy lookup    -- same cap-efficacy query as before, via the live
     MeTTa engine when available.
  3. PYTHON FALLBACK     -- if the authoritative Hyperon query service is
     temporarily unavailable, the gate must not silently become inert. Real
     cap-efficacy values are also retained in the nace_beliefs.metta
     compatibility projection, so when the live query is unavailable
     this now parses nace_beliefs.metta directly and computes the same
     Truth_Expectation formula (E = f*c + 0.5*(1-c), matching
     nace_substrate.metta's definition) in pure Python. Only if that also
     finds nothing does it fail open. This is the single biggest behavior
     change here: the gate goes from "always silently inert" to "actually
     advising off real data" on this machine today, independent of whether
     the native engine is temporarily offline.
  4. priority floor      -- capability_lifecycle.metta's `cap-priority`. A
     capability marked `critical` (load-bearing infra: websearch, send,
     shell, python, memory_update, remember, episodes, chroma_query,
     self_improve) uses a lower floor (0.15) before being flagged, so a
     load-bearing tool with noisy-but-nonzero efficacy isn't vetoed the
     moment confidence dips the way a flat 0.3 threshold would (this
     concretely matters today: websearch's real expectation is ~0.296,
     just under 0.3, despite ~1000 real calls and c=0.98).
  5. flat threshold       -- everything else, unchanged default 0.3.

MODES (env var METTA_GATE_MODE, default "enforce"):
  advisory -- never blocks adaptive efficacy decisions. Returns a verdict string that
              iter.py can log / prepend to the tool's own output as an FYI
              note when efficacy is low. Safe to leave on indefinitely.
  enforce  -- (default) actually blocks dispatch when efficacy-expectation is below
              the should-dispatch threshold (or when lifecycle=quarantined).
              Critical load-bearing capabilities retain their lower earned
              floor; explicit human-decision API violations veto in every mode.

SAFETY DESIGN: explicit human-decision API rules fail closed. Shell/Python source
text is not scanned for prohibited write paths or used to emit write warnings.
Revision/state services retain their own authorization and integrity checks. Adaptive NACE
reasoning failures surface as ADVISE rather than masquerading as an ALLOW
verdict. Failure to record a decision is reported, not turned into a new dispatch
veto; state-writing services still protect their own durable commits. The wall-clock timeout for this call is enforced by
iter.py's invoke_dynamic (DYNAMIC_TIMEOUT), the same mechanism every other
tool/transformation call already relies on.
"""

import hashlib
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _metta_substrate as _sub  # noqa: E402

for _root_candidate in (
        os.environ.get("ITER_DIR"), os.getcwd(), str(Path(__file__).resolve().parents[1])):
    if _root_candidate and (Path(_root_candidate) / "iterbrow_runtime").is_dir():
        if str(Path(_root_candidate)) not in sys.path:
            sys.path.insert(0, str(Path(_root_candidate)))
        break
try:
    from iterbrow_runtime.cognitive_events import commit_event, metta_string  # noqa: E402
    _RUNTIME_IMPORT_ERROR = None
except ModuleNotFoundError as _runtime_exc:
    if not str(getattr(_runtime_exc, "name", "")).startswith("iterbrow_runtime"):
        raise
    # Historical isolated fixtures intentionally copy only this helper and its
    # legacy belief files. They may inspect pure parsing/trust-stage functions,
    # but any real consequential dispatch still fails closed in `_finish`.
    _RUNTIME_IMPORT_ERROR = _runtime_exc

    def metta_string(value):
        return json.dumps(str(value), ensure_ascii=False)

    def commit_event(*_args, **_kwargs):
        raise RuntimeError(
            "authoritative cognitive-event runtime is unavailable: %s"
            % _RUNTIME_IMPORT_ERROR
        )

DESCRIPTION = "internal: metta-based dispatch gate, not an LLM-facing tool"

_BREAKER_KEY = "gate"
_THRESHOLD = 0.3  # mirrors nace_substrate.metta's should-dispatch threshold
_CRITICAL_THRESHOLD = 0.15  # priority floor for cap-priority=critical
_LIFECYCLE_FILENAME = "capability_lifecycle.metta"

# ===== STAGE 3: 4-stage trust lifecycle (candidate -> probe_eligible ->
# authoritative -> durable), 2026-09-14 =====
_PROBE_CONFIDENCE_THRESHOLD = 0.4   # c below this -> probe_eligible
_DURABLE_CONFIDENCE_THRESHOLD = 0.8  # c at/above this -> durable
_DURABLE_DISCOUNT = 0.05             # extra floor discount once durable
_MIN_FLOOR = 0.10                    # absolute floor, even durable can't go below this
_PROBE_LOG_FILENAME = "memory/probe_log.json"
_PROBE_LOG_MAX = 200  # size-capped: this is a visibility log, not an audit trail

_LIFECYCLE_RE = re.compile(r"\(cap-lifecycle\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)")
_PRIORITY_RE = re.compile(r"\(cap-priority\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\)")
_BELIEF_RE = re.compile(
    r"\(cap-efficacy\s+([A-Za-z0-9_]+)\s+\(stv\s+([-\d.eE]+)\s+([-\d.eE]+)\)\)"
)

_AUDITED_CAPS = {
    "atomspace", "forget", "memory_update", "pwq_write", "python",
    "revision_control", "self_improve", "send", "shell",
}
_FEATURE_INVARIANTS = {
    "bypasses_human_authorization": "human_agency_before_dispatch",
}


def run(cap_name, arguments=None, governance_context=None):
    mode = os.environ.get("METTA_GATE_MODE", "enforce").strip().lower()
    if mode not in ("advisory", "enforce"):
        mode = "enforce"
    cap = _safe_atom(cap_name)
    arguments = arguments if isinstance(arguments, dict) else {}
    governance_context = governance_context if isinstance(governance_context, dict) else {}

    hard_violation = _hard_policy_violation(cap, arguments)
    if hard_violation:
        feature, explanation = hard_violation
        invariant, authority = _kb_invariant_for(feature)
        return _finish(
            cap, arguments, governance_context, "enforce", "VETO",
            "%s [KB feature=%s invariant=%s]" % (explanation, feature, invariant),
            authority=authority,
        )

    if _sub.breaker_should_skip(_BREAKER_KEY):
        return _finish(
            cap, arguments, governance_context, mode, "ADVISE",
            "circuit breaker open; no adaptive KB/NACE claim was made",
            authority=None,
        )

    lifecycle, priority = _load_lifecycle_and_priority(cap)

    if lifecycle == "quarantined":
        action = "VETO" if mode == "enforce" else "ADVISE"
        return _finish(
            cap, arguments, governance_context, mode, action,
            "capability %r is lifecycle=quarantined (confirmed repeated failure) -- "
            "manual override, ignores current efficacy number" % cap_name,
            authority=None,
        )

    query = (
        "!(match &self (cap-efficacy %s (stv $f $c)) "
        "(cap-evaluation $f $c (Truth_Expectation (stv $f $c))))" % cap
    )
    result = _sub.run_query(query, view="current")
    _sub.breaker_record_result(_BREAKER_KEY, result["ok"])
    metrics = _extract_metrics(result.get("result", "")) if result["ok"] else None
    source = "authoritative-atomspace"
    if metrics is None:
        fallback = _python_fallback_metrics(cap)
        if fallback is not None:
            metrics = fallback
            source = "legacy-projection-fallback"

    confidence = metrics[1] if metrics is not None else None
    trust_stage = _determine_trust_stage(lifecycle, confidence)

    if trust_stage == "candidate":
        # STAGE 3: this is the concrete behavior change for the gap where 4
        # capabilities were declared lifecycle=new but the gate silently
        # ALLOWed them exactly like everything else. Never VETO purely for
        # having no track record yet (that would risk bricking a genuinely
        # fine new capability the first time it's ever called) -- but never
        # silently ALLOW either. Always surfaced, in both modes.
        reason = ("manually declared candidate" if lifecycle == "candidate"
                  else "no cap-efficacy belief data yet")
        _log_probe(cap, trust_stage, confidence, reason)
        return _finish(
            cap, arguments, governance_context, mode, "ADVISE",
            "capability %r is trust_stage=candidate (%s) -- always surfaced, "
            "never a silent fail-open ALLOW while untested" % (cap_name, reason),
            authority=result if result.get("ok") else None,
        )

    base_threshold = _CRITICAL_THRESHOLD if priority == "critical" else _THRESHOLD

    if trust_stage == "probe_eligible":
        # Hasn't earned the critical floor discount yet, regardless of what
        # cap-priority says -- that discount is for load-bearing capabilities
        # with an established track record, not ones still building one.
        threshold = _THRESHOLD
        stage_note = " [probe_eligible: critical floor not yet earned, c=%.2f]" % (confidence or 0.0)
    elif trust_stage == "durable":
        threshold = max(_MIN_FLOOR, base_threshold - _DURABLE_DISCOUNT)
        stage_note = " [durable: extra floor discount earned, c=%.2f]" % (confidence or 0.0)
    else:
        threshold = base_threshold
        stage_note = ""

    expectation = metrics[2] if metrics is not None else None

    if expectation is None:
        return _finish(
            cap, arguments, governance_context, mode, "ADVISE",
            "no calibration data available for %r; no adaptive KB/NACE claim was made"
            % cap_name,
            authority=result if result.get("ok") else None,
        )

    floor_note = " [critical floor %.2f]" % _CRITICAL_THRESHOLD if (priority == "critical" and trust_stage == "authoritative") else ""

    if trust_stage == "probe_eligible":
        _log_probe(cap, trust_stage, confidence, "expectation=%.3f threshold=%.2f" % (expectation, threshold))

    if expectation < threshold:
        action = "VETO" if mode == "enforce" else "ADVISE"
        return _finish(
            cap, arguments, governance_context, mode, action,
            "efficacy expectation %.3f < %.2f threshold for %r (%s)%s%s"
            % (expectation, threshold, cap_name, source, floor_note, stage_note),
            authority=result if result.get("ok") else None,
        )

    return _finish(
        cap, arguments, governance_context, mode, "ALLOW",
        "efficacy expectation %.3f >= %.2f threshold for %r (%s)%s%s"
        % (expectation, threshold, cap_name, source, floor_note, stage_note),
        authority=result if result.get("ok") else None,
    )


def _hard_policy_violation(cap, arguments):
    action = str(arguments.get("action", "")).strip().lower()
    if cap == "pwq_write" and action in (
            "approve", "reject", "reorder", "write", "sync"):
        return (
            "bypasses_human_authorization",
            "Iter cannot perform human PWQ decisions or replace the board projection wholesale",
        )
    return None


def _kb_invariant_for(feature):
    fallback = _FEATURE_INVARIANTS.get(feature, "unknown_invariant")
    result = _sub.run_query(
        "!(match &self (inv-feature-invariant %s $inv) $inv)" % _safe_atom(feature), view="current"
    )
    if not result.get("ok"):
        return fallback, None
    match = re.search(r"\[\[([A-Za-z0-9_:-]+)\]\]", result.get("result", ""))
    if not match:
        return fallback, None
    return match.group(1), result


def _extract_metrics(result_text):
    match = re.search(
        r"cap-evaluation\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)",
        str(result_text),
    )
    if not match:
        return None
    try:
        return tuple(float(match.group(index)) for index in (1, 2, 3))
    except ValueError:
        return None


def _finish(cap, arguments, governance_context, mode, action, detail, authority=None):
    decision_id = str(uuid.uuid4())
    args_hash = hashlib.sha256(
        json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    evaluated_commit = authority.get("commit") if isinstance(authority, dict) else None
    should_record = action != "ALLOW" or cap in _AUDITED_CAPS
    if should_record:
        state_atom = "(governance-decision %s %s %s %s %s %s)" % (
            metta_string(decision_id), metta_string(cap), metta_string(action),
            metta_string(mode), str(evaluated_commit if evaluated_commit is not None else -1),
            metta_string(args_hash),
        )
        payload = {
            "decision_id": decision_id,
            "capability": cap,
            "mode": mode,
            "action": action,
            "detail": detail,
            "arguments_sha256": args_hash,
            "evaluated_epoch": authority.get("epoch") if isinstance(authority, dict) else None,
            "evaluated_commit": evaluated_commit,
            "evaluated_state_hash": authority.get("state_hash") if isinstance(authority, dict) else None,
            "context": {
                key: governance_context.get(key)
                for key in ("cycle", "generation_id", "pwq_proposal_id")
                if governance_context.get(key) is not None
            },
        }
        try:
            recorded = commit_event(
                "governance", cap, "action_decision", payload=payload,
                state_atom=state_atom, actor="iter.governance",
                source="tools._metta_gate", event_id=decision_id,
                transaction_id="governance:%s" % decision_id,
            )
            if isinstance(recorded, dict) and not recorded.get("deferred"):
                detail += " [decision=%s evaluated_state=%s decision_saved_at=%s]" % (
                    decision_id, evaluated_commit, recorded.get("commit"),
                )
        except Exception as exc:
            if action == "ALLOW":
                action = "ADVISE"
            detail += " [decision evidence unavailable: %s: %s]" % (
                type(exc).__name__, exc,
            )
    return _format(mode, action, detail)


def _lookup_confidence(cap, root="."):
    # Pure-regex read of nace_beliefs.metta's confidence `c` (second stv
    # component) for `cap`. Returns None if no belief atom exists yet --
    # that absence IS the signal for trust_stage=candidate, not an error.
    path = os.path.join(root, "nace_beliefs.metta")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return None
    for m in _BELIEF_RE.finditer(content):
        if m.group(1) != cap:
            continue
        try:
            return float(m.group(3))
        except ValueError:
            return None
    return None


def _determine_trust_stage(lifecycle, confidence):
    # STAGE 3: derive one of candidate/probe_eligible/authoritative/durable.
    # `lifecycle` is the manual override from capability_lifecycle.metta
    # (already known not to be "quarantined" -- caller handles that
    # separately) or None when there's no line for this capability at all.
    # `confidence` is the real `c` from nace_beliefs.metta, or None when no
    # belief atom exists yet.
    if lifecycle == "candidate":
        return "candidate"
    if confidence is None:
        return "candidate"
    if confidence < _PROBE_CONFIDENCE_THRESHOLD:
        return "probe_eligible"
    if confidence < _DURABLE_CONFIDENCE_THRESHOLD:
        return "authoritative"
    return "durable"


def _log_probe(cap, trust_stage, confidence, detail):
    # Append one small entry to a size-capped, human-readable probe log.
    # This is deliberately NOT the calibration ledger (nace_beliefs.metta /
    # soul_gate_log.json stay the sources of truth for real evidence) -- it's
    # just visibility into what happened the first few times an
    # under-evidenced capability actually ran, so a human (or a future
    # capability) reviewing candidate/probe_eligible capabilities has
    # something concrete to look at instead of nothing. Never raises: a
    # logging failure here must never affect the gate's own ALLOW/ADVISE/VETO
    # decision.
    try:
        os.makedirs("memory", exist_ok=True)
        entries = []
        if os.path.exists(_PROBE_LOG_FILENAME):
            try:
                with open(_PROBE_LOG_FILENAME, "r", encoding="utf-8") as fh:
                    entries = json.load(fh)
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []
        entries.append({
            "ts": time.time(),
            "cap": cap,
            "trust_stage": trust_stage,
            "confidence": confidence,
            "detail": detail,
        })
        if len(entries) > _PROBE_LOG_MAX:
            entries = entries[-_PROBE_LOG_MAX:]
        with open(_PROBE_LOG_FILENAME, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2)
    except Exception:
        pass


def _load_lifecycle_and_priority(cap, root="."):
    """Pure-regex read of capability_lifecycle.metta -- deliberately NOT
    routed through the MeTTa engine, so this remains available while the
    authoritative query service is offline. Fails safe to
    (None, None) on any error -- caller then uses default lifecycle=active,
    priority=normal."""
    path = os.path.join(root, _LIFECYCLE_FILENAME)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return None, None

    lifecycle = None
    priority = None
    for m in _LIFECYCLE_RE.finditer(content):
        if m.group(1) == cap:
            lifecycle = m.group(2)
    for m in _PRIORITY_RE.finditer(content):
        if m.group(1) == cap:
            priority = m.group(2)
    return lifecycle, priority


def _python_fallback_expectation(cap, root="."):
    """Pure-Python re-derivation of the same Truth_Expectation the live
    MeTTa query would compute, read directly from nace_beliefs.metta.
    Formula mirrors nace_substrate.metta: E = f*c + 0.5*(1-c). Returns None
    if the file can't be read or the capability has no belief entry."""
    path = os.path.join(root, "nace_beliefs.metta")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return None

    for m in _BELIEF_RE.finditer(content):
        if m.group(1) != cap:
            continue
        try:
            f = float(m.group(2))
            c = float(m.group(3))
        except ValueError:
            continue
        return f * c + 0.5 * (1.0 - c)
    return None


def _python_fallback_metrics(cap, root="."):
    """Transitional recovery from the NACE projection, never the preferred authority."""
    path = os.path.join(root, "nace_beliefs.metta")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read()
    except Exception:
        return None
    for match in _BELIEF_RE.finditer(content):
        if match.group(1) != cap:
            continue
        try:
            frequency = float(match.group(2))
            confidence = float(match.group(3))
        except ValueError:
            continue
        expectation = frequency * confidence + 0.5 * (1.0 - confidence)
        return frequency, confidence, expectation
    return None


def _safe_atom(cap_name):
    # cap_name comes from the LLM's own chosen tool_name, already validated
    # against INOPS by iter.py before this is ever called -- strip anything
    # that isn't a plain identifier as a defensive measure before it's
    # spliced into MeTTa source text.
    return "".join(ch for ch in str(cap_name) if ch.isalnum() or ch == "_") or "unknown"


def _extract_number(result_text):
    # Hyperon versions return either [[Grounded(0.289042)]] or [[0.289042]].
    m = re.search(r"Grounded\(([-\d.eE]+)\)", str(result_text))
    if not m:
        m = re.search(r"\[\[\s*([-\d.eE]+)\s*\]\]", str(result_text))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _format(mode, action, detail):
    return "%s|%s|%s" % (mode, action, detail)
