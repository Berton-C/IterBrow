"""Give an app the ally: install IterAlly (iter/sdk) into one of the person's apps.

docs/milestones/M10_ally_sdk.md section B. The app's own users then get the noticing and the
returned choice (cards, forks, a passing notice, the kernel's lens) with no IterBrow present. The
app's flourishing brief becomes its Soul, so it needs one first (the brief tool).

Foundry projects: a checkpointed source write (FoundryProjects.write_source with the current context
hash). Plain app folders: files written next to index.html, and nowhere else.
"""
import json
import os
import sys
from pathlib import Path

DESCRIPTION = """Install IterAlly into an app so its own users get the Soul's noticing and returned choice (fork cards, notices, the kernel's lens) without IterBrow: copies the SDK and kernel into the app and adds the include with the app's brief. The app needs a brief first. Idempotent. The SDK has no gate and never phones home."""

INCLUDE = '<script src="iter_ally.js"></script>'
SDK_FILES = ("iter_ally.js", "soul_kernel.json", "soul_kernel.js")
TOOLS_DIR = Path(__file__).resolve().parent
ROOT = os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd())
for _path in (str(TOOLS_DIR.parent), ROOT):  # ROOT ends up first; the code tree is the fallback
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _sdk_dir():
    for base in (Path(ROOT), TOOLS_DIR.parent):
        if all((base / "sdk" / name).is_file() for name in SDK_FILES):
            return base / "sdk"
    return None


def _person():
    try:
        from iterbrow_runtime import soul_settings
        return soul_settings.person()
    except Exception:
        return "guest"


def _js_string(value):
    return json.dumps(str(value), ensure_ascii=False).replace("</", "<\\/")


def snippet(brief):
    return ("%s\n<script>IterAlly.install({ brief: {for: %s, flourishing: %s}, person: \"guest\" });</script>\n"
            % (INCLUDE, _js_string(brief["for"]), _js_string(brief["flourishing"])))


def inject(html, brief):
    """The page with the include added just before the last </body>, or at the end."""
    block = snippet(brief)
    lower = html.lower()
    at = lower.rfind("</body>")
    if at < 0:
        return html + ("" if html.endswith("\n") or not html else "\n") + block
    return html[:at] + block + html[at:]


def run(app):
    from iterbrow_runtime import soul_briefs
    app = str(app or "").strip()
    root = soul_briefs.iter_root()
    project = soul_briefs._project_dir(root, app)
    plain = None if project else soul_briefs.app_folder(root, app)
    if not project and not plain:
        return "ERROR: no app named %r" % app
    brief = soul_briefs.read(app)
    if not brief:
        return "ERROR: give %s a brief first (brief tool)" % app
    sdk = _sdk_dir()
    if sdk is None:
        return "ERROR: the SDK files are missing from iter/sdk (run scripts/export_soul_kernel.py)"
    files = {name: (sdk / name).read_text(encoding="utf-8") for name in SDK_FILES}
    target = (project / "src") if project else plain
    page = target / "index.html"
    if not page.is_file():
        return "ERROR: %s has no %s" % (app, "src/index.html" if project else "index.html")
    html = page.read_text(encoding="utf-8")
    current = {name: (target / name).read_text(encoding="utf-8") if (target / name).is_file() else None for name in SDK_FILES}
    if INCLUDE in html and current == files:
        return "ALLY-SDK: already installed in %s" % app
    updates = {name: text for name, text in files.items() if current[name] != text}
    if INCLUDE not in html:
        updates["index.html"] = inject(html, brief)
    person = _person()
    if project:
        from iterbrow_runtime.foundry_projects import FoundryProjects
        projects = FoundryProjects(root)
        context = projects.inspect(app)
        projects.write_source(app, updates, context["source_context_hash"], directory="src",
                              provenance={"tool": "ally_sdk", "person": person})
    else:
        for name, text in updates.items():
            path = target / name
            if path.is_symlink():
                return "ERROR: %s/%s is a symlink" % (app, name)
            temporary = target / (".%s.%d.tmp" % (name, os.getpid()))
            temporary.write_text(text, encoding="utf-8")
            from iterbrow_runtime import vault
            vault.snapshot(path, "ally_sdk")  # M14-B1: undoable in a vault app; a no-op elsewhere
            os.replace(temporary, path)
    return "ALLY-SDK: %s in %s" % ("installed" if "index.html" in updates else "updated", app)
