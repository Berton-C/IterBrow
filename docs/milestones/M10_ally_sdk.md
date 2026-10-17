# Milestone 10 — The app inherits the ally; focus, not clutter

Status: **scoped, tests written, implementation pending.** Roadmap: `docs/soul/SOUL_IN_THE_FOUNDRY.md`
(the roadmap's M11, the last Soul milestone of this series) plus one browser-track fix Berton asked for.
Base: M6–M9. Tests: `tests/test_m10_*.py`, `tests/e2e/test_m10_loop.py`; helpers in `tests/m10_support.py`.
Every test starts `@pending("M10-xx")`; remove the decorator as each passes. `M10_IMPLEMENTED` is keyed
on `iter/sdk/iter_ally.js`.

## Why

Everything the Soul does so far happens inside IterBrow. The apps Iter builds leave it: NodeQuest,
Little Orbit, the CRM run as plain pages. This milestone gives those apps a small, self-contained SDK
so their own users get the same noticing and the same returned choice — a fork card, a felt line, the
kernel's lens — with no IterBrow present and no server: a static page, optionally the app owner's own
model key, and a calibration record the app keeps for itself. The app's flourishing brief is its Soul.
And the everyday browser sense Berton asked for: every local app (Foundry projects and plain folders
like mapstation and nodequest, which today can only be reached by typing a file URL) is one click away
under an Apps button, opens as a real app tab with the margin, and the Dashboards / PWQ / CRM / Apps
buttons focus a tab that is already open instead of opening another.

Principles unchanged: nothing gates, pauses or vetoes (the SDK has no way to block an app; a card only
returns a pick); pattern text reaches JavaScript only from the kernel atoms through the lens (the SDK's
kernel file is generated, never hand-written); a feature that is off leaves no trace (an app without the
SDK is untouched; the SDK never phones home); honest surfaces.

## Vocabulary

- *SDK*: `iter/sdk/iter_ally.js` (one file, no dependencies, classic script that sets `window.IterAlly`;
  CommonJS export too so node tests can load it) and `iter/sdk/soul_kernel.json`.
- *Kernel JSON*: `{"generated_from": "seeds/soul_kernel.metta", "patterns": [..nine, seed order..],
  "facets": {<pattern>: {description, flourishing, captured, signal, felt, moat, anti, proxy, gap}},
  "pairs": [[a, b], ...], "tension_vectors": {<vector>: [patterns]}}`, produced by
  `scripts/export_soul_kernel.py` through `soul_lens` (the service's `soul` view), committed, and checked
  by a test against a fresh export.
- *Calibration*: the app's own record of picks, `localStorage["iter-ally.calibration"]`, a JSON array of
  `{at, kind, topic, pick, person}`; exportable as `iter_ally_calibration.json`.

---

## A. The SDK

**M10-A1 — Install and the lens.** `IterAlly.install({brief, person, model, kernel})`:
- `brief` `{for, flourishing}` (strings; both required, each ≤ 200 chars, else the install throws
  `IterAlly: a brief needs "for" and "flourishing"`), `person` (identifier, default `"guest"`),
  `model` optional `{baseUrl, apiKey, model}`, `kernel` optional (the parsed kernel JSON; when absent the
  SDK fetches `soul_kernel.json` next to itself, resolved from its own `<script src>`).
- After install: `IterAlly.patterns()` (nine, seed order), `IterAlly.facet(pattern, name)`,
  `IterAlly.gap(pattern)`, `IterAlly.pairs()`, `IterAlly.paraconsistent(a, b)` (order-free), and
  `IterAlly.brief()`; all read from the kernel data, never from literals in the SDK.
- `IterAlly.install` returns a promise that resolves once the kernel is loaded; calling anything that
  needs it before then throws `IterAlly: not installed yet`.

**M10-A2 — Cards.** `IterAlly.card({kind, title, body, choices, topic})` → `Promise<pick>` (`"dismiss"`
on the ×). Same rules as IterBrow cards: kind one of fork / brief / read / offer / note; 1–3 choices
(`{id, label, hint?, pattern?}` or labels, ids default a / b / c; `pattern` must be one of the nine);
rendered into `#iter-ally-root` (fixed bottom-right, inline styles only, one root node) with
`.iter-ally-card`, `.iter-ally-title`, `.iter-ally-body`, `button.iter-ally-choice[data-choice]`,
`button.iter-ally-dismiss`; one card at a time (a second call while one is open queues it). Every pick,
dismiss included, is appended to the calibration with `at` (ms), `kind`, `topic` (or null), `pick`,
`person`. `IterAlly.fork({title, body, a: {label, pattern}, b: {label, pattern}, topic})` is a card of
kind fork whose two patterns must be a declared pair (else it throws `IterAlly: <a> and <b> are not a
declared pair`); its body gets one trailing line, `Both can be true at once; this is yours to choose.`
`IterAlly.notice(text)` shows a felt-style line (`.iter-ally-notice`, ✦) for a few seconds and records
nothing.

**M10-A3 — Calibration.** `IterAlly.calibration()` → the array (survives reloads: localStorage, wrapped
in try/catch so a blocked storage still lets cards work, in memory only); `IterAlly.forget()` clears it;
`IterAlly.exportCalibration()` → a `Blob` download named `iter_ally_calibration.json` containing
`{"app": <document.title>, "person", "brief", "picks": [...]}` (the test checks the generated object via
`IterAlly.calibrationExport()`, which returns it without downloading).

**M10-A4 — The model, optional.** `IterAlly.ask(text)` POSTs to `<baseUrl>/chat/completions` with the
app owner's key, `model`, and messages `[system: brief + the lens (patterns with description and gap,
the same prose `soul_lens.lens_text` renders), user: text]`, and resolves with the reply text. With no
`model` configured it rejects with `IterAlly: no model configured` and makes no network request at all.
Nothing else in the SDK touches the network.

**M10-A5 — Kernel export.** `scripts/export_soul_kernel.py` writes `iter/sdk/soul_kernel.json` from the
running service through `soul_lens` (`facet` for each of the nine facets, `declared_pairs`,
`tension_vectors`); `--check` exits non-zero when the committed file differs. The committed JSON is
byte-identical to a fresh export (sorted keys, 2-space indent, trailing newline) and holds no
pattern text that is not in the seed.

---

## B. Installing it into an app

**M10-B1 — `ally_sdk` tool.** `ally_sdk.run(app)`: for a Foundry project, writes `src/iter_ally.js`,
`src/soul_kernel.json` through `FoundryProjects.write_source` with the current context hash (provenance
`{"tool": "ally_sdk", "person": <person>}`) and injects the include into `src/index.html`; for a plain
app dir (as `brief` resolves them), writes the two files next to `index.html` and injects into it. The
injection goes just before `</body>` (or at the end when there is none):
```html
<script src="iter_ally.js"></script>
<script>IterAlly.install({ brief: {for: "...", flourishing: "..."}, person: "guest" });</script>
```
with the brief taken from the app's brief (`BRIEF-NONE` → `ERROR: give <app> a brief first (brief
tool)`). Idempotent: a second run returns `ALLY-SDK: already installed in <app>` and changes nothing;
first run returns `ALLY-SDK: installed in <app>`. Never writes outside the app.

**M10-B2 — NodeQuest first.** The test copies `iter/nodequest` into a root, gives it a brief, installs the
SDK, and loads the page in Chromium: `IterAlly.brief().for` is the brief, `IterAlly.patterns()` has nine,
a fork card renders and its pick lands in the calibration, with `fetch` stubbed to prove no request is
made. The copied page's own markup above the injection is unchanged (byte-compare before `</body>`).

**M10-B3 — Docs.** `AGENTS.md`'s Soul section names `ally_sdk` and the SDK's three guarantees (no gate,
no phoning home, the brief is the app's Soul); the tools table gains the row. The margin's presence line
is unchanged (the 900-char cap stands).

---

## C. Apps: every local app in the fold, and focus, not clutter

**M10-C1 — What counts as an app.** `iterbrow_runtime/local_apps.py`: `list_apps(root)` → sorted
`[{id, kind: "foundry" | "plain", path, entry, brief}]` where a Foundry project is a directory under
`apps/` holding `app.json` (entry from its manifest; `brief` from `blueprint.flourishing_brief`), and a
plain app is a top-level directory of `ITER_DIR` holding an `index.html` (entry `index.html`; `brief` from
`brief.json`); never symlinks, never `apps` itself, never dot-directories, never `node_modules`. Ids are
the directory names and must match `^[a-z][a-z0-9_-]{0,62}$`. `main.js` gets the same list through a
new `apps:catalog` IPC that runs `python3 -m iterbrow_runtime.local_apps` (JSON on stdout) — one source of
truth, used by the toolbar menu and by `registeredAppForUrl`.

**M10-C2 — The Apps button.** The toolbar gains `#btn-apps` ("Apps") next to CRM. Clicking it asks
main for the catalog and shows a native menu (`Menu.buildFromTemplate`, via `apps:menu`) with one item per
app, labelled `<id>` and, when it has a brief, `<id> — for <brief.for>`; Foundry and plain apps in one
list, sorted by id. Choosing one calls `apps:open <id>`. The CRM stays as its own button.

