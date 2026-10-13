"""Lossless rotation of existing episodic files; archives never enter prompts."""
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from .atomspace_store import _atomic_text, _atomic_json


def _rotation_path(path):
    return Path('memory/archive') / Path(path).name / '.rotation.json'


def recover_rotation(path):
    """Finish a pending archive/tail operation before any subsequent append."""
    marker = _rotation_path(path)
    if not marker.exists():
        return
    record = json.loads(marker.read_text(encoding='utf-8'))
    target = marker.parent / record['archive']
    current = Path(path).read_text(encoding='utf-8')
    before, after = record['before'], record['after']
    if current == after:
        restored = current
    elif current.startswith(before):
        restored = after + current[len(before):]
    elif current.startswith(after):
        restored = current
    else:
        raise RuntimeError('History changed during pending rotation; preserving all copies')
    if not target.exists():
        _atomic_text(target, record['prefix'])
    if restored != current:
        _atomic_text(path, restored)
    marker.unlink()


def rotate_tail(path, max_lines, max_bytes=0):
    recover_rotation(path)
    target = Path(path)
    if not target.exists():
        return 0
    before = target.read_text(encoding='utf-8')
    lines = before.splitlines(keepends=True)
    kept = lines[-max_lines:]
    total = sum(len(line.encode('utf-8')) for line in kept)
    while max_bytes and total > max_bytes and len(kept) > 1:
        total -= len(kept.pop(0).encode('utf-8'))
    prefix = ''.join(lines[:len(lines) - len(kept)])
    if not prefix:
        return 0
    after = ''.join(kept)
    marker = _rotation_path(path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    # A unique operation, not a content hash: identical independent episodes
    # must not collapse into one archive. Intent precedes both durable writes.
    _atomic_json(marker, {'before': before, 'after': after, 'prefix': prefix,
                         'archive': '%s-rotation-%s.txt' % (time.time_ns(), uuid.uuid4().hex)})
    recover_rotation(path)
    return len(prefix.encode('utf-8'))


def archive_text(path, text):
    if not text:
        return None
    folder = Path("memory/archive") / Path(path).name
    folder.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = next(folder.glob("*-" + digest + ".txt"), None)
    if existing:
        return existing
    target = folder / (str(time.time_ns()) + "-" + digest + ".txt")
    _atomic_text(target, text)  # durable before the working tail is shortened
    return target


def _segments(path):
    """The archives (in order) and working tail that make up a log's logical
    history, applying the interrupted-rotation and legacy-archive skip rules."""
    current = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    archives = sorted((Path("memory/archive") / Path(path).name).glob("*.txt"))
    marker = _rotation_path(path)
    pending = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else {}
    kept = []
    for index, archive in enumerate(archives):
        # A crash after archiving but before replacing the tail must not make
        # these records appear twice or move recap's logical position twice.
        if (archive.name == pending.get('archive')
                and current != pending['after'] and current.startswith(pending['before'])):
            continue
        if ('-rotation-' not in archive.name and index == len(archives) - 1
                and current.startswith(archive.read_text(encoding="utf-8"))):
            continue
        kept.append(archive)
    return kept, current


def history_lines(path):
    """Chronological archive + working tail, including interrupted rotation."""
    archives, current = _segments(path)
    for archive in archives:
        yield from archive.read_text(encoding="utf-8").splitlines(keepends=True)
    yield from current.splitlines(keepends=True)


def history_lines_from(path, start):
    """(position, line) for logical records at 1-based position >= start;
    whole archives before `start` are skipped via cached line counts."""
    archives, current = _segments(path)
    counts = _archive_line_counts(archives[0].parent, archives) if archives else {}
    position = 1
    for archive in archives:
        if position + counts[archive.name] <= start:
            position += counts[archive.name]
            continue
        for line in archive.read_text(encoding="utf-8").splitlines(keepends=True):
            if position >= start:
                yield position, line
            position += 1
    for line in current.splitlines(keepends=True):
        if position >= start:
            yield position, line
        position += 1


_COUNT_CACHE = ".line_counts.json"


def _archive_line_counts(folder, archives):
    """Line count of each (immutable) archive file, cached by name and size in
    <folder>/.line_counts.json so a cycle does not re-read every archive."""
    cache_path = folder / _COUNT_CACHE
    try:
        cache = json.loads(cache_path.read_bytes().decode("utf-8"))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError, UnicodeDecodeError):
        cache = {}
    counts, changed = {}, False
    for archive in archives:
        size = archive.stat().st_size
        entry = cache.get(archive.name)
        if isinstance(entry, list) and len(entry) == 2 and entry[0] == size:
            counts[archive.name] = entry[1]
            continue
        with open(archive, "r", encoding="utf-8") as handle:
            counts[archive.name] = sum(1 for _ in handle)
        changed = True
    if changed or set(cache) != set(counts):
        try:
            _atomic_json(cache_path, {name: [archive.stat().st_size, counts[archive.name]]
                                      for archive in archives for name in [archive.name]})
        except OSError:
            pass  # a cache only; the count itself is exact either way
    return counts


