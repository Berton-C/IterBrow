"""Turn due reminder files (memory/alarms/<unix time>[.NNN]) into ordinary input.

transformations/alarms.py used to delete a due alarm and append it only to
one attempt's request copy, so a retry (no tool call / length) or a provider
error rollback lost it for good. iter.py now, right after receive():

  1. pending_alarms() reads the due alarms WITHOUT deleting them,
  2. saves them to experience as one message marked _iter_alarm, carrying the
     alarms' identities in _iter_alarm_ids,
  3. acknowledge_alarms() deletes the files only after that save succeeded.

A crash between 2 and 3 leaves the files on disk; the next pending_alarms()
sees their identities in experience (delivered_alarm_ids) and only deletes
them, so an alarm is neither lost nor delivered twice. An identity is the
file name plus its modification time, so a new reminder later created under
the same name is a different alarm.
"""
import os
import time


def _due(name):
    try:
        return float(name)
    except ValueError:
        return None


def _identity(alarms_dir, name):
    try:
        st = os.stat(os.path.join(alarms_dir, name))
    except OSError:
        return None
    return "%s:%d" % (name, st.st_mtime_ns)


def delivered_alarm_ids(experience):
    """Identities of alarms already saved as input."""
    ids = set()
    for message in experience:
        if isinstance(message, dict):
            ids.update(message.get("_iter_alarm_ids") or ())
    return ids


def acknowledge_alarms(alarms_dir, ids):
    """Delete the alarm files with these identities (after they were saved)."""
    for identity in ids:
        name = str(identity).rsplit(":", 1)[0]
        if _identity(alarms_dir, name) == identity:
            try:
                os.unlink(os.path.join(alarms_dir, name))
            except OSError:
                pass


def pending_alarms(alarms_dir, delivered=(), now=None):
    """('[channel] [ALARM] message' lines, identities) for due alarms not yet
    delivered, oldest first. Nothing is deleted except files whose alarm was
    already saved (delivered)."""
    now = time.time() if now is None else now
    delivered = set(delivered)
    try:
        names = os.listdir(alarms_dir)
    except OSError:
        return "", []
    due = sorted((value, name) for name in names
                 for value in [_due(name)] if value is not None and value <= now)
    lines, ids, stale = [], [], []
    for _, name in due:
        path = os.path.join(alarms_dir, name)
        if not os.path.isfile(path):
            continue
        identity = _identity(alarms_dir, name)
        if identity is None:
            continue
        if identity in delivered:
            stale.append(identity)
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                content = fh.read().strip()
        except OSError:
            continue
        channel, _, message = content.partition("\n")
        if not message:
            channel, message = "terminal", content
        lines.append("[" + channel.strip() + "] [ALARM] " + message)
        ids.append(identity)
    acknowledge_alarms(alarms_dir, stale)
    return "\n".join(lines), ids
