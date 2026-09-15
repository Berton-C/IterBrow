"""Attention Stewardship Bridge -- feeds real evidence into the previously-
dormant `conserve_cycles` NAL compass pattern, reinterpreted through the
flourishing lens the user approved as Attention Stewardship: compute and
attention are a shared finite resource, not something to extract from
without limit.

SIGNAL, NOT A NEW BUDGET: dynamic_tool_budget.py already computes a real
per-cycle tool-call budget each turn (from reliability, stall, and memory
pressure signals) and persists it to transformations/.runtime/tool_budget.
json. Rather than inventing a second budget concept, this file compares
that EXISTING computed budget against the ACTUAL number of tool calls made
since the last `send` (parsed from transcript.txt the same way stall_
detect.py already does), only at a natural boundary -- the cycle that just
ended with a `send` call, so a mid-stream read never mistakes "not done
yet" for "went over budget".

  * actual calls since send > budget * OVERSPEND_RATIO -> the computed
    budget existed and was exceeded by a real margin. Recorded as
    `violated` (attention/compute spent past what the system's own signals
    said was warranted).
  * actual calls since send <= budget -> spent within the resource
    envelope the system itself computed. Recorded as `confirmed`.

Both are throttled to at most once per completed cycle (tracked by the
transcript window's own length, mirroring stall_detect's window concept)
so this never double-records the same cycle twice.

INTEGRATION: mirrors idle_cycle_detector.py's convention -- one
`(pending-revision pattern conserve_cycles <outcome>)` line into
nace_pending.metta via tools/_provenance.record_pattern_outcome, letting
nace_courier.py's normal NAL Truth_Revision cycle do the math. Never
touches dynamic_tool_budget.py's own budget/hiding logic, never withholds
tools.

Fails open on any error -- never blocks dispatch, never raises.
"""
import os
import sys
import json

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    import _provenance as _prov
except Exception:
    _prov = None

DESCRIPTION = "Feeds real confirmed/violated evidence into the conserve_cycles compass pattern (Attention Stewardship) by comparing dynamic_tool_budget.py's computed budget against actual tool-call spend per cycle"

BUDGET_FILE = os.path.join("transformations", ".runtime", "tool_budget.json")
TRANSCRIPT_PATH = "transcript.txt"
STATE_PATH = os.path.join("memory", ".attention_stewardship_state.json")
OVERSPEND_RATIO = 1.5
WINDOW_SIZE = 60


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _read_json(path):
    if not _exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path, data):
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


def _parse_transcript_tail():
    """Mirrors stall_detect.py's own transcript parsing convention:
    [timestamp] [tool_name args...] lines, tail-windowed."""
    if not _exists(TRANSCRIPT_PATH):
        return []
    try:
        with open(TRANSCRIPT_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []
    calls = []
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        parts = line.split("]")
        if len(parts) < 2:
            continue
        tool_info = parts[1].strip().lstrip("[")
        tokens = tool_info.split()
        if not tokens:
            continue
        calls.append(tokens[0])
    return calls[-WINDOW_SIZE:]


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools

        window = _parse_transcript_tail()
        if not window or window[-1] != "send":
            # Only judge a completed cycle -- one that just ended in send.
            return messages, tools

        budget_data = _read_json(BUDGET_FILE)
        if not isinstance(budget_data, dict) or "budget" not in budget_data:
            return messages, tools
        budget = budget_data.get("budget")
        if not isinstance(budget, (int, float)) or budget <= 0:
            return messages, tools

        # window[-1] is "send"; count calls before it back to the previous send
        actual = 0
        for t in reversed(window[:-1]):
            if t == "send":
                break
            actual += 1

        state = _read_json(STATE_PATH) or {}
        fingerprint = "%d:%d" % (len(window), actual)
        if state.get("last_fingerprint") == fingerprint:
            return messages, tools
        state["last_fingerprint"] = fingerprint

        if actual > budget * OVERSPEND_RATIO:
            _prov.record_pattern_outcome("conserve_cycles", "violated")
        elif actual <= budget:
            _prov.record_pattern_outcome("conserve_cycles", "confirmed")
        _write_json(STATE_PATH, state)
    except Exception:
        pass
    return messages, tools
