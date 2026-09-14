import json
import re
import os
import time
import shutil


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _mkdirs(path):
    current = ""
    for part in str(path).split("/"):
        if not part:
            current = "/" if not current else current
            continue
        current = (current.rstrip("/") + "/" + part) if current else part
        try:
            os.mkdir(current)
        except OSError:
            pass

DESCRIPTION = "Tracks reliability of tools"

ROOT = "."
RUNTIME_DIR = ROOT + "/transformations/.runtime"
RELIABILITY_FILE = RUNTIME_DIR + "/tool_reliability.json"
STATE_FILE = RUNTIME_DIR + "/tool_reliability_state.txt"
ISSUE_LOG = RUNTIME_DIR + "/tracker_issues.log"

def _log_issue(detail):
    # Best-effort diagnostic trail only -- never allowed to raise or block
    # reliability recording itself.
    try:
        with open(ISSUE_LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "detail": detail}) + "\n")
    except Exception:
        pass

def nal_revise(f1, c1, f2, c2):
    w1 = c1 / (1 - c1) if c1 < 1.0 else 1e10
    w2 = c2 / (1 - c2) if c2 < 1.0 else 1e10
    f_new = (w1 * f1 + w2 * f2) / (w1 + w2)
    c_new = (w1 + w2) / (w1 + w2 + 1)
    return round(f_new, 4), round(c_new, 4)

def update_reliability(tool_name, success):
    try:
        _mkdirs(RUNTIME_DIR)
    except OSError:
        pass
    if _exists(RELIABILITY_FILE):
        try:
            with open(RELIABILITY_FILE, "r") as f:
                scores = json.loads(f.read())
        except Exception as e:
            # File exists but is unreadable/corrupt. Previously this just
            # `return`-ed here, which silently dropped THIS outcome (the
            # current tool call's success/failure never got recorded, with
            # no signal anywhere). Instead: preserve a copy of the bad file
            # for forensics, log it, and fall through to record this outcome
            # against a fresh scores dict rather than losing it.
            _log_issue("tool_reliability.json unreadable/corrupt, starting fresh scores this call: %s: %s" % (type(e).__name__, e))
            try:
                shutil.copy(RELIABILITY_FILE, RELIABILITY_FILE + ".corrupt.%d.bak" % int(time.time()))
            except Exception:
                pass
            scores = {}
    else:
        scores = {}
    if tool_name not in scores:
        scores[tool_name] = {"f": 0.5, "c": 0.0, "calls": 0, "successes": 0, "failures": 0}
    s = scores[tool_name]
    calls = s.get("calls", 0)
    if calls < 1:
        if success:
            s["f"] = 1.0
            s["c"] = 0.5
        else:
            s["f"] = 0.0
            s["c"] = 0.5
    else:
        obs_f = 1.0 if success else 0.0
        new_f, new_c = nal_revise(s["f"], s["c"], obs_f, 0.5)
        s["f"] = new_f
        s["c"] = new_c
    s["calls"] = calls + 1
    if success:
        s["successes"] = s.get("successes", 0) + 1
    else:
        s["failures"] = s.get("failures", 0) + 1
    scores[tool_name] = s
    try:
        with open(RELIABILITY_FILE, "w") as f:
            f.write(json.dumps(scores))
    except Exception:
        pass

# Specific error patterns that indicate actual tool failures.
# Avoids false positives from memory text containing words like "error", "failed", etc.
ERROR_PATTERNS = [
    r"traceback\s*\(most recent call last\)",
    r"tool execution failed",
    r"\bsyntaxerror\b",
    r"\bnameerror\b",
    r"\btypeerror\b",
    r"\bvalueerror\b",
    r"\bimporterror\b",
    r"\battributeerror\b",
    r"\bkeyerror\b",
    r"\bindexerror\b",
    r"\bruntimeerror\b",
    r"\boserror\b",
    r"\bpermissionerror\b",
    r"\bfilenotfounderror\b",
    r"\benoent\b",
    r"no such file or directory",
    r"connection refused",
    r"connection reset",
    r"network unreachable",
    r"jsondecodeerror",
]

# Tools that return historical/transcript/memory text containing error keywords
# by nature. These should always be counted as success since the presence of
# error words in their output is expected (they return records of past errors,
# not tool failures).
EXEMPT_TOOLS = {"episodes", "search_transcript", "chroma_query"}

def has_error(content):
    lower = content.lower()
    for pattern in ERROR_PATTERNS:
        if re.search(pattern, lower):
            return True
    return False

def transform(messages, tools):
    try:
        with open(STATE_FILE, "r") as file:
            previous_ids = set(line.strip() for line in file if line.strip())
    except Exception:
        previous_ids = set()

    current_ids = set()
    for i in range(len(messages)):
        msg = messages[i]
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "tool":
            continue
        content = msg.get("content", "")
        if not content:
            continue
        tool_call_id = msg.get("tool_call_id", "")
        if not tool_call_id:
            continue
        current_ids.add(tool_call_id)
        if tool_call_id in previous_ids:
            continue
        for j in range(i):
            prev = messages[j]
            if not isinstance(prev, dict):
                continue
            if prev.get("role") != "assistant":
                continue
            tcs = prev.get("tool_calls", [])
            for tc in tcs:
                if isinstance(tc, dict) and tc.get("id") == tool_call_id:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    if tool_name:
                        if tool_name in EXEMPT_TOOLS:
                            success = True
                        else:
                            success = not has_error(content)
                        update_reliability(tool_name, success)
                        # --- NACE: push to pending queue ---
                        try:
                            outcome = 'confirmed' if success else 'disconfirmed'
                            with open('nace_pending.metta', 'a') as nf:
                                nf.write('(pending-revision tool ' + tool_name + ' ' + outcome + ')' + chr(10))
                        except Exception:
                            pass
                    break

    try:
        _mkdirs(RUNTIME_DIR)
    except OSError:
        pass
    try:
        with open(STATE_FILE, "w") as file:
            file.write("\n".join(current_ids))
    except Exception:
        pass
    return messages, tools