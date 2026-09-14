"""Completion Claim Guard -- checks the LAST assistant message for
completion-style language ('already exists', 'is now live', 'verified',
'built', 'complete') and cross-checks it against task_state.metta's most
recently recorded phase. A transformation runs BEFORE the next generation,
not as an outgoing filter on the message that was just sent -- so this
cannot block a premature claim before it goes out, but it closes the loop
within one cycle instead of waiting for the user to catch it, which is what
actually happened in the real incident below.

REAL INCIDENT (2026-09-14, episode 36): a completion claim ("the founder
toolkit tab already exists") was sent before the tab had actually been
built. The user caught it, not the system. This is the concrete evidence
this transformation exists to act on.

STAGE 5 (2026-09-14): this used to be advisory-only (append a note, never
enforce). It now has real severing power: when an unverified completion
claim is detected, it removes "send" from the tools offered for the very
next model call, so the model literally cannot repeat/reaffirm the claim to
the user until it does something else first (check task_state, verify,
correct itself). This is bounded to exactly one upcoming call -- it is
recomputed fresh from `messages` on every transform() call, so once a new
non-claim assistant message appears (e.g. after the model calls task_state
to mark verifying/complete), the gate clears on its own. It also fails open
in two ways: (1) any internal error returns the tools unchanged rather than
risking a silent lockout, and (2) it will not strip "send" once the
assistant is already close to iter.py's HARD_SEND_STREAK check-in threshold
(see _recent_silent_streak below) -- so this can never combine with that
safety net to leave the user in total silence.
"""
import re

DESCRIPTION = "Flags likely-premature completion claims in the previous assistant turn against task_state.metta's recorded phases, and withholds send for one cycle until they're addressed"

TASK_STATE_PATH = "task_state.metta"
_CLAIM_RE = re.compile(
    r"\b(already exists|is now (live|done|complete|built)|has been (built|created|verified)|"
    r"tab \d+ (is|exists)|successfully (built|created|verified)|verified as)\b",
    re.IGNORECASE,
)
_PHASE_RE = re.compile(r'\(task-phase "([^"]*)" ([a-z]+)')
# Mirrors iter.py's own HARD_SEND_STREAK=3 hard safety net (silent_streak >= 3
# forces a send-only check-in). We stay at least one cycle clear of that so
# this gate and that safety net can never both demand mutually exclusive
# things of the same turn.
_HARD_SEND_STREAK = 3
_SAFE_MARGIN = 1


def _latest_phases():
    try:
        with open(TASK_STATE_PATH, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return {}
    latest = {}
    for m in _PHASE_RE.finditer(content):
        latest[m.group(1)] = m.group(2)
    return latest


def _recent_silent_streak(messages):
    """Best-effort mirror of iter.py's silent_streak: walk assistant turns
    from the end backwards, counting consecutive ones with no "send" tool
    call. Stops counting (returns early) at the first "send" call found.
    Never raises -- any unexpected shape just yields 0 (treated as safe)."""
    streak = 0
    try:
        for msg in reversed(messages):
            if not isinstance(msg, dict) or msg.get("role") != "assistant":
                continue
            calls = msg.get("tool_calls") or []
            names = []
            for call in calls:
                fn = call.get("function") if isinstance(call, dict) else None
                if isinstance(fn, dict) and fn.get("name"):
                    names.append(fn["name"])
            if "send" in names:
                break
            streak += 1
    except Exception:
        return 0
    return streak


def transform(messages, tools):
    try:
        last_assistant = None
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                msg_content = msg.get("content", "")
                if isinstance(msg_content, str) and msg_content.strip():
                    last_assistant = msg_content
                break
        if not last_assistant or not _CLAIM_RE.search(last_assistant):
            return messages, tools

        phases = _latest_phases()
        verified_recent = any(p in ("verifying", "complete") for p in phases.values())
        if not verified_recent:
            note = (
                "\n\n## Completion Claim Guard\n"
                "Your previous message used completion-style language (e.g. 'already exists', "
                "'is now live', 'verified'), but task_state.metta has no task currently recorded "
                "at phase verifying/complete. This is the exact pattern behind the 2026-09-14 "
                "founder-toolkit-tab mistake (claimed before built, caught by the user). If that "
                "claim was accurate, call task_state(action='set', phase='verifying'|'complete') "
                "to record it. If you are not certain it is true, verify it now before the user "
                "acts on it. send has been withheld this turn until you do one of those -- it "
                "returns as soon as you take a real step, not on a timer."
            )
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = msg.get("content", "") + note
                    break

            # STAGE 5 enforcement: actually withhold send, not just ask nicely --
            # unless doing so would collide with iter.py's own HARD_SEND_STREAK
            # check-in safety net, in which case we fail open and leave tools
            # untouched (that safety net's job -- keeping the user from total
            # silence -- always wins).
            if _recent_silent_streak(messages) < (_HARD_SEND_STREAK - _SAFE_MARGIN):
                tools = [t for t in tools if not (
                    isinstance(t, dict) and t.get("function", {}).get("name") == "send"
                )]
    except Exception:
        pass
    return messages, tools
