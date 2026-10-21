# Milestone 16 — Two shell features ported from the EAOS Foundry: pop-out tabs and the model settings panel

Status: **scoped 2026-10-21, not implemented.** Base: M6–M15. Tests: `tests/test_m16_popout.py`,
`tests/test_m16_settings.py` (16 `@pending`) and `tests/test_m16_present.py` (guards that already pass: the two
features Berton also asked for that IterBrow already has); helpers in `tests/m16_support.py`. How to build it:
`CLAUDE.md`; check a section with `scripts/check_section.sh M16-A`. `M16_IMPLEMENTED` is keyed on
`bridge/model_settings.js` (B1). Implement A then B, one commit each.

## Why

Berton's EAOS Foundry (private, on his Mac, not on GitHub) grew an Electron shell beside IterBrow's. Four things
from it he wants here: a tab that pops out into its own window on a double-click and comes back; drag-to-reorder
tabs; Iter's replies as rich text; and a settings panel where a provider's models are fetched, one is clicked,
tested and saved. Two of the four IterBrow already has (`renderer/markdown.js` renders every Iter message and card;
`tabstrip.js` + `TabManager.reorder` drag tabs since 2026-09-14) — `tests/test_m16_present.py` pins them so they are
not rebuilt. This milestone ports the other two. Nothing is copied from EAOS: its modules were read for their
design (the pop-out is its R11; the settings module its `bridge/settings.js`) and the behaviour is written here in
IterBrow's own files and style. EAOS stays untouched and private.

Principles unchanged (`CLAUDE.md`): the person's locks refuse Iter in a popped tab exactly as in the strip; a
feature that is off leaves no trace; keys never reach the renderer, a log, or a commit; pushes are Berton's.

## Decisions

- **D1 — the view moves, nothing reloads.** A pop-out moves the tab's `WebContentsView` into a bare `BaseWindow`
  and back; same tab id, same page, same lock and pin, same app scope. Closing the pop-out window returns the tab
  to the strip — it never closes the tab.
- **D2 — a popped tab is displayed.** For Iter it counts as on screen (`_displayed`): click, type, screenshot and
  scroll work there; `browser_tabs` says which window.
- **D3 — keys stay in the main process.** `settings:load` reports `hasKey` per provider, never the key; the
  renderer sends a key only when the person typed a new one; the stored key is used when the field is empty.
- **D4 — every provider keeps its own route.** Switching the provider in the panel loses nothing: each has its
  endpoint, model, key and (OpenAI) reasoning; `.runtime/settings.json` keeps them as today under their names.
- **D5 — Iter is unchanged.** The panel changes what `startIterProcess` puts in Iter's environment, nothing in
  `iter/`. Direct OpenAI keeps `LLM_PROVIDER=openai` (Responses API); every other provider is OpenAI-compatible
  chat completions, as OpenRouter and LM Studio are today.

## Test seams

`bridge/tab_manager.js`: `popOut(id)`, `popIn(id)`, `isPopped(id)`, `windowFor(id)`, `makePopoutWindow` (injected by
main.js; the tests inject a fake), `list()` rows carry `window`. `bridge/model_settings.js` (new, pure, no Electron):
`PROVIDERS`, `fetchModels(endpoint, key, fetchImpl)`, `testConnection({endpoint, key, model, reasoning}, fetchImpl)`,
`applyProvider(settings, change)`, `panelState(settings)`, `envFor(settings)`. Renderer wiring is checked by source
(`tests/m16_support.py` reads `renderer/*.js`, `main.js`, `preload.js`).

## A. A tab pops out and comes back

Files: `bridge/tab_manager.js`, `main.js` (`makePopoutWindow`, IPC `tabs:popOut`/`tabs:popIn`, Tabs menu items,
quit), `preload.js` (`popOutTab`, `popInTab`), `renderer/tabstrip.js` (double-click; popped pills), `bridge/
browser_bridge_server.js` (`getTabs` rows), `iter/tools/browser_tabs.py` (shows the window).

- **A1 — the move.** `TabManager.popOut(id)`: when the tab is in the strip, remove its view from the main window,
  create the window with `this.makePopoutWindow({id, title, url, appScope, locked, pinned})`, add the view to the
  window's `contentView`, size it to the window's content (and on every `resize`), show and focus it. If the popped
  tab was active, the newest remaining strip tab becomes active. A second `popOut` of a popped tab focuses its
  window. `popIn(id)`: take the view out of the window, close the window, put the tab back as the active tab.
  The window's `close` takes the view out first; its `closed` returns the tab (`popIn` without a window). `closeTab`
  of a popped tab closes its window and never brings the tab back. `windowFor(id)` is the pop-out window or the
  main window; `isPopped(id)`; `list()` rows carry `window: 'main' | <window id>`. `main.js` quits close every
  pop-out before the main window. `makePopoutWindow` is a `BaseWindow` (no menu bar, the toolbar's background
  colour, titled "IterBrow — <title>", at most 1100×800 and never larger than the work area).
- **A2 — the person's gestures.** Double-click a pill → `tabs:popOut`. A popped tab's pill stays in the strip with
  a `⧉` marker and the title "In its own window — double-click to bring it back"; a click on it focuses its window;
  a double-click → `tabs:popIn`. Tabs menu: "Open in its own window" / "Return to the tab strip" (one item, its
  label by state) with `CmdOrCtrl+Shift+P`. The tab context menu gets the same item. Lock and pin are unchanged in
  both windows.
