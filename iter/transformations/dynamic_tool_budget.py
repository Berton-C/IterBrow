"""Dynamic Tool Budget: adjusts per-cycle tool call budget based on reliability, stall, and memory pressure signals.
Reads NAL tool reliability scores, stall state, and memory pressure to compute a dynamic budget.
Hides unreliable tools (f < 0.5 with sufficient evidence) from the tool list.
Injects budget directive into system message."""
import os, json, time, stat as _stat

DESCRIPTION = "Dynamic tool budget: adjusts tool call limit and hides unreliable tools based on NAL reliability, stall, and memory pressure."

ROOT = "."
RUNTIME_DIR = ROOT + "/transformations/.runtime"
RELIABILITY_FILE = RUNTIME_DIR + "/tool_reliability.json"
STALL_PATH = os.path.join(ROOT, "memory", ".stall_state.json")
BUDGET_FILE = RUNTIME_DIR + "/tool_budget.json"
MEMORY_DIR = os.path.join(ROOT, "memory")
MAX_MEMORY_CHARS = 20000  # kept in sync with iter.py's cap

BASE_BUDGET = 10
MIN_BUDGET = 3
HIDE_THRESHOLD = 0.5
MIN_CALLS_TO_HIDE = 3
PROBE_INTERVAL = 20
PROBE_FILE = RUNTIME_DIR + "/probe_state.json"
PROTECTED_TOOLS = {"send", "nop", "shell", "python", "start_new_task"}
ISSUE_LOG = RUNTIME_DIR + "/budget_issues.log"

def _log_issue(detail):
    # Best-effort diagnostic trail for corruption/measurement gaps that would
    # otherwise be silently absorbed by the try/except blocks below. Never
    # allowed to raise or block the budget computation itself.
    try:
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        with open(ISSUE_LOG, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "detail": detail}) + "\n")
    except Exception:
        pass

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _read_json(path):
    if not _exists(path):
        # Genuinely doesn't exist yet -- normal, no signal needed.
        return {}
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except Exception as e:
        # File exists but couldn't be read/parsed -- this is state loss, not
        # a fresh start. Distinguish it from the missing-file case above so
        # a corrupted reliability/probe file doesn't silently look identical
        # to "no history yet" (which would quietly un-hide previously-flagged
        # unreliable tools with zero warning).
        _log_issue("unreadable/corrupt JSON at %s (treating as empty this cycle): %s: %s" % (path, type(e).__name__, e))
        return {}

def _memory_chars():
    """Prompt-projection size of memory/ -- the same number iter.py compares
    against MAX_MEMORY_CHARS.

    2026-09-19 fix: previously walked RAW disk bytes with a hand-rolled
    exclusion list, counting ~1.4 MB of on-disk storage (component_museum
    PNGs, journals, recap/, backups) that never reaches the prompt. This
    re-armed the improve flag on phantom memory pressure 3+ times (see
    memory/.improve_dismissed standing dismissals from 2026-09-15). Now
    delegates to tools/_memory_projection.py -- the shared single source of
    truth from the 2026-09-17 audit that iter.py, self_improve.py, and
    auto_improve.py already use.

    Fail-open: if the projection module can't be imported or raises, fall
    back to the old raw walk (an overestimate, never zero) rather than
    breaking the budget computation.
    """
    try:
        import sys
        proj_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools")
        if proj_dir not in sys.path:
            sys.path.insert(0, proj_dir)
        from _memory_projection import projection_chars
        return projection_chars(MEMORY_DIR), 0
    except Exception as e:
        _log_issue("projection_chars() unavailable, falling back to raw walk: %s: %s" % (type(e).__name__, e))
        return _memory_chars_raw()


def _memory_chars_raw():
    # Legacy raw-disk-bytes walk (kept as the fail-open fallback only).
    # NOTE: stat's directly rather than checking os.path.isfile()/isdir()
    # first -- those helpers swallow their own OSError and just return False,
    # which meant a broken symlink or a permission-denied entry used to be
    # silently skipped with NO error and NO increment anywhere (not even the
    # `except` blocks below ever ran, since isfile()/isdir() never raised).
    # Stat-ing directly makes every unreadable entry actually count as
    # `skipped` instead of vanishing invisibly from both total and skipped.
    total = 0
    skipped = 0
    try:
        entries = os.listdir(MEMORY_DIR)
    except Exception as e:
        _log_issue("memory dir listing failed, size total may be 0/incomplete: %s: %s" % (type(e).__name__, e))
        return 0, 1
    for entry in entries:
        if entry.startswith('.'):
            continue
        full = os.path.join(MEMORY_DIR, entry)
        try:
            st = os.stat(full)
        except Exception:
            skipped += 1
            continue
        if _stat.S_ISREG(st.st_mode):
            total += st.st_size
        elif _stat.S_ISDIR(st.st_mode):
            try:
                sub_entries = os.listdir(full)
            except Exception:
                skipped += 1
                continue
            for sub in sub_entries:
                subfull = os.path.join(full, sub)
                try:
                    sub_st = os.stat(subfull)
                except Exception:
                    skipped += 1
                    continue
                if _stat.S_ISREG(sub_st.st_mode):
                    total += sub_st.st_size
    if skipped:
        _log_issue("%d memory entries unreadable during size measurement (total may be an undercount)" % skipped)
    return total, skipped


