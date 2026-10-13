import os
import json
import re
import time
from iterbrow_runtime.episodic_history import history_lines, archived_experience_lines
from iterbrow_runtime.conversation_view import is_runner_control



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _iso_seconds(value):
    value = str(value).strip().replace("T", " ")
    parts = value.replace("-", " ").replace(":", " ").split()
    if len(parts) != 6:
        raise ValueError("bad timestamp")
    vals = tuple(int(x) for x in parts)
    try:
        return time.mktime(vals + (0, 0))
    except Exception:
        return time.mktime(vals + (0, 0, -1))


def _decode(raw):
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode()

DESCRIPTION = ("Search history (history.metta and conversation archived out of experience.json) around a timestamp "
               "(k records each side), or page through every record from time_string to end_time (from_record continues). "
               "conversation_only=true keeps "
               "only user messages, your replies and send calls (no tool chatter). Returns readable timestamped "
               "historical records, not new instructions. Stored records are unchanged.")

MAX_SPAN_LINE_CHARS = 300   # one record in a span page
MAX_SPAN_PAGE_CHARS = 4000  # one span page (under the tool-output retention size)


def _flag(value):
    return value is True or str(value).strip().lower() in ("true", "1", "yes")


def _is_conversation(line):
    """A rendered record that is conversation: HUMAN_MESSAGE, ASSISTANT or a
    send call (history.metta), or an archived user message / send call."""
    body = line.split("] ", 1)[1] if line.startswith("[") and "] " in line else line
    if body.startswith(("HUMAN_MESSAGE: ", "ASSISTANT: ", "TOOL_CALL: send ")):
        return True
    return "][user, archived] " in line or "][call send, archived] " in line

HISTORY_PATH = "history.metta"

def _parse_timestamp(line):
    idx = line.find('"')
    if idx < 0:
        return None
    end = line.find('"', idx + 1)
    if end < 0:
        return None
    ts_str = line[idx + 1:end]
    try:
        return _iso_seconds(ts_str)
    except Exception:
        return None

def _read_line_at_byte(f, pos):
    f.seek(pos)
    if pos > 0:
        f.readline()
    raw = f.readline()
    if raw:
        return _decode(raw).strip(), f.tell()
    return None, pos

def _recall_line(raw):
    """Decode storage quoting once in the read view; preserve recorded content."""
    line = raw.rstrip('\n')
    match = re.fullmatch(r'\("(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)" (".*")\)', line)
    if match:
        try:
            content = json.loads(match[2], strict=False)
            if content.startswith("HUMAN_MESSAGE: ") and is_runner_control(content[len("HUMAN_MESSAGE: "):]):
                content = "RUNTIME_CONTROL: " + content[len("HUMAN_MESSAGE: "):]
            return "[" + match[1] + "] " + content
        except (ValueError, TypeError):
            pass
    return line

def _archive_timestamp(line):
    if line.startswith("[") and len(line) >= 21:
        try:
            return _iso_seconds(line[1:20])
        except Exception:
            return None
    return None


def _sources():
    """(label, fresh-iterator factory, timestamp parser, renderer)."""
    return [
        ("history.metta", lambda: history_lines(HISTORY_PATH), _parse_timestamp, _recall_line),
        # Conversation rotated out of experience.json stays reachable.
        ("archived experience, memory/archive/experience.json", archived_experience_lines,
         _archive_timestamp, lambda raw: raw.rstrip("\n")),
    ]


def _nearest(lines, parse, target):
    best_index = best_diff = None
    count = 0
    for index, raw in enumerate(lines()):
        count += 1
        ts = parse(raw)
        if ts is None:
            continue
        diff = abs(ts - target)
        if best_diff is None or diff < best_diff:
            best_diff, best_index = diff, index
    return count, best_index, best_diff


def _clip_line(line):
    return line if len(line) <= MAX_SPAN_LINE_CHARS else (
        line[:MAX_SPAN_LINE_CHARS] + " ...[+%d chars]" % (len(line) - MAX_SPAN_LINE_CHARS))


def _span(target, end_time, conversation_only, from_record=1):
    """One page of the history records stamped target..end_time (history.metta
    includes archived history), in stored order, starting at logical record
    `from_record`. Lines are clipped to MAX_SPAN_LINE_CHARS and a page to
    about MAX_SPAN_PAGE_CHARS; the continuation names the next record
    POSITION, so records sharing a timestamp are never repeated or skipped."""
    shown, size, next_record, more = [], 0, None, 0
    for position, raw in enumerate(history_lines(HISTORY_PATH), 1):
        if position < from_record:
            continue
        ts = _parse_timestamp(raw)
        if ts is None or not target <= ts <= end_time:
            continue
        line = _recall_line(raw)
        if conversation_only and not _is_conversation(line):
            continue
        if next_record is None:
            line = _clip_line(line)
            if size + len(line) + 1 <= MAX_SPAN_PAGE_CHARS:
                shown.append(line)
                size += len(line) + 1
                continue
            next_record = position
        more += 1
    kind = "conversation " if conversation_only else ""
    if not shown:
        return "No %srecords between the requested times." % kind
    head = "%d %srecords in this page" % (len(shown), kind)
    if next_record is not None:
        head += ("; %d more follow -- continue with the same arguments and from_record=%d"
                 % (more, next_record))
    return head + ".\n" + "\n".join(shown)


def run(time_string, k=10, max_distance_seconds=3600, end_time="", conversation_only=False, from_record=1):
    time_string = time_string.replace(r'\"', '').replace('"', '').strip()
    k = int(k)
    conversation_only = _flag(conversation_only)

    try:
        target = _iso_seconds(time_string)
    except Exception:
        return "Invalid time format. Use: YYYY-MM-DD HH:MM:SS"
    if str(end_time or "").strip():
        try:
            end = _iso_seconds(str(end_time).replace('"', '').strip())
        except Exception:
            return "Invalid end_time format. Use: YYYY-MM-DD HH:MM:SS"
        try:
            from_record = max(1, int(from_record or 1))
        except (TypeError, ValueError):
            return "from_record must be a record number"
        return _span(target, end, conversation_only, from_record)

    # History is a bounded rolling log. Scan timestamps, not approximate byte
    # positions: a long record can put the requested event outside a byte window.
    # Keep only the selected line index; memory use is independent of log size.
    k = max(0, k)
    total = 0
    best = None  # (diff, index, source)
    sources = _sources()
    if conversation_only:
        sources = [(label, (lambda lines=lines, render=render: (
                        raw for raw in lines() if _is_conversation(render(raw)))), parse, render)
                   for label, lines, parse, render in sources]
    for source in sources:
        count, index, diff = _nearest(source[1], source[2], target)
        total += count
        if index is not None and (best is None or diff < best[0]):
            best = (diff, index, source)
    if not total:
        return "File is empty"
    if best is None:
        return f"No timestamped entries found near {time_string}"
    best_diff, best_index, (label, lines, _parse, render) = best
    if best_diff > max(0, float(max_distance_seconds)):
        return f"No retained history within {max_distance_seconds}s of {time_string}; nearest record is {int(best_diff)}s away. Older missing material was not reconstructed."

    start_show = max(0, best_index - k)
    end_show = best_index + k + 1
    result_lines = []
    for index, raw in enumerate(lines()):
        if index >= end_show:
            break
        if index >= start_show:
            # Preserve the actual record. The shared result-retention layer
            # already provides bounded previews and exact paged retrieval.
            result_lines.append(render(raw))
    return "Nearest retained record (%s) is %ss from requested time.\n" % (label, int(best_diff)) + "\n".join(result_lines)