**M10-C3 — Plain apps open as app tabs.** `apps:open` (and `openRegisteredApp`) handles a plain app by
`tabs.createTab(file://<ITER_DIR>/<id>/index.html, appTabOptions(id))`: app scope, the app preload, the
margin. `registeredAppForUrl(url)` also maps a plain app's `file://…/<id>/index.html` (and anything under
`…/<id>/`) to that id, so session restore re-scopes restored plain-app tabs. `app:context` /
`app:command` from a plain app return the same "no contract" error they do today for an unknown app;
mapstation and nodequest never call them.

**M10-C4 — External links leave the app.** A restricted (app) tab that would navigate to, or `window.open`,
an `http(s)` URL opens it in a **new ordinary tab** instead of silently denying it (`tab_manager.js`:
the `will-navigate` handler and `setWindowOpenHandler`); `file:` and other schemes are still denied, and
navigation within the app's own directory (`…/<id>/…`) is allowed. `onExternalLink` is the hook main.js
sets so the new tab is created through the same path as `tabs:new`.

**M10-C6 — Iter reads the same catalog.** `apps` tool: `run()` → one line per app,
`<id> (<kind>) <file URL of its entry>[ — for <brief.for>]`, from `local_apps.list_apps`, so Iter opens an
app by its real URL (`browser_new_tab`) instead of guessing a path (it guessed `apps/mapstation/` on
2026-10-17 and reported the page missing). `ALLY: none` when there are no apps.

**M10-C5 — Focus, not clutter.** `TabManager.findTab(predicate)` returns the first tab (in strip order)
for which `predicate({id, url, locked, pinned, appScope})` is true, or null. `dashboards:open` focuses an
existing tab whose URL is the gallery file (or the empty-gallery page); `pwq:open` one whose URL is the
PWQ page; `crm:open` / `apps:open` one whose `appScope.appId` is that app (any revision URL). Only when
none is open does a new tab open. A locked tab is still focused (the person is switching to their own
tab). The context-menu "duplicate" path is untouched, so a second CRM tab is still possible on purpose.

---

## D. End-to-end

**M10-D1** — through the real loop: `brief` then `ally_sdk` on a plain app → the two files and the
include exist, the brief is in the injected install call, a second `ally_sdk` is a no-op, and the
`apps` tool lists that app with its brief. (That the tool writes nothing outside the app is checked at
unit level, where only the tool runs.)

## Out of scope (next)

Browser track II (bookmarks, reader mode, history search, picture-in-picture); the parked NACE stage 1;
the Muse (person-read, twin) as a separate build.