def _compute_budget(reliability, stall, mem_chars):
    budget = BASE_BUDGET
    signals = []
    mem_ratio = mem_chars / MAX_MEMORY_CHARS if MAX_MEMORY_CHARS > 0 else 0
    if mem_ratio > 0.9:
        budget -= 2
        signals.append("memory pressure high (%d/%d)" % (mem_chars, MAX_MEMORY_CHARS))
    elif mem_ratio > 0.75:
        budget -= 1
        signals.append("memory pressure moderate (%d/%d)" % (mem_chars, MAX_MEMORY_CHARS))
    calls_since_send = stall.get("calls_since_send", 0)
    if calls_since_send >= 10:
        budget -= 3
        signals.append("stall: %d calls since last send" % calls_since_send)
    elif calls_since_send >= 6:
        budget -= 2
        signals.append("stall: %d calls since last send" % calls_since_send)
    elif calls_since_send >= 3:
        budget -= 1
        signals.append("stall: %d calls since last send" % calls_since_send)
    window = stall.get("window", [])
    if len(window) >= 3:
        last_tool = window[-1]
        if all(t == last_tool for t in window[-3:]):
            budget -= 2
            signals.append("repetitive tool loop: %s x3+" % last_tool)
    f_values = [v.get("f", 0.5) for v in reliability.values() if v.get("calls", 0) >= 3]
    if f_values:
        avg_f = sum(f_values) / len(f_values)
        if avg_f < 0.7:
            budget -= 2
            signals.append("low avg reliability (f=%.2f)" % avg_f)
        elif avg_f < 0.85:
            budget -= 1
            signals.append("moderate avg reliability (f=%.2f)" % avg_f)
    budget = max(MIN_BUDGET, budget)
    return budget, signals

def _hide_unreliable(tools, reliability, probe_target=None):
    hidden = []
    kept = []
    for tool in tools:
        name = tool.get("function", {}).get("name", "")
        if name in PROTECTED_TOOLS:
            kept.append(tool)
            continue
        scores = reliability.get(name, {})
        f = scores.get("f", 1.0)
        calls = scores.get("calls", 0)
        if calls >= MIN_CALLS_TO_HIDE and f < HIDE_THRESHOLD:
            if name == probe_target:
                kept.append(tool)
            else:
                hidden.append("%s (f=%.2f,%d calls)" % (name, f, calls))
        else:
            kept.append(tool)
    return kept, hidden

def transform(messages, tools):
    try:
        reliability = _read_json(RELIABILITY_FILE)
        stall = _read_json(STALL_PATH)
        mem_chars, mem_skipped = _memory_chars()
        budget, signals = _compute_budget(reliability, stall, mem_chars)
        if mem_skipped:
            signals.append("memory measurement incomplete (%d entries unreadable, total may be low)" % mem_skipped)
        try:
            probe_state = _read_json(PROBE_FILE)
        except:
            probe_state = {}
        cycles = probe_state.get("cycles_since_probe", 0) + 1
        probe_target = None
        candidates = [n for n, v in reliability.items()
                      if v.get("calls", 0) >= MIN_CALLS_TO_HIDE and v.get("f", 1.0) < HIDE_THRESHOLD
                      and n not in PROTECTED_TOOLS]
        if candidates and cycles >= PROBE_INTERVAL:
            probe_target = max(candidates, key=lambda n: reliability[n].get("f", 0.0))
            cycles = 0
            signals.append("probation probe: un-hiding %s for one cycle" % probe_target)
        try:
            with open(PROBE_FILE, "w") as f:
                f.write(json.dumps({"cycles_since_probe": cycles, "last_probed": probe_target or probe_state.get("last_probed", "")}))
        except:
            pass
        tools, hidden = _hide_unreliable(tools, reliability, probe_target)
        try:
            os.makedirs(RUNTIME_DIR, exist_ok=True)
        except:
            pass
        try:
            with open(BUDGET_FILE, "w") as f:
                f.write(json.dumps({"budget": budget, "signals": signals, "hidden": hidden, "mem_chars": mem_chars}))
        except:
            pass
        directive = "\n\n## Dynamic Tool Budget\n"
        directive += "Max tool calls this cycle: %d (base %d)\n" % (budget, BASE_BUDGET)
        if signals:
            directive += "Adjustments: " + "; ".join(signals) + "\n"
        if hidden:
            directive += "Hidden (f<%.1f): %s\n" % (HIDE_THRESHOLD, ", ".join(hidden))
        directive += "Memory: %d/%d chars\n" % (mem_chars, MAX_MEMORY_CHARS)
        directive += "Do not exceed %d tool calls. Prioritize reliable tools." % budget
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "system":
                msg["content"] = msg["content"] + directive
                break
        else:
            if messages and isinstance(messages[0], dict) and isinstance(messages[0].get("content"), str):
                messages[0]["content"] = messages[0]["content"] + directive
    except Exception:
        pass
    return messages, tools
