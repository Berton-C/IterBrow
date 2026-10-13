"""Sanctioned, deterministic tier regeneration (Headlong-inspired fix #2).

memory/tiers/tier3.txt / tier4.txt / tier5.txt are a *projection* -
Headlong's real principle, verified against philosophy.md: the append-only
trajectory (here: memory/recap/episode_*.json, backed 1:1 by history.metta)
is the sole source of truth. Tiers are always fully recomputable from it and
must never be hand-edited or destructively trimmed in place - that was the
actual mechanism of the memory-lobotomy incident.

This tool is the ONLY sanctioned writer of memory/tiers/*.txt (enforced by
tools/_memory_guard.py's REGEN_ONLY_PATTERNS - direct writes from agent
python code are blocked; shell checks are best effort). It always rewrites all three tiers from
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
import hashlib
from iterbrow_runtime.episodic_history import list_episodes, archive_text, chronological
from iterbrow_runtime.atomspace_store import _atomic_text

DESCRIPTION = (
    "Regenerate memory/tiers/tier3.txt, tier4.txt, and tier5.txt from "
    "memory/recap/episode_*.json (the source of truth). This is the ONLY "
    "sanctioned way to update tier files - direct writes are blocked in the "
    "python tool (shell checks are best effort). Safe to call any time; always idempotent. "
    "Call this instead of hand-editing tier files whenever memory/tiers/"
    ".rollup_needed exists or tiers look stale."
)

RECAP_DIR = "memory/recap"
TIER_DIR = "memory/tiers"
STATE_PATH = os.path.join(TIER_DIR, ".rebuild_state.json")
FLAG_PATH = os.path.join(TIER_DIR, ".rollup_needed")
# Tier4/tier5 text that existed before the first rebuild (hand-maintained,
# covering episodes that no longer exist) is frozen here once and injected by
# tiered_memory ahead of the regenerated tiers.  Never written by the agent.
LEGACY_PATH = os.path.join(TIER_DIR, "legacy_summary.txt")
LEGACY_LIMIT = 1500  # characters tiered_memory injects

TIER3_EPISODE_WINDOW = 10   # most recent N episodes, one line each, verbatim summary
TIER4_CHUNK_SIZE = 5        # older episodes collapsed into eras of N
ERA_SUMMARY_CHARS = 90      # per-episode excerpt inside an era line
# One size unit everywhere: CHARACTERS of the text (len(str)), never file bytes.
# transformations/tiered_memory.py and auto_consolidation.py import these.
TIER_LIMITS = {"tier3": 3000, "tier4": 1500, "tier5": 300}
TIER3_LIMIT = TIER_LIMITS["tier3"]
TIER4_LIMIT = TIER_LIMITS["tier4"]
TIER5_LIMIT = TIER_LIMITS["tier5"]
TIER_NAMES = ("tier3", "tier4", "tier5")


def _list_episodes():
    # Ordered by the time each episode covers (end_time, else start_time;
    # untimed ones keep their numeric place), so an episode written late about
    # an earlier period is not "most recent". Numbers are numeric, never
    # lexicographic: episode_10 sorts after episode_9.
    return chronological(list_episodes(RECAP_DIR))


def _episode_num(ep):
    """Real on-disk schema: {"e" or "id": N, "s": summary, optional "t": type}."""
    if ep.get("_n") is not None:
        return ep["_n"]
    return ep.get("e", ep.get("id", ep.get("e_num", "?")))


def _summary(ep):
    return (ep.get("s", "") or ep.get("summary", "") or ep.get("title", "") or "").strip().replace("\n", " ")


def _clip(text, limit):
    return text if len(text) <= limit else text[:max(0, limit - 3)] + "..."


def _one_line(ep):
    num = _episode_num(ep)
    summary = _clip(_summary(ep), 160)
    mem_type = ep.get("t", "")
    type_tag = " (%s)" % mem_type if mem_type else ""
    return "E%s%s: %s" % (num, type_tag, summary) if summary else "E%s%s" % (num, type_tag)


def _keep_newest(lines, limit):
    """Join lines under `limit` characters, dropping the OLDEST lines first."""
    kept = list(lines)
    while kept and len("\n".join(kept)) > limit:
        if len(kept) == 1:
            return _clip(kept[0], limit), len(lines) - 1
        kept.pop(0)
    return "\n".join(kept), len(lines) - len(kept)


def _build_tier3(recent_eps):
    text, _dropped = _keep_newest([_one_line(ep) for ep in recent_eps], TIER3_LIMIT)
    return text


def _eras(older_eps):
    eras = []
    for i in range(0, len(older_eps), TIER4_CHUNK_SIZE):
        chunk = older_eps[i:i + TIER4_CHUNK_SIZE]
        summaries = [_clip(_summary(ep), ERA_SUMMARY_CHARS) for ep in chunk]
        summaries = [s for s in summaries if s]
        label = "%s-%s" % (_episode_num(chunk[0]), _episode_num(chunk[-1]))
        eras.append((label, "E%s: %s" % (label, "; ".join(summaries[:3]))))
    return eras


def _build_tier4(older_eps):
    """Newest eras that fit TIER4_LIMIT; returns (text, labels of folded older eras)."""
    eras = _eras(older_eps)
    text, dropped = _keep_newest([line for _label, line in eras], TIER4_LIMIT)
    return text, [label for label, _line in eras[:dropped]]


def _build_tier5(all_eps, folded=()):
    if not all_eps:
        return ""
    text = "%d episodes recorded, E%s to E%s." % (
        len(all_eps), _episode_num(all_eps[0]), _episode_num(all_eps[-1]))
    if folded:
        text += " Older eras E%s to E%s are folded into this count (see memory/recap/)." % (
            folded[0].split("-")[0], folded[-1].split("-")[-1])
    return _clip(text, TIER5_LIMIT)


def plan(episodes=None):
    """The tier texts the current episodes produce (no writes)."""
    episodes = _list_episodes() if episodes is None else episodes
    recent = episodes[-TIER3_EPISODE_WINDOW:]
    older = episodes[:-TIER3_EPISODE_WINDOW] if len(episodes) > TIER3_EPISODE_WINDOW else []
    tier4, folded = _build_tier4(older)
    return {"tier3": _build_tier3(recent), "tier4": tier4, "tier5": _build_tier5(episodes, folded)}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_signature():
    """Identity of the episode set (names, sizes, mtimes): changes when an
    episode is added, so tiers are known to be stale without re-reading them."""
    rows = []
    try:
        for name in sorted(os.listdir(RECAP_DIR)):
            if name.startswith("episode_") and name.endswith(".json"):
                st = os.stat(os.path.join(RECAP_DIR, name))
                rows.append("%s:%d:%d" % (name, st.st_size, st.st_mtime_ns))
    except OSError:
        pass
    return _sha("\n".join(rows))


def _read_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _read_tier(name):
    try:
        with open(os.path.join(TIER_DIR, name + ".txt"), "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def needs_rebuild():
    """Why the tier files do not match the episodes, or None when current."""
    state = _read_state()
    if state.get("source") != source_signature():
        return "episodes changed since the last rebuild"
    written = state.get("written", {})
    for name in TIER_NAMES:
        text = _read_tier(name)
        if text is None:
            return "%s.txt missing" % name
        if written.get(name) != _sha(text):
            return "%s.txt changed outside rebuild_tiers" % name
        if len(text) > TIER_LIMITS[name]:
            return "%s.txt over its %d-character limit" % (name, TIER_LIMITS[name])
    return None


def _freeze_legacy_summary(tiers):
    """First rebuild only: keep the pre-existing life (tier5) and era (tier4)
    summaries -- the only summaries of episodes that no longer exist -- as
    legacy_summary.txt, created once and never rewritten."""
    parts = []
    for name, label in (("tier5", "Life summary"), ("tier4", "Era summaries")):
        current = (_read_tier(name) or "").strip()
        if current and current != tiers[name].strip():
            parts.append("%s (written before episode records):\n%s" % (label, current))
    if not parts:
        return False
    try:
        with open(LEGACY_PATH, "x", encoding="utf-8") as handle:
            handle.write("\n\n".join(parts) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        return False
    return True


def rebuild(actor="agent"):
    """The ONLY writer of tier3/4/5. Deterministic and idempotent: unchanged
    tiers are not rewritten. Tier text this tool did not write itself (e.g. an
    older hand-maintained tier) is archived under memory/archive/ first."""
    signature = source_signature()
    episodes = _list_episodes()
    os.makedirs(TIER_DIR, exist_ok=True)
    tiers = plan(episodes)
    state = _read_state()
    previous = state.get("written", {})

    written, changed = {}, []
    with guard.allow_protected_write("rebuild_tiers: regenerating from recap source of truth"):
        if not state and not os.path.exists(LEGACY_PATH):
            _freeze_legacy_summary(tiers)
        for name in TIER_NAMES:
            content = tiers[name]
            path = os.path.join(TIER_DIR, name + ".txt")
            current = _read_tier(name)
            if current != content:
                if current and previous.get(name) != _sha(current):
                    archive_text(path, current)  # preserve text rebuild did not produce
                _atomic_text(path, content)
                changed.append(name)
            written[name] = len(content)

        if os.path.exists(FLAG_PATH):
            try:
                os.remove(FLAG_PATH)
            except OSError:
                pass
    _atomic_text(STATE_PATH, json.dumps({
        "source": signature, "episode_count": len(episodes),
        "written": {name: _sha(tiers[name]) for name in TIER_NAMES}}))

    if changed:
        memory_journal.log(actor, "rebuild_tiers", {
            "episode_count": len(episodes), "tier_sizes": written, "changed": changed})
    return {"episode_count": len(episodes), "tier_sizes": written, "changed": changed}


def ensure_current(actor="auto"):
    """Rebuild only when the tiers do not match the episodes. Never blanks
    tiers when there are no episodes at all."""
    if not _list_episodes():
        return None
    reason = needs_rebuild()
    if reason is None:
        return None
    result = rebuild(actor=actor)
    result["reason"] = reason
    return result


def run(actor="agent"):
    return json.dumps(rebuild(actor=actor))
