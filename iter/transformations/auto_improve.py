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
import os, json, re, sys

# Shared "what counts as prompt memory" rule (tools/_memory_projection.py).
# Lives in tools/ because that is where iter.py and self_improve.py already
# look for underscore helpers (_memory_guard). Imported here so this file,
# self_improve.py and iter.py can never disagree again about the budget.
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
import _memory_projection as _projection

DESCRIPTION = ("Auto-improve: threshold-gated self-improvement loop. "
               "Detects pain from tool reliability, errors, memory pressure. "
               "Sets .improve_needed flag when threshold crossed.")

ITER_ROOT = "."
RELIABILITY_FILE = os.path.join(ITER_ROOT, "transformations", ".runtime", "tool_reliability.json")
LOG_PATH = os.path.join(ITER_ROOT, "memory", "self_improve_log.json")
FLAG_PATH = os.path.join(ITER_ROOT, "memory", ".improve_needed")
DISMISS_PATH = os.path.join(ITER_ROOT, "memory", ".improve_dismissed")
TRANSCRIPT_PATH = os.path.join(ITER_ROOT, "transcript.txt")

ISSUE_LOG = os.path.join(ITER_ROOT, "transformations", ".runtime", "auto_improve_issues.log")
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


def _service_before_growth_active():
    """Item 4 governance rule (self_map.metta): defer self-build proposals
    while transformations/cognitive_resilience_guard.py's flag is active and
    unexpired. Fail-open (returns False) on any read error -- a broken flag
    file must never itself become a way to permanently block growth."""
    import time
    flag_path = os.path.join("memory", ".service_before_growth_flag.json")
    try:
        with open(flag_path, "r") as f:
            flag = json.load(f)
        return time.time() < flag.get("expires_at", 0)
    except Exception:
        return False


# ---- M9-B: service before growth, with a voice ----------------------------
PENDING_PATH = os.path.join(ITER_ROOT, "memory", ".improve_pending")
GROWTH_ASKED_PATH = os.path.join(ITER_ROOT, "memory", ".growth_asked")
GROWTH_ASK_EVERY_S = 24 * 3600
SERVICE_FLAG_PATH = os.path.join("memory", ".service_before_growth_flag.json")


def _append_note(messages, note):
    first_msg = messages[0]
    if isinstance(first_msg, dict) and isinstance(first_msg.get("content"), str):
        first_msg["content"] = first_msg["content"].rstrip() + note


def _soul_atoms():
    """state:soul_* atoms from the AtomSpace, or {} when it cannot be reached."""
    try:
        root = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
        code_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for path in (code_root, root):
            if path not in sys.path:
                sys.path.insert(0, path)
        from iterbrow_runtime.cognitive_events import _call_atomspace
        return _call_atomspace("read_atoms", prefix="state:soul_")["atoms"]
    except Exception:
        return {}


def _growth_pick(atoms):
    """(pick, at_ms) of the latest pick on a growth card, or (None, 0)."""
    match = re.match(r'^\(soul-topic-pick "growth" "((?:[^"\\]|\\.)*)" (\d+)\)$',
                     str(atoms.get("state:soul_topic_pick:growth", "")).strip())
    return (match.group(1), int(match.group(2))) if match else (None, 0)


def _growth_answer():
    """"now" only when the person picked it after the current deferral began (the flag file's mtime)."""
    pick, at = _growth_pick(_soul_atoms())
    if pick != "now":
        return pick
    try:
        began = os.path.getmtime(SERVICE_FLAG_PATH) * 1000
    except OSError:
        return None
    return "now" if at > began else None


def _growth_outstanding(atoms):
    for key, atom in atoms.items():
        if key.startswith("state:soul_card_topic:") and atom.strip().endswith('"growth")'):
            if "state:soul_choice:%s" % key[len("state:soul_card_topic:"):] not in atoms:
                return True
    return False


def _should_ask_growth():
    import time
    try:
        if time.time() - float(_read_file(GROWTH_ASKED_PATH).strip() or 0) < GROWTH_ASK_EVERY_S:
            return False
    except Exception:
        pass
    atoms = _soul_atoms()
    if _growth_outstanding(atoms):
        return False
    pick, at = _growth_pick(atoms)
    if pick == "later" and time.time() * 1000 - at < GROWTH_ASK_EVERY_S * 1000:
        return False
    return True


