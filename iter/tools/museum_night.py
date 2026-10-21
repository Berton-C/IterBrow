"""Museum night: walk the kept, rejected and unvoted variants, and why.

docs/milestones/M8_soul_presence.md section C. Reads the component museum and the soul atoms;
each voted piece is joined to the fork card that decided it (which pattern that pole protected,
whether it was picked), and the walk ends with what the Soul has learned of the person's leans.
Reading only: no museum record, memory item or atom changes.
"""
import json
import os
import re
import sys
from pathlib import Path

DESCRIPTION = (
    "List the museum's kept, rejected and unvoted variants with the fork card that decided each and the "
    "person's leans. app filters; limit caps. Reads only."
)

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT, str(TOOLS_DIR)):  # tools dir for _component_museum
    if _path not in sys.path:
        sys.path.insert(0, _path)

_S = r'"((?:[^"\\]|\\.)*)"'
CARD_CHOICE = re.compile(r'^\(soul-card-choice %s %s (\S+) %s\)$' % (_S, _S, _S))
CHOICE = re.compile(r'^\(soul-choice %s %s %s %s (\d+)\)$' % (_S, _S, _S, _S))


def _unquote(text):
    return json.loads('"%s"' % text)


def pieces(limit=12, app=None):
    """Latest record per museum id, newest first (the log is append-only; votes append)."""
    import _component_museum as museum
    latest, order = {}, []
    for record in museum._load_all():
        comp_id = record.get("id")
        if not comp_id:
            continue
        if comp_id not in latest:
            order.append(comp_id)
        latest[comp_id] = record
    out = [latest[comp_id] for comp_id in reversed(order)]
    if app:
        needle = str(app).lower()
        out = [r for r in out if needle in str(r.get("label", "")).lower() or needle in str(r.get("url", "")).lower()]
    return out[:max(1, int(limit))]


def forks_by_museum_id(atoms):
    """{museum id: (card id, pattern or None, picked: bool)} from soul-card-choice + soul-choice atoms."""
    picks = {}
    for key, atom in atoms.items():
        if key.startswith("state:soul_choice:"):
            match = CHOICE.match(atom.strip())
            if match:
                picks[_unquote(match.group(3))] = _unquote(match.group(4))
    out = {}
    for key, atom in atoms.items():
        if not key.startswith("state:soul_card_choice:"):
            continue
        match = CARD_CHOICE.match(atom.strip())
        if not match:
            continue
        card_id, choice_id, pattern, museum_id = (_unquote(match.group(1)), _unquote(match.group(2)),
                                                  match.group(3), _unquote(match.group(4)))
        if museum_id in ("", "-") or card_id not in picks:
            continue
        out[museum_id] = (card_id, None if pattern == "none" else pattern, picks[card_id] == choice_id)
    return out


def run(app=None, limit=12):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return "ERROR: limit must be a number"
    entries = pieces(limit, app)
    try:
        from iterbrow_runtime import soul_lens, soul_settings
        from iterbrow_runtime.cognitive_events import _call_atomspace
        atoms = _call_atomspace("read_atoms", prefix="state:soul_")["atoms"]
        leans = soul_lens.taste_line(soul_settings.person(), atoms=atoms)
    except Exception:
        atoms, leans = {}, ""
    forks = forks_by_museum_id(atoms)

    def line(record, with_fork):
        text = "- %s %s (%s, %s)" % (record.get("id"), record.get("label", "untitled"), record.get("source", "?"), record.get("ts", "?"))
        fork = forks.get(record.get("id")) if with_fork else None
        if fork:
            card_id, pattern, picked = fork
            text += " — fork %s: %s%s" % (card_id, (pattern + ", ") if pattern else "", "picked" if picked else "passed over")
        return text

    groups = {"keep": [], "reject": [], None: []}
    for record in entries:
        groups.get(record.get("vote"), groups[None]).append(record)
    lines = ["Museum night (%d pieces)" % len(entries), "Kept:"]
    lines += [line(r, True) for r in groups["keep"]] or ["- (none)"]
    lines.append("Rejected:")
    lines += [line(r, True) for r in groups["reject"]] or ["- (none)"]
    lines.append("Unvoted:")
    lines += [line(r, False) for r in groups[None]] or ["- (none)"]
    lines.append("Leans: " + (leans or "none yet"))
    return "\n".join(lines)
