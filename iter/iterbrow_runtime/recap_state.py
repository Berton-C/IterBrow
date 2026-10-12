"""Recap cursor and pending recap request, shared by transformations/recap.py
(which asks the agent for an episode) and tools/record_episode.py (the
sanctioned way the agent writes one).

Positions are 1-based LOGICAL history record numbers: archived history plus
the working history.metta tail, as episodic_history.history_lines() yields
them. memory/recap/.recap_state keeps its original meaning - the number of
history records already summarized into episodes (a plain integer).

memory/recap/.recap_request.json holds the span recap.py last asked for:
{"next_e": N, "start": a, "end": b, "start_time": ..., "end_time": ...}.
The cursor advances when an episode covering the span exists: either the
episode records the history lines it covers ("lines": [a, b], written by
record_episode), or - for an episode written some other way - an episode
numbered >= the requested next_e appears, which completes the request.
"""
import json
import os
import re
import time

from .atomspace_store import _atomic_text
from .episodic_history import history_lines, history_lines_from, history_line_count, list_episodes, RECAP_DIR

HISTORY_PATH = "history.metta"
STATE_PATH = os.path.join(RECAP_DIR, ".recap_state")
FLAG_PATH = os.path.join(RECAP_DIR, ".recap_needed")
REQUEST_PATH = os.path.join(RECAP_DIR, ".recap_request.json")
MIGRATION_PATH = os.path.join(RECAP_DIR, ".recap_cursor_migrated")

_TIMESTAMP = re.compile(r'^\("(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"')
_PLAIN_TIME = re.compile(r'^\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d')


def record_timestamp(line):
    match = _TIMESTAMP.match(line)
    return match.group(1) if match else None


def read_cursor():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return max(0, int(f.read().strip() or 0))
    except (OSError, ValueError):
        return 0


def write_cursor(value):
    os.makedirs(RECAP_DIR, exist_ok=True)
    _atomic_text(STATE_PATH, str(int(value)))


def read_request():
    try:
        with open(REQUEST_PATH, "r", encoding="utf-8") as f:
            request = json.load(f)
        if isinstance(request, dict) and all(isinstance(request.get(k), int) for k in ("next_e", "start", "end")):
            return request
    except (OSError, ValueError):
        pass
    return None


def total_records(path=HISTORY_PATH):
    return history_line_count(path)


def next_episode_number(episodes=None):
    episodes = list_episodes() if episodes is None else episodes
    numbers = [e["_n"] for e in episodes if e.get("_n") is not None]
    return max(numbers) + 1 if numbers else 1


def covered_end(episode):
    """Last history record an episode says it covers, or None."""
    lines = episode.get("lines")
    if isinstance(lines, list) and len(lines) == 2 and all(isinstance(v, int) for v in lines):
        return lines[1]
    return None


def advanced_cursor(cursor, episodes, request):
    """The cursor after accounting for episodes that cover requested history."""
    for episode in episodes:
        end = covered_end(episode)
        if end is not None:
            cursor = max(cursor, end)
    if request and any(e.get("_n") is not None and e["_n"] >= request["next_e"] for e in episodes):
        cursor = max(cursor, request["end"])
    return cursor


def span_times(start, end, path=HISTORY_PATH):
    """(earliest, latest) record timestamps within logical records start..end.

    Records carry event-time stamps, so history is not strictly in time order:
    min/max, never first/last."""
    stamps = []
    for position, raw in history_lines_from(path, start):
        if position > end:
            break
        stamp = record_timestamp(raw)
        if stamp:
            stamps.append(stamp)
    return (min(stamps), max(stamps)) if stamps else (None, None)


def span_for_times(start_time, end_time, path=HISTORY_PATH):
    """(lowest, highest) logical record positions whose timestamps fall in the
    range (out-of-order records included)."""
    positions = []
    for position, raw in enumerate(history_lines(path), 1):
        stamp = record_timestamp(raw)
        if stamp and start_time <= stamp <= end_time:
            positions.append(position)
    return (min(positions), max(positions)) if positions else (None, None)


def _episode_time(episode, recap_dir=RECAP_DIR):
    """When an episode's span ended: end_time, else a timestamp in "t"/"time"
    ("t" is normally the mem_type), else the episode file's modification time."""
    for key in ("end_time", "t", "time"):
        value = episode.get(key)
        if isinstance(value, str) and _PLAIN_TIME.match(value.strip()):
            return value.strip().replace("T", " ")[:19]
    try:
        mtime = os.stat(os.path.join(recap_dir, episode["_file"])).st_mtime
    except (OSError, KeyError):
        return None
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))


def migrate_cursor(episodes, path=HISTORY_PATH):
    """One-time cursor migration for episodes written before episodes carried
    "lines" (the owner's .recap_state counted something else).

    If episodes exist and none says which history records it covers, the
    cursor becomes the logical position of the last history record at or
    before the newest episode's end time (never moved backwards), and the
    decision is persisted in .recap_cursor_migrated so it runs once.
    Returns the new cursor, or None when nothing was migrated.
    """
    if not episodes or os.path.exists(MIGRATION_PATH):
        return None
    if any(covered_end(episode) is not None for episode in episodes):
        return None
    newest = episodes[-1]
    when = _episode_time(newest)
    position = 0
    if when:
        for index, raw in enumerate(history_lines(path), 1):
            stamp = record_timestamp(raw)
            if stamp and stamp <= when:
                position = index
    stored = read_cursor()
    cursor = max(stored, position)
    if cursor != stored:
        write_cursor(cursor)
    os.makedirs(RECAP_DIR, exist_ok=True)
    _atomic_text(MIGRATION_PATH, json.dumps({
        "from_episode": newest.get("_n"), "episode_time": when, "previous_cursor": stored, "cursor": cursor}))
    return cursor
