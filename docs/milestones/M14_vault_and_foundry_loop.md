# Milestone 14 — The vault and the foundry loop: apps that live somewhere, and a way of building them

Status: **scoped 2026-10-19, not implemented.** Base: M6–M13. Tests: `tests/test_m14_*.py` and
`tests/e2e/test_m14_loop.py`; helpers in `tests/m14_support.py`. Every test starts `@pending("M14-xx")`;
remove the decorator as each passes. `M14_IMPLEMENTED` is keyed on `iter/iterbrow_runtime/vault.py` (A1,
the first file this milestone creates). Sections are independent except where noted; implement A→G, one
commit per section.

## Why

M12 gave Iter hands, M13 eyes. On 2026-10-19 Iter opened Map Station, waited for the button, clicked it
and reported what it hit — the first scored success of `browser_click` since September. What is still
missing is everything around that moment, in Berton's words: "I can ask IterBrow to build any app I can
imagine and it will research (look at github projects for ideas and inspiration), propose creative
innovative additions, confirm the plan, build the tab/app, test the tab/app ensuring it works, ask for
feedback when it reports the tab/app is built … apps that work the first time, can be iterated on, made
better, and keep working." Verified in code and in the 2026-10-12→19 transcript:

- **Apps have no home.** A plain app is a top-level folder of `iter/` — inside the git checkout, beside
  the agent's own code, invisible to the person in Finder, lost on a reinstall, and colliding with every
  `git pull` (Iter's Map Station work sat uncommitted for a week). Berton rejected both a git tool ("we
  don't want every copy of IterBrow pushing git commits") and a fixed `~/IterBrow Apps` folder.
- **The Foundry project layer is not the answer.** `apps/<id>/` projects (`foundry_projects.py`,
  `app_revision_manager.py`) are served only from an immutable bundle under `.runtime/app_revisions`
  after stage → validate → activate → Electron probation; `src/` is never shown; any `fetch(` or
  `https://` in a file fails validation (Map Station could not exist there); `history/` keeps full-text
  snapshots but nothing restores them; no tool creates a project. The submit/decide/execute workflow is
  retired (AGENTS.md). It stays as it is — untouched by this milestone — and the vault takes the plain-app
  model, which is what every working app uses today.
- **No undo.** `write_file` replaces; `edit_file` edits in place. One bad edit to a working app is a
  conversation to recover from, not a click.
- **No scaffold, no contract, no app-owned proof.** `app_probe` needs assertions typed by hand each time;
  nothing records what "working" means for an app, so nothing re-checks it after the next edit.
- **The loop is theatre-prone.** Oct 12–13: ~30 "I'm tracing… next I'll…" messages over a CRM headline
  before any page changed. The work was good once it landed; the messages were progress reports without
  progress. Nothing in the loop notices a `send` with no tool result since the last one.
- **Research is blind.** `websearch` has f≈0.36: DuckDuckGo's instant-answer API returns nothing for most
  queries and the cascade then raises ("all backends returned no results"), scored as a failure. There is
  no way to read a GitHub repository's files, only to find its name.
- **Every cycle waits ~5 s for nothing.** 49 transformations each run in their own fresh Python process
  (`invoke_dynamic` → `dynamic_worker`), ~0.09 s floor apiece plus 49 serialisations of the whole message
  list; on a cycle with nothing pending the stage costs 4.5–5 s before NACE's own work (courier and tracker
  commits, ~6.5 s after a tool call, which is NACE's and stays). The Soul, NACE, the courier and the
  tracker are not touched by this item — the same code runs, in one interpreter instead of 49.

Principles unchanged: nothing gates or vetoes Iter (a note is a note; `send` is never refused); only the
person's own locks and switches refuse anything; a feature that is off leaves no trace (no vault chosen →
no `.iter/`, no menu items beyond "Choose…", `vault/` paths refused with the reason); NACE's tracker,
courier and episodic memory are not changed (the M12-A3 guard test still pins them); the Soul is values,
not rules — the build loop *uses* its cards, it does not add rules to it; pattern text enters Python only
through the lens; pushes are the person's.