def history_line_count(path):
    """Number of logical records history_lines(path) yields, using cached
    per-archive line counts instead of re-reading every archive each cycle."""
    archives, current = _segments(path)
    counts = _archive_line_counts(archives[0].parent, archives) if archives else {}
    return sum(counts[a.name] for a in archives) + len(current.splitlines(keepends=True))


EXPERIENCE_ARCHIVE = Path("memory/archive") / "experience.json"
_STEP = re.compile(r"^Step (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d): ")


def _one_line(text, limit=600):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


def archived_experience_lines(folder=EXPERIENCE_ARCHIVE):
    """Messages rotated out of experience.json, as timestamped read-only lines
    "[YYYY-MM-DD HH:MM:SS][role] text" in archive (chronological) order.
    User/tool messages carry their Step time; a tool call the time of its result."""
    try:
        archives = sorted(Path(folder).glob("*.txt"))
    except OSError:
        return
    for archive in archives:
        try:
            messages = json.loads(archive.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(messages, list):
            continue
        times = {}
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "tool":
                match = _STEP.match(str(message.get("content", "")))
                if match:
                    times[message.get("tool_call_id")] = match.group(1)
        for message in messages:
            if not isinstance(message, dict):
                continue
            role, content = message.get("role"), message.get("content")
            if role == "user" and isinstance(content, str):
                match = _STEP.match(content)
                if match:
                    yield "[%s][user, archived] %s\n" % (match.group(1), _one_line(content))
            elif role == "assistant":
                for call in message.get("tool_calls") or []:
                    stamp = times.get(call.get("id"))
                    function = call.get("function", {})
                    if stamp:
                        yield "[%s][call %s, archived] %s\n" % (
                            stamp, function.get("name", ""), _one_line(function.get("arguments", "")))
            elif role == "tool" and isinstance(content, str):
                match = _STEP.match(content)
                if match:
                    yield "[%s][result %s, archived] %s\n" % (
                        match.group(1), message.get("tool_call_id", ""), _one_line(content))


RECAP_DIR = "memory/recap"
_EPISODE_NAME = re.compile(r"^episode_(\d+)\.json$")


def episode_number(episode, filename=""):
    """Numeric identity of an episode: its "e" (or legacy "id") field, else the
    digits in its file name. None when neither is a number."""
    for key in ("e", "id", "e_num"):
        value = episode.get(key) if isinstance(episode, dict) else None
        try:
            if value is not None and not isinstance(value, bool):
                return int(str(value).strip().lstrip("Ee"))
        except ValueError:
            pass
    match = _EPISODE_NAME.match(Path(filename).name)
    return int(match.group(1)) if match else None


def list_episodes(recap_dir=RECAP_DIR):
    """All readable episode records, ordered by episode NUMBER (never by the
    lexicographic file name: episode_10 sorts after episode_9). Gaps are fine.
    Each record gets "_file" (its file name) and "_n" (its number)."""
    episodes = []
    try:
        names = os.listdir(recap_dir)
    except OSError:
        return episodes
    for name in names:
        if not (name.startswith("episode_") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(recap_dir, name), "r", encoding="utf-8") as handle:
                episode = json.loads(handle.read())
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(episode, dict):
            continue
        episode["_file"] = name
        episode["_n"] = episode_number(episode, name)
        episodes.append(episode)
    episodes.sort(key=lambda e: (e["_n"] is None, e["_n"] if e["_n"] is not None else 0, e["_file"]))
    return episodes


_EPISODE_TIME = re.compile(r"^\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d")


def episode_time(episode):
    """When an episode's period ended: end_time, else start_time, else a
    timestamp-like "time" (legacy); None when it names no time."""
    for key in ("end_time", "start_time", "time"):
        value = episode.get(key)
        if isinstance(value, str) and _EPISODE_TIME.match(value.strip()):
            return value.strip().replace("T", " ")[:19]
    return None


def chronological(episodes):
    """Episodes ordered by the TIME they cover, not by number: an episode
    written late about an earlier period must not rank as most recent. An
    episode without a time keeps its place after the episode before it by
    number (it inherits that one's time); ties keep number order."""
    keyed, last = [], ""
    for index, episode in enumerate(episodes):
        when = episode_time(episode)
        if when is not None:
            last = when
        keyed.append((when if when is not None else last, index, episode))
    keyed.sort(key=lambda row: (row[0], row[1]))
    return [episode for _, _, episode in keyed]


def load_experience(path="experience.json", log=print):
    """Load saved conversation history without ever refusing to start.

    A missing file starts empty.  A corrupt or non-list file (partial write,
    disk full, hand edit) is moved aside as ``<path>.corrupt-<ns>`` so nothing
    is lost, the event is logged, and Iter starts with an empty history
    instead of crashing on every launch."""
    target = Path(path)
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    try:
        experience = json.loads(raw)
        if not isinstance(experience, list) or not all(isinstance(m, dict) for m in experience):
            raise ValueError("history is not a list of messages")
        return experience
    except (ValueError, UnicodeDecodeError) as error:
        quarantine = target.with_name(target.name + ".corrupt-%d" % time.time_ns())
        target.replace(quarantine)
        log("[continuity] %s unreadable (%s); moved to %s and starting with empty history"
            % (target, error, quarantine.name))
        return []
