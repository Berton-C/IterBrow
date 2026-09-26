import os
import subprocess
import sys
from iterbrow_runtime.tool_results import ToolOutput

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as _guard

DESCRIPTION = "Execute a command on %s using %s. Working directory: %s. Uses the native host's installed utilities." % (
    {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, sys.platform),
    os.environ.get("COMSPEC", "cmd.exe") if os.name == "nt" else "/bin/sh",
    os.getcwd(),
)


def run(cmd):
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
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    prefix = "SUCCESS, RETURN: " if result.returncode == 0 else "FAILED (exit %s), RETURN: " % result.returncode
    return ToolOutput(prefix + result.stdout + result.stderr,
                      result.returncode == 0, exit_code=result.returncode)