## Decisions taken in scoping (Berton, 2026-10-18/19)

- **D2 — the vault pattern** (Obsidian-style): the person chooses a folder; shipped apps are read-only
  examples copied in when the vault is first chosen (Arduino-style); file-recovery snapshots, not git.
  "Export/import" is the folder itself — copy it. Several vaults are allowed by switching; one is active.
- **D3 — plain-app model for the vault.** A vault app is a folder with `index.html` (plus `probe.json`,
  optional `brief.json`); it runs as an app tab with the app preload, straight from its folder, network
  allowed. The Foundry project layer and `crm` keep their existing paths.
- **D4 — one interpreter per cycle** (section F) is in scope because it changes no NACE semantics; the
  courier/tracker commit cost after a tool call is NACE's and is reported, not reduced.

## Test seams

`iter/iterbrow_runtime/vault.py` is pure over an explicit root and settings path (no Electron);
`bridge/vault_menu.js` exports `appsMenuTemplate(catalog, state, handlers)` (pure, so the menu shape is
tested in node); `iter/tools/_files.py` gains `roots()`; `iter/transformations/build_mode.py` exports
`active(messages)`, `BUILD_LOOP` and (in `build_watch.py`) `note(messages)` (pure); `iter/tools/github.py`
exports `parse_tree(json) → [(path, size)]` sorted, `raw_url(repo, path)`, `format_search(json) → [lines]`,
`valid_repo`, `valid_path`; `iter/tools/websearch.py` exports `parse_ddg_html(html)`; `vault.py` exports
`prune_plan(entries, now)`; `scripts/foundry_bench/bench.py` exports `score(record)` and `table(records)`;
the batch worker is `iter.py --invoke-batch <manifest> <result>` (F1) and is run directly by its test.
Tools run in a throwaway ITER_DIR with a throwaway vault (`m14_support.vault_root`), as M12/M13 do.

## Vocabulary

- *Vault*: the folder the person chose, `settings.vault` in `.runtime/settings.json` (absolute real path of
  an existing directory, no symlink). *Vault app*: `<vault>/<id>/index.html`, `id` matching
  `^[a-z][a-z0-9-]{0,62}$`, not a symlink, not `.iter`. `<vault>/.iter/` is IterBrow's own (snapshots,
  the examples marker) and is never an app and never written by the file tools.
- *Example*: a shipped plain app under `iter/` (`mapstation`, `nodequest`); `crm` is registered and is not
  an example. Examples run from `iter/` as today and are copied into the vault once (`.iter/examples.json`
  records which were copied, so a deleted copy is not recreated).
- *Catalog*: `local_apps.list_apps()` — vault apps (`kind: "vault"`) first, then Foundry projects, then plain
  apps of `iter/`; an id present in the vault hides a same-named plain app (never a Foundry project).
- *Snapshot*: the previous content of one file, saved before a file tool writes it. *Entry*: one line of
  `<vault>/.iter/snapshots/<app>/log.jsonl`. *Rollback*: restore the newest N entries, newest first.
- *Build*: the stretch of conversation in which Iter is making or changing a vault app; `build_mode`
  decides it from the messages (no state file).
- *Report*: Iter's `send` that says an app is built or changed; it carries the probe result.

## A. The vault

Files: `iter/iterbrow_runtime/vault.py` (new), `iter/iterbrow_runtime/local_apps.py`, `iter/tools/_files.py`,
`iter/tools/{read,write,edit}_file.py`, `list_files.py`, `grep_files.py`, `shell.py` (cwd may be in the
vault), `main.js`, `bridge/vault_menu.js` (new), `preload.js`, `renderer/index.html` + `toolbar.*` (Apps menu),
`iter/state_manifest.json` is unchanged (the vault is outside ITER_DIR).

