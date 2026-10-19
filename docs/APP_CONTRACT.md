# The app contract

What every app in the person's apps folder (the vault) follows, so it works the first time, can be changed
safely, and keeps working. `new_app` creates a folder that already meets it. Spec:
`docs/milestones/M14_vault_and_foundry_loop.md`.

## The folder

- One folder per app: `vault/<id>/`, where `id` is lowercase letters, digits and dashes and starts with a letter.
- `index.html` is the entry. Assets use relative paths (`./app.js`, `img/logo.svg`); nothing outside the folder.
- No build step: what is in the folder is what runs. Plain HTML, CSS and JavaScript; a library may be a file in
  the folder or a pinned CDN URL.
- `README.md` says what the app does, what it stores, what network it uses, and which ideas it adopted from
  elsewhere (with their licenses).

## Ready

- `<body data-iter-ready="false">` in the markup; set `document.body.dataset.iterReady = 'true'` once the app
  is usable (after its data has loaded and its first render is done). Probes and people wait for it.
- An error during start-up leaves it `false` and shows a readable message in the page, never a blank screen.

## State

- Keep state in `localStorage` under keys that start `iter:<id>:` (the scaffold's `load`/`save` helpers do it),
  or through `window.iterApp` when the app needs the application contract (opened from the Apps menu).
- State survives a reload. Changing its shape reads the old shape too (or migrates it once).

## Proof: probe.json

- `probe.json` is `{"steps": [...], "assertions": [...]}` in `app_probe`'s grammar:
  steps `{kind: click|fill, selector, value?}`, assertions `{kind: text|value|count|visible, selector, expected}`.
- It passes on the fresh app, and it grows with every feature: steps that exercise the main action, assertions
  that would fail if that action broke.
- Run `app_probe(<id>)` (no assertions → probe.json) after every change and before saying the app works.
  Report what it checked.
- Selectors are stable ids (`#add`, `#list li`), not layout paths.

## Network

- Allowed, and named in the README (which service, what for). The app still loads and says so when offline.
- No secrets in the folder: a key the person must supply is asked for in the page and kept in `localStorage`.

## Changing an app

- Edit with `write_file`/`edit_file` under `vault/<id>/`: every change keeps the previous version, and
  `app_rollback(<id>)` (or Apps ▸ Undo) restores it.
- After a change: open it (`browser_open_app`), wait for the main element (`browser_wait_for`), run the probe,
  click the main action once yourself, then report.
