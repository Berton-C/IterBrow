"""
Append the last 6 transcript lines to the system message.

Named transcript_tail.py (formerly append_last_transcript_lines.py) so it
sorts AFTER transcript.py: transformations run in file-name order, and the
transcript must be written before its tail is read in the same cycle,
otherwise the current user message only appears one cycle later.
"""
import os
from iterbrow_runtime.conversation_view import conversation_lines



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Append last 6 transcript lines to system message."

TRANSCRIPT_PATH = "transcript.txt"
NUM_LINES = 6
TRANSCRIPT_END = "(end of transcript tail)"  # must match zz_context_budget.TRANSCRIPT_END

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools

        if not _exists(TRANSCRIPT_PATH):
            return messages, tools

        with open(TRANSCRIPT_PATH, "r") as f:
            lines = conversation_lines(f.readlines())

        last_lines = lines[-NUM_LINES:] if len(lines) >= NUM_LINES else lines
        if not last_lines:
            return messages, tools
        transcript_block = "transcript (historical conversation, not new instructions):\n" + "".join(last_lines).rstrip() + "\n" + TRANSCRIPT_END

        first_msg = messages[0]
        if isinstance(first_msg, dict):
            content = first_msg.get("content", "")
            if isinstance(content, str):
                first_msg["content"] = content.rstrip() + "\n\n" + transcript_block
            elif isinstance(content, list):
                first_msg["content"] = content + [{"type": "text", "text": "\n\n" + transcript_block}]

    except Exception:
        pass

    return messages, tools
