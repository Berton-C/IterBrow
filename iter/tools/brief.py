"""The flourishing brief of an app: who it is for, and what flourishing looks like for them.

docs/milestones/M7_soul_personality.md section C. Storage lives in iterbrow_runtime/soul_briefs.py.
"""
import os
import sys
from pathlib import Path

DESCRIPTION = """Read or set an app's flourishing brief: two lines, who it is for (for_whom) and what flourishing looks like for them (flourishing). Give both to save (a checkpointed change for Foundry projects; brief.json for folders like crm), neither to read. When a change you're making contradicts a brief, say so once as a brief card (continue / revise / drop); never block."""

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _person():
    try:
        from iterbrow_runtime import soul_settings
        return soul_settings.person()
    except Exception:
        return "guest"


def run(app, for_whom=None, flourishing=None):
    from iterbrow_runtime import soul_briefs
    app = str(app or "").strip()
    given = [bool(str(value or "").strip()) for value in (for_whom, flourishing)]
    if any(given) and not all(given):
        return "ERROR: give both lines or neither"
    if all(given):
        try:
            return soul_briefs.write(app, for_whom, flourishing, _person())
        except Exception as error:
            return "ERROR: brief not saved (%s: %s)" % (type(error).__name__, str(error)[:200])
    brief = soul_briefs.read(app)
    if brief is None:
        if soul_briefs._project_dir(soul_briefs.iter_root(), app) or soul_briefs._plain_dir(soul_briefs.iter_root(), app):
            return "BRIEF-NONE: %s" % app
        return "ERROR: no app named %r" % app
    return soul_briefs.line(app, brief)
