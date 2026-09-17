"""Mode Signal Bridge -- first slice of the add/subtract/loosen layer:
three generative postures IterBrow can show up with, arrived at by
collapsing the 9 flourishing compass patterns to a higher level rather
than gating on any one of them individually (Muse Mode = add, Stillness
Mode = subtract, and a third dissolving move = loosen). This file wires
exactly ONE real, honest signal for ONE posture -- `loosen` -- into a NEW
NAL belief prefix (`mode-signal`), reusing nace_courier.py's existing
Truth_Revision engine completely unchanged.

GROUNDING: CognitiveResilience's own documented activation-signal (Miter's
constitution/soul_compass.metta:21) names "repeated confident closure" as
exactly the moment this posture answers -- certainty asserted again
without new evidence, the capture-pole moment where "distinctions and
alternatives" have narrowed (soul_compass.metta:25, gap-signature). This
bridge is an honest first-pass proxy for that signal, not a finished
detector: it counts a small, explicit list of absolute/closure-language
markers in the HUMAN's own turns (never the agent's own language), and
looks for that count staying high across consecutive turns -- mirroring
wonder_preservation_bridge.py's window-based transition convention
(record only on a change of state, not every cycle, so a long stretch of
closed language can never double-count itself).

WHAT THIS IS NOT: not a gate, not a violation, not a scored judgment of
the user, and not a claim that keyword-counting is a good measure of
"repeated confident closure" -- it is a small, cheap, legible stand-in
for it, chosen so this first slice is something concrete to look at
rather than a design document. It produces zero user-facing output on
its own: it only revises one NAL belief (`mode-signal:mode_loosen`) via
the exact same nal_revise/nal_expectation math nace_courier.py already
runs for the 9 compass patterns, and lets the courier's own summary line
(see nace_courier.py's OPENING branch, added alongside this file) decide
whether the session's running tendency is confident enough to mention to
the generation as something to be aware of. The generation stays free to
do nothing with it -- there is no tool to withhold, nothing blocked.

STILL A STUB, ON PURPOSE: only `loosen` is wired. `add` and `subtract`
need their own sensors (openness/curiosity density for add; velocity/
cadence for subtract) and are deliberately left for a second slice once
this one has been looked at, not invented here to pad it out.

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

DESCRIPTION = (
    "First slice of the add/subtract/loosen mode-signal layer: feeds a "
    "real, honest 'repeated confident closure' proxy (a small closure-"
    "language marker count, held across consecutive human turns) into a "
    "new mode-signal:mode_loosen NAL belief via the existing Truth_Revision "
    "pipeline -- never a gate, never scored at the user, purely evidence "
    "the generation may or may not act on."
)

STATE_PATH = os.path.join("memory", ".mode_signal_state.json")

# A small, explicit, honestly-incomplete list -- a first-pass proxy for
# "confident closure" language, not an attempt to enumerate every case.
# Deliberately short so this stays a structural signal, not a growing
# longtail of special-cased phrases.
CLOSURE_MARKERS = [
    "always", "never", "obviously", "clearly", "definitely", "certainly",
    "must", "have to", "no doubt", "impossible", "the only way", "simply",
]
MARKER_THRESHOLD = 2   # distinct markers in one turn to count that turn as "closed"
WINDOW = 2             # consecutive human turns required to call it "repeated"


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


def _closure_count(text):
    if not isinstance(text, str) or not text:
        return 0
    lowered = text.lower()
    return sum(1 for marker in CLOSURE_MARKERS if marker in lowered)


def _human_turns(messages):
    out = []
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            out.append(msg.get("content", ""))
    return out


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools

        human_turns = _human_turns(messages)
        if not human_turns:
            return messages, tools

        latest = human_turns[-1]
        closed_now = _closure_count(latest) >= MARKER_THRESHOLD

        state = _read_json(STATE_PATH) or {}
        window = state.get("window", [])
        window.append(bool(closed_now))
        window = window[-WINDOW:]
        state["window"] = window

        repeated_now = len(window) >= WINDOW and all(window)
        was_repeated = bool(state.get("repeated"))

        # Transition-only recording, mirroring wonder_preservation_bridge.py --
        # a long closed stretch is one event, not one event per cycle.
        if repeated_now and not was_repeated:
            _prov.record_pattern_outcome("mode_loosen", "confirmed", rtype="mode")
            state["repeated"] = True
        elif not repeated_now and was_repeated:
            _prov.record_pattern_outcome("mode_loosen", "disconfirmed", rtype="mode")
            state["repeated"] = False

        _write_json(STATE_PATH, state)
    except Exception:
        pass
    return messages, tools
