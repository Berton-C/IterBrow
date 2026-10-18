import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    "Read a text file with numbered lines (`   12| text`). path is relative to iter/ (`../main.js` reaches "
    "the repo root); offset is the first line (1-based), limit at most 400 lines. Page with offset to read on. "
    "Use this instead of shell cat; then edit_file to change a few lines."
)

MAX_LINES = 400
MAX_CHARS = 24000


def run(path, offset="1", limit="200"):
    try:
        real = _files.resolve(path)
    except _files.FileScopeError as error:
        return _files.refused(error)
    if not real.exists():
        return _files.input_error("ERROR: no file at %s" % path)
    if real.is_dir():
        return _files.input_error("ERROR: %s is a directory; use list_files" % path)
    text, problem = _files.read_text(real)
    if problem:
        return _files.input_error("ERROR: %s %s; read_file shows text only" % (path, problem))
    try:
        first = max(1, int(str(offset or "1").strip()))
        count = max(1, min(MAX_LINES, int(str(limit or "200").strip())))
    except ValueError:
        return _files.input_error("ERROR: offset and limit are line numbers")
    lines = text.splitlines()
    total = len(lines)
    if total == 0:
        return "%s (empty file)" % path
    if first > total:
        return _files.input_error("ERROR: offset %d is past the end of %s (%d lines)" % (first, path, total))
    page = lines[first - 1:first - 1 + count]
    out, used, cut_at = [], 0, None
    for index, line in enumerate(page):
        row = "%5d| %s" % (first + index, line)
        if used + len(row) + 1 > MAX_CHARS:
            if not out:  # one line longer than the whole page: show its start
                out.append(row[:MAX_CHARS - 40] + " …")
                cut_at = first + index + 1
            else:
                cut_at = first + index
            break
        out.append(row)
        used += len(row) + 1
    last = first + len(out) - 1
    header = "%s (lines %d–%d of %d)" % (path, first, last, total)
    if cut_at is not None:
        header += " …cut at line %d (page with offset=%d)" % (cut_at, cut_at)
    return "\n".join([header] + out)
