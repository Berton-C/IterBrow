import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402
import write_file  # noqa: E402

DESCRIPTION = (
    'Replace one exact piece of text in a file. old must occur exactly once (copy from read_file without '
    'line numbers); new replaces it (empty deletes). Shows the edited lines. Nothing changes when old '
    'occurs 0 or 2+ times.'
)


def run(path, old, new=""):
    try:
        real = _files.resolve(path, write=True)
    except _files.FileScopeError as error:
        return _files.refused(error)
    path = _files.label(path, real)  # M14-A3: vault files are always named vault/<rel>
    if not real.is_file():
        return _files.input_error("ERROR: no file at %s" % path)
    text, problem = _files.read_text(real)
    if problem:
        return _files.input_error("ERROR: %s %s" % (path, problem))
    old = "" if old is None else str(old)
    new = "" if new is None else str(new)
    if not old:
        return _files.input_error("EDIT-FAILED: old text is empty; give the exact text to replace")
    occurrences = text.count(old)
    if occurrences != 1:
        return _files.input_error("EDIT-FAILED: old text occurs %d times in %s" % (occurrences, path))
    at = text.index(old)
    updated = text[:at] + new + text[at + len(old):]
    written = write_file.write(path, updated, "edit_file")
    if not str(written).startswith("WROTE"):
        return written
    lines = updated.splitlines()
    start = updated[:at].count("\n")  # 0-based line where the replacement begins
    end = start + max(_files.line_count(new), 1) - 1
    first, last = max(0, start - 2), min(len(lines) - 1, end + 2)
    header = "EDITED %s (+%d −%d lines)" % (path, _files.line_count(new), _files.line_count(old))
    region = _files.numbered(lines[first:last + 1], first + 1) if lines else []
    return "\n".join([header] + region)
