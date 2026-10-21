DESCRIPTION = (
    'Save a note in the episodic trace. handoff=true carries a short working account (max 4000 chars: '
    'understanding, evidence, open work, next action) into the next turns. A note is interpretation, not '
    'proof of completion.'
)
def run(message="", handoff="false"):
    if handoff not in (True, False, "true", "false"):
        return "ERROR: handoff must be true or false; ordinary work is unaffected."
    if handoff is True or handoff == "true":
        if not isinstance(message, str) or not 0 < len(message.strip()) <= 4000:
            return "ERROR: a working handoff needs a nonempty note of at most 4000 characters."
    return "SUCCESS"
