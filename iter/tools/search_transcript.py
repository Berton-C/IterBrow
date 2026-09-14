"""Find communication transcript lines near a wall-clock timestamp."""

import os
import json




def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

DESCRIPTION = "Search the communication transcript around a timestamp. Use YYYY-MM-DD HH:MM:SS; returns nearby user and send lines."

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


def _nearest_lines(path, target, k):
    before = []
    after = []
    found = False
    timestamped = 0

    with open(path, "r") as file:
        for raw in file:
            line = raw.rstrip("\n")
            timestamp = _timestamp_from_line(line)
            if timestamp:
                timestamped += 1

            if not found and timestamp and timestamp >= target:
                found = True
                after.append(line)
                continue

            if found:
                after.append(line)
                if len(after) >= k + 1:
                    break
            else:
                before.append(line)
                if len(before) > k:
                    before.pop(0)

    if timestamped == 0:
        return None
    return "\n".join(before + after)


def run(time_string, k=10):
    target = _canonical_timestamp(str(time_string).replace(r'\"', "").replace('"', ""))
    if target is None:
        return "Invalid time format. Use: YYYY-MM-DD HH:MM:SS"
    k = max(0, int(k))

    for path in (TRANSCRIPT_PATH, CHAT_PATH):
        if not _exists(path):
            continue
        result = _nearest_lines(path, target, k)
        if result is not None:
            return result

    return "No timestamped communication transcript found."
