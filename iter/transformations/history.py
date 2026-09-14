import time
import os
import gc



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Stores episodes (deduped, restart-safe)"

HISTORY = "history.metta"
STATE_PATH = ".history_state"

CONTROL_PATTERNS = [
    "[NO ADDITIONAL",
    "[TASK COMPLETED",
    "[NO NEW USER",
    "[TOOL LIMIT",
    "[MEMORY FOLDER",
    "[OUTPUT TOKEN",
    "[YOUR PREVIOUS",
    "[NOT DELIVERED",
]

def _timestamp():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

def _escape_metta(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

def _is_control(content):
    return any(pattern in content for pattern in CONTROL_PATTERNS)

def transform(messages, tools):
    ts_str = _timestamp()

    if _exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                logged = set(f.read().split("\n"))
            logged.discard("")
        except Exception:
            logged = set()
    else:
        logged = set()

    history_lines = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "system":
            continue
        elif role == "user":
            if content and isinstance(content, str):
                if _is_control(content):
                    continue
                key = "u:" + content
                if key not in logged:
                    history_lines.append(
                        '("' + ts_str + '" "HUMAN_MESSAGE: ' + _escape_metta(content) + '")'
                    )
                    logged.add(key)
        elif role == "assistant":
            if content and isinstance(content, str):
                tool_ids = [str(tc.get("id", "")) for tc in msg.get("tool_calls", []) if isinstance(tc, dict)]
                key = "a:" + ("|".join(tool_ids) if tool_ids else content)
                if key not in logged:
                    history_lines.append(
                        '("' + ts_str + '" "ASSISTANT: ' + _escape_metta(content) + '")'
                    )
                    logged.add(key)
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args_str = fn.get("arguments", "{}")
                    key = "t:" + str(tc.get("id", name + " " + args_str))
                    if key not in logged:
                        history_lines.append(
                            '("' + ts_str + '" "TOOL_CALL: ' + name + " " + _escape_metta(args_str) + '")'
                        )
                        logged.add(key)
        elif role == "tool":
            if content and isinstance(content, str):
                key = "r:" + str(msg.get("tool_call_id", content))
                if key not in logged:
                    history_lines.append(
                        '("' + ts_str + '" "TOOL_RESULT: ' + _escape_metta(content) + '")'
                    )
                    logged.add(key)

    if history_lines:
        try:
            with open(HISTORY, "a") as f:
                for line in history_lines:
                    f.write(line + "\n")
        except Exception:
            pass

    current = set()
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "system":
            continue
        elif role == "user":
            if content and isinstance(content, str):
                if _is_control(content):
                    continue
                current.add("u:" + content)
        elif role == "assistant":
            if content and isinstance(content, str):
                tool_ids = [str(tc.get("id", "")) for tc in msg.get("tool_calls", []) if isinstance(tc, dict)]
                current.add("a:" + ("|".join(tool_ids) if tool_ids else content))
            for tc in (msg.get("tool_calls", []) if isinstance(msg, dict) else []):
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    current.add("t:" + str(tc.get("id", fn.get("name", "") + " " + fn.get("arguments", "{}"))))
        elif role == "tool":
            if content and isinstance(content, str):
                current.add("r:" + str(msg.get("tool_call_id", content)))
    logged = logged & current

    try:
        with open(STATE_PATH, "w") as f:
            f.write("\n".join(logged))
    except Exception:
        pass

    gc.collect()
    return messages, tools
