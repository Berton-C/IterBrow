"""Cognitive Resilience Guard -- escalation layer above idle_cycle_detector.

idle_cycle_detector.py recognizes a RECURRING send-discipline gap and feeds
it into the normal pending-revision belief pipeline. This module reads the
same detection state and, once the pattern crosses a HIGHER, severe bar,
raises a governance flag that transformations/auto_improve.py's self-build
trigger checks before setting memory/.improve_needed -- i.e. if the
system's own send-discipline is currently degraded, self-directed growth
work defers until service to the present user thread is demonstrably
stable again, rather than compounding a service gap with more autonomous
activity. This is Item 4's "service-before-growth" rule in its one concrete
enforcement path (see self_map.metta for the MeTTa-side documentation of
the rule).

PROVEN AGAINST REAL DATA (2026-09-14): the real recurrence count observed on
this machine's history.metta was 9 occurrences in ~40 minutes -- well above
SEVERE_THRESHOLD (5) below. Had this guard been active during that session,
it would have deferred any concurrent self-build proposal rather than
letting it run in parallel with an active send-discipline gap.
"""
import os
import json
import time

DESCRIPTION = "Escalates a severe/recurring send-discipline pattern into a governance deferral flag consumed by auto_improve.py's build-trigger path"

STATE_PATH = os.path.join("memory", ".idle_cycle_state.json")
FLAG_PATH = os.path.join("memory", ".service_before_growth_flag.json")
SEVERE_THRESHOLD = 5        # occurrences within idle_cycle_detector's window
FLAG_TTL_SECONDS = 30 * 60  # deferral auto-expires so a stale flag can't wedge growth forever


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def transform(messages, tools):
    try:
        if not _exists(STATE_PATH):
            return messages, tools
        with open(STATE_PATH, "r") as f:
            state = json.load(f)
        count = state.get("count", 0)
        now_ts = time.time()

        if count >= SEVERE_THRESHOLD:
            flag = {
                "reason": "recurring send-discipline gap (%d occurrences)" % count,
                "set_at": now_ts,
                "expires_at": now_ts + FLAG_TTL_SECONDS,
            }
            try:
                os.makedirs("memory", exist_ok=True)
                with open(FLAG_PATH, "w") as f:
                    json.dump(flag, f)
            except Exception:
                pass
            note = (
                "\n\n## Cognitive Resilience Guard\n"
                "SEVERE: the send-discipline pattern has recurred %d times recently -- this "
                "crosses the service-before-growth threshold. Any self-directed build/"
                "self-improve proposal is now deferred (memory/.service_before_growth_flag.json) "
                "until a clean stretch of responsive send() behavior re-establishes that the "
                "current user thread is being served. Prioritize a direct, honest status "
                "update to the user right now over any further autonomous building." % count
            )
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = msg.get("content", "") + note
                    break
        else:
            # Clear a stale flag once the pattern has genuinely subsided --
            # a bad stretch should not defer growth forever.
            if _exists(FLAG_PATH):
                try:
                    os.remove(FLAG_PATH)
                except Exception:
                    pass
    except Exception:
        pass
    return messages, tools
