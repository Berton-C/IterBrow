"""Trajectory Capture - records per-cycle tool-call snapshots."""
import os, json

DESCRIPTION = "Trajectory capture: per-cycle tool-call snapshots for self-improvement evidence."

ROOT = "."
TRAJ_DIR = os.path.join(ROOT, ".trajectory")
TRANSCRIPT_PATH = os.path.join(ROOT, "transcript.txt")
TASKS_PATH = os.path.join(ROOT, "memory", "tasks", "current_tasks.txt")
MAX_ENTRIES = 20

def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def _ensure_dir(path):
    try:
        os.stat(path)
    except OSError:
        try:
            os.mkdir(path)
        except:
            pass

def _get_task_context():
    if not _exists(TASKS_PATH):
        return ""
    try:
        with open(TASKS_PATH, "r") as f:
            for line in f:
                if "Task Content:" in line:
                    return line.split("Task Content:")[1].strip()[:80]
    except:
        pass
    return ""

def _parse_recent_calls(last_n=10):
    if not _exists(TRANSCRIPT_PATH):
        return []
    try:
        with open(TRANSCRIPT_PATH, "r") as f:
            lines = f.readlines()
    except:
        return []
    calls = []
    for line in lines:
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        parts = line.split("]")
        if len(parts) < 2:
            continue
        tool_info = parts[1].strip().lstrip("[")
        tokens = tool_info.split()
        if not tokens:
            continue
        calls.append(tokens[0])
    return calls[-last_n:] if len(calls) > last_n else calls

def _list_snapshots():
    if not _exists(TRAJ_DIR):
        return []
    try:
        files = os.listdir(TRAJ_DIR)
        snapshots = []
        for f in files:
            if f.endswith(".json") and f.startswith("snap_"):
                try:
                    num = int(f.replace("snap_", "").replace(".json", ""))
                    snapshots.append((num, f))
                except:
                    pass
        snapshots.sort()
        return snapshots
    except:
        return []

def _trim_old_snapshots():
    snapshots = _list_snapshots()
    if len(snapshots) <= MAX_ENTRIES:
        return
    excess = len(snapshots) - MAX_ENTRIES
    for i in range(excess):
        try:
            os.remove(os.path.join(TRAJ_DIR, snapshots[i][1]))
        except:
            pass

def _next_snapshot_num():
    snapshots = _list_snapshots()
    if not snapshots:
        return 1
    return snapshots[-1][0] + 1

def transform(messages, tools):
    try:
        _ensure_dir(TRAJ_DIR)
        calls = _parse_recent_calls()
        has_send = "send" in calls
        task_ctx = _get_task_context()
        snapshot = {
            "n": _next_snapshot_num(),
            "calls": calls,
            "n_calls": len(calls),
            "send": has_send,
            "task": task_ctx,
        }
        fname = "snap_%04d.json" % snapshot["n"]
        fpath = os.path.join(TRAJ_DIR, fname)
        with open(fpath, "w") as f:
            f.write(json.dumps(snapshot))
        _trim_old_snapshots()
    except Exception:
        pass
    return messages, tools