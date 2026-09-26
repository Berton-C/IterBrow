DESCRIPTION = "Save a note in the existing episodic trace. Optional handoff=true carries a short current working account (max 4000 characters) into relevant next turns alongside newer observations. Describe current understanding, supporting evidence, unresolved work and next action, not private reasoning. Update when these change; ordinary notes remain unchanged. A note is interpretation, not proof of completion."
def run(message="", handoff="false"):
    if handoff not in (True, False, "true", "false"):
        return "ERROR: handoff must be true or false; ordinary work is unaffected."
    if handoff is True or handoff == "true":
        if not isinstance(message, str) or not 0 < len(message.strip()) <= 4000:
            return "ERROR: a working handoff needs a nonempty note of at most 4000 characters."
    return "SUCCESS"
