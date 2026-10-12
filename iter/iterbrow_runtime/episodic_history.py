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


def history_lines(path):
    """Chronological archive + working tail, including interrupted rotation."""
    current = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    archives = sorted((Path("memory/archive") / Path(path).name).glob("*.txt"))
    marker = _rotation_path(path)
    pending = json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else {}
    for index, archive in enumerate(archives):
        text = archive.read_text(encoding="utf-8")
        # A crash after archiving but before replacing the tail must not make
        # these records appear twice or move recap's logical position twice.
        if (archive.name == pending.get('archive')
                and current != pending['after'] and current.startswith(pending['before'])):
            continue
        if '-rotation-' not in archive.name and index == len(archives) - 1 and current.startswith(text):
            continue
        yield from text.splitlines(keepends=True)
    yield from current.splitlines(keepends=True)


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
