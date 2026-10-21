import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    'List files under a folder (relative to iter/): path size, folders end with /. glob: * this folder, '
    '**/*.js below. Skips .git, node_modules, .venv.'
)


def run(path=".", glob="*", limit="200"):
    try:
        base = _files.resolve(path)
    except _files.FileScopeError as error:
        return _files.refused(error)
    if not base.exists():
        return _files.input_error("ERROR: no folder at %s" % path)
    if not base.is_dir():
        return _files.input_error("ERROR: %s is a file; use read_file" % path)
    pattern = str(glob or "*").strip() or "*"
    try:
        cap = max(1, int(str(limit or "200").strip()))
    except ValueError:
        return _files.input_error("ERROR: limit is a number")
    matcher = _files.glob_regex(pattern)
    recursive = "/" in pattern or "**" in pattern
    rows = []
    for rel, absolute, is_dir in _files.walk(base, recursive=recursive):
        if not matcher.match(rel):
            continue
        shown = _files.shown(absolute)
        if is_dir:
            rows.append((shown, shown + "/"))
        else:
            try:
                size = absolute.stat().st_size
            except OSError:
                continue
            rows.append((shown, "%s  %d" % (shown, size)))
    rows.sort(key=lambda row: row[0])
    if not rows:
        return "NO FILES matching %s under %s" % (pattern, path)
    lines = [row[1] for row in rows[:cap]]
    if len(rows) > cap:
        lines.append("… and %d more" % (len(rows) - cap))
    return "\n".join(lines)
