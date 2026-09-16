"""Sanctioned, deterministic tier regeneration (Headlong-inspired fix #2).

memory/tiers/tier3.txt / tier4.txt / tier5.txt are a *projection* -
Headlong's real principle, verified against philosophy.md: the append-only
trajectory (here: memory/recap/episode_*.json, backed 1:1 by history.metta)
is the sole source of truth. Tiers are always fully recomputable from it and
must never be hand-edited or destructively trimmed in place - that was the
actual mechanism of the memory-lobotomy incident.

This tool is the ONLY sanctioned writer of memory/tiers/*.txt (enforced by
tools/_memory_guard.py's REGEN_ONLY_PATTERNS - direct writes from agent
python/shell code are blocked). It always rewrites all three tiers from
scratch by reading memory/recap/episode_*.json, so re-running it is always
safe and idempotent; there is no "trim the existing tier file" code path at
all, by construction.

Deterministic (no LLM call, no network dependency) so it can be run any
time - including automatically when transformations/tiered_memory.py's
rollup-needed flag fires - without depending on LM Studio being reachable.
"""

import json
import os
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as guard
import memory_journal

DESCRIPTION = (
    "Regenerate memory/tiers/tier3.txt, tier4.txt, and tier5.txt from "
    "memory/recap/episode_*.json (the source of truth). This is the ONLY "
    "sanctioned way to update tier files - direct writes to them from "
    "python/shell are blocked. Safe to call any time; always idempotent. "
    "Call this instead of hand-editing tier files whenever memory/tiers/"
    ".rollup_needed exists or tiers look stale."
)

RECAP_DIR = "memory/recap"
TIER_DIR = "memory/tiers"

TIER3_EPISODE_WINDOW = 10   # most recent N episodes, one line each, verbatim summary
TIER4_CHUNK_SIZE = 5        # older episodes collapsed into chunks of N
TIER3_LIMIT = 3000
TIER4_LIMIT = 1500
TIER5_LIMIT = 300


def _list_episodes():
    episodes = []
    if not os.path.isdir(RECAP_DIR):
        return episodes
    for entry in sorted(os.listdir(RECAP_DIR)):
        if entry.startswith("episode_") and entry.endswith(".json"):
            path = os.path.join(RECAP_DIR, entry)
            try:
                with open(path, "r") as f:
                    ep = json.loads(f.read())
                ep["_file"] = entry
                episodes.append(ep)
            except Exception:
                continue
    episodes.sort(key=lambda e: e.get("_file", ""))
    return episodes


def _episode_num(ep):
    """Real on-disk schema (verified against live episode_*.json, not the
    more verbose {title, start_time, ...} shape transformations/recap.py's
    flag message describes aspirationally): {"e" or "id": N, "s": summary,
    optional "t": type}."""
    return ep.get("e", ep.get("id", ep.get("e_num", "?")))


def _one_line(ep):
    num = _episode_num(ep)
    summary = (ep.get("s", "") or ep.get("summary", "") or "").strip().replace("\n", " ")
    if len(summary) > 160:
        summary = summary[:157] + "..."
    mem_type = ep.get("t", "")
    type_tag = " (%s)" % mem_type if mem_type else ""
    return "E%s%s: %s" % (num, type_tag, summary) if summary else "E%s%s" % (num, type_tag)


def _build_tier3(recent_eps):
    lines = [_one_line(ep) for ep in recent_eps]
    text = "\n".join(lines)
    if len(text) > TIER3_LIMIT:
        text = text[:TIER3_LIMIT - 3].rsplit("\n", 1)[0] + "\n..."
    return text


def _build_tier4(older_eps):
    chunks = []
    for i in range(0, len(older_eps), TIER4_CHUNK_SIZE):
        chunk = older_eps[i:i + TIER4_CHUNK_SIZE]
        first_num = _episode_num(chunk[0])
        last_num = _episode_num(chunk[-1])
        summaries = [(ep.get("s", "") or ep.get("summary", "") or "").strip() for ep in chunk]
        summaries = [s for s in summaries if s]
        summary = "; ".join(summaries[:3])
        era_label = "%s-%s" % (first_num, last_num)
        chunks.append("E%s: %s" % (era_label, summary))
    text = "\n".join(chunks)
    if len(text) > TIER4_LIMIT:
        text = text[:TIER4_LIMIT - 3].rsplit("\n", 1)[0] + "\n..."
    return text


def _build_tier5(all_eps):
    if not all_eps:
        return ""
    n = len(all_eps)
    first_num = _episode_num(all_eps[0])
    last_num = _episode_num(all_eps[-1])
    text = "%d episodes recorded, E%s to E%s." % (n, first_num, last_num)
    if len(text) > TIER5_LIMIT:
        text = text[:TIER5_LIMIT - 3] + "..."
    return text


def rebuild(actor="agent"):
    episodes = _list_episodes()
    os.makedirs(TIER_DIR, exist_ok=True)

    recent = episodes[-TIER3_EPISODE_WINDOW:] if episodes else []
    older = episodes[:-TIER3_EPISODE_WINDOW] if len(episodes) > TIER3_EPISODE_WINDOW else []

    tier3 = _build_tier3(recent)
    tier4 = _build_tier4(older)
    tier5 = _build_tier5(episodes)

    written = {}
    with guard.allow_protected_write("rebuild_tiers: regenerating from recap source of truth"):
        for name, content in (("tier3.txt", tier3), ("tier4.txt", tier4), ("tier5.txt", tier5)):
            path = os.path.join(TIER_DIR, name)
            with open(path, "w") as f:
                f.write(content)
            written[name] = len(content)

        flag_path = os.path.join(TIER_DIR, ".rollup_needed")
        if os.path.exists(flag_path):
            try:
                os.remove(flag_path)
            except Exception:
                pass

    memory_journal.log(actor, "rebuild_tiers", {
        "episode_count": len(episodes),
        "tier_sizes": written,
    })
    return {"episode_count": len(episodes), "tier_sizes": written}


def run(actor="agent"):
    result = rebuild(actor=actor)
    import json as _json
    return _json.dumps(result)
