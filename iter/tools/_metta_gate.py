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
  3. PYTHON FALLBACK     -- pymetta is NOT currently installed on this
     machine (tools/metta.py's ENGINE_AVAILABLE is False), which means the
     live-engine query above always returns ok=False and, under the OLD
     single-path logic, this gate silently fell open on every single call
     forever -- never actually advising on real numbers. Real cap-efficacy
     values are still tracked correctly (nace_courier.py writes them from
     pure Python, no engine needed), so when the live query is unavailable
     this now parses nace_beliefs.metta directly and computes the same
     Truth_Expectation formula (E = f*c + 0.5*(1-c), matching
     nace_substrate.metta's definition) in pure Python. Only if that also
     finds nothing does it fail open. This is the single biggest behavior
     change here: the gate goes from "always silently inert" to "actually
     advising off real data" on this machine today, independent of whether
     pymetta ever gets installed.
  4. priority floor      -- capability_lifecycle.metta's `cap-priority`. A
     capability marked `critical` (load-bearing infra: websearch, send,
     shell, python, memory_update, remember, episodes, chroma_query,
     self_improve) uses a lower floor (0.15) before being flagged, so a
     load-bearing tool with noisy-but-nonzero efficacy isn't vetoed the
     moment confidence dips the way a flat 0.3 threshold would (this
     concretely matters today: websearch's real expectation is ~0.296,
     just under 0.3, despite ~1000 real calls and c=0.98).
  5. flat threshold       -- everything else, unchanged default 0.3.

MODES (env var METTA_GATE_MODE, default "advisory"):
  advisory -- (default) never blocks anything. Returns a verdict string that
              iter.py can log / prepend to the tool's own output as an FYI
              note when efficacy is low. Safe to leave on indefinitely.
  enforce  -- actually blocks dispatch when efficacy-expectation is below
              the should-dispatch threshold (or when lifecycle=quarantined).
              NOT enabled by default: nace_beliefs.metta ships with real,
              already-accumulated calibration data, and at least one
              capability (websearch, expectation ~0.296) is already just
              under the old flat 0.3 threshold -- flipping to enforce mode
              without reviewing/resetting calibration first, or without this
              pipeline's critical-priority floor, will immediately start
              blocking it. See README.md before enabling.

SAFETY DESIGN: fails OPEN, always, in both modes. Any error, timeout, missing
engine AND missing fallback data, or tripped circuit breaker returns ALLOW --
a reasoning-layer glitch must never be able to stall or block the agent's
ability to act. The wall-clock timeout for this entire call is enforced by
iter.py's invoke_dynamic (DYNAMIC_TIMEOUT), the same mechanism every other
tool/transformation call already relies on.
"""

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _metta_substrate as _sub  # noqa: E402

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


def run(cap_name):
    mode = os.environ.get("METTA_GATE_MODE", "advisory").strip().lower()
    cap = _safe_atom(cap_name)

    if _sub.breaker_should_skip(_BREAKER_KEY):
        return _format(mode, "ALLOW", "circuit breaker open (recent repeated failures) -- fail-open")

    lifecycle, priority = _load_lifecycle_and_priority(cap)

    if lifecycle == "quarantined":
        action = "VETO" if mode == "enforce" else "ADVISE"
        return _format(
            mode, action,
            "capability %r is lifecycle=quarantined (confirmed repeated failure) -- "
            "manual override, ignores current efficacy number" % cap_name,
        )

    confidence = _lookup_confidence(cap)
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
        return _format(
            mode, "ADVISE",
            "capability %r is trust_stage=candidate (%s) -- always surfaced, "
            "never a silent fail-open ALLOW while untested" % (cap_name, reason),
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

    query = "!(match &self (cap-efficacy %s $stv) (Truth_Expectation $stv))" % cap
    result = _sub.run_query(query)
    _sub.breaker_record_result(_BREAKER_KEY, result["ok"])

    source = "live-engine"
    expectation = None
    if result["ok"]:
        expectation = _extract_number(result["result"])

    if expectation is None:
        # Either the live engine is unavailable (pymetta not installed --
        # the actual current state of this machine) or it ran but found no
        # belief. Try the pure-Python fallback against the same file the
        # live query would have read, before giving up and failing open.
        expectation = _python_fallback_expectation(cap)
        source = "python-fallback"

    if expectation is None:
        return _format(
            mode, "ALLOW",
            "no calibration data available for %r via live engine or fallback -- fail-open" % cap_name,
        )

    floor_note = " [critical floor %.2f]" % _CRITICAL_THRESHOLD if (priority == "critical" and trust_stage == "authoritative") else ""

    if trust_stage == "probe_eligible":
        _log_probe(cap, trust_stage, confidence, "expectation=%.3f threshold=%.2f" % (expectation, threshold))

    if expectation < threshold:
        action = "VETO" if mode == "enforce" else "ADVISE"
        return _format(
            mode, action,
            "efficacy expectation %.3f < %.2f threshold for %r (%s)%s%s"
            % (expectation, threshold, cap_name, source, floor_note, stage_note),
        )

    return _format(
        mode, "ALLOW",
        "efficacy expectation %.3f >= %.2f threshold for %r (%s)%s%s"
        % (expectation, threshold, cap_name, source, floor_note, stage_note),
    )


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
    routed through the MeTTa engine, so this works even when pymetta is
    unavailable (the actual state of this machine today). Fails safe to
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


def _safe_atom(cap_name):
    # cap_name comes from the LLM's own chosen tool_name, already validated
    # against INOPS by iter.py before this is ever called -- strip anything
    # that isn't a plain identifier as a defensive measure before it's
    # spliced into MeTTa source text.
    return "".join(ch for ch in str(cap_name) if ch.isalnum() or ch == "_") or "unknown"


def _extract_number(result_text):
    # result_text looks like "[[Grounded(0.289042)]]" on a hit, "[[]]" on no data.
    m = re.search(r"Grounded\(([-\d.eE]+)\)", str(result_text))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _format(mode, action, detail):
    return "%s|%s|%s" % (mode, action, detail)
