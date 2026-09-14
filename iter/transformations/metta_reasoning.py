"""MeTTa reasoning substrate -- Phase 1 (pre-decision symbolic summary).

Runs once per turn, before the LLM call. Loads nace_substrate.metta's NAL
formulas together with nace_beliefs.metta's live efficacy/calibration state
into a fresh, safety-bounded MeTTa space, evaluates the efficacy expectation
for each tool currently on offer, and appends a short symbolic summary to
the system message -- the same "[note]" pattern nace_courier.py already uses
for its belief-revision summary.

This is intentionally read-only: it never writes nace_beliefs.metta (that
stays nace_courier.py's job) and never blocks or vetoes anything (that is
tools/_metta_gate.py's job, wired in separately and only active in "enforce"
mode). If the reasoning substrate errors, times out, or the circuit breaker
is open, this transformation silently leaves messages/tools unchanged --
exactly like every other transformation in this pipeline degrades on
failure.

QUERY DESIGN NOTE: uses a direct `(match &self (cap-efficacy $cap $stv) ...)`
per tool rather than calling nace_substrate.metta's own should-dispatch/
current-efficacy directly -- those have a generic (stv 0.5 0.0) fallback
equation that overlaps with the real-belief equation, so MeTTa (which
returns every matching equation, not just the first) answers a direct
should-dispatch query ambiguously (both the real and the fallback result at
once). Querying cap-efficacy facts directly avoids that ambiguity and also
gives an unambiguous "no data yet" case (empty result) for tools with no
calibration history, which this transformation reports as such rather than
guessing.

Safety: this whole call runs inside its own iter.py invoke_dynamic()
subprocess and inherits its wall-clock timeout + hard process-group kill.
tools/_metta_substrate.py additionally runs a portable memory watchdog
(RSS-polling, since setrlimit is not enforced on macOS) around the actual
MeTTa evaluation, and a circuit breaker skips this pass entirely after
repeated recent failures.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import _metta_substrate as _sub  # noqa: E402

DESCRIPTION = (
    "Runs a bounded MeTTa reasoning pass over nace_substrate.metta + "
    "nace_beliefs.metta each turn and appends a short symbolic summary "
    "(efficacy expectation for the tools on offer this turn) to the system "
    "message. Read-only and fail-open: never writes beliefs, never blocks "
    "anything -- degrades silently on error."
)

_BREAKER_KEY = "reasoning_pass"
_MAX_TOOLS_CHECKED = 12  # keep the generated MeTTa program small/bounded
_THRESHOLD = 0.3


def _tool_names(tools):
    names = []
    for t in (tools or [])[:_MAX_TOOLS_CHECKED]:
        try:
            name = t.get("function", {}).get("name")
        except AttributeError:
            name = None
        if name:
            cleaned = "".join(ch for ch in str(name) if ch.isalnum() or ch == "_")
            if cleaned:
                names.append(cleaned)
    return names


def _parse_batch_result(result_text, names):
    """result_text looks like '[[Grounded(0.29)], [Grounded(0.96)], []]' --
    one bracketed group per query, in the same order names were queried."""
    groups = re.findall(r"\[([^\[\]]*)\]", result_text)
    # re.findall on nested brackets grabs innermost groups first, in order --
    # matches how many queries we issued as long as none of them themselves
    # contain nested brackets, which Truth_Expectation's numeric output never does.
    parsed = {}
    for name, group in zip(names, groups):
        m = re.search(r"Grounded\(([-\d.eE]+)\)", group)
        parsed[name] = float(m.group(1)) if m else None
    return parsed


def transform(messages, tools):
    if _sub.breaker_should_skip(_BREAKER_KEY):
        return messages, tools

    names = _tool_names(tools)
    if not names:
        return messages, tools

    query = "\n".join(
        "!(match &self (cap-efficacy %s $stv) (Truth_Expectation $stv))" % n for n in names
    )
    result = _sub.run_query(query)
    _sub.breaker_record_result(_BREAKER_KEY, result["ok"])
    if not result["ok"]:
        return messages, tools

    expectations = _parse_batch_result(result["result"], names)
    low = [n for n, e in expectations.items() if e is not None and e < _THRESHOLD]
    unknown_count = sum(1 for e in expectations.values() if e is None)

    parts = []
    if low:
        parts.append("below should-dispatch threshold (%.2f): %s" % (_THRESHOLD, ", ".join(low)))
    if unknown_count:
        parts.append("%d tool(s) with no calibration data yet" % unknown_count)
    if not parts:
        parts.append("all %d checked tools currently above threshold" % len(names))

    summary = "[NACE reasoning pass: " + "; ".join(parts) + "]"
    for message in messages:
        if message.get("role") == "system":
            message["content"] = message.get("content", "") + "\n\n" + summary
            break

    return messages, tools
