"""Flourishing briefs: two lines per app -- who it is for, what flourishing looks like for them.

docs/milestones/M7_soul_personality.md section C. A Foundry project keeps its brief in
blueprint.json as `flourishing_brief` (written through FoundryProjects.revise_blueprint, so it
is a checkpointed change with provenance); a plain app directory under ITER_DIR (one holding an
index.html, e.g. crm or music) keeps it in <app>/brief.json. Reading never writes.
"""
import json
import os
import re
import time
from pathlib import Path

MAX_LINE = 200
MAX_PROMPT_LINES = 8
APP_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,62}$")


def iter_root():
    return Path(os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd()))


def _clean(text):
    return " ".join(str(text or "").split())


def _plain_dir(root, app):
    """<root>/<app> when it is a real (non-symlink) directory holding an index.html."""
    if not APP_NAME.match(app) or app == "apps":
        return None
    path = root / app
    if path.is_symlink() or not path.is_dir() or not (path / "index.html").is_file():
        return None
    return path


def _project_dir(root, app):
    path = root / "apps" / app
    if not APP_NAME.match(app) or path.is_symlink() or not (path / "blueprint.json").is_file():
        return None
    return path


def _valid(brief):
    return (isinstance(brief, dict) and isinstance(brief.get("for"), str) and brief["for"].strip()
            and isinstance(brief.get("flourishing"), str) and brief["flourishing"].strip())


def read(app, root=None):
    """The brief dict for `app`, or None. Foundry projects win over a same-named plain dir."""
    root = Path(root) if root else iter_root()
    project = _project_dir(root, app)
    try:
        if project:
            brief = json.loads((project / "blueprint.json").read_text(encoding="utf-8")).get("flourishing_brief")
            return brief if _valid(brief) else None
        plain = _plain_dir(root, app)
        if plain and (plain / "brief.json").is_file() and not (plain / "brief.json").is_symlink():
            brief = json.loads((plain / "brief.json").read_text(encoding="utf-8"))
            return brief if _valid(brief) else None
    except (OSError, ValueError, AttributeError):
        return None
    return None


def line(app, brief):
    return "%s: for %s. Flourishing: %s." % (app, _clean(brief["for"]).rstrip("."), _clean(brief["flourishing"]).rstrip("."))


def all_briefs(root=None):
    """[(app, brief)] for every app with a brief, sorted by app id."""
    root = Path(root) if root else iter_root()
    names = set()
    apps = root / "apps"
    if apps.is_dir() and not apps.is_symlink():
        names.update(p.name for p in apps.iterdir() if p.is_dir())
    names.update(p.name for p in root.iterdir() if p.is_dir() and (p / "index.html").is_file())
    out = []
    for name in sorted(names):
        brief = read(name, root)
        if brief:
            out.append((name, brief))
    return out


def write(app, for_whom, flourishing, person, root=None):
    """Save a brief. Returns "BRIEF-SAVED: <app>" or "ERROR: ..."."""
    root = Path(root) if root else iter_root()
    for_whom, flourishing = _clean(for_whom), _clean(flourishing)
    if not for_whom or not flourishing:
        return "ERROR: give both lines or neither"
    if len(for_whom) > MAX_LINE or len(flourishing) > MAX_LINE:
        return "ERROR: keep each brief line under %d characters" % MAX_LINE
    brief = {"for": for_whom, "flourishing": flourishing, "by": person, "at": int(time.time() * 1000)}
    if _project_dir(root, app):
        from iterbrow_runtime.foundry_projects import FoundryProjects
        projects = FoundryProjects(root)
        context = projects.inspect(app)
        blueprint = dict(context["blueprint"], flourishing_brief=brief)
        projects.revise_blueprint(app, blueprint, context["source_context_hash"],
                                  provenance={"tool": "brief", "person": person})
        return "BRIEF-SAVED: %s" % app
    plain = _plain_dir(root, app)
    if plain:
        target = plain / "brief.json"
        if target.is_symlink():
            return "ERROR: %s/brief.json is a symlink" % app
        temporary = plain / (".brief.json.%d.tmp" % os.getpid())
        temporary.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, target)
        return "BRIEF-SAVED: %s" % app
    return "ERROR: no app named %r (a Foundry project under apps/ or a folder with an index.html)" % app
