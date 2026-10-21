"""Find communication transcript lines near a wall-clock timestamp."""

import os
import json
from datetime import datetime
from iterbrow_runtime.episodic_history import history_lines, archived_experience_lines




def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = (
    'Search the communication transcript (and archived conversation) around a timestamp (YYYY-MM-DD '
    'HH:MM:SS); returns the nearest record with nearby lines.'
)

TRANSCRIPT_PATH = "transcript.txt"
CHAT_PATH = "chat.txt"


def _canonical_timestamp(value):
    value = str(value or "").strip().replace("T", " ")
    if len(value) < 19:
        return None
    value = value[:19]
    if value[4:5] != "-" or value[7:8] != "-" or value[10:11] != " " or value[13:14] != ":" or value[16:17] != ":":
        return None
    return value


def _timestamp_from_line(line):
    line = line.strip()
    if line.startswith("[") and len(line) >= 20:
        timestamp = _canonical_timestamp(line[1:20])
        if timestamp:
            return timestamp

    marker = "Step "
    position = line.find(marker)
    if position >= 0:
        timestamp = _canonical_timestamp(line[position + len(marker):position + len(marker) + 19])
        if timestamp:
            return timestamp

    if line.startswith("{"):
        try:
            item = json.loads(line)
            return _canonical_timestamp(item.get("time"))
        except Exception:
            return None
    return None


def _seconds(timestamp):
    return datetime.fromisoformat(timestamp).timestamp()


def _nearest(lines, target, k, label):
    """(distance, text) for the record NEAREST the target in a source, with k
    lines of context on each side; None when the source has no timestamps.
    `lines` is a zero-argument callable returning a fresh iterator."""
    goal = _seconds(target)
    best = None  # (distance, index, delta)
    for index, raw in enumerate(lines()):
        timestamp = _timestamp_from_line(raw)
        if not timestamp:
            continue
        delta = _seconds(timestamp) - goal
        if best is None or abs(delta) < best[0]:
            best = (abs(delta), index, delta)
    if best is None:
        return None
    distance, center, delta = best
    window = [raw.rstrip("\n") for index, raw in enumerate(lines()) if center - k <= index <= center + k]
    where = "at" if delta == 0 else ("%ds %s" % (int(distance), "before" if delta < 0 else "after"))
    heading = "Nearest retained record (%s) is %s the requested time." % (label, where)
    return distance, heading + "\n" + "\n".join(window)


def _sources():
    return [
        (TRANSCRIPT_PATH, lambda: history_lines(TRANSCRIPT_PATH)),
        (CHAT_PATH, lambda: history_lines(CHAT_PATH)),
        # Conversation rotated out of experience.json stays reachable.
        ("archived experience, memory/archive/experience.json", archived_experience_lines),
    ]


def run(time_string, k=10):
    target = _canonical_timestamp(str(time_string).replace(r'\"', "").replace('"', ""))
    if target is None:
        return "Invalid time format. Use: YYYY-MM-DD HH:MM:SS"
    k = max(0, int(k))

    found = [result for label, lines in _sources() for result in [_nearest(lines, target, k, label)] if result]
    if found:
        distance, text = min(found, key=lambda item: item[0])
        if distance <= 3600:
            return text
    return "No retained communication transcript within one hour of the requested time; missing older history was not reconstructed."