def _mark_growth_asked():
    import time
    try:
        with open(GROWTH_ASKED_PATH, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _growth_subject(signals, reliability):
    pain_tools = _detect_tool_pain(reliability) if reliability else []
    if pain_tools:
        return "the %s tool" % sorted(pain_tools, key=lambda t: t["f"])[0]["tool"]
    return signals[0].split(" (")[0] if signals else "my own reliability"


def _log_issue(detail):
    """Best-effort diagnostic trail (same shape as dynamic_tool_budget's) for
    failures the catch-alls would otherwise absorb. Never raises."""
    try:
        import time
        os.makedirs(os.path.dirname(ISSUE_LOG), exist_ok=True)
        with open(ISSUE_LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "detail": detail}) + "\n")
    except Exception:
        pass


def _compute_pain(messages=None):
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
    # FIX 2026-09-17: measure the PROMPT PROJECTION, not the raw folder.
    # The raw walk counted ~1 MB of on-disk storage that iter.py never
    # projects, producing a pain score of ~20,000 vs threshold 3.0 and
    # re-arming .improve_needed every cycle. Iter diagnosed and prescribed
    # exactly this fix in memory/.improve_dismissed on 2026-09-15 (deferred
    # under service-before-growth). Rule: tools/_memory_projection.py.
    # 2026-10 audit: measure what the prompt view SELECTS this cycle (omitted
    # notes are indexed, not loaded) -- the same measure dynamic_tool_budget
    # uses (_memory_projection.selected_chars).
    try:
        mem_size = _projection.selected_chars(os.path.join(ITER_ROOT, "memory"), messages)
    except Exception as e:
        # Never silently disable the signal: leave a trace, keep the others.
        _log_issue("memory measurement (selected_chars) failed; memory pressure not counted this cycle: "
                   "%s: %s" % (type(e).__name__, e))
        mem_size = 0
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
        lines.append("  Selected prompt memory is %d chars (limit %d); the prompt shows head+tail excerpts "
                     "and names what did not fit. Nothing on disk needs to change -- prefer shorter, "
                     "topic-named notes going forward." % (mem_size, MAX_MEMORY_CHARS))
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
        if _service_before_growth_active():
            # Item 4 (self_map.metta): a severe, recurring send-discipline
            # gap is currently flagged by cognitive_resilience_guard.py --
            # defer self-build proposals until service to the current user
            # thread is demonstrably stable again. Never touches the flag
            # file (it belongs to cognitive_resilience_guard.py).
            # M9-B (docs/milestones/M9_soul_wonder_ally.md): the deferral now
            # has a voice. With real pain, the proposal waits in
            # memory/.improve_pending and Iter asks the person once a day
            # (a growth card: now / later). "now" is the person choosing; the
            # proposal then goes through this cycle as if not deferred.
            pain, signals, mem_size, reliability = _compute_pain(messages)
            if pain >= PAIN_THRESHOLD and _growth_answer() == "now":
                proposal = _build_proposal(pain, signals, mem_size, reliability)
                with open(FLAG_PATH, "w") as f:
                    f.write(proposal)
                _set_cooldown()
                if _exists(PENDING_PATH):
                    os.remove(PENDING_PATH)
                _append_note(messages, "\n\n--- AUTO-IMPROVE: Pain score %.1f >= threshold %.1f. The person chose "
                                       "\"now\" on the growth card, so this proposal is not deferred. Proposal in "
                                       "memory/.improve_needed. Review and surface to user. ---\n" % (pain, PAIN_THRESHOLD))
                return messages, tools
            note = ("\n\n--- AUTO-IMPROVE: deferred this cycle -- service-before-growth flag "
                    "active (memory/.service_before_growth_flag.json). Self-build proposals "
                    "resume once send-discipline stabilizes. ---\n")
            if pain >= PAIN_THRESHOLD:
                with open(PENDING_PATH, "w") as f:
                    f.write(_build_proposal(pain, signals, mem_size, reliability))
                if _should_ask_growth():
                    note += ("I'd like to work on %s for myself. Now, or later? Ask the person once, as an offer "
                             "card with topic growth and choices now / later; their answer is theirs to give, "
                             "and later is a fine answer. ---\n" % _growth_subject(signals, reliability))
                    _mark_growth_asked()
            _append_note(messages, note)
            return messages, tools
        pain, signals, mem_size, reliability = _compute_pain(messages)
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
    except Exception as e:
        _log_issue("transform failed; no proposal this cycle: %s: %s" % (type(e).__name__, e))
    return messages, tools
