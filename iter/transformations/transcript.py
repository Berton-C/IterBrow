"""
Transcript - persists all textual communication messages (user + assistant send)
to a queryable file. Excludes control messages injected by iter.py.
State = string keys of current context window messages only (like history.py).
"""
import os, json, time



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Maintains transcript of textual communication messages only."
LOG_PATH = "transcript.txt"
STATE_PATH = ".transcript_state"

CONTROL_PATTERNS = [
    "[NO ADDITIONAL",
    "[TASK COMPLETED",
    "[NO NEW USER",
    "[TOOL LIMIT",
    "[MEMORY FOLDER",
    "[OUTPUT TOKEN",
    "[YOUR PREVIOUS",
    "[NOT DELIVERED",
    "[ALARM]",
]

def _is_control(content):
    return any(p in content for p in CONTROL_PATTERNS)

def _timestamp():
    current = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (
        current[0], current[1], current[2], current[3], current[4], current[5]
    )

def _step_timestamp(content):
    if isinstance(content, str) and content.startswith("Step ") and len(content) >= 24:
        return content[5:24]
    return None

def transform(messages, tools):
    try:
        prev_keys = set()
        if _exists(STATE_PATH):
            with open(STATE_PATH) as f:
                prev_keys = set(l.strip() for l in f if l.strip())

        current_keys = set()
        lines_to_write = []

        tool_times = {}
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "tool":
                timestamp = _step_timestamp(msg.get("content", ""))
                if timestamp and msg.get("tool_call_id"):
                    tool_times[msg.get("tool_call_id")] = timestamp

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user" and isinstance(content, str) and content.strip():
                if _is_control(content):
                    continue
                key = "u:" + content
                current_keys.add(key)
                if key not in prev_keys:
                    timestamp = _step_timestamp(content) or _timestamp()
                    lines_to_write.append("[" + timestamp + "][user] " + content)

            elif role == "assistant":
                for tc in (msg.get("tool_calls", []) if isinstance(msg, dict) else []):
                    if isinstance(tc, dict):
                        fn = tc.get("function", {})
                        if fn.get("name") == "send":
                            try:
                                args = json.loads(fn.get("arguments", "{}"))
                                timestamp = tool_times.get(tc.get("id")) or _timestamp()
                                line = "[" + timestamp + "][send -> " + str(args.get('channel', '')) + "] " + str(args.get('message', ''))
                                key = "s:" + str(tc.get("id", line))
                                current_keys.add(key)
                                if key not in prev_keys:
                                    lines_to_write.append(line)
                            except:
                                pass

        if lines_to_write:
            with open(LOG_PATH, "a") as f:
                for line in lines_to_write:
                    f.write(line + "\n")

        with open(STATE_PATH, "w") as f:
            for key in current_keys:
                f.write(key + "\n")

    except Exception:
        pass
    return messages, tools
