import os
import time



def _mkdirs(path):
    current = ""
    for part in str(path).split("/"):
        if not part:
            current = "/" if not current else current
            continue
        current = (current.rstrip("/") + "/" + part) if current else part
        try:
            os.mkdir(current)
        except OSError:
            pass

DESCRIPTION = "Create a reminder/alarm. Usage: run(when='2026-08-19 09:00:00', channel='terminal', message='Submit paper')"


def _unix_time(when):
    value = str(when).strip().replace("T", " ")
    try:
        parts = value.replace("-", " ").replace(":", " ").split()
        if len(parts) != 6:
            raise ValueError()
        values = tuple(int(part) for part in parts)
    except Exception:
        raise ValueError("Invalid time format. Use YYYY-MM-DD HH:MM:SS")
    try:
        return int(time.mktime(values + (0, 0)))
    except Exception:
        return int(time.mktime(values + (0, 0, -1)))


def run(when, channel="terminal", message=""):
    alarms_dir = "memory/alarms"
    try:
        _mkdirs(alarms_dir)
    except OSError:
        pass

    timestamp = _unix_time(when)
    # Never overwrite another reminder due the same second: "<ts>", "<ts>.001", ...
    # (the name is parsed with float(), so the suffix keeps ordering and dueness).
    for n in range(1000):
        alarm_file = alarms_dir + "/" + str(timestamp) + ("" if n == 0 else ".%03d" % n)
        try:
            with open(alarm_file, "x") as file:
                file.write(channel + "\n" + message)
            break
        except FileExistsError:
            continue
    else:
        return "ERROR: too many reminders already set for " + str(when)
    return "SUCCESS: Reminder set for " + str(when) + " -> " + alarm_file
