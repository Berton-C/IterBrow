"""task_state -- explicit phase tracking, so a completion claim (in a
`send`) can be checked against what phase the work was actually last
recorded at, instead of only trusting the model's own claim in the moment.

Ported from ClarityOmega/soul/task_state.metta's phase-atom concept. Call
this explicitly whenever you start, progress, or finish a distinct piece of
work -- especially right before claiming something is done in a send.
Cheap: one appended file line per call, plain text (no MeTTa engine
dependency -- pymetta is not installed on this machine, see
tools/_metta_gate.py's docstring), consistent with how nace_beliefs.metta
and other state files here are already read/written directly.

Phases (expected order, not enforced -- honesty over rigidity):
  planning   -- deciding what to build/do
  building   -- actively doing it
  verifying  -- checking the result actually exists/works
  complete   -- verified and done

WHY THIS EXISTS (real incident, 2026-09-14, episode 36): a completion claim
("the founder toolkit tab already exists") was sent before the tab had
actually been built -- caught by the user, not by the system. This tool
plus transformations/completion_claim_guard.py exist so that gap is at
least flagged by the system itself next time, not solely dependent on
remembering to self-check in the moment.
"""
import os
import re
import time

DESCRIPTION = "Record or query a task's current phase (planning/building/verifying/complete) -- call this before claiming something is done, run(action='set', label=..., phase=...) or run(action='get'|'list')"

PATH = "task_state.metta"
_VALID_PHASES = ("planning", "building", "verifying", "complete")
_LINE_RE = re.compile(r'\(task-phase "([^"]*)" ([a-z]+)(?: "([^"]*)")?\)')


def _timestamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _read_lines():
    try:
        with open(PATH, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except Exception:
        return []


def run(action="get", label="", phase="", note=""):
    action = str(action).strip().lower()

    if action == "set":
        phase_norm = str(phase).strip().lower()
        if phase_norm not in _VALID_PHASES:
            return "error: phase must be one of %s" % (_VALID_PHASES,)
        if not label:
            return "error: label is required"
        label_safe = str(label).replace('"', "'")[:120]
        note_safe = str(note).replace('"', "'")[:200]
        line = '(task-phase "%s" %s "%s") ;; %s\n' % (label_safe, phase_norm, note_safe, _timestamp())
        try:
            with open(PATH, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            return "error writing task_state.metta: %s" % e
        return "recorded: %s -> %s" % (label_safe, phase_norm)

    elif action == "get":
        lines = _read_lines()
        for line in reversed(lines):
            m = _LINE_RE.search(line)
            if m and (not label or m.group(1) == label):
                return "%s -> %s (%s)" % (m.group(1), m.group(2), m.group(3) or "")
        return "no phase recorded" + (" for %r" % label if label else "")

    elif action == "list":
        lines = _read_lines()
        latest = {}
        for line in lines:
            m = _LINE_RE.search(line)
            if m:
                latest[m.group(1)] = m.group(2)
        if not latest:
            return "no tasks recorded"
        return "\n".join("%s: %s" % (k, v) for k, v in latest.items())

    else:
        return "error: action must be 'set', 'get', or 'list'"
