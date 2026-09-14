import time
import os



def _isfile(path):
    try:
        return (os.stat(path)[0] & 0x4000) == 0
    except OSError:
        return False


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

DESCRIPTION = "Alarm clock handling"

ALARMS_DIR = "memory/alarms"

def _timestamp():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

def transform(messages, tools):
    try:
        _mkdirs(ALARMS_DIR)
    except Exception:
        pass
    now = time.time()

    try:
        files = sorted(os.listdir(ALARMS_DIR))
    except Exception:
        files = []

    for alarm_file in files:
        alarm_path = ALARMS_DIR + "/" + alarm_file
        if not _isfile(alarm_path):
            continue
        try:
            target_time = float(alarm_file)
        except ValueError:
            continue

        if now >= target_time:
            try:
                with open(alarm_path, "r") as f:
                    content = f.read().strip()
            except Exception:
                continue
            lines = content.split("\n", 1)

            if len(lines) == 2:
                channel, msg = lines
            else:
                channel, msg = "terminal", content

            try:
                os.unlink(alarm_path)
            except Exception:
                pass

            messages.append({
                "role": "user",
                "content": "Step " + _timestamp() + ": [" + channel + "] [ALARM] " + msg
            })

    return messages, tools
