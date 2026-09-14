"""
Auto-Improve - autonomous self-improvement loop as a transformation.

Runs every cycle. Threshold-gated detection of pain signals:
  1. Tool reliability: tools with low frequency (f) x high confidence (c)
  2. Recent errors in transcript
  3. Memory pressure: checks memory folder size vs MAX_MEMORY_CHARS

When pain crosses a threshold, sets .improve_needed flag with a
structured proposal. The agent (LLM) picks it up next cycle and
surfaces it to the user (human-in-the-loop).

Most cycles: zero overhead (reads one small JSON, computes a score,
returns). No context budget consumed unless action is needed.

Avoids repeats: checks self_improve_log.json lineage before proposing.
"""
import os, json, re

DESCRIPTION = ("Auto-improve: threshold-gated self-improvement loop. "
               "Detects pain from tool reliability, errors, memory pressure. "
               "Sets .improve_needed flag when threshold crossed.")

ITER_ROOT = "."
RELIABILITY_FILE = os.path.join(ITER_ROOT, "transformations", ".runtime", "tool_reliability.json")
LOG_PATH = os.path.join(ITER_ROOT, "memory", "self_improve_log.json")
FLAG_PATH = os.path.join(ITER_ROOT, "memory", ".improve_needed")
DISMISS_PATH = os.path.join(ITER_ROOT, "memory", ".improve_dismissed")
TRANSCRIPT_PATH = os.path.join(ITER_ROOT, "transcript.txt")

PAIN_THRESHOLD = 3.0
MAX_MEMORY_CHARS = 20000  # kept in sync with iter.py's cap
RECENT_LINES = 30
REPEAT_LOOKBACK = 10
LOW_FREQ_THRESHOLD = 0.5
MIN_CONFIDENCE = 0.6
MEMORY_PRESSURE_WEIGHT = 2.0
ERROR_WEIGHT = 1.0
LOW_FREQ_WEIGHT = 1.5
COOLDOWN_CYCLES = 5
COOLDOWN_PATH = os.path.join(ITER_ROOT, "memory", ".improve_cooldown")

ERROR_PATTERNS = [
    r"traceback\s*\(most recent call last\)",
    r"\bsyntaxerror\b", r"\bnameerror\b", r"\btypeerror\b",
    r"\bvalueerror\b", r"\bimporterror\b", r"\battributeerror\b",
    r"\bkeyerror\b", r"\bindexerror\b", r"\bruntimeerror\b",
    r"\boserror\b", r"no such file or directory",
    r"connection refused", r"jsondecodeerror",
]


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception:
        return ""


def _read_json(path):
    try:
        return json.loads(_read_file(path))
    except Exception:
        return {}


# Binary/media extensions: these bytes are never loaded into the agent's
# text context window, so counting them against MAX_MEMORY_CHARS produces
# a false "memory pressure" signal. Discovered 2026-09-14: component_museum
# screenshots (~2.9MB of PNGs) were driving the pain score to ~58000 against
# a threshold of 3.0, forcing repeated false-positive self-improve triage
# cycles that found nothing real to fix each time.
_BINARY_EXTS = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico",
    ".pdf", ".zip", ".gz", ".tar", ".tgz", ".mp4", ".mp3", ".wav",
)


def _dir_size_chars(path):
    total = 0
    try:
        for entry in os.listdir(path):
            if entry.startswith("."):
                continue
            full = os.path.join(path, entry)
            try:
                if os.stat(full)[0] & 0x4000:
                    total += _dir_size_chars(full)
                elif entry.lower().endswith(_BINARY_EXTS):
                    continue
                else:
                    total += os.stat(full)[6]
            except OSError:
                pass
    except OSError:
        pass
    return total


def _read_log():
    if not _exists(LOG_PATH):
        return []
    try:
        return json.loads(_read_file(LOG_PATH))
    except Exception:
        return []


def _count_recent_errors():
    if not _exists(TRANSCRIPT_PATH):
        return 0
    lines = _read_file(TRANSCRIPT_PATH).split("\n")
    recent = lines[-RECENT_LINES:] if len(lines) > RECENT_LINES else lines
    count = 0
    for line in recent:
        lower = line.lower()
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, lower):
                count += 1
                break
    return count


