"""Distinguish runner controls from conversation without rewriting history."""
import re


CONTROL_PATTERNS = (
    "[NO ADDITIONAL", "[TASK COMPLETED", "[NO NEW USER", "[TOOL LIMIT",
    "[MEMORY FOLDER", "[OUTPUT TOKEN", "[YOUR PREVIOUS", "[NOT DELIVERED",
    "[ALARM]", "[URGENT — THIS OVERRIDES EVERYTHING ELSE THIS TURN:",
)
STEP = re.compile(r"^Step \d{4}-\d\d-\d\d \d\d:\d\d:\d\d: ")
RECORD = re.compile(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\]\[(user|send -> [^\]]*)\] (.*)")


def is_runner_control(content):
    # Match the runner envelope, not a user's quotation of an old instruction.
    return isinstance(content, str) and STEP.sub("", content, count=1).startswith(CONTROL_PATTERNS)


def conversation_lines(lines):
    """Omit historical control records, including their continuation lines."""
    visible = []
    control = False
    for line in lines:
        record = RECORD.match(line)
        if record:
            control = record[1] == "user" and is_runner_control(record[2])
        if not control:
            visible.append(line)
    return visible