- **A1 — `vault.py`.** `path(settings_path=None)` → the vault as a `Path` or `None` when unset/missing/
  not a directory/a symlink (never raises). `apps(root)` → `[{id, path, entry: "index.html", brief}]`
  sorted, skipping `.iter`, symlinks, bad ids and folders without `index.html`. `app_dir(id, root=None)`
  → the folder or `None`. `EXAMPLES = ("mapstation", "nodequest")`; `copy_examples(root, iter_dir)` copies
  each example folder not already in the vault and not in `.iter/examples.json`, records it there, returns
  the ids copied; it never overwrites and never copies `crm` or dot-files/`node_modules`. CLI: `python3 -m
  iterbrow_runtime.vault {path|apps|copy-examples|rollback <app> [n]|history <app>}` printing JSON (B uses
  rollback/history). `settings.vault` is read on every call (no env, no cache): the person can switch
  vaults while Iter runs.
- **A2 — the catalog.** `local_apps.list_apps()` adds vault apps with `kind: "vault"`, `path`, `entry`,
  `brief` (from `<app>/brief.json`, same shape as plain apps); vault first; a vault id hides a plain `iter/`
  app of the same id. `soul_briefs.read/write` and `ally_sdk` resolve a vault app before a plain one (a
  brief for `todo` lands in `<vault>/todo/brief.json`). The `apps` tool prints `todo (vault) file:///…`.
- **A3 — the file tools reach the vault.** `_files.roots()` → `[repo_root()] + [vault]` when set.
  `resolve()` accepts a real path inside any root; the spelling `vault/<rel>` (and bare `vault`) means
  `<vault>/<rel>`; `shown()` prints vault files as `vault/<rel>`. With no vault, `vault/...` is
  `REFUSED: no apps folder chosen yet (Apps ▸ Choose apps folder…)`. Writes under `<vault>/.iter` are
  `REFUSED:` like `.git`. `list_files("vault")` lists the apps as `vault/todo/` lines; `grep_files` and
  `read_file` work on `vault/todo/index.html`; `shell(cwd="vault/todo")` runs there. The M12 tests keep
  passing unchanged.
- **A4 — the Apps menu, in Electron.** `bridge/vault_menu.js` exports `appsMenuTemplate(catalog, state,
  handlers)` → an Electron menu template (plain objects): vault apps (label `id — for <brief.for>` when it
  has one), a separator, `Examples ▸` submenu with the shipped examples and the registered `crm`, a
  separator, `Choose apps folder…`, `Reveal apps folder` (only when a vault is set), `Recent ▸` (the last
  5 vaults from `settings.recentVaults`, only when there are others). `state = {vault, recentVaults,
  undoable}` (`undoable` = app ids with history, B4; `[]` until then); `handlers = {open(id), choose(),
  reveal(), switchTo(path), undo(id)}`. `main.js` uses it for `apps:menu`;
  `Choose apps folder…` is `dialog.showOpenDialog({properties: ['openDirectory', 'createDirectory']})`
  defaulting to `~/Documents`; choosing saves `settings.vault` (real path), pushes the previous one onto
  `recentVaults` (max 5, deduplicated), runs `copy-examples` once and logs `[vault] <path> (copied:
  mapstation, nodequest)` (or `(nothing to copy)`), then reopens the menu. No vault → the menu is
  `Examples ▸`, `Choose apps folder…` only. `openRegisteredApp(id)` opens a vault app before a plain
  one (`vaultAppDir(id)` mirrors `vault.app_dir`), as an app tab from its folder; `registeredAppForUrl`
  maps any URL under `<vault>/<id>/` back to `id` (session restore keeps the scope); `_insideAppDir` lets
  the tab move inside its folder. Choosing a vault while Iter runs needs no restart (A1).
- **A5 — Settings shows it.** The Settings panel shows the current vault path (read-only text, `Choose…`
  beside it calling the same handler) under a "Apps" heading; `settings:load` includes `vault` and
  `recentVaults`; `settings:save` never changes `vault` (only the chooser does).

Tests: `tests/test_m14_vault.py`.

## B. Snapshots and one-action rollback

