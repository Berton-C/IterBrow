"""Soul taste: fold the person's card answers into what the Soul has learned about them.

docs/milestones/M7_soul_personality.md sections A2 and D1. Every cycle, one read of the
state:soul_* atoms. For each recorded choice not yet folded (no soul-taste-seen marker):

- a pick on a card whose choices name Soul patterns revises two taste beliefs, NAL style:
  (soul-taste "<person>" <Picked> <Over> (stv f c) n) is positive evidence for the picked
  pole over each other pole and negative evidence for the reverse ordering
  (f = picks/n, c = n/(n+1), capped at 0.99 -- evidence horizon k=1, as NACE and the kb use);
- a dismissal counts toward (soul-dismissed "<person>" "<kind>" n);
- choices carrying museum ids cast the museum votes (keep the picked variant, reject the rest);
- then the seen marker, so each answer is folded exactly once.

The atoms are the record: this never reads the chat journal. It never touches keys outside
state:soul_taste*, state:soul_dismiss:* and state:soul_taste_seen:*, and it never gates,
filters or changes the prompt. With nothing new it costs one read and commits nothing.
"""
import importlib.util
import json
import os
import re
import sys

DESCRIPTION = "Soul taste: fold card answers into per-person taste beliefs (NAL) and cast museum votes"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _path in (CODE_ROOT, ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)

MAX_CONFIDENCE = 0.99
_S = r'"((?:[^"\\]|\\.)*)"'
CHOICE = re.compile(r'^\(soul-choice %s %s %s %s (\d+)\)$' % (_S, _S, _S, _S))
CARD = re.compile(r'^\(soul-card %s %s %s (\d+)\)$' % (_S, _S, _S))
CARD_CHOICE = re.compile(r'^\(soul-card-choice %s %s (\S+) %s\)$' % (_S, _S, _S))
TASTE = re.compile(r'^\(soul-taste %s (\S+) (\S+) \(stv ([0-9.]+) ([0-9.]+)\) (\d+)\)$' % _S)
DISMISS = re.compile(r'^\(soul-dismissed %s %s (\d+)\)$' % (_S, _S))


def _unquote(text):
    return json.loads('"%s"' % text)


def _quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def _fmt(value):
    return repr(round(float(value), 6))


def _call(method, **params):
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace(method, **params)


def _log(line):
    print("[soul_taste] " + line, file=sys.stderr)


def truth(picks, n):
    """(f, c) for `picks` positive out of `n` observations."""
    return (picks / n if n else 0.0), min(MAX_CONFIDENCE, n / (n + 1.0))


def taste_atom(person, picked, over, picks, n):
    f, c = truth(picks, n)
    return "(soul-taste %s %s %s (stv %s %s) %d)" % (_quote(person), picked, over, _fmt(f), _fmt(c), n)


