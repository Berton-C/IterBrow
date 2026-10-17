"""Wonder jar atoms (docs/milestones/M9_soul_wonder_ally.md section A).

(soul-wonder "<person>" "<app>" "<id>" "<idea>" "<status>" <at-ms>) at state:soul_wonder:<id>,
status open | taken | let-go. Shared by the `wonder` tool and transformations/soul_wonder.py.
"""
import json
import re

_S = r'"((?:[^"\\]|\\.)*)"'
WONDER = re.compile(r'^\(soul-wonder %s %s %s %s %s (\d+)\)$' % (_S, _S, _S, _S, _S))
STATUSES = ("open", "taken", "let-go")


def quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def unquote(text):
    return json.loads('"%s"' % text)


def atom(person, app, wid, idea, status, at):
    return "(soul-wonder %s %s %s %s %s %d)" % (quote(person), quote(app), quote(wid), quote(idea), quote(status), int(at))


def parse(text):
    match = WONDER.match(str(text or "").strip())
    if not match:
        return None
    person, app, wid, idea, status = (unquote(match.group(i)) for i in range(1, 6))
    return {"person": person, "app": app, "id": wid, "idea": idea, "status": status, "at": int(match.group(6))}


def ideas(atoms, person=None, status=None, app=None):
    """Parsed ideas from {key: atom}, oldest first."""
    out = []
    for key, text in atoms.items():
        if not key.startswith("state:soul_wonder:"):
            continue
        item = parse(text)
        if not item:
            continue
        if person is not None and item["person"] != person:
            continue
        if status is not None and item["status"] != status:
            continue
        if app is not None and item["app"] != app:
            continue
        out.append(item)
    out.sort(key=lambda i: (i["at"], i["id"]))
    return out
