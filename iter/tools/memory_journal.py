"""Append-only audit journal for memory-management actions (Headlong's
trajectory-DAG idea, adapted: every memory-mutating action - trim,
regenerate, forget, vote - gets one immutable line here, so a future
incident is auditable from a single file instead of forensic diffing
across the whole memory/ tree.

Callable both as a tool (run(...)) and as a plain import from other
tools (log(...)) since several sanctioned tools need to journal without
exposing a second LLM-facing tool call every time.
"""

import json
import os
import sys
import time

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
import _memory_guard as guard

DESCRIPTION = (
    "Append-only audit journal for memory-management actions. action='log' "
    "records {actor, action, detail} as a new immutable line (use this "
    "whenever you trim, regenerate, forget, or vote on memory content so "
    "there is always an audit trail). action='tail' returns the last n "
    "entries."
)

JOURNAL_PATH = "memory/journal.jsonl"


def _ts():
    t = time.localtime()
    return "%04d-%02d-%02d %02d:%02d:%02d" % (t[0], t[1], t[2], t[3], t[4], t[5])


def log(actor, action, detail=None):
    """Append one journal entry. Safe to call from any sanctioned tool."""
    entry = {
        "ts": _ts(),
        "actor": actor,
        "action": action,
        "detail": detail if detail is not None else "",
    }
    line = json.dumps(entry, ensure_ascii=False)
    os.makedirs(os.path.dirname(JOURNAL_PATH) or ".", exist_ok=True)
    with guard.allow_protected_write("memory_journal.log"):
        with open(JOURNAL_PATH, "a") as f:
            f.write(line + "\n")
    return entry


def _tail(n):
    if not os.path.exists(JOURNAL_PATH):
        return []
    with open(JOURNAL_PATH, "r") as f:
        lines = f.readlines()
    out = []
    for raw in lines[-n:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except Exception:
            out.append({"raw": raw})
    return out


def run(action="tail", actor="agent", detail="", n="20"):
    if action == "log":
        entry = log(actor, detail or "manual", detail)
        return json.dumps({"logged": entry})
    elif action == "tail":
        try:
            n = int(n)
        except Exception:
            n = 20
        entries = _tail(n)
        return json.dumps({"count": len(entries), "entries": entries})
    else:
        return json.dumps({"error": "unknown action, use 'log' or 'tail'"})