Files: `iter/iterbrow_runtime/vault.py` (`snapshot`, `rollback`, `history`, `prune`), `iter/tools/_files.py`
(`before_write`), `write_file.py`, `edit_file.py`, `iter/tools/app_rollback.py` (new), `main.js` (Undo item).

- **B1 — snapshot before write.** `_files.before_write(real)`: when `real` is inside the vault and exists,
  `vault.snapshot(app, rel, reason)` copies its bytes to `<vault>/.iter/snapshots/<app>/<stamp>__<rel with
  "/" → "__">` (`stamp` = UTC `%Y%m%dT%H%M%S%fZ`) and appends `{"at", "file": rel, "bytes", "stored":
  <name>, "reason": "write_file"|"edit_file"}` to `.iter/snapshots/<app>/log.jsonl`; a new file (nothing to
  save) appends `{"at", "file", "bytes": null, "stored": null, "reason"}` so rollback can delete it.
  `write_file` and `edit_file` call it just before their atomic replace; `WROTE`/`EDITED` lines are unchanged
  except `(unchanged)` writes take no snapshot. Outside the vault nothing happens (no trace).
- **B2 — rollback.** `vault.rollback(app, steps=1)` restores the newest `steps` entries newest-first (a
  `stored: null` entry deletes the file it created), removes those entries from the log, and returns
  `[{file, restored_from | deleted}]`. Tool `app_rollback(app, steps="1")` → `ROLLED BACK todo: index.html
  (to 2026-10-19T05:12:03Z)` one line per file, or `NOTHING TO ROLL BACK: todo`; `steps="0"` prints the
  history: `todo: 3 changes` then `2026-10-19T05:12:03Z edit_file index.html (1,204 bytes)` newest first,
  at most 20. Unknown app → input error; no vault → refused (A3's message).
- **B3 — pruning.** After every snapshot, `vault.prune(app)` keeps the newest 50 entries plus, among older
  ones, the newest entry of each UTC day for 30 days; everything else (file and line) goes. Pure over the
  log (`prune_plan(entries, now)` returns what to keep) so it is tested with synthetic timestamps.
- **B4 — the person's undo.** The Apps menu gains `Undo Iter's last change to <id>` when the displayed tab
  is a vault app with history (`vault history` via CLI, cached per menu open); it runs `vault rollback
  <id> 1`, reloads the tab, logs `[vault] rolled back <id>: index.html`. Nothing is shown when there is
  no history.

Tests: `tests/test_m14_snapshots.py`.

## C. The scaffold and the app's own proof

Files: `iter/tools/new_app.py` (new), `iter/tools/app_probe.py`, `iter/iterbrow_runtime/vault.py`
(`scaffold`), `iter/transformations/build_watch.py` (new), `docs/APP_CONTRACT.md` (new).

- **C1 — `new_app(id, title, from_example="")`.** Creates `<vault>/<id>/` with `index.html`, `probe.json`
  and `README.md` from the scaffold; `from_example="mapstation"` copies that example instead (every file
  except dot-files) and writes a `probe.json` only when the example has none. Returns `NEW-APP vault/todo:
  index.html, probe.json, README.md — open it with browser_open_app(todo)`. Existing folder → input error
  `EXISTS: vault/todo`; bad id → input error; no vault → refused. The scaffold `index.html`: `<!doctype
  html>`, `<title>`, `<body data-iter-ready="false">`, an `<h1 id="title">`, a `<main id="app">`, a `<script>`
  that sets `document.body.dataset.iterReady = 'true'` after init and keeps state in `localStorage` under
  `iter:<id>:`; no external resources by default (the contract allows them). `probe.json` is `{"steps":
  [], "assertions": [{"kind": "text", "selector": "#title", "expected": "<title>"}]}`.
- **C2 — the app contract** (`docs/APP_CONTRACT.md`, ≤ 60 lines, linked from AGENTS.md): one folder,
  `index.html` entry, relative asset paths, `data-iter-ready` true once usable, a `probe.json` that passes
  on the fresh app and is kept current with every feature (steps that exercise the main action, assertions
  that would fail if it broke), state in `localStorage` under `iter:<id>:` or through `window.iterApp`,
  network allowed and named in the README, no build step (what is in the folder runs).
- **C3 — `app_probe` uses the app's own spec.** `app_probe(app, steps="", assertions="", timeout="")`: with
  no `assertions`, the app's `probe.json` (vault app or plain app) is the spec and the first line reads
  `PROBE todo (probe.json): 3 passed, 0 failed`; with neither, input error `no assertions given and
  vault/todo/probe.json is missing`. A malformed `probe.json` is an input error naming the file.
- **C4 — build_watch: changed since the last probe.** `iter/transformations/build_watch.py`: pure
  `note(messages)` → the one line `[build: vault/todo changed since its last probe — app_probe(todo)
  before reporting]` when, since the last `app_probe` result for that app (or ever), a `write_file`/
  `edit_file`/`new_app` result touched `vault/<app>/` and the newest assistant turn is a `send`; else
  `None`. `transform` appends the note to the system prompt. It never removes a tool and never alters the
  `send`. At most one note per app per request.

Tests: `tests/test_m14_scaffold.py`.

## D. The foundry loop: research, propose, confirm, build, prove, report

Files: `iter/transformations/build_mode.py` (new), `iter/AGENTS.md`, `README.md`.

- **D1 — build mode.** `build_mode.active(messages)` is true when the last 16 messages contain a
  `new_app`/`app_probe`/`app_rollback` call, a file-tool call whose `path` starts with `vault/`, or a user
  message containing `build`, `make me`, `app`, or `vault` (case-insensitive, whole words). When active,
  `transform` appends `BUILD_LOOP` (a constant, ≤ 1,100 characters) to the system prompt; when not, nothing.
- **D2 — the loop text.** `BUILD_LOOP` says, in this order: (1) *Research*: for anything beyond a tweak,
  one `websearch(source="github")` and at most two `github` reads for ideas, then stop researching.
  (2) *Propose*: one `card(kind="fork")` with two or three shapes — the ask as stated, the ask plus one
  creative addition you can name, and the smallest version — with a `pattern` on each choice; wait for
  the pick (`[choice card=… pick=…]`). Skip the card when the person already said how, or asked for a
  tweak. (3) *Build*: `new_app`, then `write_file`/`edit_file` under `vault/<id>/`, keeping `probe.json`
  current. (4) *Prove*: `browser_open_app`, `browser_wait_for` the main element, `app_probe(<id>)`, and one
  real `browser_click` on the main action; fix until the probe passes; never report a probe you did not
  run. (5) *Report*: one `send` with what works, what the probe checked, and what you would add next;
  then a `card(kind="offer")` with up to three next steps. One rule throughout: a message to the person
  is either a question you need answered or a report of a tool result since your last message; never a
  progress note. When the person says who the app is for, `brief` it (and offer `ally_sdk`).
- **D3 — guidance.** AGENTS.md's `## Building and changing code` gains two lines (section still ≤ 1,800
  characters, inside the injected 6,000): where apps live (`vault/<id>/`, `new_app`, `app_rollback`,
  `probe.json`) and the no-progress-notes rule; the Tool Inventory and README tables gain `new_app`,
  `app_rollback`, `github`; the `app_probe`, `apps`, `websearch` rows are regenerated from their
  descriptions; the README gets a short "Where apps live" paragraph (the vault, examples, undo).
