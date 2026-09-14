"""Idle Cycle Detector -- recognizes RECURRING send-discipline gaps across
many cycles, as a pattern, not just the single-turn nag iter.py's
HARD_SEND_STREAK safety net already injects (iter.py:258-300, deliberately
left untouched -- this is an ADDITIVE layer, not a replacement).

Ported from ClarityOmega/soul/idle_cycle_detector.metta's concept (recognize
a recurring cognitive-loop signature), implemented in Python against this
app's real history.metta log rather than through the MeTTa engine, since
pymetta is not installed on this machine (see tools/_metta_gate.py's
docstring) -- matching nace_courier.py's established "Python computes,
MeTTa validates" split.

PROVEN AGAINST REAL DATA (2026-09-14): this exact nag fired 9 times between
09:22 and 09:59 on this machine's live history.metta during one repair
session -- a real, observed recurring pattern, not a hypothetical one.
iter.py's per-turn safety net caught every individual occurrence correctly;
what was missing is recognizing that 9 occurrences in under 40 minutes IS
itself information (a degraded send-discipline pattern under repair-mode
load).

INTEGRATION (organic, not a special-cased writer): when the recurrence
crosses the threshold, this appends ONE `(pending-revision pattern
prioritize_user violated)` line to nace_pending.metta -- the exact same
queue every other belief revision in this app already flows through (see
nace_courier.py). It does NOT write nace_beliefs.metta directly; the
courier's normal cycle (with its own NAL Truth_Revision math and, when the
engine is available, its own live-engine cross-check) picks it up like any
other outcome. `prioritize_user` is an EXISTING compass pattern
(space.metta) -- going silent on the user for an extended, recurring
stretch is a real violation of that pattern, not a new concept -- so this
plants the observation into reasoning that already exists everywhere else,
rather than growing an orphan belief only this file understands.
"""
import os
import re
import time
import json

DESCRIPTION = "Detects recurring send-discipline gaps across cycles (not just single-turn) and records the pattern via the normal pending-revision pipeline"

HISTORY_PATH = "history.metta"
PENDING_PATH = "nace_pending.metta"
STATE_PATH = os.path.join("memory", ".idle_cycle_state.json")

WINDOW_SECONDS = 60 * 60          # look back 1 hour
RECURRENCE_THRESHOLD = 3          # 3+ nag firings inside the window = worth naming as a pattern
RECORD_STEP = 2                   # re-record if it gets at least this much worse since last record

_NAG_RE = re.compile(
    r'^\("([\d-]+ [\d:]+)"\s+"HUMAN_MESSAGE:.*you have gone \d+ tool calls in a row without calling send'
)


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _parse_ts(s):
    try:
        return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def _recent_nag_timestamps(now_ts):
    if not _exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []
    out = []
    for line in lines[-500:]:  # history.metta stays bounded (see AGENTS.md)
        m = _NAG_RE.match(line.strip())
        if not m:
            continue
        ts = _parse_ts(m.group(1))
        if ts is not None and 0 <= now_ts - ts <= WINDOW_SECONDS:
            out.append(ts)
    return out


def _load_state():
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state):
    try:
        os.makedirs("memory", exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _record_pending_violation():
    line = "(pending-revision pattern prioritize_user violated)\n"
    try:
        with open(PENDING_PATH, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass


def transform(messages, tools):
    try:
        now_ts = time.time()
        occurrences = _recent_nag_timestamps(now_ts)
        count = len(occurrences)
        state = _load_state()
        last_recorded = state.get("last_recorded_count", 0)

        if count >= RECURRENCE_THRESHOLD and count - last_recorded >= RECORD_STEP:
            _record_pending_violation()
            state["last_recorded_count"] = count
        elif count < RECURRENCE_THRESHOLD:
            state["last_recorded_count"] = 0

        state["count"] = count
        state["window_s"] = WINDOW_SECONDS
        state["checked_at"] = now_ts
        _save_state(state)

        if count >= RECURRENCE_THRESHOLD:
            note = (
                "\n\n## Idle Cycle Pattern\n"
                "RECURRING PATTERN DETECTED: the 'gone N tool calls without send' safety "
                "message has fired %d times in the last %d minutes. Each individual firing "
                "was handled, but the recurrence itself is a signal -- something about the "
                "current work (likely multi-step repair/self-build) is degrading send "
                "discipline between bursts, not just once. Send shorter, more frequent status "
                "updates proactively rather than waiting for the safety net to force it each "
                "time." % (count, WINDOW_SECONDS // 60)
            )
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = msg.get("content", "") + note
                    break
    except Exception:
        pass
    return messages, tools
