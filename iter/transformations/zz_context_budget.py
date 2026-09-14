"""
Context Budget Coordinator â runs last (zz_ prefix).

Upgraded: structured section tagging, error reporting, dynamic budget,
extensible dedup, feedback loop, multi-message support.
"""
import os, json, time

DESCRIPTION = "Context budget coordinator: priority-based trimming with dedup and dynamic budget."

BASE = "."
LOG_PATH = os.path.join(BASE, ".context_budget_log.txt")
ERROR_LOG = os.path.join(BASE, ".context_budget_errors.txt")

# ---- Budget configuration (derive-able) ----
# Model context window estimate; budget = fraction of window for injected content
MODEL_CONTEXT_WINDOW = 128000       # chars (rough estimate for ~32k tokens)
INJECTED_FRACTION = 0.20            # 20% of context window for memory injections
BASE_BUDGET = int(MODEL_CONTEXT_WINDOW * INJECTED_FRACTION)  # 25600
FLOOR_BUDGET = 4000                  # absolute minimum
SHRINK_THRESHOLD = 10               # messages before budget starts shrinking
SHRINK_PER_5_MSGS = 800             # chars to subtract per 5 additional messages
MIN_FREE_RATIO = 0.50              # reserve at least 50% for conversation

# ---- Section registry (extensible) ----
# Each entry: (marker_substring, priority, label, max_fraction)
# max_fraction = cap this section at this fraction of total budget
SECTIONS = [
    ("--- AGENTS.md (auto-included) ---", "CRITICAL", "AGENTS.md", 0.40),
    ("## Tiered Memory Pyramid",         "HIGH",     "TieredMemory", 0.35),
    ("## Episode Recap",                  "MEDIUM",   "Recap",        0.20),
    ("transcript:",                       "LOW",      "Transcript",   0.10),
    ("--- \u26a0\ufe0f AGENTS.md STALENESS WARNING ---", "LOW", "Staleness", 0.05),
]

# Extensible dedup: (keeper_label, redundant_label, min_keeper_chars)
DEDUP_RULES = [
    ("TieredMemory", "Recap", 100),
]

# ---- Error reporting ----
def _log_error(msg):
    try:
        with open(ERROR_LOG, "a") as f:
            f.write("[{}] {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass

def _split_sections(content):
    """Split content into tagged sections. Returns list of dicts."""
    markers = []
    for marker, priority, label, max_frac in SECTIONS:
        idx = content.find(marker)
        if idx >= 0:
            markers.append((idx, marker, priority, label, max_frac))
    markers.sort(key=lambda m: m[0])
    if not markers:
        return [{"label": "BasePrompt", "priority": "CRITICAL", "text": content, "counted": False, "max_fraction": 1.0}]
    sections = []
    first_idx = markers[0][0]
    if first_idx > 0:
        base = content[:first_idx].rstrip()
        if base:
            sections.append({"label": "BasePrompt", "priority": "CRITICAL", "text": base, "counted": False, "max_fraction": 1.0})
    for i, (idx, marker, priority, label, max_frac) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(content)
        sections.append({
            "label": label, "priority": priority,
            "text": content[idx:end].rstrip(), "counted": True, "max_fraction": max_frac,
            "status": "kept",
        })
    return sections

def _apply_dedup(sections):
    labels_present = {s["label"] for s in sections if len(s["text"]) > 50}
    dropped = []
    for keeper, redundant, min_chars in DEDUP_RULES:
        keeper_sections = [s for s in sections if s["label"] == keeper]
        if keeper in labels_present and redundant in labels_present:
            keeper_size = sum(len(s["text"]) for s in keeper_sections)
            if keeper_size >= min_chars:
                sections = [s for s in sections if s["label"] != redundant]
                dropped.append(redundant)
    return sections, dropped

def _truncate_section(text, max_chars):
    if max_chars < 50:
        return ""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars - 30]
    cut = truncated.rfind("\n\n")
    if cut > max_chars // 2:
        truncated = truncated[:cut]
    else:
        cut = truncated.rfind("\n")
        if cut > max_chars // 2:
            truncated = truncated[:cut]
    return truncated + "\n...[trimmed by context budget]"

