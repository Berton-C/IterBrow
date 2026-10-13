"""Turn due reminder files (memory/alarms/<unix time>[.NNN]) into ordinary input.

transformations/alarms.py used to delete a due alarm and append it only to
one attempt's request copy, so a retry (no tool call / length) or a provider
error rollback lost it for good. iter.py now calls take_due_alarms() right
after receive() and appends the text to the cycle's event input, which is
saved to experience before any model call. A file is removed only after it
was read, and its text is returned only when it was removed, so an alarm is
neither lost nor delivered every cycle.
"""
import os
import time


def _due(name):
    try:
        return float(name)
    except ValueError:
        return None


def take_due_alarms(alarms_dir, now=None):
    """'[channel] [ALARM] message' lines for every due alarm, oldest first."""
    now = time.time() if now is None else now
    try:
        names = os.listdir(alarms_dir)
    except OSError:
        return ""
    due = sorted((value, name) for name in names
                 for value in [_due(name)] if value is not None and value <= now)
    lines = []
    for _, name in due:
        path = os.path.join(alarms_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read().strip()
            os.unlink(path)
        except OSError:
            continue
        channel, _, message = content.partition("\n")
        if not message:
            channel, message = "terminal", content
        lines.append("[" + channel.strip() + "] [ALARM] " + message)
    return "\n".join(lines)
