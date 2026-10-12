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
   transcript.txt. These are logs. Any write mode other than append
   ('w', 'x', 'r+', 'w+', ...) is blocked; 'a'/'a+' and reads are allowed.

2. CREATE_ONLY  - memory/recap/episode_*.json. New episodes may be
   created (file does not yet exist). An existing episode file may never
   be written again, in any mode (overwrite, 'r+', append).

3. REGEN_ONLY   - memory/tiers/tier*.txt (and the frozen legacy_summary.txt
   rebuild_tiers writes once). These are a pure, regenerable
   index/projection. Every write from agent code is blocked; only
   tools/rebuild_tiers.py may write them, via the `allow_protected_write()`
   bypass below.

Deletion (os.remove/os.unlink/shutil.rmtree), and renaming or replacing
another file ONTO a protected path, are blocked for all three classes.

Enforcement: tools/python.py installs guard_process() for the duration of
the agent's code: builtins.open, io.open, os.open, os.remove/unlink/
rename/replace/truncate are checked process-wide, which also covers
pathlib and modules the code imports itself. tools/shell.py can only scan
the command text (scan_shell_command) - that part is BEST EFFORT; a shell
can always bypass it.
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
    # Frozen pre-episode summaries, written once by rebuild_tiers.
    "memory/tiers/legacy_summary.txt",
    "*/memory/tiers/legacy_summary.txt",
]

ALL_PROTECTED_PATTERNS = APPEND_ONLY_PATTERNS + CREATE_ONLY_PATTERNS + REGEN_ONLY_PATTERNS

_bypass = threading.local()


def _candidates(path):
    try:
        raw = os.fspath(path)
    except TypeError:
        return []
    if isinstance(raw, bytes):
        raw = os.fsdecode(raw)
    out = [os.path.normpath(raw).replace(os.sep, "/")]
    try:
        out.append(os.path.abspath(raw).replace(os.sep, "/"))
    except Exception:
        pass
    return out


def _norm(path):
    found = _candidates(path)
    return found[0] if found else str(path)