def _dynamic_budget(num_messages):
    budget = BASE_BUDGET
    if num_messages > SHRINK_THRESHOLD:
        excess = num_messages - SHRINK_THRESHOLD
        budget -= (excess // 5) * SHRINK_PER_5_MSGS
    return max(budget, FLOOR_BUDGET)

def _write_log(allocation, total, budget, dropped, num_messages, mode):
    try:
        lines = ["=== Context Budget Log ===",
                 "Mode: {} | Messages: {} | Budget: {} | Used: {} | Free: {} | Over?: {}".format(
                     mode, num_messages, budget, total, budget - total, total > budget)]
        if dropped:
            lines.append("Deduped: " + ", ".join(dropped))
        lines.append("--- Sections ---")
        for s in allocation:
            lines.append("  {:<15} {:<8} {:>6} chars  [{}] ({})".format(
                s["label"], s["priority"], s["size"], s.get("status", "kept"),
                "budget" if s.get("counted", True) else "base"))
        lines.append("")
        with open(LOG_PATH, "w") as f:
            f.write("\n".join(lines))
    except Exception as e:
        _log_error("write_log failed: {}".format(e))

def _feedback_check(total, budget, mode):
    """If budget was exceeded, note it so other systems can react."""
    if total > budget:
        try:
            flag_path = os.path.join(BASE, ".budget_exceeded")
            with open(flag_path, "w") as f:
                f.write(json.dumps({"mode": mode, "total": total, "budget": budget, "ts": time.time()}))
        except Exception:
            pass

def _reassemble(msg, sections):
    msg["content"] = "\n\n".join(s["text"] for s in sections if s["text"])

def _alloc_entry(s):
    return {"label": s["label"], "priority": s["priority"], "size": len(s["text"]),
            "status": s.get("status", "kept"), "counted": s.get("counted", True)}

def _counted_total(sections):
    return sum(len(s["text"]) for s in sections if s.get("counted", True))

def _process_one(msg, budget, num_messages):
    """Process a single system message. Returns (sections, dropped, mode)."""
    if not isinstance(msg, dict):
        return None, [], "skip"
    content = msg.get("content", "")
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text", ""))
            elif isinstance(b, str):
                parts.append(b)
        content = "\n\n".join(parts)
    elif not isinstance(content, str):
        return None, [], "skip"

    sections = _split_sections(content)
    sections, dropped = _apply_dedup(sections)
    total = _counted_total(sections)

    if total <= budget:
        _write_log([_alloc_entry(s) for s in sections], total, budget, dropped, num_messages, "pass-through")
        _reassemble(msg, sections)
        return sections, dropped, "pass-through"

    # Phase 1: Truncate LOW to 50%
    for s in sections:
        if s.get("counted", True) and s["priority"] == "LOW":
            s["text"] = _truncate_section(s["text"], len(s["text"]) // 2)
            s["status"] = "truncated-50%"
    total = _counted_total(sections)
    if total <= budget:
        _write_log([_alloc_entry(s) for s in sections], total, budget, dropped, num_messages, "trim-low-50")
        _reassemble(msg, sections)
        return sections, dropped, "trim-low-50"

    # Phase 2: Drop LOW
    kept = [s for s in sections if not (s.get("counted", True) and s["priority"] == "LOW")]
    total = _counted_total(kept)
    if total <= budget:
        _write_log([_alloc_entry(s) for s in kept], total, budget, dropped + ["LOW"], num_messages, "drop-low")
        _reassemble(msg, kept)
        return kept, dropped, "drop-low"

    # Phase 3: Truncate MEDIUM to 50%
    for s in kept:
        if s.get("counted", True) and s["priority"] == "MEDIUM":
            s["text"] = _truncate_section(s["text"], len(s["text"]) // 2)
            s["status"] = "truncated-50%"
    total = _counted_total(kept)
    if total <= budget:
        _write_log([_alloc_entry(s) for s in kept], total, budget, dropped, num_messages, "trim-medium-50")
        _reassemble(msg, kept)
        return kept, dropped, "trim-medium-50"

    # Phase 4: Drop MEDIUM
    kept2 = [s for s in kept if not (s.get("counted", True) and s["priority"] == "MEDIUM")]
    total = _counted_total(kept2)
    if total <= budget:
        _write_log([_alloc_entry(s) for s in kept2], total, budget, dropped + ["MEDIUM"], num_messages, "drop-medium")
        _reassemble(msg, kept2)
        return kept2, dropped, "drop-medium"

    # Phase 5: Proportional truncation of HIGH and CRITICAL together
    # Distribute budget proportionally across all remaining counted sections,
    # respecting max_fraction caps. Always runs â even if one section exceeds budget.
    counted_remaining = [s for s in kept2 if s.get("counted", True)]
    n = len(counted_remaining)
    if n > 0:
        # Give each section a share proportional to budget, capped by max_fraction
        per = budget // n
        for s in counted_remaining:
            cap = min(per, int(budget * s.get("max_fraction", 0.40)))
            # Always at least 200 chars if section exists (don't zero it out)
            cap = max(cap, 200) if len(s["text"]) > 200 else min(cap, len(s["text"]))
            s["text"] = _truncate_section(s["text"], cap)
            s["status"] = "truncated-fit"

    # Phase 6: If still over, hard-truncate largest section
    total = _counted_total(kept2)
    if total > budget:
        counted_remaining = [s for s in kept2 if s.get("counted", True)]
        # Sort by size descending, trim the biggest
        counted_remaining.sort(key=lambda s: len(s["text"]), reverse=True)
        while total > budget and counted_remaining:
            largest = counted_remaining[0]
            excess = total - budget
            new_size = max(200, len(largest["text"]) - excess - 100)
            largest["text"] = _truncate_section(largest["text"], new_size)
            largest["status"] = "hard-trimmed"
            total = _counted_total(kept2)
            counted_remaining = [s for s in kept2 if s.get("counted", True)]
            counted_remaining.sort(key=lambda s: len(s["text"]), reverse=True)

    total = _counted_total(kept2)
    _write_log([_alloc_entry(s) for s in kept2], total, budget, dropped, num_messages, "trim-high+critical")
    _feedback_check(total, budget, "trim-high+critical")
    _reassemble(msg, kept2)
    return kept2, dropped, "trim-high+critical"

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools
        num_messages = len(messages)
        budget = _dynamic_budget(num_messages)

        # Process ALL system messages (role == "system"), not just the first
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                _process_one(msg, budget, num_messages)

    except Exception as e:
        _log_error("transform failed: {}".format(e))

    return messages, tools
