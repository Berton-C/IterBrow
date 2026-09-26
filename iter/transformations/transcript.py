"""
Transcript - persists all textual communication messages (user + assistant send)
to a queryable file. Excludes control messages injected by iter.py.
State = string keys of current context window messages only (like history.py).
"""
import os, json, time
from iterbrow_runtime.conversation_view import CONTROL_PATTERNS, is_runner_control



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Maintains transcript of textual communication messages only."
LOG_PATH = "transcript.txt"
STATE_PATH = ".transcript_state"

def _is_control(content):
    return is_runner_control(content)

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
        legacy_state = ""
        if _exists(STATE_PATH):
            with open(STATE_PATH) as f:
                raw = f.read()
            if raw.lstrip().startswith("["):
                prev_keys = set(json.loads(raw))
            else:
                prev_keys = set(raw.splitlines())
                legacy_state = "\n" + raw.strip("\n") + "\n"

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
                if msg.get("_iter_runner") or _is_control(content):
                    continue
                key = "u:" + content
                current_keys.add(key)
                if key not in prev_keys and not (legacy_state and "\n" + key + "\n" in legacy_state):
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
                                # send.run(channel, content) has used `content`
                                # for years; the old `message` lookup recorded a
                                # delivery marker with an empty body, destroying
                                # the evidence needed to distinguish model silence
                                # from a UI delivery failure. Keep `message` only
                                # as a compatibility fallback for old episodes.
                                body = args.get('content', args.get('message', ''))
                                line = "[" + timestamp + "][send -> " + str(args.get('channel', '')) + "] " + str(body)
                                key = "s:" + str(tc.get("id", line))
                                current_keys.add(key)
                                if key not in prev_keys:
                                    lines_to_write.append(line)
                            except:
                                pass

        if lines_to_write:
            from iterbrow_runtime.episodic_history import recover_rotation
            recover_rotation(LOG_PATH)
            with open(LOG_PATH, "a") as f:
                for line in lines_to_write:
                    f.write(line + "\n")

        temporary = STATE_PATH + ".tmp"
        with open(temporary, "w") as f:
            json.dump(sorted(current_keys), f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, STATE_PATH)

    except Exception:
        pass
    return messages, tools
