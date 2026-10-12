"""
Quota Guard â lightweight storage management transformation.
Runs on every cycle (zz prefix = last), performs:
  1. Log rotation: trim transcript.txt and history.metta to max lines
  2. Screenshot sweep: delete oldest screenshots beyond a retention count
  3. Storage note: report usage in the system message when ~/iter exceeds the quota
"""
import os, gc, time, json
from iterbrow_runtime.episodic_history import rotate_tail
from iterbrow_runtime.atomspace_store import _atomic_text

DESCRIPTION = "Quota guard: log rotation, screenshot sweep, storage warning."

MAX_TRANSCRIPT_LINES = 200      # keep last 200 lines of transcript
MAX_HISTORY_LINES    = 500      # keep last 500 lines of history.metta
MAX_HISTORY_BYTES    = 120_000  # hard cap on history.metta (120 KB)
MAX_SCREENSHOTS      = 6        # keep at most 6 screenshot files
STORAGE_QUOTA_BYTES  = 5_000_000  # warn if ~/iter exceeds 5 MB

HOME = "."

def _fsize(path):
    try:
        return os.stat(path)[6]
    except OSError:
        return 0

LOW_WATER = 0.8  # rotate in batches: once over a cap, trim to 80% of it


def _truncate_tail(path, max_lines, max_bytes=0):
    """Once a log exceeds max_lines/max_bytes, archive its oldest lines down to
    LOW_WATER of the caps. Below the caps nothing is rotated, so one archive
    file is created per batch instead of one per cycle."""
    try:
        size = os.stat(path).st_size
    except OSError:
        return 0
    if not (max_bytes and size > max_bytes):
        with open(path, "rb") as handle:
            lines = sum(1 for _ in handle)
        if lines <= max_lines:
            return 0
    return rotate_tail(path, int(max_lines * LOW_WATER), int(max_bytes * LOW_WATER) if max_bytes else 0)

def _screenshot_sweep():
    """Delete oldest screenshots beyond MAX_SCREENSHOTS."""
    ss_dir = os.path.join(HOME, "screenshots")
    try:
        files = [os.path.join(ss_dir, f) for f in os.listdir(ss_dir)]
        files = [f for f in files if os.path.isfile(f)]
    except OSError:
        return 0
    if len(files) <= MAX_SCREENSHOTS:
        return 0
    # Sort by modification time (oldest first)
    files.sort(key=lambda f: os.stat(f)[8])  # st_mtime
    removed = 0
    while len(files) > MAX_SCREENSHOTS:
        try:
            os.remove(files[0])
            removed += 1
        except OSError:
            pass
        files.pop(0)
    return removed

def _dir_size(path):
    total = 0
    try:
        for entry in os.listdir(path):
            # memory/archive counts: it is where rotated history accumulates.
            if entry in (".venv", ".git", ".runtime", "node_modules"):
                continue
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                total += _dir_size(full)
            else:
                total += _fsize(full)
    except OSError:
        pass
    return total

def transform(messages, tools):
    try:
        reclaimed = 0

        # 1. Log rotation
        reclaimed += _truncate_tail(
            os.path.join(HOME, "transcript.txt"),
            MAX_TRANSCRIPT_LINES
        )
        reclaimed += _truncate_tail(
            os.path.join(HOME, "history.metta"),
            MAX_HISTORY_LINES,
            MAX_HISTORY_BYTES
        )

        # 2. Screenshot sweep
        _screenshot_sweep()

        # 3. Storage warning
        stamp = os.path.join(HOME, "transformations/.runtime/quota_scan.json")
        try:
            previous = json.load(open(stamp))
        except (OSError, ValueError):
            previous = {}
        total = previous.get("bytes", 0)
        if time.time() - previous.get("at", 0) >= 300:
            total = _dir_size(HOME)
            from iterbrow_runtime.atomspace_store import _atomic_json
            _atomic_json(stamp, {"at": time.time(), "bytes": total})
        if total > STORAGE_QUOTA_BYTES and messages and isinstance(messages[0], dict):
            # A one-line fact in the system message (the agent's own context,
            # never a message to the user). It reports usage only: archived
            # history is memory, so it suggests no action at all.
            note = ("STORAGE NOTE: the iter folder uses %.1f MB (soft quota %.1f MB), including "
                    "memory/archive. For information only; no action is needed."
                    % (total / 1e6, STORAGE_QUOTA_BYTES / 1e6))
            content = messages[0].get("content", "")
            if isinstance(content, str):
                messages[0]["content"] = content.rstrip() + "\n\n" + note
            elif isinstance(content, list):
                messages[0]["content"] = content + [{"type": "text", "text": "\n\n" + note}]

        gc.collect()
    except Exception:
        pass

    return messages, tools
