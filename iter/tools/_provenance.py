"""Internal: shared structural provenance-grounding primitives. NOT an
LLM-facing tool (underscore-prefixed) -- imported by
transformations/provenance_guard.py.

THE AXIS: does a piece of newly-written code have a real, checkable fact
behind its two most common failure modes, or does it merely assume one.
Deliberately NOT keyword-matching English promise phrasing ("will update
once...", "is wired to...") -- that is a long-tail problem, infinitely many
ways to phrase an ungrounded claim. Both checks below are mechanical
instead -- exactly one true/false fact each, independent of phrasing:

  1. misplaced_hook_reason(...) -- a file that structurally LOOKS like a
     transformation/tool hook (defines transform()/run(), has a
     DESCRIPTION) but is being written outside the directories iter.py's
     own loader actually globs. The hot-dir list is derived by reading
     iter.py's own load_tools()/apply_transformation() glob patterns at
     call time (not a hardcoded duplicate list), so this check cannot
     itself silently drift stale against the thing it verifies.

  2. unproduced_keys(...) -- a dict/metadata key literal the new content
     reads via .get("key")/["key"], alongside a hint it's reading shared
     on-disk state, that NO OTHER file in the repo ever writes. A key with
     zero producers anywhere in the codebase is a checkable fact, not a
     guess about naming.

REAL INCIDENT this generalizes from (2026-09-14): refresh_beliefs_fc.py sat
at iter/ root (not transformations/) reading metadata["stv"] -- a key
nothing in tools/support.py or tools/contradict.py ever writes (they write
metadata["strength"] and metadata["confidence"] separately). Both checks
above map directly onto that incident's two root causes.
"""
import os
import re

# Deliberately CWD-relative, matching nace_courier.py's own convention
# (ITER_ROOT = "."), not module-file-relative -- iter.py's real process
# always runs with cwd=iter/, and cwd-relative paths let a test harness
# os.chdir() into an isolated fixture dir and get fully isolated behavior,
# the same way _test_dashboard_beliefs_refresh.py's fixtures do.
ITER_ROOT = "."
PENDING_PATH = os.path.join(ITER_ROOT, "nace_pending.metta")

_GLOB_RE = re.compile(r'Path\(\s*["\']([\w./]+)["\']\s*\)\.glob\(\s*["\']\*\.py["\']\s*\)')
_HOOK_SIGNATURE_RE = re.compile(r"^\s*def\s+(transform|run)\s*\(", re.MULTILINE)
_DESCRIPTION_RE = re.compile(r"^\s*DESCRIPTION\s*=", re.MULTILINE)

# Narrowed deliberately to accesses off a metadata-ish variable name (not
# any dict) -- catches per-record field guesses like metadata.get("stv")
# without flagging unrelated container keys (e.g. chroma's own fixed
# "ids"/"metadatas" schema keys, which are containers, not the per-record
# field an agent invented a name for).
_KEY_READ_RE = re.compile(
    r"""\b(?:metadata|meta|md)\s*(?:\.get\(\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]|\[\s*['"]([A-Za-z_][A-Za-z0-9_]*)['"]\s*\])"""
)
_KEY_STOPLIST = {
    "get", "self", "name", "value", "type", "id", "path", "data", "result",
    "content", "message", "role", "text", "error", "ok", "function",
    "arguments", "role", "tool_calls",
}
_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "chroma_db",
    "backups", "uploads", "_screenshots", ".runtime",
}


def hot_dirs(iter_py_path=None):
    """Authoritative set of directories iter.py's own loader actually
    scans for hook files, derived by reading iter.py itself. Falls back to
    the two directories known-true today only if iter.py can't be read --
    never invents a broader list than what's actually in the source."""
    path = iter_py_path or os.path.join(ITER_ROOT, "iter.py")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except Exception:
        return {"tools", "transformations"}
    dirs = set(_GLOB_RE.findall(content))
    return dirs or {"tools", "transformations"}


def looks_like_hook(content):
    """True if `content` structurally looks like a transformation/tool
    hook (defines transform()/run() AND a DESCRIPTION) -- independent of
    where the file actually lives."""
    return bool(_HOOK_SIGNATURE_RE.search(content)) and bool(_DESCRIPTION_RE.search(content))


