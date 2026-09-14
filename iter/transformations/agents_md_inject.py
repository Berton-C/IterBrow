"""
Auto-inject AGENTS.md content into the system message.

Reads AGENTS.md and appends it to the first message (system message).
If the file exceeds MAX_CHARS, it is truncated to the last MAX_CHARS characters
(preserving the most recent / bottom content, which tends to be more relevant).
"""
import os

DESCRIPTION = "Auto-inject AGENTS.md reference into system message."

AGENTS_MD_PATH = "AGENTS.md"
MAX_CHARS = 6000  # cap to avoid eating too much context

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools

        if not _exists(AGENTS_MD_PATH):
            return messages, tools

        with open(AGENTS_MD_PATH, "r") as f:
            content = f.read().strip()

        if len(content) > MAX_CHARS:
            content = "...(truncated, showing last {} chars)...\n".format(MAX_CHARS) + content[-MAX_CHARS:]

        header = "\n\n--- AGENTS.md (auto-included) ---\n"
        block = header + content

        first_msg = messages[0]
        if isinstance(first_msg, dict):
            fc = first_msg.get("content", "")
            if isinstance(fc, str):
                first_msg["content"] = fc.rstrip() + block
            elif isinstance(fc, list):
                first_msg["content"] = fc + [{"type": "text", "text": block}]

    except Exception:
        pass

    return messages, tools
