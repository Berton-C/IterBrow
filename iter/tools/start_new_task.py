import importlib.util
import os
import re
import sys
import time
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from iterbrow_runtime.cognitive_events import commit_event, metta_string



def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _mkdirs(path):
    current = ""
    for part in str(path).split("/"):
        if not part:
            current = "/" if not current else current
            continue
        current = (current.rstrip("/") + "/" + part) if current else part
        try:
            os.mkdir(current)
        except OSError:
            pass

DESCRIPTION = (
    'Register the current task (memory/tasks/current_tasks.txt); by default updates existing work. '
    'new_work=true only for a separate goal, never a clarification or repair. All five fields are '
    'required.'
)

ARCHIVE_KEEP = 200


def _archive(archive_dir, previous):
    _mkdirs(archive_dir)
    with open("%s/%d-current_tasks.txt" % (archive_dir, time.time_ns()), "x") as f:
        f.write(previous)
    names = sorted(n for n in os.listdir(archive_dir) if n.endswith("-current_tasks.txt"))
    for name in names[:-ARCHIVE_KEEP]:
        try:
            os.remove(os.path.join(archive_dir, name))
        except OSError:
            pass


def _send_to_channel(channel, content):
    """Send a message through a channel module, loaded the same way tools/send.py
    does it (importlib module-from-spec) so __file__ and package context are set
    correctly. The previous exec(src, {}) approach ran the channel module with no
    __file__ in its namespace, which crashed any channel - like electron_ui.py -
    that computes its runtime paths relative to __file__."""
    channel = str(channel or "").strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", channel):
        return f"Invalid channel: {channel}"
    path = Path(__file__).resolve().parents[1] / "channels" / (channel + ".py")
    if not _exists(path):
        return f"Channel file not found: {path}"
    spec = importlib.util.spec_from_file_location("channel_" + channel, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "send"):
        return f"Channel {channel} cannot send"
    module.send(content)
    return "SUCCESS"

def run(person, requestchannel, taskcontent, completionsendcriterium, originalUserMessage="", new_work="false"):
    # The existing tool catalog advertises scalar arguments as strings.
    if new_work in ("true", "false"):
        new_work = new_work == "true"
    if type(new_work) is not bool:
        return "ERROR: new_work must be a boolean; no task state changed."
    ROOT = "."
    TASKS_DIR = ROOT + "/memory/tasks"
    try:
        _mkdirs(TASKS_DIR)
    except:
        pass
    TASK_FILE = TASKS_DIR + "/current_tasks.txt"

    now = time.localtime()
    now_str = "%04d-%02d-%02d %02d:%02d:%02d" % (now[0], now[1], now[2], now[3], now[4], now[5])
    try:
        with open(TASK_FILE, "r", encoding="utf-8", errors="replace") as f:
            previous = f.read()
    except OSError:
        previous = ""
    started_str = now_str
    if previous and not new_work:
        # An update continues the same task: keep its start time and the
        # original request unless the caller supplies a new one.
        m = re.search(r"^# Current Task \(started ([^)]*)\)", previous, re.M)
        started_str = m.group(1) if m else now_str
        if not str(originalUserMessage).strip():
            m = re.search(r"^# Original User Message: (.*?)\n# =+[ \t]*$", previous, re.M | re.S)
            originalUserMessage = m.group(1) if m else originalUserMessage

    content = f"""# Current Task (started {started_str})
# =============================================
# Person:               {person}
# Request Channel:      {requestchannel}
# Task Content:         {taskcontent}
# Completion Criterion: {completionsendcriterium}
# Original User Message: {originalUserMessage}
# =============================================
"""
    # Never destroy the prior task account: archive it BEFORE committing, so
    # an archive failure can never be reported as an uncommitted task.
    # memory/tasks/archive/ is excluded from the prompt projection (EXCLUDE_DIRS
    # "archive"), covered by the state manifest as part of memory/, and keeps
    # the newest ARCHIVE_KEEP files.
    archive_note = ""
    if previous and previous != content:
        try:
            _archive(TASKS_DIR + "/archive", previous)
        except Exception as e:
            archive_note = "\n  Task committed; archive failed: %s" % e
    try:
        commit_event(
            "current_task", "active", "task_started",
            {
                "person": person,
                "request_channel": requestchannel,
                "task_content": taskcontent,
                "completion_criterion": completionsendcriterium,
                "original_user_message": originalUserMessage,
                "started_at": started_str,
                "new_work": new_work,
            },
            state_atom="(current-task %s %s %s)" % (
                metta_string(str(person)), metta_string(str(taskcontent)),
                metta_string(str(completionsendcriterium)),
            ),
            source="tools.start_new_task",
        )
        tmp = TASK_FILE + ".tmp"
        with open(tmp, 'w') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TASK_FILE)
    except Exception as e:
        return "ERROR: task was not committed: %s" % e

    notification = (
        ("**NEW TASK STARTED**\n" if new_work else "**CURRENT TASK UPDATED**\n") +
        f"**Person:** {person}\n"
        f"**Channel:** {requestchannel}\n"
        f"**Task:** {taskcontent}\n"
        f"**Completion Criterion:** {completionsendcriterium}\n"
        f"**Started:** {started_str}"
    )

    send_status = "not sent"
    try:
        send_status = _send_to_channel(requestchannel, notification)
    except Exception as e:
        send_status = f"send failed: {e}"

    status = "New task started" if new_work else "Current task updated"
    return f"SUCCESS, RETURN: {status} at {now_str}.\n  Person: {person}\n  Channel: {requestchannel}\n  Task: {taskcontent}\n  Completion criterion: {completionsendcriterium}\n  Original message: {originalUserMessage}\n  Written to: {TASK_FILE}\n  Channel notification: {send_status}" + archive_note
