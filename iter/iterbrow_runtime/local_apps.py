"""Every local app, in one catalog (docs/milestones/M10_ally_sdk.md C1; the vault: M14-A2).

Vault apps (<vault>/<id>/index.html, iterbrow_runtime/vault.py) come first, kind "vault"; a vault id hides
a same-named plain app of ITER_DIR, never a Foundry project (the project keeps its id).

A Foundry project is a directory under apps/ holding app.json; a plain app is a top-level directory
of ITER_DIR holding an index.html (crm, mapstation, nodequest ...). Never symlinks, never apps/
itself, never dot-directories or node_modules. The Apps button (main.js, via
`python3 -m iterbrow_runtime.local_apps`), session restore and the `apps` tool all read this list.
"""
import json
import os
import re
import sys
from pathlib import Path

APP_ID = re.compile(r"^[a-z][a-z0-9-]{0,62}$")  # the same rule as foundry_projects.py (M12-C2)
SKIP = {"apps", "node_modules"}


def iter_root():
    return Path(os.path.realpath(os.environ.get("ITER_DIR") or os.getcwd()))


def _json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _brief(raw):
    if isinstance(raw, dict) and isinstance(raw.get("for"), str) and raw["for"].strip() \
            and isinstance(raw.get("flourishing"), str) and raw["flourishing"].strip():
        return {"for": raw["for"].strip(), "flourishing": raw["flourishing"].strip()}
    return None


def list_apps(root=None):
    """[{id, kind, path, entry, brief}]: vault apps sorted by id, then the rest sorted by id."""
    root = Path(root) if root else iter_root()
    apps = {}
    projects = root / "apps"
    if projects.is_dir() and not projects.is_symlink():
        for path in sorted(projects.iterdir()):
            if path.is_symlink() or not path.is_dir() or not APP_ID.match(path.name):
                continue
            manifest = _json(path / "app.json")
            if manifest is None:
                continue
            blueprint = _json(path / "blueprint.json") or {}
            entry = str(manifest.get("entrypoint") or "index.html")
            source = str(manifest.get("source_dir") or "src")
            apps[path.name] = {"id": path.name, "kind": "foundry", "path": str(path), "entry": "%s/%s" % (source, entry),
                               "brief": _brief(blueprint.get("flourishing_brief"))}
    for path in sorted(root.iterdir()) if root.is_dir() else []:
        name = path.name
        if name in SKIP or name.startswith(".") or name in apps or path.is_symlink() or not path.is_dir():
            continue
        if not APP_ID.match(name) or not (path / "index.html").is_file():
            continue
        apps[name] = {"id": name, "kind": "plain", "path": str(path), "entry": "index.html",
                      "brief": _brief(_json(path / "brief.json"))}
    from iterbrow_runtime import vault as vault_store
    vault = [dict(app, kind="vault") for app in vault_store.apps(vault_store.path(vault_store.settings_file(root)))
             if not (apps.get(app["id"]) or {}).get("kind") == "foundry"]
    for app in vault:
        apps.pop(app["id"], None)
    return vault + [apps[name] for name in sorted(apps)]


def entry_url(app):
    return Path(app["path"], app["entry"]).resolve().as_uri()


if __name__ == "__main__":
    sys.stdout.write(json.dumps(list_apps()) + "\n")
