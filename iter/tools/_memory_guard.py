"""Memory write-protection guard (Headlong-inspired).

NOT a tool itself (leading underscore -> Iter's tool loader ignores this
file, per the "#LESSONS" underscore convention already used for
_browser_bridge.py / _petta_db.py / _metta_gate.py / _metta_substrate.py).

Root cause of the memory-lobotomy incident: tools/python.py and
tools/shell.py give the agent raw, unsandboxed `open()`/`subprocess`
access with zero path restrictions. Under budget pressure the agent used
that raw access to directly rewrite/shrink its own append-only memory
files. Headlong's actual principle (verified against philosophy.md, not
assumed) is: the trajectory/log is immutable and append-only; anything
"compacted" is a *projection* computed from it, never a replacement for
it, and the projection is always regenerable from the source of truth.

This module enforces that boundary at the file-I/O layer so no future
self-repair spiral can repeat the incident, regardless of what Python
code or shell command the agent writes.

Three protection classes:

1. APPEND_ONLY  - history.metta, space.metta, nace_*.metta, chat.txt,
   transcript.txt. These are logs. 'w'/'x'/'w+' opens (which truncate or
   replace) are blocked. 'a'/'a+' (append) and read modes are always
   allowed.

2. CREATE_ONLY  - memory/recap/episode_*.json. New episodes may be
   created (file does not yet exist). An existing episode file may never
   be opened in a truncating/overwriting mode again.

3. REGEN_ONLY   - memory/tiers/tier*.txt. These are a pure, regenerable
   index/projection. Direct writes from agent code are always blocked;
   only tools/rebuild_tiers.py may write them, via the
   `allow_protected_write()` bypass below.

Deletion (os.remove/os.unlink/shutil.rmtree) of anything matching any of
the three classes is always blocked, with no bypass exposed to agent
code.
"""

import contextlib
import fnmatch
import os
import threading

APPEND_ONLY_PATTERNS = [
    "history.metta",
    "space.metta",
    "nace_*.metta",
    "chat.txt",
    "transcript.txt",
    "*/history.metta",
    "*/space.metta",
    "*/nace_*.metta",
    "*/chat.txt",
    "*/transcript.txt",
]

CREATE_ONLY_PATTERNS = [
    "memory/recap/episode_*.json",
    "*/memory/recap/episode_*.json",
]

REGEN_ONLY_PATTERNS = [
    "memory/tiers/tier*.txt",
    "*/memory/tiers/tier*.txt",
]

ALL_PROTECTED_PATTERNS = APPEND_ONLY_PATTERNS + CREATE_ONLY_PATTERNS + REGEN_ONLY_PATTERNS

_bypass = threading.local()


def _norm(path):
    try:
        return os.path.normpath(str(path)).replace(os.sep, "/")
    except Exception:
        return str(path)


def _matches(path, patterns):
    norm = _norm(path)
    base = os.path.basename(norm)
    for pat in patterns:
        if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(base, pat):
            return True
    return False


def _bypassed():
    return getattr(_bypass, "reason", None) is not None


@contextlib.contextmanager
def allow_protected_write(reason):
    """Sanctioned bypass for the regeneration/journal tools themselves.

    Usage (inside rebuild_tiers.py / memory_journal.py / episode-creation
    helpers only):
        with allow_protected_write("rebuild_tiers: regenerating tier3"):
            with open(path, "w") as f:
                f.write(content)
    """
    prev = getattr(_bypass, "reason", None)
    _bypass.reason = reason
    try:
        yield
    finally:
        _bypass.reason = prev


def _journal_block(kind, path, reason):
    try:
        import memory_journal
        memory_journal.log("_memory_guard", "blocked_" + kind, {"path": str(path), "reason": reason})
    except Exception:
        pass  # never let journaling itself break the guard


