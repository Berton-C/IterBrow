"""Soul wonder: offer one kept idea back, rarely.

docs/milestones/M9_soul_wonder_ally.md section A2. Only when the person turned "wonder" on and is
not in quiet mode, an idea of theirs is open, no wonder offer card is waiting for an answer, and the
frequency dial's wait has passed since the last offer (whisper 24 h, occasional 4 h, chatty 1 h).
Then one short block names the idea offered longest ago, and the offer is recorded. Otherwise it
adds nothing. It never decides anything: Iter offers, the person takes, keeps or lets go.
"""
import os
import re
import sys
import time

DESCRIPTION = "Soul wonder: offer one kept idea back as an offer card, as rarely as the person's dial says"

ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
CODE_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
for _path in (CODE_ROOT, ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)

HOUR_MS = 3600 * 1000
WAIT = {"whisper": 24 * HOUR_MS, "occasional": 4 * HOUR_MS, "chatty": 1 * HOUR_MS}
_S = r'"((?:[^"\\]|\\.)*)"'
CARD_TOPIC = re.compile(r'^\(soul-card-topic %s %s\)$' % (_S, _S))
OFFERED = re.compile(r'^\(soul-wonder-offered %s %s (\d+)\)$' % (_S, _S))
LAST = re.compile(r'^\(soul-wonder-last %s (\d+)\)$' % _S)


def _outstanding(atoms, now):
    for key, text in atoms.items():
        if not key.startswith("state:soul_card_topic:"):
            continue
        match = CARD_TOPIC.match(text.strip())
        if not match or not match.group(2).startswith("wonder:"):
            continue
        card_id = key[len("state:soul_card_topic:"):]
        # Waiting until the person answers or dismisses it (the card stays in the sidebar).
        if "state:soul_choice:%s" % card_id in atoms:
            continue
        return True
    return False


def plan(atoms, person, frequency, now):
    """Pure: (block text, operations) or ("", []) for one cycle."""
    from iterbrow_runtime import soul_wonder_store as store
    open_ideas = store.ideas(atoms, person=person, status="open")
    if not open_ideas or _outstanding(atoms, now):
        return "", []
    offered = OFFERED.match(atoms.get("state:soul_wonder_offer:%s" % person, "").strip())
    if offered and now - int(offered.group(3)) < WAIT.get(frequency, WAIT["occasional"]):
        return "", []
    last = {}
    for key, text in atoms.items():
        if key.startswith("state:soul_wonder_last:"):
            match = LAST.match(text.strip())
            if match:
                last[store.unquote(match.group(1))] = int(match.group(2))
    idea = sorted(open_ideas, key=lambda i: (last.get(i["id"], -1), i["at"], i["id"]))[0]
    block = ("## Wonder\nOne kept idea you may offer back now, as an offer card with topic wonder:%s and "
             "choices take / keep / let_go: %s: %s" % (idea["id"], idea["app"], idea["idea"]))
    operations = [
        {"op": "upsert", "key": "state:soul_wonder_offer:%s" % person,
         "atom": "(soul-wonder-offered %s %s %d)" % (store.quote(person), store.quote(idea["id"]), now)},
        {"op": "upsert", "key": "state:soul_wonder_last:%s" % idea["id"],
         "atom": "(soul-wonder-last %s %d)" % (store.quote(idea["id"]), now)},
    ]
    return block, operations


def wonder_block():
    try:
        from iterbrow_runtime import soul_settings
        if not soul_settings.enabled("wonder") or soul_settings.mode() == "quiet":
            return ""
        person, frequency = soul_settings.person(), soul_settings.frequency()
        from iterbrow_runtime.cognitive_events import _call_atomspace
        atoms = _call_atomspace("read_atoms", prefix="state:soul_")["atoms"]
        block, operations = plan(atoms, person, frequency, int(time.time() * 1000))
        if not block:
            return ""
        _call_atomspace("transact", operations=operations, actor="iter", source="soul_wonder")
        return block
    except Exception as error:
        print("[soul_wonder] no offer this cycle: %s: %s" % (type(error).__name__, str(error)[:200]), file=sys.stderr)
        return ""


def transform(messages, tools):
    block = wonder_block()
    if not block:
        return messages, tools
    for message in reversed(messages):
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = message["content"] + "\n\n" + block
            return messages, tools
    return [{"role": "system", "content": block}] + list(messages), tools
