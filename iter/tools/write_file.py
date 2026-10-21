import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    'Write a whole text file (UTF-8), creating folders; atomic. path: relative to iter/ (vault/<id>/... '
    "for the person's apps; ../ is the repo root). For a few lines, prefer edit_file."
)


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


import re  # noqa: E402

VAULT_APP = re.compile(r"^vault/([a-z][a-z0-9-]{0,62})/")


def ledger_reminder(path):
    """M15-C4: a write in a vault app leaves its build ledger behind the files; say so (the file tools observe
    nothing — browser_open_app checks the running app)."""
    found = VAULT_APP.match(str(path))
    if not found:
        return ""
    return " · ledger: changed since last check — browser_open_app(%s) to re-check" % found.group(1)


def run(path, content=""):
    return write(path, content, "write_file")


def write(path, content, reason):
    """The write itself; `reason` names the tool in the vault's snapshot log (edit_file passes its own)."""
    try:
        real = _files.resolve(path, write=True)
    except _files.FileScopeError as error:
        return _files.refused(error)
    path = _files.label(path, real)  # M14-A3: vault files are always named vault/<rel>
    text = "" if content is None else str(content)
    data = text.encode("utf-8")
    if len(data) > _files.MAX_WRITE_BYTES:
        return _files.refused("REFUSED: %s would be %d bytes; write_file writes at most 2 MB" % (path, len(data)))
    if real.is_dir():
        return _files.input_error("ERROR: %s is a directory" % path)
    if real.exists() and real.read_bytes() == data:
        return "WROTE %s (unchanged)" % path
    _files.before_write(real, reason)  # M14-B1: the previous content is kept (vault apps only)
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
    return "WROTE %s (%d bytes, %d lines)" % (path, len(data), _files.line_count(text)) + ledger_reminder(path)
