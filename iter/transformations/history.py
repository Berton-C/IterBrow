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

def _step_timestamp(content):
    """The event time iter.py stamped on a message ("Step YYYY-MM-DD HH:MM:SS: ...")."""
    if isinstance(content, str) and content.startswith("Step ") and len(content) >= 24:
        stamp = content[5:24]
        if stamp[4:5] == "-" and stamp[10:11] == " " and stamp[13:14] == ":":
            return stamp
    return None


def _report(messages, text):
    """Surface a logging failure in the system message instead of swallowing it."""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system" and isinstance(msg.get("content"), str):
            msg["content"] = msg["content"].rstrip() + "\n\n" + text
            return


def transform(messages, tools):
    now = _timestamp()
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

    # Records carry the EVENT's time, not the time this transformation ran:
    # user/tool messages their own Step stamp; an assistant turn (and each of
    # its tool calls) the time of its result, as transcript.py does.
    result_times = {}
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "tool" and msg.get("tool_call_id"):
            stamp = _step_timestamp(msg.get("content", ""))
            if stamp:
                result_times[str(msg.get("tool_call_id"))] = stamp

    history_lines = []   # (key, record)
    pending = set()

    def seen(key):
        return key in logged or key in pending or (legacy_state and "\n" + key + "\n" in legacy_state)

    def add(key, stamp, text):
        history_lines.append((key, '("' + (stamp or now) + '" "' + text + '")'))
        pending.add(key)

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
                    add(key, _step_timestamp(content), "HUMAN_MESSAGE: " + _escape_metta(content))
        elif role == "assistant":
            tool_calls = [tc for tc in msg.get("tool_calls", []) or [] if isinstance(tc, dict)]
            turn_time = next((result_times[str(tc.get("id"))] for tc in tool_calls
                              if str(tc.get("id")) in result_times), None)
            if content and isinstance(content, str):
                tool_ids = [str(tc.get("id", "")) for tc in tool_calls]
                key = "a:" + ("|".join(tool_ids) if tool_ids else content)
                if not seen(key):
                    add(key, turn_time, "ASSISTANT: " + _escape_metta(content))
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_str = fn.get("arguments", "{}")
                key = "t:" + str(tc.get("id", name + " " + args_str))
                if not seen(key):
                    add(key, result_times.get(str(tc.get("id"))) or turn_time,
                        "TOOL_CALL: " + name + " " + _escape_metta(args_str))
        elif role == "tool":
            if content and isinstance(content, str):
                key = "r:" + str(msg.get("tool_call_id", content))
                if not seen(key):
                    add(key, _step_timestamp(content), "TOOL_RESULT: " + _escape_metta(content))

    if history_lines:
        try:
            from iterbrow_runtime.episodic_history import recover_rotation
            recover_rotation(HISTORY)
            with open(HISTORY, "a") as f:
                for _key, line in history_lines:
                    f.write(line + "\n")
                f.flush()
            # Only now are these records logged; a failed append is retried.
            logged.update(pending)
        except Exception as error:
            pending.clear()
            _report(messages, "[history.py: could not append %d records to %s (%s: %s). They are kept "
                    "pending and retried next cycle; episodic history is not being recorded until this "
                    "is repaired.]" % (len(history_lines), HISTORY, type(error).__name__, error))

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
                tool_ids = [str(tc.get("id", "")) for tc in msg.get("tool_calls", []) or [] if isinstance(tc, dict)]
                current.add("a:" + ("|".join(tool_ids) if tool_ids else content))
            for tc in msg.get("tool_calls", []) or []:
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
    except Exception as error:
        _report(messages, "[history.py: could not save %s (%s: %s).]" % (STATE_PATH, type(error).__name__, error))

    gc.collect()
    return messages, tools
