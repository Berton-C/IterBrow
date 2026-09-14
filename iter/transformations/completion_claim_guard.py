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
"""
import re

DESCRIPTION = "Flags likely-premature completion claims in the previous assistant turn against task_state.metta's recorded phases"

TASK_STATE_PATH = "task_state.metta"
_CLAIM_RE = re.compile(
    r"\b(already exists|is now (live|done|complete|built)|has been (built|created|verified)|"
    r"tab \d+ (is|exists)|successfully (built|created|verified)|verified as)\b",
    re.IGNORECASE,
)
_PHASE_RE = re.compile(r'\(task-phase "([^"]*)" ([a-z]+)')


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


def transform(messages, tools):
    try:
        last_assistant = None
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    last_assistant = content
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
                "acts on it."
            )
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = msg.get("content", "") + note
                    break
    except Exception:
        pass
    return messages, tools
