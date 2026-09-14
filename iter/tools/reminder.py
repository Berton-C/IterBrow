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
    alarm_file = alarms_dir + "/" + str(timestamp)
    with open(alarm_file, "w") as file:
        file.write(channel + "\n" + message)
    return "SUCCESS: Reminder set for " + str(when) + " -> " + alarm_file
