# Shared helper for the file tools (read_file, write_file, edit_file, list_files, grep_files) and for
# shell's cwd (docs/milestones/M12_builder_hands.md section B). Not a tool: the leading underscore keeps
# Iter's loader from offering it.
#
# Scope: the repository. The repo root is the directory holding main.js above ITER_DIR (a source checkout);
# in a packaged install with no main.js beside iter/, it is ITER_DIR itself. Paths are relative to ITER_DIR
# unless absolute, `..` is fine while the real path stays inside the root, and every check is made on the
# real path, so a symlink that leads out is refused. Writes are also refused under .git/, node_modules/ and
# iter/.venv/. A refusal is the tool's own scope rule, reported as REFUSED: and scored as a refusal.
import os
import re
import sys
from pathlib import Path

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, os.path.dirname(TOOLS_DIR))
from iterbrow_runtime.tool_results import ToolOutput  # noqa: E402

MAX_WRITE_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}
NO_WRITE_PARTS = {".git", "node_modules"}


class FileScopeError(Exception):
    """A path outside the tool's scope. str(error) starts with REFUSED:."""


def iter_dir():
    return Path(os.path.realpath(os.environ.get("ITER_DIR") or os.path.dirname(TOOLS_DIR)))


def repo_root():
    here = iter_dir()
    return here.parent if (here.parent / "main.js").is_file() else here


def resolve(path, *, write=False):
    """The real absolute path for `path`, or FileScopeError when it leaves the repository."""
    raw = str(path if path is not None else "").strip() or "."
    candidate = Path(os.path.expanduser(raw))
    if not candidate.is_absolute():
        candidate = iter_dir() / candidate
    real = Path(os.path.realpath(candidate))
    root = Path(os.path.realpath(repo_root()))
    if real != root and root not in real.parents:
        raise FileScopeError("REFUSED: %s is outside the repository (%s)" % (raw, root))
    if write:
        parts = real.relative_to(root).parts
        venv = iter_dir() / ".venv"
        if NO_WRITE_PARTS.intersection(parts) or real == venv or venv in real.parents:
            raise FileScopeError("REFUSED: %s is under .git, node_modules or iter/.venv, which the file tools never write" % raw)
    return real


def shown(real):
    """How a path is printed back: relative to ITER_DIR (`../main.js` for the repo's own files)."""
    return os.path.relpath(str(real), str(iter_dir())).replace(os.sep, "/")


def refused(message):
    return ToolOutput(str(message), None, state="refused")


def input_error(message):
    """The tool worked; the request did not fit (no such file, ambiguous edit). Moves no belief."""
    return ToolOutput(str(message), None, state="invalid_input")


def line_count(text):
    return len(text.splitlines())


def numbered(lines, first):
    """`read_file`'s line format: a right-aligned 5-wide number, `|`, one space, the text."""
    return ["%5d| %s" % (first + i, line) for i, line in enumerate(lines)]


def read_text(real):
    """(text, None) or (None, error message) for a file that is not UTF-8."""
    try:
        return real.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, "is not UTF-8 text"


def looks_binary(real, sample=8192):
    try:
        with open(real, "rb") as handle:
            chunk = handle.read(sample)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError as error:
        return error.start < len(chunk) - 4  # a multi-byte character cut by the sample edge is fine
    return False


def glob_regex(pattern):
    """A pathlib-style glob as a regex over '/'-separated relative paths: `**/` spans directories."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def walk(base, *, recursive):
    """(relative path, absolute Path, is_dir) under `base`, skipping SKIP_DIRS and symlinks that leave."""
    root = Path(os.path.realpath(repo_root()))
    if not recursive:
        for entry in sorted(base.iterdir(), key=lambda p: p.name):
            if entry.name in SKIP_DIRS:
                continue
            yield entry.name, entry, entry.is_dir()
        return
    for current, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        here = Path(current)
        for name in dirs:
            path = here / name
            if path.is_symlink() and root not in Path(os.path.realpath(path)).parents:
                continue
            yield os.path.relpath(path, base).replace(os.sep, "/"), path, True
        for name in sorted(files):
            path = here / name
            if path.is_symlink() and root not in Path(os.path.realpath(path)).parents:
                continue
            yield os.path.relpath(path, base).replace(os.sep, "/"), path, False
