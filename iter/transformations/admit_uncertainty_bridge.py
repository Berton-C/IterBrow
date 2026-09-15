"""Completion-Claim Evidence Bridge -- feeds real evidence into TWO
previously-underweighted NAL compass patterns from the ONE signal
completion_claim_guard.py already computes, reinterpreted through the
flourishing lens the user approved:

  * admit_uncertainty  -> Cognitive Resilience (was fully dormant: zero
    producers anywhere in the codebase before this file)
  * verify_before_claiming -> Shared Understanding (already has a producer,
    provenance_guard.py, but that one only watches CODE WRITES; this adds
    a second, independent producer watching CHAT CLAIMS -- a different
    observable surface of the same underlying pattern, not a duplicate)

WHY ONE SIGNAL, TWO PATTERNS: completion_claim_guard.py's own check --
does the last assistant message use completion-style language ("already
exists", "is now live", "verified", ...) while task_state.metta has NO
task recorded at phase verifying/complete? -- is genuinely one real-world
moment read two ways. Asserting something as done without having checked
it is simultaneously (a) a failure to verify before claiming, and (b) a
failure to admit the uncertainty that was actually still there. The
2026-09-14 founder-toolkit-tab incident that motivated completion_claim_
guard.py in the first place is a real instance of both at once. Feeding
both patterns from the one mechanical fact is honest about that overlap,
not padding -- it is NOT a second independent check invented to look more
thorough.

NOT A NEW DETECTOR: this deliberately imports completion_claim_guard's own
compiled `_CLAIM_RE` pattern and `_latest_phases()` helper rather than
re-implementing the regex/phase-check, so the two files can never drift
apart. completion_claim_guard.py itself is left completely untouched (it
already has real Stage-5 enforcement power -- withholding `send` -- and is
deployed/tested; this file only adds an evidence feed alongside it,
purely advisory, no enforcement change).

INTEGRATION: mirrors idle_cycle_detector.py's established convention --
plant `(pending-revision pattern <name> <outcome>)` lines into
nace_pending.metta via tools/_provenance.record_pattern_outcome (the same
shared append helper provenance_guard.py already uses) and let
nace_courier.py's normal NAL Truth_Revision cycle do the math. Never
writes nace_beliefs.metta directly, never touches `tools`.

Dedup: keyed on a hash of (last assistant message text, phase snapshot) so
the same unresolved claim is not re-recorded every single cycle it stays
unresolved -- only once per distinct state, mirroring provenance_guard's
per-call-id processed set.

Fails open on any error -- never blocks dispatch, never raises.
"""
import os
import sys
import json
import hashlib

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    import _provenance as _prov
except Exception:
    _prov = None

try:
    import completion_claim_guard as _ccg
except Exception:
    _ccg = None

DESCRIPTION = "Feeds real confirmed/violated evidence into admit_uncertainty (Cognitive Resilience) and a second producer for verify_before_claiming (Shared Understanding), reusing completion_claim_guard's own claim-vs-phase check"

STATE_PATH = os.path.join("memory", ".admit_uncertainty_state.json")
STATE_MAX_ENTRIES = 200
_PATTERNS = ("admit_uncertainty", "verify_before_claiming")


def _load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict) or not isinstance(state.get("processed"), list):
            return {"processed": []}
        return state
    except Exception:
        return {"processed": []}


def _save_state(state):
    try:
        os.makedirs("memory", exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def transform(messages, tools):
    try:
        if _prov is None or _ccg is None or not isinstance(messages, list) or not messages:
            return messages, tools

        last_assistant = None
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    last_assistant = content
                break
        if not last_assistant or not _ccg._CLAIM_RE.search(last_assistant):
            return messages, tools

        phases = _ccg._latest_phases()
        verified_recent = any(p in ("verifying", "complete") for p in phases.values())

        fingerprint = hashlib.sha1(
            (last_assistant.strip() + "|" + json.dumps(phases, sort_keys=True)).encode("utf-8", "replace")
        ).hexdigest()[:16]

        state = _load_state()
        processed = set(state.get("processed", []))
        if fingerprint in processed:
            return messages, tools

        outcome = "confirmed" if verified_recent else "violated"
        for pattern_name in _PATTERNS:
            _prov.record_pattern_outcome(pattern_name, outcome)

        processed.add(fingerprint)
        state["processed"] = list(processed)
        if len(state["processed"]) > STATE_MAX_ENTRIES:
            state["processed"] = state["processed"][-STATE_MAX_ENTRIES:]
        _save_state(state)

        if outcome == "violated":
            note = (
                "\n\n## Admit Uncertainty / Verify Before Claiming\n"
                "Your last message used confident completion language without a recorded "
                "verifying/complete phase -- recorded as a 'violated' observation against both "
                "the admit_uncertainty (Cognitive Resilience) and verify_before_claiming (Shared "
                "Understanding) patterns (nace_pending.metta -> nace_beliefs.metta). This is "
                "advisory, not a block: naming what you haven't checked yet is the flourishing "
                "move here, not asserting it as settled."
            )
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "system":
                    msg["content"] = msg.get("content", "") + note
                    break
    except Exception:
        pass
    return messages, tools
