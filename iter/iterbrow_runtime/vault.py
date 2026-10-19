"""The vault: the folder the person chose for their apps (docs/milestones/M14_vault_and_foundry_loop.md A1).

The person picks it from Apps ▸ Choose apps folder… (main.js saves the real path as `settings.vault` in
<ITER_DIR>/.runtime/settings.json). It is read on every call — no env variable, no cache — so switching
vaults while Iter runs needs no restart. A vault app is <vault>/<id>/index.html: a real folder (never a
symlink), `id` matching the app-id rule, never `.iter`. <vault>/.iter/ is IterBrow's own (snapshots, the
examples marker) and is never an app.

No vault chosen → every function answers None/[] and nothing is written anywhere (a feature that is off
leaves no trace).

CLI (main.js and the tests): python3 -m iterbrow_runtime.vault {path|apps|copy-examples}, JSON on stdout.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

APP_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")  # the same rule as local_apps.py and foundry_projects.py
EXAMPLES = ("mapstation", "nodequest")  # shipped plain apps copied into a new vault; crm is registered, not an example
OWN = ".iter"
COPY_SKIP = {"node_modules", "__pycache__"}


def iter_root():
    return Path(os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd()))


def settings_file(root=None):
    return Path(root or iter_root()) / ".runtime" / "settings.json"


def path(settings_path=None):
    """The vault as a real Path, or None when unset, missing, not a directory or a symlink. Never raises."""
    try:
        data = json.loads(Path(settings_path or settings_file()).read_text(encoding="utf-8"))
        raw = data.get("vault") if isinstance(data, dict) else None
        if not isinstance(raw, str) or not raw.strip():
            return None
        candidate = Path(os.path.expanduser(raw.strip()))
        if not candidate.is_absolute() or candidate.is_symlink() or not candidate.is_dir():
            return None
        return Path(os.path.realpath(candidate))
    except (OSError, ValueError, TypeError):
        return None


def _json(file):
    try:
        if file.is_symlink():
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _brief(raw):
    if isinstance(raw, dict) and isinstance(raw.get("for"), str) and raw["for"].strip() \
            and isinstance(raw.get("flourishing"), str) and raw["flourishing"].strip():
        return {"for": raw["for"].strip(), "flourishing": raw["flourishing"].strip()}
    return None


def _is_app(folder):
    name = folder.name
    if name == OWN or name.startswith(".") or not APP_ID.match(name):
        return False
    if folder.is_symlink() or not folder.is_dir():
        return False
    entry = folder / "index.html"
    return entry.is_file() and not entry.is_symlink()


def apps(root):
    """[{id, path, entry, brief}] for every app folder in the vault `root`, sorted by id."""
    if root is None:
        return []
    root = Path(root)
    try:
        folders = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return []
    return [{"id": f.name, "path": str(f), "entry": "index.html", "brief": _brief(_json(f / "brief.json"))}
            for f in folders if _is_app(f)]


def app_dir(app_id, root=None):
    """<vault>/<app_id> when it is an app folder, else None (also None with no vault)."""
    root = Path(root) if root is not None else path()
    if root is None or not isinstance(app_id, str):
        return None
    folder = root / app_id
    return folder if _is_app(folder) else None


def _marker(root):
    data = _json(Path(root) / OWN / "examples.json") or {}
    copied = data.get("copied") if isinstance(data.get("copied"), list) else []
    seen = data.get("seen") if isinstance(data.get("seen"), list) else []
    return {"copied": [str(x) for x in copied], "seen": [str(x) for x in seen]}


def _write_json(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(".%s.%d.tmp" % (file.name, os.getpid()))
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, file)


def _ignore(directory, names):
    """copytree filter: no dot-files, no node_modules/__pycache__, no symlinks (nothing that leads out)."""
    return [n for n in names if n.startswith(".") or n in COPY_SKIP or os.path.islink(os.path.join(directory, n))]


def copy_folder(source, target):
    """Copy an app folder (everything except dot-files, node_modules, __pycache__, symlinks) atomically."""
    target = Path(target)
    staging = target.with_name(".%s.copy-%d" % (target.name, os.getpid()))
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging, ignore=_ignore)
    os.replace(staging, target)


def copy_examples(root, iter_dir):
    """Copy each shipped example not already in the vault (and never copied before); return the ids copied.

    Never overwrites, never copies crm; a copy the person deleted is not recreated, and neither is an
    example whose name they already used for their own app."""
    root, iter_dir = Path(root), Path(iter_dir)
    marker = _marker(root)
    known = set(marker["copied"]) | set(marker["seen"])
    copied = []
    changed = False
    for name in EXAMPLES:
        source = iter_dir / name
        if name in known or source.is_symlink() or not (source / "index.html").is_file():
            continue
        if (root / name).exists() or (root / name).is_symlink():
            marker["seen"].append(name)
            changed = True
            continue
        copy_folder(source, root / name)
        marker["copied"].append(name)
        copied.append(name)
        changed = True
    if changed:
        _write_json(root / OWN / "examples.json", marker)
    return copied


def _cli(argv):
    command = argv[0] if argv else "path"
    vault = path()
    if command == "path":
        return str(vault) if vault else None
    if command == "apps":
        return apps(vault)
    if command == "copy-examples":
        return copy_examples(vault, iter_root()) if vault else []
    raise SystemExit("usage: python3 -m iterbrow_runtime.vault {path|apps|copy-examples}")


if __name__ == "__main__":
    sys.stdout.write(json.dumps(_cli(sys.argv[1:])) + "\n")
