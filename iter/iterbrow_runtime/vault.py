"""The vault: the folder the person chose for their apps (docs/milestones/M14_vault_and_foundry_loop.md A1).

The person picks it from Apps ▸ Choose apps folder… (main.js saves the real path as `settings.vault` in
<ITER_DIR>/.runtime/settings.json). It is read on every call — no env variable, no cache — so switching
vaults while Iter runs needs no restart. A vault app is <vault>/<id>/index.html: a real folder (never a
symlink), `id` matching the app-id rule, never `.iter`. <vault>/.iter/ is IterBrow's own (snapshots, the
examples marker) and is never an app.

No vault chosen → every function answers None/[] and nothing is written anywhere (a feature that is off
leaves no trace).

Snapshots (M14-B): before a file tool writes a file inside a vault app, the previous bytes are saved to
<vault>/.iter/snapshots/<app>/<stamp>__<rel with / as __> and a line is appended to that folder's log.jsonl
({"at", "file", "bytes", "stored", "reason"}; a new file logs bytes/stored null so rollback can delete it).
rollback() restores the newest entries newest-first; prune() keeps the newest 50 plus one per earlier UTC
day for 30 days.

CLI (main.js and the tests): python3 -m iterbrow_runtime.vault
{path|apps|copy-examples|history <app>|rollback <app> [n]}, JSON on stdout.
"""
import datetime as dt
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


# ---- Snapshots, rollback, pruning (M14-B) ---------------------------------------------------------------
KEEP_NEWEST = 50
KEEP_DAYS = 30


def _utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _store(root, app_id):
    return Path(root) / OWN / "snapshots" / app_id


def locate(real, root=None):
    """(vault, app_id, rel) for a path inside a vault app folder, else None. `rel` uses '/'."""
    root = Path(root) if root is not None else path()
    if root is None:
        return None
    real = Path(os.path.realpath(real))
    try:
        parts = real.relative_to(root).parts
    except ValueError:
        return None
    if len(parts) < 2 or parts[0] == OWN or parts[0].startswith(".") or not APP_ID.match(parts[0]):
        return None
    return root, parts[0], "/".join(parts[1:])


def entries(root, app_id):
    """The app's snapshot log, oldest first ([] when none or unreadable lines)."""
    log = _store(root, app_id) / "log.jsonl"
    out = []
    try:
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and isinstance(item.get("file"), str) and isinstance(item.get("at"), str):
                out.append(item)
    except OSError:
        return []
    return out


def _write_log(root, app_id, items):
    store = _store(root, app_id)
    store.mkdir(parents=True, exist_ok=True)
    temporary = store / (".log.jsonl.%d.tmp" % os.getpid())
    temporary.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in items), encoding="utf-8")
    os.replace(temporary, store / "log.jsonl")


def snapshot(real, reason, root=None, now=None):
    """Save the current bytes of `real` (a file in a vault app) before a tool replaces it. Returns the entry,
    or None when `real` is not inside a vault app (then nothing at all is written)."""
    where = locate(real, root)
    if where is None:
        return None
    vault, app_id, rel = where
    now = now or _utcnow()
    entry = {"at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "file": rel, "bytes": None, "stored": None, "reason": str(reason)}
    store = _store(vault, app_id)
    store.mkdir(parents=True, exist_ok=True)
    real = Path(real)
    if real.is_file():
        data = real.read_bytes()
        stored = "%s__%s" % (now.strftime("%Y%m%dT%H%M%S%fZ"), rel.replace("/", "__"))
        temporary = store / (".%s.tmp" % stored)
        temporary.write_bytes(data)
        os.replace(temporary, store / stored)
        entry.update(bytes=len(data), stored=stored)
    with open(store / "log.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    prune(app_id, vault, now=now)
    return entry


def _parse(at):
    try:
        return dt.datetime.strptime(at, "%Y-%m-%dT%H:%M:%S.%fZ")
    except (TypeError, ValueError):
        return None


def prune_plan(items, now):
    """The entries to keep (original order): the newest 50, plus — for each UTC day of the last 30 that the
    newest 50 do not already cover — that day's newest entry."""
    if len(items) <= KEEP_NEWEST:
        return list(items)
    keep = set(range(len(items) - KEEP_NEWEST, len(items)))
    covered = {items[i]["at"][:10] for i in keep}
    cutoff = (now.date() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    newest_of_day = {}
    for index in range(len(items) - KEEP_NEWEST):
        day = items[index]["at"][:10]
        if day >= cutoff and day not in covered:
            if day not in newest_of_day or items[index]["at"] >= items[newest_of_day[day]]["at"]:
                newest_of_day[day] = index
    keep.update(newest_of_day.values())
    return [items[i] for i in sorted(keep)]


def prune(app_id, root=None, now=None):
    """Apply prune_plan to the app's log and delete the stored files of dropped entries."""
    root = Path(root) if root is not None else path()
    if root is None:
        return 0
    items = entries(root, app_id)
    keep = prune_plan(items, now or _utcnow())
    if len(keep) == len(items):
        return 0
    kept = {item.get("stored") for item in keep}
    for item in items:
        stored = item.get("stored")
        if stored and stored not in kept:
            try:
                (_store(root, app_id) / stored).unlink()
            except OSError:
                pass
    _write_log(root, app_id, keep)
    return len(items) - len(keep)


def _second(at):
    parsed = _parse(at)
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ") if parsed else at


def history(app_id, root=None):
    """The app's changes, newest first."""
    root = Path(root) if root is not None else path()
    return list(reversed(entries(root, app_id))) if root is not None else []


def rollback(app_id, steps=1, root=None):
    """Undo the newest `steps` changes, newest first: restore each saved file, delete each file a change
    created. Consumed entries leave the log. Returns [{file, restored_from} | {file, deleted: True}]."""
    root = Path(root) if root is not None else path()
    if root is None or steps < 1:
        return []
    items = entries(root, app_id)
    if not items:
        return []
    take, rest = items[-steps:][::-1], items[:-steps] if steps < len(items) else []
    folder = root / app_id
    done = []
    for item in take:
        target = folder / item["file"]
        if not locate(target, root) or locate(target, root)[1] != app_id:
            continue  # a log line that points outside the app is never followed
        stored = item.get("stored")
        if stored:
            source = _store(root, app_id) / stored
            if not source.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(".%s.rollback-%d" % (target.name, os.getpid()))
            temporary.write_bytes(source.read_bytes())
            os.replace(temporary, target)
            source.unlink()
            done.append({"file": item["file"], "restored_from": _second(item["at"])})
        else:
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            done.append({"file": item["file"], "deleted": True})
    _write_log(root, app_id, rest)
    return done


def _cli(argv):
    command = argv[0] if argv else "path"
    vault = path()
    if command == "path":
        return str(vault) if vault else None
    if command == "apps":
        return apps(vault)
    if command == "copy-examples":
        return copy_examples(vault, iter_root()) if vault else []
    if command in ("history", "rollback") and len(argv) >= 2 and APP_ID.match(argv[1]):
        if command == "history":
            return history(argv[1], vault)
        return rollback(argv[1], int(argv[2]) if len(argv) > 2 else 1, vault)
    raise SystemExit("usage: python3 -m iterbrow_runtime.vault {path|apps|copy-examples|history <app>|rollback <app> [n]}")


if __name__ == "__main__":
    sys.stdout.write(json.dumps(_cli(sys.argv[1:])) + "\n")
