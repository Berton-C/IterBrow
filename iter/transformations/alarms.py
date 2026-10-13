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

DESCRIPTION = "Alarm clock directory (due alarms are delivered as saved input by iter.py)"

ALARMS_DIR = "memory/alarms"

def _timestamp():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])

def transform(messages, tools):
    """Delivery moved to iter.py (iterbrow_runtime/alarm_inbox.py): due alarms
    become saved input right after receive(). Consuming them here edited only
    one attempt's request copy, so a retry or rollback lost the alarm. This
    transformation only keeps the alarms directory present."""
    try:
        _mkdirs(ALARMS_DIR)
    except Exception:
        pass
    return messages, tools