def _matches(path, patterns):
    for norm in _candidates(path):
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
    protection rule. Returns silently (None) if the call is fine. Any of
    'w', 'x', 'a', '+' in the mode is a write."""
    if _bypassed() or isinstance(path, int):
        return
    mode = mode or "r"
    if not any(c in mode for c in "wxa+"):
        return  # read-only
    appending = "a" in mode and not any(c in mode for c in "wx")

    if _matches(path, REGEN_ONLY_PATTERNS):
        _journal_block("open", path, "regenerable tier file, use rebuild_tiers")
        raise PermissionError(
            "BLOCKED: %r is a regenerable memory-tier file. Direct writes are "
            "not permitted from agent code - call the rebuild_tiers tool "
            "instead, which regenerates it from memory/recap/ (the source of "
            "truth)." % (path,)
        )

    if _matches(path, APPEND_ONLY_PATTERNS) and not appending:
        _journal_block("open", path, "append-only log opened in mode %r" % (mode,))
        raise PermissionError(
            "BLOCKED: %r is an append-only memory log. Opening it in a "
            "truncating/overwrite mode (%r) is not permitted. Open with mode "
            "'a' to append instead." % (path, mode)
        )

    if _matches(path, CREATE_ONLY_PATTERNS):
        if os.path.exists(path):
            _journal_block("open", path, "attempted write to existing episode")
            raise PermissionError(
                "BLOCKED: %r is an existing recap episode. Episodes are "
                "immutable once written and may never be overwritten. Use the "
                "record_episode tool to add the next episode instead." % (path,)
            )
        return  # creating a brand-new episode file is fine


def check_os_open(path, flags):
    """os.open() flags expressed as an open() mode for check_open."""
    if flags & getattr(os, "O_TRUNC", 0):
        mode = "w"
    elif flags & getattr(os, "O_APPEND", 0):
        mode = "a"
    elif flags & (os.O_WRONLY | os.O_RDWR):
        mode = "x" if flags & getattr(os, "O_EXCL", 0) else "r+"
    elif flags & getattr(os, "O_CREAT", 0):
        mode = "x"
    else:
        mode = "r"
    check_open(path, mode)


def check_replace_target(dst):
    """Renaming/replacing a file ONTO a protected path overwrites it."""
    if _bypassed():
        return
    if _matches(dst, REGEN_ONLY_PATTERNS) or _matches(dst, APPEND_ONLY_PATTERNS) or (
            _matches(dst, CREATE_ONLY_PATTERNS) and os.path.exists(dst)):
        _journal_block("replace", dst, "rename/replace onto protected memory content")
        raise PermissionError(
            "BLOCKED: %r is protected memory content; renaming or replacing "
            "another file onto it is not permitted." % (dst,)
        )


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
        check_replace_target(dst)
        return self._real_os.rename(src, dst, *a, **kw)

    def replace(self, src, dst, *a, **kw):
        check_remove(src)
        check_replace_target(dst)
        return self._real_os.replace(src, dst, *a, **kw)

    def truncate(self, path, *a, **kw):
        check_remove(path)
        return self._real_os.truncate(path, *a, **kw)

    def __getattr__(self, name):
        return getattr(self._real_os, name)


@contextlib.contextmanager
def guard_process():
    """Check file writes PROCESS-WIDE while agent code runs (python tool).

    Patches builtins.open, io.open, os.open and os.remove/unlink/rename/
    replace/truncate, so pathlib, `import io`, `from os import remove` and
    modules imported by the agent's code are covered too, not just names in
    the exec namespace. Sanctioned writers (rebuild_tiers, record_episode)
    pass through allow_protected_write() / create-only rules. Everything is
    restored on exit."""
    import builtins
    import io

    real = {"open": builtins.open, "io_open": io.open, "os_open": os.open,
            "remove": os.remove, "unlink": os.unlink, "rename": os.rename,
            "replace": os.replace, "truncate": os.truncate}

    def g_open(file, mode="r", *a, **kw):
        check_open(file, mode)
        return real["open"](file, mode, *a, **kw)

    def g_io_open(file, mode="r", *a, **kw):
        check_open(file, mode)
        return real["io_open"](file, mode, *a, **kw)

    def g_os_open(path, flags, *a, **kw):
        check_os_open(path, flags)
        return real["os_open"](path, flags, *a, **kw)

    def g_remove(path, *a, **kw):
        check_remove(path)
        return real["remove"](path, *a, **kw)

    def g_unlink(path, *a, **kw):
        check_remove(path)
        return real["unlink"](path, *a, **kw)

    def g_rename(src, dst, *a, **kw):
        check_remove(src)
        check_replace_target(dst)
        return real["rename"](src, dst, *a, **kw)

    def g_replace(src, dst, *a, **kw):
        check_remove(src)
        check_replace_target(dst)
        return real["replace"](src, dst, *a, **kw)

    def g_truncate(path, *a, **kw):
        if not isinstance(path, int):
            check_remove(path)
        return real["truncate"](path, *a, **kw)

    builtins.open, io.open, os.open = g_open, g_io_open, g_os_open
    os.remove, os.unlink, os.rename, os.replace, os.truncate = g_remove, g_unlink, g_rename, g_replace, g_truncate
    try:
        yield
    finally:
        builtins.open, io.open, os.open = real["open"], real["io_open"], real["os_open"]
        os.remove, os.unlink, os.rename = real["remove"], real["unlink"], real["rename"]
        os.replace, os.truncate = real["replace"], real["truncate"]


_PROTECTED_FILE = r"(tiers?/tier\d\.txt|recap/episode_\d+\.json)"

SHELL_DANGER_PATTERNS = [
    r">\s*\S*(history|space|chat|transcript)\.(metta|txt)\b",
    r">\s*\S*nace_\w*\.metta\b",
    r">\s*\S*tiers?/tier\d\.txt\b",
    r">\s*\S*recap/episode_\d+\.json\b",
    r"\brm\s+.*(history\.metta|space\.metta|chat\.txt|transcript\.txt|nace_\w*\.metta|tiers?/tier\d\.txt|recap/episode_\d+\.json)",
    r"\btruncate\s+.*(history\.metta|space\.metta|chat\.txt|transcript\.txt|tiers?/tier\d\.txt)",
    r":\s*>\s*\S*(history|space|chat|transcript)\.(metta|txt)\b",
    r"\bmv\s+.*(recap/episode_\d+\.json|tiers?/tier\d\.txt)\b",
    # Best effort only: interpreter one-liners and copy/edit tools touching a
    # tier or episode file. A shell can always find another way.
    r"\b(python3?|perl|ruby|node)\b[^|;&]*" + _PROTECTED_FILE,
    r"\b(cp|tee|dd|install|rsync)\b[^|;&]*" + _PROTECTED_FILE,
    r"\bsed\s+(-\w*\s+)*-i[^|;&]*" + _PROTECTED_FILE,
]


def scan_shell_command(cmd):
    """BEST-EFFORT heuristic scan for shell commands. Shell is
    fundamentally unsandboxable without an OS-level jail, so this only
    catches the obvious/likely destructive patterns (the python tool's
    process-wide guard_process() is the stronger check)."""
    import re
    for pat in SHELL_DANGER_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return pat
    return None
