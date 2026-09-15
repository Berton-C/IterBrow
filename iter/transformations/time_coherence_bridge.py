"""Time Coherence Bridge -- feeds real evidence into the previously-
dormant `backup_before_change` NAL compass pattern, reinterpreted through
the flourishing lens the user approved as Time Coherence: irreversibility
smuggled through under time pressure is exactly an un-backed-up change.

SIGNAL: tools/soul_lock.py already implements the real backup/rollback
transaction (begin -> backup -> mutate -> commit/rollback) for the
soul-namespace files listed in its own SOUL_FILES -- see nace_courier.py's
own use of it (STAGE 4, 2026-09-14) as the reference caller. This file
reads memory/soul_lock.json (soul_lock's own persisted lock record) rather
than re-implementing any locking logic:

  * status == "locked" and the lock has been held past STALE_SECONDS ->
    an in-flight mutation was begun but never committed or rolled back --
    a backup was taken but the change was abandoned mid-transaction, the
    exact "irreversibility smuggled through under time pressure" pattern
    the user named. Recorded as `violated`.
  * a previously-stuck lock clears (status flips back to "unlocked") ->
    the transaction eventually resolved cleanly. Recorded as `confirmed`
    once, not every cycle, since a normal healthy unlocked state carries
    no signal on its own (most cycles never touch soul_lock at all).

INTEGRATION: mirrors idle_cycle_detector.py's convention -- one
`(pending-revision pattern backup_before_change <outcome>)` line into
nace_pending.metta via tools/_provenance.record_pattern_outcome, letting
nace_courier.py's normal NAL Truth_Revision cycle do the math. Never reads
or writes soul_lock.json's contents beyond the status/timestamp fields it
already publishes, never touches the lock itself, never withholds tools.

Fails open on any error -- never blocks dispatch, never raises.
"""
import os
import sys
import json
import time

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    import _provenance as _prov
except Exception:
    _prov = None

DESCRIPTION = "Feeds real confirmed/violated evidence into the backup_before_change compass pattern (Time Coherence) by watching soul_lock.json for abandoned (stuck) transactions"

LOCK_PATH = os.path.join("memory", "soul_lock.json")
STATE_PATH = os.path.join("memory", ".time_coherence_state.json")
STALE_SECONDS = 300  # 5 minutes held with no commit/rollback = abandoned, not just slow


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


def _lock_age_seconds(lock, now_ts):
    ts = lock.get("timestamp")
    if ts is None:
        return None
    try:
        # soul_lock.py writes timestamp via time.time() convention used
        # elsewhere in this codebase (nace_courier, idle_cycle_detector);
        # accept either an epoch float/int or a strptime-able string.
        if isinstance(ts, (int, float)):
            return now_ts - float(ts)
        return now_ts - time.mktime(time.strptime(str(ts), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None


def transform(messages, tools):
    try:
        if _prov is None or not isinstance(messages, list) or not messages:
            return messages, tools
        if not os.path.exists(LOCK_PATH):
            return messages, tools

        lock = _read_json(LOCK_PATH)
        if not isinstance(lock, dict):
            return messages, tools

        state = _read_json(STATE_PATH) or {}
        was_stuck = bool(state.get("stuck"))
        now_ts = time.time()

        status = lock.get("status", "unlocked")
        if status == "locked":
            age = _lock_age_seconds(lock, now_ts)
            if age is not None and age >= STALE_SECONDS:
                if not was_stuck:
                    _prov.record_pattern_outcome("backup_before_change", "violated")
                    note = (
                        "\n\n## Time Coherence (backup_before_change)\n"
                        "soul_lock.json has been held locked for over %d minutes with no commit/"
                        "rollback -- an in-flight soul-namespace change was begun but abandoned "
                        "mid-transaction. Recorded as 'violated' against backup_before_change "
                        "(Time Coherence). If this lock is truly stuck, resolve or clear it before "
                        "further soul-namespace writes." % (STALE_SECONDS // 60)
                    )
                    for msg in reversed(messages):
                        if isinstance(msg, dict) and msg.get("role") == "system":
                            msg["content"] = msg.get("content", "") + note
                            break
                state["stuck"] = True
                _write_json(STATE_PATH, state)
        else:
            if was_stuck:
                _prov.record_pattern_outcome("backup_before_change", "confirmed")
            state["stuck"] = False
            _write_json(STATE_PATH, state)
    except Exception:
        pass
    return messages, tools
