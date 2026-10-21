"""Start a new app in the person's vault (docs/milestones/M14_vault_and_foundry_loop.md C1).

The scaffold follows docs/APP_CONTRACT.md: one folder, index.html, data-iter-ready once usable, state in
localStorage under iter:<id>:, and a probe.json that passes on the fresh app. from_example copies an
existing app (a shipped example like mapstation, or another app in the vault) instead.
"""
import html
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402

DESCRIPTION = (
    "Start an app in the person's apps folder: vault/<id>/ with index.html, probe.json, README.md per "
    'docs/APP_CONTRACT.md; the probe fails until the placeholder is replaced. id: lowercase, digits, '
    'dashes. from_example: copy an app instead. Then edit and browser_open_app(<id>).'
)

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light dark; --fg: #1d1b22; --bg: #faf9fc; --muted: #6b6578; --accent: #6b4fd8; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --fg: #ece9f3; --bg: #17151c; --muted: #9a93a8; }} }}
    body {{ margin: 0; font: 15px/1.5 -apple-system, system-ui, sans-serif; color: var(--fg); background: var(--bg); }}
    header, main {{ max-width: 720px; margin: 0 auto; padding: 16px; }}
    h1 {{ margin: 24px 0 8px; font-size: 24px; }}
  </style>
</head>
<body data-iter-ready="false">
  <header><h1 id="title">{title}</h1></header>
  <main id="app"><p id="placeholder">Nothing here yet — this app is still being built.</p></main>
  <script>
    // App contract (docs/APP_CONTRACT.md): state lives in localStorage under this prefix.
    const STORE = 'iter:{id}:';
    const load = (key, fallback) => {{ try {{ const v = localStorage.getItem(STORE + key); return v === null ? fallback : JSON.parse(v); }} catch (_) {{ return fallback; }} }};
    const save = (key, value) => {{ try {{ localStorage.setItem(STORE + key, JSON.stringify(value)); }} catch (_) {{}} }};

    function init() {{
      // Build the app here, replacing the placeholder (the probe insists it is gone).
      document.body.dataset.iterReady = 'true';
    }}
    init();
  </script>
</body>
</html>
"""

README = """# {title}

An app in the person's IterBrow apps folder (`vault/{id}/`). Follows docs/APP_CONTRACT.md.

- Entry: `index.html` (no build step: what is in this folder runs).
- State: `localStorage` keys starting `iter:{id}:`.
- Proof: `probe.json` — run it with `app_probe({id})` after every change; keep it current with each feature.
- Network: none.
- Ideas adopted from elsewhere (with their licenses): none yet.
"""


def _probe(title):
    # The second assertion fails on the bare scaffold on purpose: a probe that passes before anything is
    # built would let an empty app be reported as working (the converter, 2026-10-19).
    return {"steps": [], "assertions": [{"kind": "text", "selector": "#title", "expected": title},
                                        {"kind": "count", "selector": "#placeholder", "expected": 0}]}


def _example_probe():
    # A copied example's own markup is unknown here: prove only that it loads; the builder makes it specific.
    return {"steps": [], "assertions": [{"kind": "count", "selector": "body", "expected": 1}]}


def _write_new(folder, files):
    """Create `folder` with `files` ({name: text}) atomically: a staging folder renamed into place."""
    staging = folder.with_name(".%s.new-%d" % (folder.name, os.getpid()))
    staging.mkdir()
    for name, text in files.items():
        (staging / name).write_text(text, encoding="utf-8")
    os.replace(staging, folder)


def run(id, title="", from_example=""):
    vault = _files.vault_dir()
    if vault is None:
        return _files.refused(_files.NO_VAULT)
    from iterbrow_runtime import vault as store, soul_briefs
    app_id = str(id or "").strip()
    title = " ".join(str(title or "").split()) or app_id
    if not store.APP_ID.match(app_id):
        return _files.input_error("ERROR: id %r must be lowercase letters, digits and dashes, starting with a letter" % app_id)
    folder = vault / app_id
    if folder.exists() or folder.is_symlink():
        return _files.input_error("EXISTS: vault/%s" % app_id)
    try:  # M15-C5: a new app starts with no build ledger (state:build:<id>:* removed)
        from iterbrow_runtime import build_ledger
        build_ledger.forget([app_id])
    except Exception:
        pass
    example = str(from_example or "").strip()
    if example:
        # The shipped example first (a fresh copy even after the vault's own copy was changed), then a vault app.
        source = (soul_briefs._plain_dir(store.iter_root(), example) if store.APP_ID.match(example) else None) \
            or store.app_dir(example, vault)
        if source is None:
            return _files.input_error("ERROR: no app named %r to copy (shipped examples: %s)" % (example, ", ".join(store.EXAMPLES)))
        store.copy_folder(source, folder)
        if not (folder / "probe.json").is_file():
            (folder / "probe.json").write_text(json.dumps(_example_probe(), indent=2) + "\n", encoding="utf-8")
        names = sorted(p.name for p in folder.iterdir())
        shown = ", ".join(names[:8]) + (", …" if len(names) > 8 else "")
        return "NEW-APP vault/%s: %s — copied from %s; open it with browser_open_app(%s)" % (app_id, shown, example, app_id)
    _write_new(folder, {
        "index.html": PAGE.format(title=html.escape(title), id=app_id),
        "probe.json": json.dumps(_probe(title), indent=2) + "\n",
        "README.md": README.format(title=title, id=app_id),
    })
    return "NEW-APP vault/%s: index.html, probe.json, README.md — open it with browser_open_app(%s)" % (app_id, app_id)