def _normalize(path):
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.startswith("iter/"):
        p = p[len("iter/"):]
    return p


def misplaced_hook_reason(target_path, content, iter_py_path=None):
    """Return a reason string if `content` written to `target_path` looks
    like a transformation/tool hook but `target_path` is not inside any
    real auto-loaded directory; None if it's fine (not hook-shaped, or
    correctly placed)."""
    if not looks_like_hook(content):
        return None
    norm = _normalize(target_path)
    dirs = hot_dirs(iter_py_path)
    for d in dirs:
        d_norm = _normalize(d).rstrip("/")
        if norm.startswith(d_norm + "/"):
            return None
    return (
        "%r defines transform()/run() + DESCRIPTION (structurally looks like "
        "a transformation/tool hook) but is not inside any real auto-loaded "
        "directory (%s) -- iter.py's own loader will never call this. This is "
        "the exact refresh_beliefs_fc.py bug (2026-09-14): a hook-shaped file "
        "at iter/ root that iter.py's glob never picked up."
        % (target_path, ", ".join(sorted(dirs)))
    )


def _extract_read_keys(content):
    keys = set()
    for m in _KEY_READ_RE.finditer(content):
        key = m.group(1) or m.group(2)
        if key and key not in _KEY_STOPLIST and len(key) > 2:
            keys.add(key)
    return keys


def touches_shared_state(content):
    """True if `content` actually accesses shared on-disk state (a real
    metadata dict access, or loading/writing a JSON/chroma file) -- not
    just mentioning the word 'metadata' in a comment or docstring. Used to
    scope the contract check to writes where a producer-mismatch is even
    possible, without flagging unrelated code that happens to say the word.
    """
    if _KEY_READ_RE.search(content):
        return True
    return bool(re.search(r"json\.load\(|json\.dump\(|chroma_db|\.json['\"]", content))


def unproduced_keys(content, repo_root=None, exclude_path=None):
    """Keys this content reads via .get("key")/["key"] that no OTHER file
    in the repo ever writes (dict-literal key or assignment target) --
    each is a real, checkable, zero-producer interface guess, exactly like
    the `stv` bug. Only checked when the content itself hints it's reading
    shared on-disk state (metadata/memories/chroma/json nearby), to avoid
    false positives on ordinary local dict use unrelated to cross-file
    contracts."""
    if not touches_shared_state(content):
        return []
    root = repo_root or ITER_ROOT
    read_keys = _extract_read_keys(content)
    if not read_keys:
        return []
    exclude_abs = os.path.abspath(exclude_path) if exclude_path else None
    unproduced = []
    for key in sorted(read_keys):
        write_re = re.compile(
            r"""['"]""" + re.escape(key) + r"""['"]\s*[:=]|\[\s*['"]""" + re.escape(key) + r"""['"]\s*\]\s*="""
        )
        found = False
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(dirpath, fname)
                if exclude_abs and os.path.abspath(fpath) == exclude_abs:
                    continue
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        if write_re.search(fh.read()):
                            found = True
                            break
                except Exception:
                    continue
            if found:
                break
        if not found:
            unproduced.append(key)
    return unproduced


def record_pattern_outcome(pattern_name, outcome, pending_path=None, rtype="pattern"):
    """Append one (pending-revision <rtype> <name> <outcome>) line to
    nace_pending.metta -- the same queue every other belief revision in
    this app already flows through (see nace_courier.py, mirrored from
    idle_cycle_detector.py's established convention: plant the observation
    into reasoning that already exists everywhere else, never write
    nace_beliefs.metta directly). Never raises.

    `rtype` defaults to "pattern" (the existing 9-compass-pattern callers,
    unchanged). Pass rtype="mode" for the add/subtract/loosen mode-signal
    layer (see mode_signal_bridge.py) -- nace_courier.py's TYPE_PREFIX maps
    "mode" to the "mode-signal" belief prefix."""
    path = pending_path or PENDING_PATH
    line = "(pending-revision %s %s %s)\n" % (rtype, pattern_name, outcome)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
        return True
    except Exception:
        return False