- **D4 — never hidden, never capped.** `new_app`, `app_rollback`, `github` join `dynamic_tool_budget.
  PROTECTED_TOOLS` and `iter.py PROTECTED_TOOL_NAMES`; `tests/test_tool_cap.py` still passes (84 of 96).

Tests: `tests/test_m14_loop.py` (unit) and `tests/e2e/test_m14_loop.py` (the loop with a fake model:
`new_app` → `edit_file` → the build_watch note appears on the next request → `app_probe` fails honestly
with no bridge → `app_rollback` restores the file → `send`).

## E. Research: GitHub and a web search that works

Files: `iter/tools/github.py` (new), `iter/tools/websearch.py`.

- **E1 — `github(action, repo="", path="", query="", max_results="8")`.** Unauthenticated, `urllib`,
  10 s timeout, User-Agent `IterBrow`. `action="search"`: `GET https://api.github.com/search/repositories?
  q=<query>&sort=stars&per_page=<n>` → one line per repo `owner/name ★stars — description (license)
  https://github.com/owner/name` (`(no description)`, `(no license)` when missing; `format_search`). `action="tree"`: `GET https://api.github.com/repos/<repo>/git/trees/HEAD?
  recursive=1` → `path  size` lines (blobs only, sorted, at most 400, truncated note), via pure `parse_tree`.
  `action="read"`: `GET https://raw.githubusercontent.com/<repo>/HEAD/<path>` → the file with `read_file`'s
  numbered format and header `owner/name:path (lines 1–N of M)`; `raw_url(repo, path)` is pure. `repo` must
  match `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`, `path` must not contain `..`; a 403 with `X-RateLimit-Remaining:
  0` returns `RATE-LIMITED: GitHub allows 10 searches a minute without a token; try again at <reset time>`
  as a *failed* result; 404 is an input error. Results are capped at `READ_WIRE_CHARS` (24,000) with a
  truncation line; `github` joins `iter.py READ_TOOLS`. The description tells Iter it is for ideas and
  patterns, to name what it adopted in the app's README, and to respect licenses.
