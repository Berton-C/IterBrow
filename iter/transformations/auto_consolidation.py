"""Auto-Consolidation: automatically roll up tier files when they exceed size limits."""
import os

DESCRIPTION = "Auto-consolidation: auto-rolls up tier files when they exceed size limits."

TIER_DIR = "memory/tiers"
TIERS = ["tier5", "tier4", "tier3", "tier2", "tier1"]
TIER_LIMITS = {"tier1": 8000, "tier2": 5000, "tier3": 3000, "tier4": 1500, "tier5": 300}
TIER_LABELS = {"tier5": "Life", "tier4": "Era", "tier3": "Episode", "tier2": "Fine", "tier1": "Step"}

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _read(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except:
        return ""

def _write(path, content):
    try:
        with open(path, "w") as f:
            f.write(content)
        return True
    except:
        return False

def _file_size(path):
    try:
        return os.stat(path)[6]
    except:
        return 0

def _compress_line(line, max_len=80):
    if len(line) <= max_len:
        return line
    return line[:max_len-3] + "..."

def _consolidate_tier(tier_name):
    """Roll up excess content from a tier into the next coarser tier."""
    idx = TIERS.index(tier_name)
    if idx == 0:
        return False  # coarsest tier, nowhere to roll up
    coarser = TIERS[idx - 1]
    fine_path = os.path.join(TIER_DIR, tier_name + ".txt")
    coarse_path = os.path.join(TIER_DIR, coarser + ".txt")
    if not _exists(fine_path):
        return False
    fine_size = _file_size(fine_path)
    fine_limit = TIER_LIMITS.get(tier_name, 9999)
    if fine_size <= fine_limit:
        return False
    fine_content = _read(fine_path)
    coarse_content = _read(coarse_path) if _exists(coarse_path) else ""
    # Split fine content into lines, keep first half in fine, roll up rest
    fine_lines = [l for l in fine_content.split("\n") if l.strip()]
    keep_count = max(1, len(fine_lines) // 2)
    keep_lines = fine_lines[:keep_count]
    roll_lines = fine_lines[keep_count:]
    # Compress rolled-up lines and append to coarse tier
    rolled = [_compress_line(l, 60) for l in roll_lines]
    new_coarse = coarse_content
    if rolled:
        if new_coarse:
            new_coarse = new_coarse + "\n" + "\n".join(rolled)
        else:
            new_coarse = "\n".join(rolled)
    _write(coarse_path, new_coarse)
    _write(fine_path, "\n".join(keep_lines))
    return True

def transform(messages, tools):
    try:
        consolidated = []
        for tier in TIERS:
            if _consolidate_tier(tier):
                consolidated.append(tier)
        if consolidated:
            block = "\n## Auto-Consolidation\nConsolidated tiers: " + ", ".join(consolidated) + "\n"
            for msg in reversed(messages):
                if msg.get("role") == "system":
                    msg["content"] = msg["content"] + block
                    break
    except Exception:
        pass
    return messages, tools