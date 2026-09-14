"""
Quota Guard â lightweight storage management transformation.
Runs on every cycle (zz prefix = last), performs:
  1. Log rotation: trim transcript.txt and history.metta to max lines
  2. Screenshot sweep: delete oldest screenshots beyond a retention count
  3. Storage warning: warn via pin/send when total ~/iter size exceeds quota
"""
import os, gc

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

def _truncate_tail(path, max_lines, max_bytes=0):
    """Keep only the tail of a text file (last max_lines, under max_bytes)."""
    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except OSError:
        return 0
    if len(lines) <= max_lines and (max_bytes == 0 or _fsize(path) <= max_bytes):
        return 0
    # Keep the tail
    kept = lines[-max_lines:]
    # If still over byte budget, trim further
    if max_bytes > 0:
        total = sum(len(l) for l in kept)
        while total > max_bytes and len(kept) > 1:
            kept.pop(0)
            total = sum(len(l) for l in kept)
    saved = _fsize(path)
    with open(path, "w") as f:
        for l in kept:
            f.write(l)
    new_size = _fsize(path)
    return saved - new_size

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
        total = _dir_size(HOME)
        if total > STORAGE_QUOTA_BYTES:
            # Pin a note rather than send (avoid spamming user every cycle)
            try:
                import bridge
                bridge.pin_note(
                    "STORAGE WARNING: ~/iter is %.1f MB (quota %.1f MB). "
                    "Consider cleanup." % (total / 1e6, STORAGE_QUOTA_BYTES / 1e6)
                )
            except Exception:
                pass

        gc.collect()
    except Exception:
        pass

    return messages, tools