- **E2 — `websearch` finds things.** A new first backend for `source="auto"`: DuckDuckGo HTML (`GET
  https://html.duckduckgo.com/html/?q=<q>`, then `https://lite.duckduckgo.com/lite/?q=<q>` when the first
  returns no results) with a browser User-Agent, parsed by pure `parse_ddg_html(html)` → `[{title, url,
  snippet}]` (the `uddg=` redirect parameter unwrapped). The instant-answer, Wikipedia and HN backends
  remain after it. When every backend answered and none had results, the tool returns `NO RESULTS: <query>`
  as a success (the tool worked); it fails only when no backend could be reached. `source="github"` is
  unchanged. `DESCRIPTION` is rewritten to describe the real backends (the README row regenerates).

Tests: `tests/test_m14_research.py` (parsers over fixtures in `tests/fixtures/m14/`; one live test per tool
that skips without network).

## F. One interpreter per cycle

Files: `iter/iter.py` (`dynamic_worker`, `apply_transformation`, new `invoke_dynamic_batch`).

- **F1 — batch worker.** `apply_transformation` runs every transformation of the cycle in **one** worker
  process (`invoke_dynamic_batch(paths, messages, tools)`): `iter.py --invoke-batch <manifest.json>
  <result.json>` where the manifest is `{"payload": <payload file, args = [messages, tools]>, "items":
  [{"path", "timeout"}]}` and the result is `{"pid", "items": [{"path", "ok", "result"|"error", "seconds"}],
  "result": [messages, tools]}`. The worker imports each module as
  `invoke_dynamic` does (its own directory first on `sys.path`, `_dynamic_<stem>` module name, fresh
  import each cycle), runs `transform(messages, tools)` under a per-transformation `signal.setitimer`
  timeout equal to the per-process timeout it has today, records `{ok, result | error, seconds}` per
  path, and passes the *returned* messages/tools to the next transformation exactly as the loop does now
  (a timeout reads `TIMEOUT after <n>s in <stem>.transform`). A transformation that raises or times out is
  reported in the same `[RUNTIME ERROR in …]` form and
  `TRANSFORMATION_HEALTH_FAILURE` keeps its rule; the batch continues with the previous messages. If the
  worker itself dies (no result file, killed, non-zero exit) the loop falls back to today's per-process
  path for the rest of that cycle and logs `[transformations] batch worker failed (…); per-process this
  cycle`. `timings` keeps one entry per transformation (its own seconds) plus `_batch_seconds`.