def _detect_tool_pain(reliability):
    pain_tools = []
    for tool_name, score in reliability.items():
        f = score.get("f", 1.0)
        c = score.get("c", 0.0)
        calls = score.get("calls", 0)
        if calls >= 3 and f < LOW_FREQ_THRESHOLD and c >= MIN_CONFIDENCE:
            pain_tools.append({
                "tool": tool_name, "f": f, "c": c,
                "calls": calls, "failures": score.get("failures", 0),
            })
    return pain_tools


def _check_cooldown():
    if not _exists(COOLDOWN_PATH):
        return False
    try:
        count = int(_read_file(COOLDOWN_PATH).strip())
        if count > 0:
            with open(COOLDOWN_PATH, "w") as f:
                f.write(str(count - 1))
            return True
    except Exception:
        pass
    return False


def _set_cooldown():
    try:
        with open(COOLDOWN_PATH, "w") as f:
            f.write(str(COOLDOWN_CYCLES))
    except Exception:
        pass


def _compute_pain():
    pain = 0.0
    signals = []
    reliability = _read_json(RELIABILITY_FILE)
    if reliability:
        pain_tools = _detect_tool_pain(reliability)
        for t in pain_tools:
            contribution = LOW_FREQ_WEIGHT * (1.0 - t["f"])
            pain += contribution
            signals.append("tool:%s f=%.2f c=%.2f (+%.1f)" % (t["tool"], t["f"], t["c"], contribution))
    error_count = _count_recent_errors()
    if error_count > 0:
        contribution = ERROR_WEIGHT * error_count
        pain += contribution
        signals.append("errors: %d recent (+%.1f)" % (error_count, contribution))
    mem_size = _dir_size_chars(os.path.join(ITER_ROOT, "memory"))
    if mem_size > MAX_MEMORY_CHARS:
        over = (mem_size - MAX_MEMORY_CHARS) / 100.0
        contribution = MEMORY_PRESSURE_WEIGHT * over
        pain += contribution
        signals.append("memory: %d chars (limit %d) (+%.1f)" % (mem_size, MAX_MEMORY_CHARS, contribution))
    return pain, signals, mem_size, reliability


def _build_proposal(pain, signals, mem_size, reliability):
    lines = [
        "AUTO-IMPROVE PROPOSAL",
        "Pain score: %.1f (threshold %.1f)" % (pain, PAIN_THRESHOLD),
        "Signals:",
    ]
    for s in signals:
        lines.append("  - %s" % s)
    pain_tools = _detect_tool_pain(reliability) if reliability else []
    if pain_tools:
        worst = sorted(pain_tools, key=lambda t: t["f"])[0]
        lines.append("")
        lines.append("Suggested action:")
        lines.append("  Tool '%s' has f=%.2f, c=%.2f (%d failures out of %d calls)." % (
            worst["tool"], worst["f"], worst["c"], worst["failures"], worst["calls"]))
        lines.append("  Review error patterns and propose a fix to the user.")
    if mem_size > MAX_MEMORY_CHARS:
        lines.append("")
        lines.append("Suggested action:")
        lines.append("  Memory folder is %d chars (limit %d). Consolidate or compress tier files." % (
            mem_size, MAX_MEMORY_CHARS))
    log = _read_log()
    lines.append("")
    lines.append("Lineage: %d entries. Check before proposing to avoid repeats." % len(log))
    return "\n".join(lines)


def transform(messages, tools):
    try:
        if not messages:
            return messages, tools
        if _check_cooldown():
            return messages, tools
        pain, signals, mem_size, reliability = _compute_pain()
        if pain >= PAIN_THRESHOLD:
            proposal = _build_proposal(pain, signals, mem_size, reliability)
            with open(FLAG_PATH, "w") as f:
                f.write(proposal)
            _set_cooldown()
            notice = "\n\n--- AUTO-IMPROVE: Pain score %.1f >= threshold %.1f. Proposal in memory/.improve_needed. Review and surface to user. ---\n" % (pain, PAIN_THRESHOLD)
            first_msg = messages[0]
            if isinstance(first_msg, dict):
                content = first_msg.get("content", "")
                if isinstance(content, str):
                    first_msg["content"] = content.rstrip() + notice
                elif isinstance(content, list):
                    first_msg["content"] = content + [{"type": "text", "text": notice}]
        else:
            if _exists(FLAG_PATH):
                try:
                    os.remove(FLAG_PATH)
                except OSError:
                    pass
    except Exception:
        pass
    return messages, tools
