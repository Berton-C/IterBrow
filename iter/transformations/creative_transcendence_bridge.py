"""Creative Transcendence Bridge -- feeds real evidence into the
previously-dormant `learn_from_experience` NAL compass pattern,
reinterpreted through the flourishing lens the user approved as Creative
Transcendence: does an observed failure become generative material that
changes future behavior, or does it get buried and repeated (the
non-flourishing pole -- entrenchment in mediocrity)?

SIGNAL, NOT A NEW TRACKER: tool_reliability_tracker.py already accumulates
real per-tool NAL (f, c) reliability scores in transformations/.runtime/
tool_reliability.json on every tool call. dynamic_tool_budget.py already
reads that same file each cycle and decides whether to hide a tool from
the model (HIDE_THRESHOLD=0.5, MIN_CALLS_TO_HIDE=3), persisting its
decision to transformations/.runtime/tool_budget.json's "hidden" list.
This file compares the two:

  * a tool has enough evidence of low reliability (f < HIDE_THRESHOLD,
    calls >= MIN_CALLS_TO_HIDE) but tool_budget.json's "hidden" list does
    NOT reflect it -> the system observed the pain but did not adapt.
    Recorded as `violated` (experience accumulated, nothing learned).
  * the same tool IS reflected in "hidden" -> the system's own behavior
    changed as a direct result of accumulated experience. Recorded as
    `confirmed`.

Both HIDE_THRESHOLD/MIN_CALLS_TO_HIDE constants are read directly from
dynamic_tool_budget.py at import time (not duplicated as literals here) so
the two files cannot silently drift apart on what "enough evidence" means.

INTEGRATION: mirrors idle_cycle_detector.py's convention -- one
`(pending-revision pattern learn_from_experience <outcome>)` line into
nace_pending.metta via tools/_provenance.record_pattern_outcome, letting
nace_courier.py's normal NAL Truth_Revision cycle do the math. Never
touches tool_reliability_tracker.py or dynamic_tool_budget.py, never
withholds tools itself (that adaptation is dynamic_tool_budget.py's own
job; this only observes whether it happened).

Dedup: per tool name, only re-records when its evidence/hidden status
actually flips relative to the last recorded state.

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

try:
    import dynamic_tool_budget as _dtb
except Exception:
    _dtb = None

DESCRIPTION = "Feeds real confirmed/violated evidence into the learn_from_experience compass pattern (Creative Transcendence) by checking whether dynamic_tool_budget.py actually adapted (hid) a tool once tool_reliability_tracker.py accumulated enough low-reliability evidence"

RELIABILITY_FILE = os.path.join("transformations", ".runtime", "tool_reliability.json")
BUDGET_FILE = os.path.join("transformations", ".runtime", "tool_budget.json")
STATE_PATH = os.path.join("memory", ".creative_transcendence_state.json")

_DEFAULT_HIDE_THRESHOLD = 0.5
_DEFAULT_MIN_CALLS_TO_HIDE = 3


def _thresholds():
    if _dtb is not None:
        return (getattr(_dtb, "HIDE_THRESHOLD", _DEFAULT_HIDE_THRESHOLD),
                getattr(_dtb, "MIN_CALLS_TO_HIDE", _DEFAULT_MIN_CALLS_TO_HIDE))
    return (_DEFAULT_HIDE_THRESHOLD, _DEFAULT_MIN_CALLS_TO_HIDE)


def _read_json(path):
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


def _hidden_tool_names(budget_data):
    """budget_data["hidden"] entries look like 'name (f=0.20,4 calls)' --
    extract just the leading tool name."""
    names = set()
    for entry in (budget_data or {}).get("hidden", []) or []:
        if isinstance(entry, str):
            names.add(entry.split(" ")[0])
    return names


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools

        reliability = _read_json(RELIABILITY_FILE)
        if not isinstance(reliability, dict) or not reliability:
            return messages, tools
        budget_data = _read_json(BUDGET_FILE) or {}
        hidden_names = _hidden_tool_names(budget_data)
        hide_threshold, min_calls = _thresholds()

        state = _read_json(STATE_PATH) or {}
        last = state.get("last", {})
        changed = False

        for tool_name, s in reliability.items():
            if not isinstance(s, dict):
                continue
            f_val = s.get("f", 0.5)
            calls = s.get("calls", 0)
            if calls < min_calls or f_val >= hide_threshold:
                continue  # not enough low-reliability evidence yet to expect adaptation
            is_hidden = tool_name in hidden_names
            outcome = "confirmed" if is_hidden else "violated"
            if last.get(tool_name) == outcome:
                continue  # already recorded this exact state for this tool
            _prov.record_pattern_outcome("learn_from_experience", outcome)
            last[tool_name] = outcome
            changed = True

        if changed:
            state["last"] = last
            _write_json(STATE_PATH, state)
    except Exception:
        pass
    return messages, tools
