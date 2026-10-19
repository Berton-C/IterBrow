# Shared helper for the file tools (read_file, write_file, edit_file, list_files, grep_files) and for
# shell's cwd (docs/milestones/M12_builder_hands.md section B). Not a tool: the leading underscore keeps
# Iter's loader from offering it.
#
# Scope: the repository. The repo root is the directory holding main.js above ITER_DIR (a source checkout);
# in a packaged install with no main.js beside iter/, it is ITER_DIR itself. Paths are relative to ITER_DIR
# unless absolute, `..` is fine while the real path stays inside the root, and every check is made on the
# real path, so a symlink that leads out is refused. Writes are also refused under .git/, node_modules/ and
# iter/.venv/. A refusal is the tool's own scope rule, reported as REFUSED: and scored as a refusal.
#
# M14-A3: the person's vault (the apps folder they chose; iterbrow_runtime/vault.py) is a second root.
# `vault/<rel>` means <vault>/<rel>, and vault files are printed back as `vault/<rel>`. With no vault chosen,
# `vault/...` is refused with the way to choose one. <vault>/.iter (snapshots) is never written.
import os
import re
import sys
from pathlib import Path

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, os.path.dirname(TOOLS_DIR))
from iterbrow_runtime.tool_results import ToolOutput  # noqa: E402

MAX_WRITE_BYTES = 2 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".iter"}
NO_WRITE_PARTS = {".git", "node_modules"}


class FileScopeError(Exception):
    """A path outside the tool's scope. str(error) starts with REFUSED:."""


def iter_dir():
    return Path(os.path.realpath(os.environ.get("ITER_DIR") or os.path.dirname(TOOLS_DIR)))


def repo_root():
    here = iter_dir()
    return here.parent if (here.parent / "main.js").is_file() else here


NO_VAULT = "REFUSED: no apps folder chosen yet (Apps ▸ Choose apps folder…)"


def vault_dir():
    """The person's vault (real path) or None. Read from settings on every call."""
    try:
        from iterbrow_runtime import vault
    except Exception:
        return None
    return vault.path(iter_dir() / ".runtime" / "settings.json")


def roots():
    """Where the file tools reach: the repository, and the vault when one is chosen."""
    vault = vault_dir()
    return [Path(os.path.realpath(repo_root()))] + ([vault] if vault else [])


def _inside(real, root):
    return real == root or root in real.parents


def in_vault(real):
    """The vault when `real` is inside it, else None."""
    vault = vault_dir()
    return vault if vault and _inside(Path(real), vault) else None


def resolve(path, *, write=False):
    """The real absolute path for `path`, or FileScopeError when it leaves the repository and the vault."""
    raw = str(path if path is not None else "").strip() or "."
    if raw == "vault" or raw.startswith("vault/"):
        vault = vault_dir()
        if vault is None:
            raise FileScopeError(NO_VAULT)
        candidate = vault / raw[len("vault/"):] if raw != "vault" else vault
    else:
        candidate = Path(os.path.expanduser(raw))
        if not candidate.is_absolute():
            candidate = iter_dir() / candidate
    real = Path(os.path.realpath(candidate))
    root = Path(os.path.realpath(repo_root()))
    vault = vault_dir()
    if vault and _inside(real, vault):
        if write and (OWN_PART in real.relative_to(vault).parts[:1]):
            raise FileScopeError("REFUSED: %s is under vault/.iter, which holds IterBrow's snapshots and is never written" % raw)
        return real
    if not _inside(real, root):
        where = "the repository (%s)" % root + (" and the apps folder (%s)" % vault if vault else "")
        raise FileScopeError("REFUSED: %s is outside %s" % (raw, where))
    if write:
        parts = real.relative_to(root).parts
        venv = iter_dir() / ".venv"
        if NO_WRITE_PARTS.intersection(parts) or real == venv or venv in real.parents:
            raise FileScopeError("REFUSED: %s is under .git, node_modules or iter/.venv, which the file tools never write" % raw)
    return real


OWN_PART = ".iter"


def shown(real):
    """How a path is printed back: `vault/<rel>` for the vault's files, else relative to ITER_DIR
    (`../main.js` for the repo's own files)."""
    vault = in_vault(real)
    if vault:
        rel = os.path.relpath(str(real), str(vault)).replace(os.sep, "/")
        return "vault" if rel == "." else "vault/" + rel
    return os.path.relpath(str(real), str(iter_dir())).replace(os.sep, "/")


def before_write(real, reason):
    """M14-B1: save a vault app file's current bytes before a tool replaces it (a new file logs a null
    snapshot, so rollback deletes it). Outside the vault this does nothing at all."""
    vault = in_vault(real)
    if not vault:
        return None
    from iterbrow_runtime import vault as vault_store
    return vault_store.snapshot(real, reason, root=vault)


def label(path, real):
    """The name a tool's result line uses: vault files always as `vault/<rel>`, others as the caller wrote them."""
    return shown(real) if in_vault(real) else str(path)


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
    scope = roots()
    root = next((r for r in scope if _inside(Path(os.path.realpath(base)), r)), scope[0])
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
