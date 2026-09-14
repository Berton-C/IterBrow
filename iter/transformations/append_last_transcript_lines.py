"""
Append last 6 transcript lines to the system message.
Reads transcript.txt, takes last 6 lines, appends them
after a "transcript:" header to the first message (system message) content.
"""
import os



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Append last 6 transcript lines to system message."

TRANSCRIPT_PATH = "transcript.txt"
NUM_LINES = 6

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools

        if not _exists(TRANSCRIPT_PATH):
            return messages, tools

        with open(TRANSCRIPT_PATH, "r") as f:
            lines = f.readlines()

        last_lines = lines[-NUM_LINES:] if len(lines) >= NUM_LINES else lines
        transcript_block = "transcript:\n" + "".join(last_lines).rstrip()

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
