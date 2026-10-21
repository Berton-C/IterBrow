"""The wonder jar: keep ideas cut from a build, so one can come back later.

docs/milestones/M9_soul_wonder_ally.md section A. Not a backlog: no due dates, no priorities.
transformations/soul_wonder.py offers one back, rarely (the frequency dial), as an offer card.
"""
import os
import sys
import time
import uuid
from pathlib import Path

DESCRIPTION = (
    "The wonder jar: keep a 'what if' cut from a build. action add (app, idea under 200 chars), list (app"
    ' optional), take or let_go (id). Not a backlog.'
)

MAX_IDEA = 200
TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _call(method, **params):
    from iterbrow_runtime.cognitive_events import _call_atomspace
    return _call_atomspace(method, **params)


def _person():
    from iterbrow_runtime import soul_settings
    return soul_settings.person()


def run(action, app=None, idea=None, id=None):
    from iterbrow_runtime import soul_briefs, soul_wonder_store as store
    action = str(action or "").strip().lower().replace("-", "_")
    person = _person()
    if action == "add":
        app = str(app or "").strip()
        root = soul_briefs.iter_root()
        if not (soul_briefs._project_dir(root, app) or soul_briefs._plain_dir(root, app)):
            return "ERROR: no app named %r" % app
        idea = " ".join(str(idea or "").split())
        if not idea:
            return "ERROR: an idea needs some words"
        if len(idea) > MAX_IDEA:
            return "ERROR: keep an idea under %d characters" % MAX_IDEA
        wid = "wonder-%s" % uuid.uuid4().hex[:8]
        _call("transact", actor="iter", source="wonder", operations=[{
            "op": "upsert", "key": "state:soul_wonder:%s" % wid,
            "atom": store.atom(person, app, wid, idea, "open", time.time() * 1000)}])
        return "WONDER-KEPT: %s" % wid
    if action == "list":
        atoms = _call("read_atoms", prefix="state:soul_wonder:")["atoms"]
        items = store.ideas(atoms, person=person, status="open", app=(str(app).strip() if app else None))
        return "\n".join(["Wonder jar (%d open)" % len(items)] + ["- %s %s: %s" % (i["id"], i["app"], i["idea"]) for i in items])
    if action in ("take", "let_go"):
        wid = str(id or "").strip()
        key = "state:soul_wonder:%s" % wid
        item = store.parse(_call("read_atoms", prefix=key)["atoms"].get(key)) if wid else None
        if not item or item["person"] != person:
            return "ERROR: no idea %s" % wid
        status = "taken" if action == "take" else "let-go"
        _call("transact", actor="iter", source="wonder", operations=[{
            "op": "upsert", "key": key, "atom": store.atom(person, item["app"], wid, item["idea"], status, item["at"])}])
        return "WONDER-%s: %s" % ("TAKEN" if action == "take" else "LET-GO", wid)
    return "ERROR: action must be add, list, take or let_go"
