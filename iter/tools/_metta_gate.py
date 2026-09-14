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

MODES (env var METTA_GATE_MODE, default "advisory"):
  advisory -- (default) never blocks anything. Returns a verdict string that
              iter.py can log / prepend to the tool's own output as an FYI
              note when efficacy is low. Safe to leave on indefinitely.
  enforce  -- actually blocks dispatch when efficacy-expectation is below
              the should-dispatch threshold. NOT enabled by default:
              nace_beliefs.metta ships with real, already-accumulated
              calibration data, and at least one capability (websearch,
              expectation ~0.289) is already just under the current 0.3
              threshold -- flipping to enforce mode without reviewing/
              resetting calibration first will immediately start blocking
              it. See README.md before enabling.

SAFETY DESIGN: fails OPEN, always, in both modes. Any error, timeout, missing
engine, no-belief-data, or tripped circuit breaker returns ALLOW -- a
reasoning-layer glitch must never be able to stall or block the agent's
ability to act. The wall-clock timeout for this entire call is enforced by
iter.py's invoke_dynamic (DYNAMIC_TIMEOUT), the same mechanism every other
tool/transformation call already relies on.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _metta_substrate as _sub  # noqa: E402

DESCRIPTION = "internal: metta-based dispatch gate, not an LLM-facing tool"

_BREAKER_KEY = "gate"
_THRESHOLD = 0.3  # mirrors nace_substrate.metta's should-dispatch threshold


def run(cap_name):
    mode = os.environ.get("METTA_GATE_MODE", "advisory").strip().lower()
    cap = _safe_atom(cap_name)

    if _sub.breaker_should_skip(_BREAKER_KEY):
        return _format(mode, "ALLOW", "circuit breaker open (recent repeated failures) -- fail-open")

    query = "!(match &self (cap-efficacy %s $stv) (Truth_Expectation $stv))" % cap
    result = _sub.run_query(query)
    _sub.breaker_record_result(_BREAKER_KEY, result["ok"])

    if not result["ok"]:
        return _format(mode, "ALLOW", "reasoning substrate unavailable this cycle (%s) -- fail-open" % result["error"])

    expectation = _extract_number(result["result"])
    if expectation is None:
        return _format(mode, "ALLOW", "no calibration data yet for %r -- fail-open" % cap_name)

    if expectation < _THRESHOLD:
        # advisory mode never blocks, but still flags this distinctly (ADVISE
        # rather than plain ALLOW) so iter.py can surface an FYI note to the
        # LLM without adding noise for every high-efficacy/no-data tool call.
        action = "VETO" if mode == "enforce" else "ADVISE"
        return _format(mode, action, "efficacy expectation %.3f < %.2f threshold for %r" % (expectation, _THRESHOLD, cap_name))

    return _format(mode, "ALLOW", "efficacy expectation %.3f >= %.2f threshold for %r" % (expectation, _THRESHOLD, cap_name))


def _safe_atom(cap_name):
    # cap_name comes from the LLM's own chosen tool_name, already validated
    # against INOPS by iter.py before this is ever called -- strip anything
    # that isn't a plain identifier as a defensive measure before it's
    # spliced into MeTTa source text.
    return "".join(ch for ch in str(cap_name) if ch.isalnum() or ch == "_") or "unknown"


def _extract_number(result_text):
    # result_text looks like "[[Grounded(0.289042)]]" on a hit, "[[]]" on no data.
    import re
    m = re.search(r"Grounded\(([-\d.eE]+)\)", str(result_text))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _format(mode, action, detail):
    return "%s|%s|%s" % (mode, action, detail)
