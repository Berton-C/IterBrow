"""Compatibility entry for completion inquiry, not phase-derived NACE evidence.

A task label or confident phrase establishes neither verified success nor failure.
The existing observation/provenance and support/contradict paths retain NACE
evidence. This hook shares one deduplicated reminder with completion_claim_guard.
"""
try:
    import completion_claim_guard as _ccg
except Exception:
    _ccg = None

DESCRIPTION = "Advisory completion inquiry; task labels never count as learning evidence."

def transform(messages, tools):
    return _ccg.transform(messages, tools) if _ccg is not None else (messages, tools)
