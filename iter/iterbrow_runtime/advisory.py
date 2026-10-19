"""The one-line NACE note a tool result carries in the prompt (docs/milestones/M13_builder_eyes.md A2).

The gate's verdict string and its recorded decision are unchanged; this only shortens what the model reads.
A capability with no track record used to carry ~250 characters of explanation on every result.
"""

MAX_CLAUSE = 160


def short_note(capability, detail):
    """`[NACE: 'x' has no track record yet] `, `[NACE advisory: <first clause>] `, or "" for no detail."""
    text = str(detail or "").strip()
    if not text:
        return ""
    if "trust_stage=candidate" in text:
        return "[NACE: '%s' has no track record yet] " % capability
    for marker in (" -- ", " [decision="):
        if marker in text:
            text = text.split(marker, 1)[0]
    text = text.strip()
    if len(text) > MAX_CLAUSE:
        text = text[:MAX_CLAUSE - 1].rstrip() + "…"
    return "[NACE advisory: %s] " % text