def check_open(path, mode):
    """Raise PermissionError if this open() call would violate a memory
    protection rule. Returns silently (None) if the call is fine."""
    if _bypassed():
        return
    mode = mode or "r"
    truncating = any(c in mode for c in ("w", "x")) and "a" not in mode

    if not truncating:
        return  # read / append modes are always fine

    if _matches(path, REGEN_ONLY_PATTERNS):
        _journal_block("open", path, "regenerable tier file, use rebuild_tiers")
        raise PermissionError(
            "BLOCKED: %r is a regenerable memory-tier file. Direct writes are "
            "not permitted from agent code - call the rebuild_tiers tool "
            "instead, which regenerates it from memory/recap/ (the source of "
            "truth)." % (path,)
        )

    if _matches(path, APPEND_ONLY_PATTERNS):
        _journal_block("open", path, "append-only log opened in mode %r" % (mode,))
        raise PermissionError(
            "BLOCKED: %r is an append-only memory log. Opening it in a "
            "truncating/overwrite mode (%r) is not permitted. Open with mode "
            "'a' to append instead." % (path, mode)
        )

    if _matches(path, CREATE_ONLY_PATTERNS):
        if os.path.exists(path):
            _journal_block("open", path, "attempted overwrite of existing episode")
            raise PermissionError(
                "BLOCKED: %r is an existing recap episode. Episodes are "
                "immutable once written and may never be overwritten. Create "
                "a new episode_NNNN.json with the next episode number "
                "instead." % (path,)
            )
        return  # creating a brand-new episode file is fine


def check_remove(path):
    if _bypassed():
        return
    if _matches(path, ALL_PROTECTED_PATTERNS):
        _journal_block("remove", path, "delete attempt on protected memory content")
        raise PermissionError(
            "BLOCKED: %r is protected memory content and may never be "
            "deleted." % (path,)
        )


def guarded_open_factory(real_open):
    def guarded_open(path, mode="r", *args, **kwargs):
        check_open(path, mode)
        return real_open(path, mode, *args, **kwargs)
    return guarded_open


class GuardedOS:
    """Thin proxy over the real `os` module: passes everything through
    unchanged except the handful of calls that can destroy protected
    memory files, which are checked first. Deliberately does NOT copy
    attributes eagerly so it always reflects the live os module."""

    def __init__(self, real_os):
        object.__setattr__(self, "_real_os", real_os)

    def remove(self, path, *a, **kw):
        check_remove(path)
        return self._real_os.remove(path, *a, **kw)

    def unlink(self, path, *a, **kw):
        check_remove(path)
        return self._real_os.unlink(path, *a, **kw)

    def rename(self, src, dst, *a, **kw):
        check_remove(src)
        return self._real_os.rename(src, dst, *a, **kw)

    def replace(self, src, dst, *a, **kw):
        check_remove(src)
        return self._real_os.replace(src, dst, *a, **kw)

    def truncate(self, path, *a, **kw):
        check_remove(path)
        return self._real_os.truncate(path, *a, **kw)

    def __getattr__(self, name):
        return getattr(self._real_os, name)


SHELL_DANGER_PATTERNS = [
    r">\s*\S*(history|space|chat|transcript)\.(metta|txt)\b",
    r">\s*\S*nace_\w*\.metta\b",
    r">\s*\S*tiers?/tier\d\.txt\b",
    r">\s*\S*recap/episode_\d+\.json\b",
    r"\brm\s+.*(history\.metta|space\.metta|chat\.txt|transcript\.txt|nace_\w*\.metta|tiers?/tier\d\.txt|recap/episode_\d+\.json)",
    r"\btruncate\s+.*(history\.metta|space\.metta|chat\.txt|transcript\.txt|tiers?/tier\d\.txt)",
    r":\s*>\s*\S*(history|space|chat|transcript)\.(metta|txt)\b",
    r"\bmv\s+.*(recap/episode_\d+\.json|tiers?/tier\d\.txt)\b",
]


def scan_shell_command(cmd):
    """Best-effort heuristic scan for shell commands. Shell is
    fundamentally unsandboxable without an OS-level jail, so this is a
    second line of defense (the real guarantee is the python.py open()/os
    guard above) - it catches the obvious/likely destructive patterns and
    always logs what it blocks."""
    import re
    for pat in SHELL_DANGER_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return pat
    return None
