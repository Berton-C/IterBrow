"""Stall Detection - detects when the agent is stuck in repetitive loops."""
import os, json

DESCRIPTION = "Stall detection: detects repetitive loops and injects warnings."

ROOT = "."
STATE_PATH = os.path.join(ROOT, "memory", ".stall_state.json")
TRANSCRIPT_PATH = os.path.join(ROOT, "transcript.txt")

WINDOW_SIZE = 30
REPEAT_THRESHOLD = 3
NOP_THRESHOLD = 5
SILENT_THRESHOLD = 5  # was 15: that let a whole cycle or more of pure self-repair noise pass before even warning

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _parse_transcript_for_calls():
    if not _exists(TRANSCRIPT_PATH):
        return []
    try:
        with open(TRANSCRIPT_PATH, "r") as f:
            lines = f.readlines()
    except:
        return []
    calls = []
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        parts = line.split("]")
        if len(parts) < 2:
            continue
        tool_info = parts[1].strip().lstrip("[")
        tokens = tool_info.split()
        if not tokens:
            continue
        tool_name = tokens[0]
        calls.append(tool_name)
    return calls[-WINDOW_SIZE:]

def _detect_stalls(window):
    warnings = []
    if not window:
        return warnings
    if len(window) >= REPEAT_THRESHOLD:
        last_tool = window[-1]
        recent = window[-REPEAT_THRESHOLD:]
        if all(t == last_tool for t in recent):
            warnings.append("STALL WARNING: tool repeated %d times consecutively. Break the loop." % REPEAT_THRESHOLD)
    nop_count = 0
    for t in reversed(window):
        if t == "nop":
            nop_count += 1
        else:
            break
    if nop_count >= NOP_THRESHOLD:
        warnings.append("STALL WARNING: %d consecutive nop calls. Produce output or take different action." % nop_count)
    return warnings

def _count_silent_calls(window):
    count = 0
    for t in reversed(window):
        if t == "send":
            break
        count += 1
    return count

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools
        window = _parse_transcript_for_calls()
        if not window:
            return messages, tools
        silent_count = _count_silent_calls(window)
        warnings = _detect_stalls(window)
        if silent_count >= SILENT_THRESHOLD:
            warnings.append(
                "STALL WARNING: %d tool calls since last send(). If there is ANY unresolved "
                "user message in the conversation, your very next tool call MUST be send with "
                "a status update — even a short one (\"still working on X, hit a snag with Y\") "
                "— before doing anything else. The user cannot see your other tool calls at all; "
                "silence looks exactly like being unresponsive." % silent_count
            )
        if warnings:
            stall_block = "\n\n## Stall Detection\n" + "\n".join(warnings) + "\n"
            for msg in reversed(messages):
                if msg.get("role") == "system":
                    msg["content"] = msg["content"] + stall_block
                    break
            else:
                if isinstance(messages[0].get("content"), str):
                    messages[0]["content"] = messages[0]["content"] + stall_block
        try:
            with open(STATE_PATH, "w") as f:
                f.write(json.dumps({"window": window, "calls_since_send": silent_count}))
        except:
            pass
    except Exception:
        pass
    return messages, tools