- **A3 — Iter in a popped tab.** `_displayed(tab)` is true for a popped tab; `switchTab` of a popped tab focuses
  its window instead of moving it; `screenshot` captures the tab's own view wherever it is; `browser_tabs` rows
  gain `window=main|<id>`; a locked popped tab refuses every action as before. `relayout()` leaves popped views
  alone.

Build notes: keep `popOut`/`popIn` next to `closeTab`; the fake window the tests inject has `contentView.children`,
`addChildView`, `removeChildView`, `getContentSize`, `on`, `show`, `focus`, `close` (which fires its own `close` then
`closed` handlers), `isDestroyed`, `id`. The pill's double-click must not fire the single-click switch first — the
renderer already uses `click`; add `dblclick` and ignore the second `click` of a double (`e.detail === 2`).

Tests: `tests/test_m16_popout.py`.

## B. The model settings panel

Files: `bridge/model_settings.js` (new), `main.js` (IPC `settings:fetchModels`, `settings:test`, `settings:save`
→ "Save & apply", `settings:load` → `panelState`), `preload.js`, `renderer/index.html` + `renderer/renderer.js`
(one panel for every provider), `iter/iterbrow_runtime/openai_models.json` (stays the OpenAI price table).

- **B1 — providers.** `PROVIDERS`: `openrouter` (https://openrouter.ai/api/v1, key), `openai` (direct, key,
  reasoning low|medium|high, the catalog's prices), `lmstudio` (http://127.0.0.1:1234/v1, no key), `ollama`
  (http://localhost:11434/v1, no key), `anthropic` (https://api.anthropic.com/v1 — Anthropic's OpenAI-compatible
  endpoint, key; `/models` may be absent, the chat ping decides), `custom` (any endpoint, key optional). Each has
  `label`, `endpoint`, `key` (needed or not), `note` (one plain sentence for the panel). `envFor(settings)` gives
  `startIterProcess` its `{BASE_URL, LLM_MODEL, LLM_PROVIDER, LLM_REASONING_EFFORT, AI_API_KEY}` for the chosen
  provider — identical to today's for openrouter/openai/lmstudio (`LLM_PROVIDER` is the provider's name; the loop
  treats everything but `openai` as compatible); `AI_API_KEY` is `lm-studio`/`ollama` for the local ones without a
  key; a provider that needs a key and has none throws the message the Start button shows today. `OPENROUTER_API_KEY`
  for embeddings keeps coming from the OpenRouter entry whatever the chat provider is.
- **B2 — fetch and test.** `fetchModels(endpoint, key, fetchImpl)` → `{ok, status, models: [ids sorted], pricing:
  {id: {input, output}} | null, error}` from `GET {endpoint}/models` with the bearer key (OpenRouter's list carries
  per-1M-token pricing; kept), never throws, 15 s deadline. `testConnection({endpoint, key, model, reasoning},
  fetchImpl)` → the models list and, when a model is named, one real chat round trip (`POST /chat/completions`,
  one short user message, `max_tokens` small) reporting `{ok, text, ms, reply, dropped}`; when the model answers HTTP
  400 for an unsupported parameter (`max_tokens`, `temperature`), the parameter is dropped and the ping retried
  once, `dropped` names it. `ok` is the chat's verdict when a model was named, else the list's.
- **B3 — the panel.** One panel for every provider (the three provider-specific blocks of today's `index.html`
  become one): provider select; endpoint (prefilled from the preset, editable for custom/local); **model**: a
  select filled by **Fetch models** (click one → it is the model) and a text field (typed name wins); the
  OpenAI reasoning select only for openai; API key (password field, empty when a key is stored, placeholder
  "stored — leave empty to keep it"); **Test connection** → one line of result (`ok — models: 312 listed · chat:
  answered in 1.8 s ("Hello…")` or the error); **Save & apply** → saves, and when Iter is running, restarts it
  (`stopIterProcess` then `startIterProcess`), the chat shows the sys line it shows on Start. The OpenAI price
  line and "last request cost" stay as they are. Apps folder, history switch, Save settings: unchanged.
- **B4 — keys stay home.** `settings:load` returns `panelState(settings)`: per provider `{endpoint, model,
  reasoning, hasKey, models: [last fetched ids], pricing}` — never a key. `settings:save` merges a non-empty typed
  key, keeps the stored one otherwise (`applyProvider`). `settings:fetchModels`/`settings:test` resolve the key in
  main from the stored entry when the form sent none. Iter's log line on start names the provider and model, never
  the key (as today).

Build notes: `model_settings.js` is pure — pass `fetchImpl` (Electron's `net.fetch` in main, a fake in tests).
Keep `.runtime/settings.json`'s shape: `provider` plus `openrouter`/`openai`/`lmstudio`/… entries with `endpoint`,
`model`, `apiKey`, `reasoning`, `models`, `pricing`; `modelConfig` in main.js becomes `envFor`. Existing files load
unchanged (a missing entry gets the preset's endpoint). `renderer.js` keeps `openaiCatalog` for the price line.

Tests: `tests/test_m16_settings.py`.

## Already here (guards, not work)

`tests/test_m16_present.py`: `renderer/markdown.js` is dependency-free and renders Iter messages and cards
(`renderer.js` uses `IterMarkdown.render` for `message.content` and `card.body`); `tabstrip.js` pills are
`draggable` and `TabManager.reorder` keeps pinned tabs first. If Berton sees either not working, that is a defect
to reproduce, not a section of this milestone.

## Not in this milestone

Tab groups and last-working-state restore (EAOS `tab_groups.js`, `session_state.js`); the terminal & files
panel; app state export/import; the ledger/dashboard/Mind views; the LAN table; a native Anthropic API route
(the OpenAI-compatible endpoint is enough here).
