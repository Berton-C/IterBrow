import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    "Write a whole text file (UTF-8), creating folders as needed; atomic, keeps an existing file's mode. "
    "path is relative to iter/ (a plain app is <id>/index.html; `../` reaches the repo root). For a change of a "
    "few lines in an existing file, prefer edit_file."
)


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def run(path, content=""):
    try:
        real = _files.resolve(path, write=True)
    except _files.FileScopeError as error:
        return _files.refused(error)
    text = "" if content is None else str(content)
    data = text.encode("utf-8")
    if len(data) > _files.MAX_WRITE_BYTES:
        return _files.refused("REFUSED: %s would be %d bytes; write_file writes at most 2 MB" % (path, len(data)))
    if real.is_dir():
        return _files.input_error("ERROR: %s is a directory" % path)
    if real.exists() and real.read_bytes() == data:
        return "WROTE %s (unchanged)" % path
    mode = (real.stat().st_mode & 0o7777) if real.exists() else (0o666 & ~_umask())
    real.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix="." + real.name + ".", suffix=".tmp", dir=str(real.parent))
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp, mode)
        os.replace(temp, real)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return "WROTE %s (%d bytes, %d lines)" % (path, len(data), _files.line_count(text))
