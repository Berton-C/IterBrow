import os
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as _guard

DESCRIPTION = "Execute a shell command."


def run(cmd):
    hit = _guard.scan_shell_command(cmd)
    if hit:
        try:
            import memory_journal
            memory_journal.log("shell", "blocked_command", {"cmd": cmd, "pattern": hit})
        except Exception:
            pass
        return (
            "BLOCKED: this command looks like it targets protected memory content "
            "(matched pattern %r) and was not run: %r. If you need to update memory "
            "tiers, use the rebuild_tiers tool. If you need to append to a log file, "
            "use `>>` (append) rather than `>` (overwrite)." % (hit, cmd)
        )
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return "SUCCESS, RETURN: " + result.stdout + result.stderr
