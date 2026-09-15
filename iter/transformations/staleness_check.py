"""
Staleness Detection for AGENTS.md.

Compares actual files on disk (tools, channels, transformations) against
what AGENTS.md documents. If discrepancies are found, appends a warning
block to the system message so the agent knows AGENTS.md needs updating.

Checks:
  - Tools: .py files in ./tools/ not starting with _
  - Channels: .py files in ./channels/ not starting with _
  - Transformations: .py files in ./transformations/ not starting with _

Matching logic:
  - Strips .py extension, checks if base name appears in AGENTS.md
  - Also checks full filename (with .py)
  - Handles glob patterns in AGENTS.md (e.g. dashboard_*.py matches dashboard_atomspace.py)

FLOURISHING BRIDGE: AGENTS.md is this system's own persistent record of
itself -- what it maintains, and how. Reinterpreted through the
flourishing lens the user approved, drift between disk and AGENTS.md is
exactly the maintain_memory pattern's non-flourishing pole (Purpose Beyond
Utility): identity-continuity documentation going stale rather than being
kept coherent. Tracked via a small streak counter (mirrors idle_cycle_
detector.py's RECURRENCE_THRESHOLD convention) so a single noisy cycle
doesn't get recorded, only a real persistent drift (3+ consecutive stale
checks) or its resolution (drift clears after having been recorded). Feeds
`(pending-revision pattern maintain_memory <outcome>)` into
nace_pending.metta via tools/_provenance.record_pattern_outcome -- the
same shared append helper provenance_guard.py already uses.
"""
import os
import sys
import json
import fnmatch

_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
try:
    import _provenance as _prov
except Exception:
    _prov = None

DESCRIPTION = "Detect staleness in AGENTS.md by comparing disk vs documented files, and feed maintain_memory (Purpose Beyond Utility) evidence on persistent-drift/repair transitions."

_PATTERN_STATE_PATH = os.path.join("memory", ".staleness_pattern_state.json")
_PATTERN_STREAK_THRESHOLD = 3  # consecutive stale checks before it's worth naming as a pattern, mirrors idle_cycle_detector's RECURRENCE_THRESHOLD convention

BASE = "."
AGENTS_MD = os.path.join(BASE, "AGENTS.md")

DIRS = {
    "tools": os.path.join(BASE, "tools"),
    "channels": os.path.join(BASE, "channels"),
    "transformations": os.path.join(BASE, "transformations"),
}

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _list_active_py(directory):
    """Return set of active .py filenames (not starting with _) in a directory."""
    result = set()
    try:
        for entry in os.listdir(directory):
            if entry.endswith(".py") and not entry.startswith("_"):
                result.add(entry)
    except OSError:
        pass
    return result

def _is_documented(fname, md_content):
    """Check if fname (e.g. 'chroma_query.py') is referenced in AGENTS.md.

    Matches if any of these appear in md_content:
      - The full filename: 'chroma_query.py'
      - The base name: 'chroma_query'
      - A glob pattern that matches: e.g. 'chroma_*.py' or '*.py'
    """
    if fname in md_content:
        return True
    base = fname[:-3] if fname.endswith(".py") else fname  # strip .py
    if base in md_content:
        return True
    # Check glob patterns in the markdown (e.g. dashboard_*.py)
    # Extract all glob-like patterns from the markdown
    for token in md_content.replace("`", " ").split():
        if "*" in token and fnmatch.fnmatch(fname, token):
            return True
    return False

def _load_pattern_state():
    try:
        with open(_PATTERN_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
            if isinstance(state, dict):
                return state
    except Exception:
        pass
    return {"streak": 0, "recorded": False}


def _save_pattern_state(state):
    try:
        os.makedirs("memory", exist_ok=True)
        with open(_PATTERN_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _record_maintain_memory(is_stale):
    """Feed maintain_memory pattern-efficacy on real streak transitions
    only -- never every cycle. `is_stale` is this cycle's raw finding
    (any undocumented files at all)."""
    if _prov is None:
        return
    state = _load_pattern_state()
    streak = state.get("streak", 0)
    recorded = state.get("recorded", False)

    if is_stale:
        streak += 1
        if streak >= _PATTERN_STREAK_THRESHOLD and not recorded:
            _prov.record_pattern_outcome("maintain_memory", "violated")
            recorded = True
    else:
        if recorded:
            _prov.record_pattern_outcome("maintain_memory", "confirmed")
        streak = 0
        recorded = False

    _save_pattern_state({"streak": streak, "recorded": recorded})


def transform(messages, tools):
    try:
        if not messages:
            return messages, tools
        if not _exists(AGENTS_MD):
            return messages, tools

        with open(AGENTS_MD, "r") as f:
            md_content = f.read()

        warnings = []
        for label, dirpath in DIRS.items():
            on_disk = _list_active_py(dirpath)
            if not on_disk:
                continue
            undocumented = []
            for fname in sorted(on_disk):
                if not _is_documented(fname, md_content):
                    undocumented.append(fname)
            if undocumented:
                warnings.append("  {} not in AGENTS.md: {}".format(label, ", ".join(undocumented)))

        if warnings:
            block = "\n\n--- \u26a0\ufe0f AGENTS.md STALENESS WARNING ---\n"
            block += "The following active files are not documented in AGENTS.md:\n"
            block += "\n".join(warnings)
            block += "\nConsider updating AGENTS.md to include them.\n"

            first_msg = messages[0]
            if isinstance(first_msg, dict):
                fc = first_msg.get("content", "")
                if isinstance(fc, str):
                    first_msg["content"] = fc.rstrip() + block
                elif isinstance(fc, list):
                    first_msg["content"] = fc + [{"type": "text", "text": block}]

        _record_maintain_memory(bool(warnings))

    except Exception:
        pass

    return messages, tools