- **F2 — tools unchanged.** Tool calls (`run`) keep their own process per call (isolation per call is
  worth it there). Descriptions (`__description__`, `__tool_metadata__`) are unchanged.
- **F3 — measured.** `[request preparation]` gains `"transformations_processes": 1|N`. Acceptance on the
  e2e harness: a cycle with nothing pending runs all transformations in one process (the fake
  transformation records `os.getpid()`), and `transformations_seconds` sums to under half of the
  per-process figure for the same harness (recorded in the implementation notes, both numbers).

Tests: `tests/test_m14_cycle.py` (unit: a batch of three fake transformations, one that raises, one that
sleeps past its timeout) and the e2e assertion in `tests/e2e/test_m14_loop.py`.

## G. The five-app benchmark and the docs

Files: `scripts/foundry_bench/bench.py` (new), `scripts/foundry_bench/briefs.json` (new),
`docs/bench/README.md` (new), `docs/soul/SOUL_IN_THE_FOUNDRY.md`, this file.

- **G1 — the briefs.** `briefs.json`: five asks, each `{id, ask, iterate, probe: {steps, assertions},
  main_action: <selector>}` (`iterate` is the second-phase ask, G2): `todo` (add/complete/delete, persists across reload), `pomodoro` (25/5 timer with start/
  pause/reset, shows remaining time), `notes` (markdown notes list with live preview, persists), `convert`
  (unit converter: length, weight, temperature, both directions), `kanban` (three columns, add card, move
  card between columns, persists). Every probe validates with `validateProbeSpec` and has ≥ 3 assertions.
- **G2 — `bench.py`.** Against a running IterBrow (the person starts it; the script needs
  `ITER_DIR`): for each brief (or `--app <id>`), writes the ask into the chat inbox the way the sidebar
  does, waits (≤ 20 min) for Iter's report (`send` mentioning the app id), then runs the brief's probe
  over the bridge socket (`probe` method, the real page), counts from `experience.json`/the request log:
  `cycles`, `tool_calls`, `sends_before_report`, `sends_without_tool_result`, `cards`, `probe_passed`
  (the brief's probe, first try), `elapsed_s`; a second phase sends one iteration ask per brief ("add a
  dark mode toggle that persists") and re-runs the probe (`iteration_kept_working`). Writes
  `docs/bench/<date>-<model>.json` and prints a table (`table(records)`: header `app …`, one row per
  record with yes/no columns, the model named). Pure `score(record)` → `{built, kept, theatre}`
  (built = probe passed first try; kept = still passes after the iteration; theatre = sends without a
  tool result in between). `--baseline` tags the record so a pre-M14 run (Berton's, with the briefs
  only) sits beside the post-M14 run.
- **G3 — docs.** `docs/bench/README.md` says how to run it and what the numbers mean;
  `SOUL_IN_THE_FOUNDRY.md`'s M14 entry is updated; this file gets the implementation notes at the top,
  including the two F3 numbers and the first benchmark table if Berton ran one.

Tests: `tests/test_m14_bench.py` (the briefs validate; `score`; the report table).

## Commit plan

A `M14-A: the vault`, B `M14-B: snapshots and rollback`, C `M14-C: new_app, the contract, build_watch`,
D `M14-D: the foundry loop`, E `M14-E: github tool, websearch that works`, F `M14-F: one interpreter per
cycle`, G `M14-G: the benchmark and docs`. Each commit removes its `@pending` decorators and keeps the
whole suite green. Don't push.

## Not in this milestone

Any gate on `send` or on a build; changes to `nace_courier`, `tool_reliability_tracker`, episodic memory
or the Soul kernel; the Foundry project layer (`apps/`, revisions, probation) — unchanged, still listed;
a GitHub token setting (unauthenticated limits are enough for ideas; add later if they bite); git in the
vault; syncing vaults between machines (copy the folder); per-app Settings UI beyond the chooser and undo.
