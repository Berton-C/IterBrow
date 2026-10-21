"""The soul-absent walk: what in an app is technically correct and dead.

docs/milestones/M8_soul_presence.md section B. Iter walks the app as the person its brief names
(or as a first-time user when there is no brief) and names the moments that work but carry no
life, each tied to one of the nine kernel patterns. The gap text for each pattern is read from
the kernel atoms through the lens, never written here. The walk changes nothing in the app; it
records one soul-critique atom so the dashboard can count it honestly.
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

DESCRIPTION = (
    'Report a soul-absent walk of an app: 1-8 moments {where, what, pattern} that are correct and dead, '
    "as the brief's person would meet them; each is shown with its pattern's gap signature. Changes "
    'nothing.'
)

MAX_MOMENTS = 8
TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _clean(text):
    return " ".join(str(text or "").split())


def _moments(raw):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None, "moments must be a list of {where, what, pattern}"
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_MOMENTS:
        return None, "give 1 to %d moments" % MAX_MOMENTS
    out = []
    for item in raw:
        if not isinstance(item, dict):
            return None, "each moment is {where, what, pattern}"
        moment = {key: _clean(item.get(key)) for key in ("where", "what", "pattern")}
        if not all(moment.values()):
            return None, "each moment needs where, what and pattern"
        out.append(moment)
    return out, None


def _person():
    try:
        from iterbrow_runtime import soul_settings
        return soul_settings.person()
    except Exception:
        return "guest"


def run(app, moments):
    from iterbrow_runtime import soul_briefs, soul_lens
    app = str(app or "").strip()
    root = soul_briefs.iter_root()
    if not (soul_briefs._project_dir(root, app) or soul_briefs._plain_dir(root, app)):
        return "ERROR: no app named %r" % app
    parsed, error = _moments(moments)
    if error:
        return "ERROR: " + error
    try:
        known = soul_lens.patterns()
        gaps = soul_lens.facet("gap")
    except Exception as failure:
        return "ERROR: the Soul lens is unavailable (%s: %s)" % (type(failure).__name__, str(failure)[:160])
    unknown = sorted({m["pattern"] for m in parsed if m["pattern"] not in known})
    if unknown:
        return "ERROR: unknown pattern %s (the nine: %s)" % (", ".join(unknown), ", ".join(known))
    brief = soul_briefs.read(app)
    walked_as = ("as: %s" % _clean(brief["for"]).rstrip(".")) if brief else "no brief; walked as a first-time user"
    person = _person()
    recorded = True
    try:
        from iterbrow_runtime.cognitive_events import _call_atomspace
        _call_atomspace("transact", actor="iter", source="soul_absent_test", operations=[{
            "op": "upsert", "key": "state:soul_critique:%s" % uuid.uuid4().hex[:12],
            "atom": "(soul-critique %s %s %d %d)" % (json.dumps(app), json.dumps(person), len(parsed), int(time.time() * 1000))}])
    except Exception:
        recorded = False
    lines = ["Soul-absent walk of %s (%s)%s" % (app, walked_as, "" if recorded else " [unrecorded]")]
    for index, moment in enumerate(parsed, 1):
        lines.append("%d. %s — %s" % (index, moment["where"], moment["what"]))
        lines.append("   gap (%s): %s" % (moment["pattern"], gaps.get(moment["pattern"], "")))
    lines.append("Nothing was changed.")
    return "\n".join(lines)
