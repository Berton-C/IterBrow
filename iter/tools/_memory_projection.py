"""Single source of truth for "which memory/ files are prompt memory".

NOT a tool (leading underscore -> iter.py's tool loader ignores this file,
same convention as _memory_guard.py).

WHY THIS EXISTS (2026-09-17 audit):
Three places independently decided what counts toward the MAX_MEMORY_CHARS
budget, and they disagreed:

  * iter.py            -- the authority. Builds the prompt projection of
                          memory/ and EXCLUDES recap/, tiers/,
                          self_improve_backups/, component_museum/, the
                          append-only journals/logs, and _-prefixed paths.
  * tools/self_improve.py     (fitness "memory_efficiency")
  * transformations/auto_improve.py (memory-pressure pain signal)
                       -- both walked the RAW folder (everything except
                          dot-files), so they counted ~1 MB of on-disk
                          storage that never reaches the prompt.

Consequences that were live before this fix:
  * memory_efficiency pinned at 0.0 -> 30% of the fitness composite dead,
    and the Sept-13 champion (0.58) unreachable by any full_loop.
  * auto_improve pain score ~20,000 vs threshold 3.0, re-arming
    .improve_needed every cycle. Iter's own dismissal note (2026-09-15)
    prescribed exactly this fix and deferred it under service-before-growth.

All three now call projection_files() / projection_chars() below. Changing
the rule here changes it everywhere at once.

Exclusions added here beyond iter.py's original list (each is on-disk
storage, not prompt memory, and was silently blowing the 20K budget):
  story_journal/   -- a web app (index.html + 293 KB stories.js) Iter built
                      on 2026-09-16 and stored under memory/.
  backups/         -- localStorage dumps.
  verification/    -- dated verification records (history, not state).
  probe_log.json   -- _metta_gate.py's runtime log.
  champion.json    -- self_improve state (its sibling self_improve_log.json
                      was already excluded).
  regression_tests.json / self_improve_regression_tests.json
                   -- eval.py results log and self_improve test definitions.
"""
import os

MEMORY_DIR = "memory"

# Directories anywhere in the relative path.
EXCLUDE_DIRS = frozenset({
    "recap",
    "tiers",
    "self_improve_backups",
    "component_museum",
    "story_journal",
    "backups",
    "verification",
})

# Exact file names.
EXCLUDE_NAMES = frozenset({
    "journal.jsonl",
    "self_improve_log.json",
    "soul_gate_log.json",
    "component_museum.jsonl",
    "probe_log.json",
    "champion.json",
    "regression_tests.json",
    "self_improve_regression_tests.json",
})


def _is_projected(rel_parts):
    """rel_parts: path components relative to memory/ (tuple of str)."""
    if not rel_parts:
        return False
    if any(part.startswith("_") for part in rel_parts):
        return False
    if any(part in EXCLUDE_DIRS for part in rel_parts):
        return False
    if rel_parts[-1] in EXCLUDE_NAMES:
        return False
    return True


def projection_files(memory_dir=MEMORY_DIR):
    """Sorted list of file paths (str) that iter.py projects into the prompt."""
    out = []
    for root, dirs, files in os.walk(memory_dir):
        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, memory_dir)
            parts = tuple(p for p in rel.split(os.sep) if p)
            if _is_projected(parts):
                out.append(full)
    out.sort()
    return out


def projection_chars(memory_dir=MEMORY_DIR):
    """Total stripped-text length of the projected files -- the same number
    iter.py compares against MAX_MEMORY_CHARS."""
    total = 0
    for path in projection_files(memory_dir):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                total += len(f.read().strip())
        except OSError:
            pass
    return total
