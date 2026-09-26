import time
import os
import gc
import json
from iterbrow_runtime.conversation_view import CONTROL_PATTERNS, is_runner_control



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Stores episodes (deduped, restart-safe)"

HISTORY = "history.metta"
STATE_PATH = ".history_state"

def _timestamp():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

def _escape_metta(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

def _is_control(content):
    return is_runner_control(content)

def transform(messages, tools):
    ts_str = _timestamp()
    legacy_state = ""

    if _exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                raw = f.read()
            if raw.lstrip().startswith("["):
                logged = set(json.loads(raw))
            else:
                # The old newline format cannot represent multiline keys.
                # Preserve its single-line keys and recognize full current keys
                # below so upgrading does not re-log an old user request.
                legacy_state = "\n" + raw.strip("\n") + "\n"
                logged = set(raw.split("\n"))
            logged.discard("")
        except Exception:
            logged = set()
    else:
        logged = set()

    history_lines = []

    def seen(key):
        return key in logged or (legacy_state and "\n" + key + "\n" in legacy_state)

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if role == "system":
            continue
        elif role == "user":
            if content and isinstance(content, str):
                if msg.get("_iter_runner") or _is_control(content):
                    continue
                key = "u:" + content
                if not seen(key):
                    history_lines.append(
                        '("' + ts_str + '" "HUMAN_MESSAGE: ' + _escape_metta(content) + '")'
                    )
                    logged.add(key)
        elif role == "assistant":
            if content and isinstance(content, str):
                tool_ids = [str(tc.get("id", "")) for tc in msg.get("tool_calls", []) if isinstance(tc, dict)]
                key = "a:" + ("|".join(tool_ids) if tool_ids else content)
                if not seen(key):
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
                    if not seen(key):
                        history_lines.append(
                            '("' + ts_str + '" "TOOL_CALL: ' + name + " " + _escape_metta(args_str) + '")'
                        )
                        logged.add(key)
        elif role == "tool":
            if content and isinstance(content, str):
                key = "r:" + str(msg.get("tool_call_id", content))
                if not seen(key):
                    history_lines.append(
                        '("' + ts_str + '" "TOOL_RESULT: ' + _escape_metta(content) + '")'
                    )
                    logged.add(key)

    if history_lines:
        try:
            from iterbrow_runtime.episodic_history import recover_rotation
            recover_rotation(HISTORY)
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
                if msg.get("_iter_runner") or _is_control(content):
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
    logged = {key for key in current if seen(key)}

    try:
        temporary = STATE_PATH + ".tmp." + str(os.getpid())
        with open(temporary, "w") as f:
            json.dump(sorted(logged), f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, STATE_PATH)
    except Exception:
        pass

    gc.collect()
    return messages, tools
