"""
Tiered Memory Pyramid with Context Budget-Fitting + Rollup Detection.

Reads pre-computed tier summaries from ./memory/tiers/ and assembles
them into the system message. Coarser tiers are always included;
finer tiers are added only if they fit within the context budget.

Also checks tier file sizes and signals when rollups are needed by
writing a flag to ./memory/tiers/.rollup_needed.

Tier files:
  tier5.txt  â coarsest (whole-life summary, ~300 chars)
  tier4.txt  â era summaries (~1500 chars)
  tier3.txt  â episode summaries (~3000 chars)
  tier2.txt  â fine episode rollups (~5000 chars)
  tier1.txt  â finest step rollups (~8000 chars)

Rollup thresholds (chars before triggering):
  tier1 > 8000  â roll up excess into tier2
  tier2 > 5000  â roll up excess into tier3
  tier3 > 3000  â roll up excess into tier4
  tier4 > 1500  â roll up excess into tier5
"""
import os

DESCRIPTION = "Tiered memory pyramid: rolls episode summaries up into era and life summaries and injects the pyramid."

TIER_DIR = "memory/tiers"
TIERS = ["tier5", "tier4", "tier3", "tier2", "tier1"]
DEFAULT_BUDGET = 8000  # character budget for assembled memory block

TIER_LIMITS = {
    "tier1": 8000,
    "tier2": 5000,
    "tier3": 3000,
    "tier4": 1500,
    "tier5": 300,
}

TIER_LABELS = {
    "tier5": "Life Summary",
    "tier4": "Era Summaries",
    "tier3": "Episode Summaries",
    "tier2": "Fine Episode Rollups",
    "tier1": "Step-Level Rollups",
}

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

def _file_size(path):
    try:
        return os.stat(path)[6]
    except Exception:
        return 0

def _check_rollups():
    """Check if any tier exceeds its limit. If so, write a flag file."""
    needed = []
    for tier in TIERS:
        path = os.path.join(TIER_DIR, tier + ".txt")
        if _exists(path):
            size = _file_size(path)
            limit = TIER_LIMITS.get(tier, 9999)
            if size > limit:
                needed.append((tier, size, limit))
    if needed:
        flag_path = os.path.join(TIER_DIR, ".rollup_needed")
        lines = [f"{t}: {s} chars (limit {l})" for t, s, l in needed]
        lines.append("Call the rebuild_tiers tool to regenerate from memory/recap/ - never hand-edit tier files directly, direct writes are blocked.")
        with open(flag_path, "w") as f:
            f.write("\n".join(lines))
    else:
        flag_path = os.path.join(TIER_DIR, ".rollup_needed")
        if _exists(flag_path):
            try:
                os.remove(flag_path)
            except Exception:
                pass

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools

        # Check if rollups are needed (side-effect: may write flag file)
        _check_rollups()

        # Read all available tiers
        tier_contents = {}
        for tier in TIERS:
            path = os.path.join(TIER_DIR, tier + ".txt")
            if _exists(path):
                content = _read_file(path)
                if content:
                    tier_contents[tier] = content

        if not tier_contents:
            return messages, tools

        # Budget-fitting: greedily include tiers from coarsest to finest
        budget = DEFAULT_BUDGET
        assembled_parts = []

        for tier in TIERS:
            if tier not in tier_contents:
                continue
            content = tier_contents[tier]
            header = "## " + TIER_LABELS.get(tier, tier)
            block = header + "\n" + content

            if len(block) <= budget:
                assembled_parts.append(block)
                budget -= len(block)
            else:
                if budget > 200:
                    truncated = content[:budget - 100].rsplit(" ", 1)[0] + "..."
                    assembled_parts.append(header + "\n" + truncated)
                    budget = 0
                break

        if not assembled_parts:
            return messages, tools

        memory_block = "## Tiered Memory Pyramid\n\n" + "\n\n".join(assembled_parts)

        # Inject into system message (first message)
        first_msg = messages[0]
        if isinstance(first_msg, dict):
            content = first_msg.get("content", "")
            if isinstance(content, str):
                first_msg["content"] = content.rstrip() + "\n\n" + memory_block
            elif isinstance(content, list):
                first_msg["content"] = content + [{"type": "text", "text": "\n\n" + memory_block}]

    except Exception:
        pass

    return messages, tools
