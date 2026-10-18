import os
import signal
import subprocess
import sys
from iterbrow_runtime.tool_results import ToolOutput

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as _guard
import _files  # noqa: E402  (M12-B6: cwd scope)

DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 170  # the loop's own bound for shell is 180 s

DESCRIPTION = (
    "Execute a command on %s using %s. cwd: a folder relative to iter/ (default iter/; `..` is the repo root). "
    "timeout: seconds, default %d, at most %d. stdout first, then a `--- stderr ---` section when there is one. "
    "python3 here is Iter's own Python. For reading or changing files, prefer read_file / edit_file."
    % ({"darwin": "macOS", "win32": "Windows"}.get(sys.platform, sys.platform),
       os.environ.get("COMSPEC", "cmd.exe") if os.name == "nt" else "/bin/sh", DEFAULT_TIMEOUT, MAX_TIMEOUT)
)


def _python_bin_dir():
    venv = _files.iter_dir() / ".venv" / "bin"
    return str(venv) if venv.is_dir() else os.path.dirname(sys.executable)


def _output(stdout, stderr):
    text = stdout or ""
    if stderr:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "--- stderr ---\n" + stderr
    return text


def run(cmd, cwd="", timeout=""):
    hit = _guard.scan_shell_command(cmd)
    if hit:
        try:
            import memory_journal
            memory_journal.log("shell", "blocked_command", {"cmd": cmd, "pattern": hit})
        except Exception:
            pass
        return ToolOutput(
            "BLOCKED: this command looks like it targets protected memory content "
            "(matched pattern %r) and was not run: %r. If you need to update memory "
            "tiers, use the rebuild_tiers tool. If you need to append to a log file, "
            "use `>>` (append) rather than `>` (overwrite)." % (hit, cmd), None, state="blocked"
        )
    try:
        workdir = _files.resolve(cwd or ".") if str(cwd or "").strip() else _files.iter_dir()
    except _files.FileScopeError as error:
        return _files.refused(error)
    if not workdir.is_dir():
        return _files.input_error("ERROR: cwd %s is not a folder" % cwd)
    try:
        seconds = int(float(str(timeout).strip())) if str(timeout or "").strip() else DEFAULT_TIMEOUT
    except ValueError:
        return _files.input_error("ERROR: timeout is a number of seconds")
    seconds = max(1, min(MAX_TIMEOUT, seconds))
    env = dict(os.environ)
    env["PATH"] = _python_bin_dir() + os.pathsep + env.get("PATH", "")
    process = subprocess.Popen(cmd, shell=True, cwd=str(workdir), env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
        stdout, stderr = process.communicate()
        return ToolOutput("FAILED (timeout after %ds), RETURN: " % seconds + _output(stdout, stderr), False, state="failed")
    prefix = "SUCCESS, RETURN: " if process.returncode == 0 else "FAILED (exit %s), RETURN: " % process.returncode
    return ToolOutput(prefix + _output(stdout, stderr), process.returncode == 0, exit_code=process.returncode)
