"""Wonder Preservation Bridge -- feeds real evidence into the previously-
dormant `explore_with_purpose` NAL compass pattern, reinterpreted through
the flourishing lens the user approved as Wonder Preservation: purposeful
exploration resisting flattening into rigid, checklist-style repetition.
Getting stuck repeating the exact same move over and over IS that
flattening; breaking out of it into a genuinely different approach is
purposeful exploration reasserting itself.

SIGNAL, NOT A NEW STALL DETECTOR: stall_detect.py already detects and
persists this exact signal every cycle to memory/.stall_state.json (same
tool repeated REPEAT_THRESHOLD+ times consecutively, or NOP_THRESHOLD+
consecutive no-ops) -- this file only reads that state across consecutive
cycles rather than re-parsing transcript.txt itself, so the two detectors
can never disagree about what a "stall" is.

  * stall_detect.py's own window shows the SAME repeated-tool stall
    persisting across two consecutive checks (not just flagged once) ->
    the rigid loop continued rather than being broken. Recorded as
    `violated`.
  * a stall was previously recorded as persisting, and the current window
    no longer shows it (last tool changed, or a `send` closed the loop) ->
    the loop was broken by a genuinely different move. Recorded as
    `confirmed`.

INTEGRATION: mirrors idle_cycle_detector.py's convention -- one
`(pending-revision pattern explore_with_purpose <outcome>)` line into
nace_pending.metta via tools/_provenance.record_pattern_outcome, letting
nace_courier.py's normal NAL Truth_Revision cycle do the math. Never
touches stall_detect.py itself, never withholds tools or duplicates its
warning note.

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

DESCRIPTION = "Feeds real confirmed/violated evidence into the explore_with_purpose compass pattern (Wonder Preservation) by watching stall_detect.py's own persisted state across consecutive cycles for a rigid loop that continues vs. one that gets broken"

STALL_STATE_PATH = os.path.join("memory", ".stall_state.json")
STATE_PATH = os.path.join("memory", ".wonder_preservation_state.json")
REPEAT_THRESHOLD = 3  # mirrors stall_detect.py's own REPEAT_THRESHOLD


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


def _is_stalled(window):
    if not window or len(window) < REPEAT_THRESHOLD:
        return False
    last_tool = window[-1]
    recent = window[-REPEAT_THRESHOLD:]
    return all(t == last_tool for t in recent) and last_tool != "send"


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools

        stall_state = _read_json(STALL_STATE_PATH)
        if not isinstance(stall_state, dict):
            return messages, tools
        window = stall_state.get("window", [])
        currently_stalled = _is_stalled(window)

        state = _read_json(STATE_PATH) or {}
        was_stalled = bool(state.get("stalled"))

        if currently_stalled:
            if was_stalled:
                # Persisted across two consecutive checks -- a real
                # continuing loop, not just one snapshot catching it once.
                fingerprint = "violated:%s:%d" % (window[-1] if window else "", len(window))
                if state.get("last_fingerprint") != fingerprint:
                    _prov.record_pattern_outcome("explore_with_purpose", "violated")
                    state["last_fingerprint"] = fingerprint
            state["stalled"] = True
        else:
            if was_stalled:
                _prov.record_pattern_outcome("explore_with_purpose", "confirmed")
                state["last_fingerprint"] = "confirmed:%d" % len(window)
            state["stalled"] = False

        _write_json(STATE_PATH, state)
    except Exception:
        pass
    return messages, tools
