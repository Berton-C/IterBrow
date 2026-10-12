"""
Tiered Memory Pyramid with Context Budget-Fitting.

Reads the tier summaries in ./memory/tiers/ and assembles them into the
system message. Coarser tiers are always included; finer tiers are added
only if they fit within the character budget.

tier3/4/5 are a projection of memory/recap/episode_*.json written ONLY by
tools/rebuild_tiers.py. When the episodes are newer than the tiers (or the
tiers are missing/edited/over limit) this transformation calls
rebuild_tiers.ensure_current() first, so the pyramid always shows the newest
episode. Sizes are CHARACTERS everywhere (limits come from rebuild_tiers).

Tier files:
  tier5.txt  - coarsest (whole-life summary)
  tier4.txt  - era summaries (newest eras)
  tier3.txt  - episode summaries (newest episodes)
  tier2.txt, tier1.txt - legacy finer tiers, injected if present (no writer)
"""
import importlib.util
import os
from pathlib import Path

DESCRIPTION = "Tiered memory pyramid: rolls episode summaries up into era and life summaries and injects the pyramid."

TIER_DIR = "memory/tiers"
TIERS = ["tier5", "tier4", "tier3", "tier2", "tier1"]
DEFAULT_BUDGET = 8000  # character budget for assembled memory block

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

def _load_rebuild_tiers():
    for base in (Path(__file__).resolve().parent.parent, Path(os.environ.get("ITER_DIR", "."))):
        path = base / "tools" / "rebuild_tiers.py"
        if path.exists():
            spec = importlib.util.spec_from_file_location("_rebuild_tiers_for_tiered_memory", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("tools/rebuild_tiers.py not found")


def _check_rollups(limits):
    """Flag any rebuild_tiers tier still over its CHARACTER limit (a rebuild bug:
    rebuild_tiers always fits them). Cleared as soon as they fit."""
    needed = []
    for tier, limit in sorted(limits.items()):
        path = os.path.join(TIER_DIR, tier + ".txt")
        if _exists(path):
            size = len(_read_file(path))
            if size > limit:
                needed.append((tier, size, limit))
    flag_path = os.path.join(TIER_DIR, ".rollup_needed")
    if needed:
        lines = [f"{t}: {s} chars (limit {l})" for t, s, l in needed]
        lines.append("Call the rebuild_tiers tool to regenerate from memory/recap/ - never hand-edit tier files directly.")
        with open(flag_path, "w") as f:
            f.write("\n".join(lines))
    elif _exists(flag_path):
        os.remove(flag_path)

def transform(messages, tools):
    try:
        if not messages:
            return messages, tools

        notes = []
        try:
            rebuild_tiers = _load_rebuild_tiers()
            rebuild_tiers.ensure_current(actor="tiered_memory")
            _check_rollups(rebuild_tiers.TIER_LIMITS)
        except Exception as error:
            notes.append("[tiered_memory could not refresh tiers from memory/recap/: %s: %s]"
                         % (type(error).__name__, error))

        # Read all available tiers
        tier_contents = {}
        for tier in TIERS:
            path = os.path.join(TIER_DIR, tier + ".txt")
            if _exists(path):
                content = _read_file(path)
                if content:
                    tier_contents[tier] = content

        if not tier_contents and not notes:
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
                    # Keep the NEWEST lines (tier files are oldest-first).
                    tail = content[-(budget - 100):]
                    truncated = "..." + (tail.split("\n", 1)[1] if "\n" in tail else tail)
                    assembled_parts.append(header + "\n" + truncated)
                    budget = 0
                break

        if not assembled_parts and not notes:
            return messages, tools

        memory_block = "## Tiered Memory Pyramid\n\n" + "\n\n".join(notes + assembled_parts)

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
