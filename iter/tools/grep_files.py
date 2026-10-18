import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    "Search text files for a Python regex: `path:line: text` per match (paths relative to iter/). Case-sensitive "
    "unless the pattern starts with (?i). glob filters file names at any depth (e.g. `*.py`); path narrows the "
    "folder. Skips binary files, .git, node_modules, .venv, __pycache__."
)

MAX_LINE = 300


def run(pattern, path=".", glob="*", limit="100"):
    try:
        base = _files.resolve(path)
    except _files.FileScopeError as error:
        return _files.refused(error)
    try:
        regex = re.compile(str(pattern))
    except re.error as error:
        return _files.input_error("ERROR: %r is not a valid regex: %s" % (pattern, error))
    try:
        cap = max(1, int(str(limit or "100").strip()))
    except ValueError:
        return _files.input_error("ERROR: limit is a number")
    if not base.exists():
        return _files.input_error("ERROR: nothing at %s" % path)
    pattern_glob = str(glob or "*").strip() or "*"
    # A glob without a folder part matches the file's name at any depth; with one, the relative path.
    matcher = _files.glob_regex(pattern_glob)
    by_name = "/" not in pattern_glob
    files = [(base.name, base)] if base.is_file() else [
        (rel, absolute) for rel, absolute, is_dir in _files.walk(base, recursive=True) if not is_dir]
    hits, more = [], False
    for rel, absolute in files:
        if not matcher.match(os.path.basename(rel) if by_name else rel):
            continue
        if _files.looks_binary(absolute):
            continue
        try:
            with open(absolute, encoding="utf-8", errors="strict") as handle:
                for number, line in enumerate(handle, 1):
                    if regex.search(line):
                        if len(hits) >= cap:
                            more = True
                            break
                        text = line.rstrip("\n")
                        if len(text) > MAX_LINE:
                            text = text[:MAX_LINE] + " …"
                        hits.append("%s:%d: %s" % (_files.shown(absolute), number, text))
        except (UnicodeDecodeError, OSError):
            continue
        if more:
            break
    if not hits:
        return "NO MATCHES"
    return "\n".join(hits + (["… and more"] if more else []))
