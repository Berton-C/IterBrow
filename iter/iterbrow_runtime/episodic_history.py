"""Lossless rotation of existing episodic files; archives never enter prompts."""
import hashlib
import json
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