def plan(atoms):
    """Pure: (operations, votes) for every unfolded choice in `atoms` ({key: atom} of state:soul_*).

    votes: [(museum_id, "keep"|"reject")] to cast after the transaction commits."""
    seen = {key[len("state:soul_taste_seen:"):] for key in atoms if key.startswith("state:soul_taste_seen:")}
    pending = []
    for key, atom in atoms.items():
        if not key.startswith("state:soul_choice:"):
            continue
        card_id = key[len("state:soul_choice:"):]
        if card_id in seen:
            continue
        match = CHOICE.match(atom.strip())
        if not match:
            pending.append((0, card_id, None))
            continue
        person, kind, _card, pick, at = (_unquote(match.group(1)), _unquote(match.group(2)),
                                          _unquote(match.group(3)), _unquote(match.group(4)), int(match.group(5)))
        pending.append((at, card_id, (person, kind, pick)))
    if not pending:
        return [], []

    # Current beliefs, updated in memory so several answers in one cycle compound.
    tastes = {}   # (person, picked, over) -> [picks, n]
    for key, atom in atoms.items():
        if key.startswith("state:soul_taste:"):
            match = TASTE.match(atom.strip())
            if match:
                n = int(match.group(6))
                tastes[(_unquote(match.group(1)), match.group(2), match.group(3))] = [round(float(match.group(4)) * n), n]
    dismissed = {}  # (person, kind) -> n
    for key, atom in atoms.items():
        if key.startswith("state:soul_dismiss:"):
            match = DISMISS.match(atom.strip())
            if match:
                dismissed[(_unquote(match.group(1)), _unquote(match.group(2)))] = int(match.group(3))

    touched_tastes, touched_dismissed, operations, votes = set(), set(), [], []
    for _at, card_id, choice in sorted(pending):
        offered = _offer(atoms, card_id)
        if choice is not None and offered is not None:
            person, kind, pick = choice
            if pick == "dismiss":
                dismissed[(person, kind)] = dismissed.get((person, kind), 0) + 1
                touched_dismissed.add((person, kind))
            elif pick in offered:
                picked_pattern, picked_museum = offered[pick]
                if picked_museum:
                    votes.append((picked_museum, "keep"))
                for other, (pattern, museum_id) in sorted(offered.items()):
                    if other == pick:
                        continue
                    if picked_pattern and pattern and pattern != picked_pattern:
                        for ordering, hit in (((person, picked_pattern, pattern), 1), ((person, pattern, picked_pattern), 0)):
                            belief = tastes.setdefault(ordering, [0, 0])
                            belief[0] += hit
                            belief[1] += 1
                            touched_tastes.add(ordering)
                    if museum_id:
                        votes.append((museum_id, "reject"))
        operations.append({"op": "upsert", "key": "state:soul_taste_seen:%s" % card_id,
                           "atom": "(soul-taste-seen %s)" % _quote(card_id)})
    for person, picked, over in sorted(touched_tastes):
        picks, n = tastes[(person, picked, over)]
        operations.append({"op": "upsert", "key": "state:soul_taste:%s:%s:%s" % (person, picked, over),
                           "atom": taste_atom(person, picked, over, picks, n)})
    for person, kind in sorted(touched_dismissed):
        operations.append({"op": "upsert", "key": "state:soul_dismiss:%s:%s" % (person, kind),
                           "atom": "(soul-dismissed %s %s %d)" % (_quote(person), _quote(kind), dismissed[(person, kind)])})
    return operations, votes


def _offer(atoms, card_id):
    """{choice id: (pattern or None, museum id or None)} for a card the card tool recorded, else None."""
    if "state:soul_card:%s" % card_id not in atoms:
        return None
    prefix = "state:soul_card_choice:%s:" % card_id
    offered = {}
    for key, atom in atoms.items():
        if not key.startswith(prefix):
            continue
        match = CARD_CHOICE.match(atom.strip())
        if not match:
            continue
        pattern = match.group(3)
        museum_id = _unquote(match.group(4))
        offered[_unquote(match.group(2))] = (None if pattern == "none" else pattern,
                                             None if museum_id in ("", "-") else museum_id)
    return offered


def _museum_vote():
    for base in (ROOT, CODE_ROOT):
        path = os.path.join(base, "tools", "museum_vote.py")
        if os.path.exists(path):
            tools_dir = os.path.dirname(path)
            if tools_dir not in sys.path:
                sys.path.insert(0, tools_dir)
            spec = importlib.util.spec_from_file_location("museum_vote_for_soul_taste", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    return None


def cast_votes(votes):
    if not votes:
        return
    try:
        voter = _museum_vote()
    except Exception as error:
        _log("museum votes skipped: %s: %s" % (type(error).__name__, error))
        return
    for museum_id, vote in votes:
        try:
            result = voter.run(museum_id, vote) if voter else "ERROR: museum_vote unavailable"
            if str(result).startswith("ERROR"):
                _log("vote %s on %s skipped: %s" % (vote, museum_id, result))
        except Exception as error:
            # The NAL side (a linked memory item) failed; the keep/reject itself still lands.
            _log("vote %s on %s: %s: %s; recording the vote only" % (vote, museum_id, type(error).__name__, error))
            try:
                sys.path.insert(0, os.path.join(ROOT, "tools"))
                import _component_museum
                if _component_museum.get(museum_id):
                    _component_museum.update_vote(museum_id, vote)
            except Exception as inner:
                _log("vote %s on %s not recorded: %s" % (vote, museum_id, inner))


def reduce_once():
    """One pass. Returns the number of choices folded (0 when there was nothing new)."""
    atoms = _call("read_atoms", prefix="state:soul_")["atoms"]
    operations, votes = plan(atoms)
    if not operations:
        return 0
    _call("transact", operations=operations, actor="iter", source="soul_taste")
    cast_votes(votes)
    return sum(1 for op in operations if op["key"].startswith("state:soul_taste_seen:"))


def transform(messages, tools):
    try:
        reduce_once()
    except Exception as error:
        _log("not folded this cycle: %s: %s" % (type(error).__name__, str(error)[:200]))
    return messages, tools
