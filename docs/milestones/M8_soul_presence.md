# Milestone 8 — Presence: the Soul in the tab, modes, critique, museum night

Status: **scoped, tests written, implementation pending.** Roadmap: `docs/soul/SOUL_IN_THE_FOUNDRY.md`
(this milestone merges the roadmap's M8 modes with M9 "Iter in the tab"; the deep person-read and the
twin are parked as a separate later build, "the Muse"). Base: M6 cards/settings/kernel, M7 taste/felt/
briefs/forks. Tests: `tests/test_m8_*.py`, `tests/e2e/test_m8_loop.py`; helpers in `tests/m8_support.py`.
Every test starts `@pending("M8-xx")`; remove the decorator as each passes. `M8_IMPLEMENTED` is keyed on
`bridge/margin.js`.

## Why

The Soul lives in the sidebar today. This milestone puts it where the person is actually looking: a
small glyph in the corner of every app tab Iter built, which opens a margin where the person can point
at a thing and say "ask about this" or "jam on this". Nothing else changes on the page. The glyph is
present the way air is: there when reached for, invisible otherwise. Around it, four modes give the
collaboration a register (jam, quiet, critique, museum night), and two of those get real tools: the
soul-absent walk (critique) and the museum night narration.

Principles carried forward: nothing gates, pauses or vetoes Iter; the person's own locks and switches
are the only things that refuse anything; a feature that is off leaves no trace; pattern text enters
Python only through the lens; `state:soul_*` atoms live in the soul view only; surfaces count from the
authority.

## Vocabulary

- *Margin*: the in-page panel opened from the glyph. Its payload `{intent: "ask"|"jam", text,
  element: {selector, tag, text}}` reaches Iter as a user line
  `[margin app=<app> tab=<tab-id> intent=<intent> element=<selector>] <text>` (`element=page` when
  nothing was pointed at; no trailing space when `text` is empty) and is journaled with a structured
  `margin` field.
- *Mode*: per person, one of `open` (default), `jam`, `quiet`, `critique`, `museum`. Stored beside the
  features in `.runtime/soul_settings.json`.
- *Soul-absent walk*: the critique output — moments in an app that are technically correct and dead,
  each tied to a kernel pattern's gap signature, read from the lens.
- Atoms (soul view only): `(soul-margin "<person>" "<app>" "<intent>" <at-ms>)` at
  `state:soul_margin:<message-id>`; `(soul-critique "<app>" "<person>" <moments> <at-ms>)` at
  `state:soul_critique:<id>`.

---

## A. Modes

**M8-A1 — Setting.** `soul_settings` gains `mode` per person (`MODES = ("open", "jam", "quiet",
"critique", "museum")`, default `open`, invalid → `open`) with `mode()` and `set_mode(person, mode)`;
`set_mode` writes the file atomically (`0o600`), touching nothing else in it, and raises `ValueError` on
an unknown mode. `main.js cleanSoulSettings` keeps a valid `mode`; the Soul panel has a `soul-mode`
select (ids `soul-mode`; option values are the five modes) saved with the rest.

**M8-A2 — `soul_mode` tool.** `soul_mode.run(mode)` → `MODE: <new> (was <old>)` for the current person;
unknown → `ERROR: mode must be one of open, jam, quiet, critique, museum`. The presence block tells Iter
that a person saying "jam", "quiet", "critique", "museum night" or "open" is asking for the switch.

**M8-A3 — The block per mode.** `soul_presence.presence_block()`:
- `quiet` → `""` (no block at all, whatever the features) and `transform` also removes the `felt` tool,
  as if felt were off. Cards remain available when the person asks for one.
- `jam` → one extra line `Mode: jam — riff freely; playful variant names; a fork may hold three poles;
  felt notes welcome.`
- `critique` → `Mode: critique — walk the app as the person its brief names; report what is technically
  correct and dead with soul_absent_test; change nothing.`
- `museum` → `Mode: museum night — walk kept and rejected variants with museum_night and say why, using
  what you've learned of their taste.`
- `open` → no mode line.
The 900-char cap holds in every mode with every feature on (the M7 test's maximal case plus the
longest mode line).

**M8-A4 — Defaults.** `margin` joins `forks` and `brief` as on by default (`DEFAULT_ON = {forks, brief,
margin}` in `soul_settings.py`, `renderer.js SOUL_DEFAULTS`, `tests/m6_support.py`; the M6 settings
tests follow). A glyph at rest is the whole cost of the default.

---

## B. The soul-absent walk (critique)

**M8-B1 — `soul_absent_test` tool.** `run(app, moments)`; `moments` is a list (or JSON string) of 1–8
`{where, what, pattern}`. Each `pattern` must be one of the nine (validated against `soul_lens.patterns()`,
never a Python list) → otherwise `ERROR: unknown pattern …` and nothing is recorded. Output:
```
Soul-absent walk of <app> (as: <brief.for>)        | or (no brief; walked as a first-time user)
1. <where> — <what>
   gap (<Pattern>): <gap facet text, verbatim from the lens>
...
Nothing was changed.
```
It records `state:soul_critique:<id>` with the moment count and returns the text (the sidebar message is
Iter's to send). The app's files are untouched (the test hashes the app directory before and after).

**M8-B2 — Honest count.** `authority_counts` adds `soul_critiques`; the dashboard Soul card shows
`critiques <n>` when non-zero.

---

## C. Museum night

**M8-C1 — `museum_night` tool.** `run(app=None, limit=12)` reads the component museum (newest first,
`limit` entries; `app` filters on `url`/`label` containing it) and the soul atoms, and returns:
```
Museum night (<n> pieces)
Kept:
- <id> <label> (<source>, <ts>) — fork <card-id>: <Pattern>, picked
Rejected:
- <id> <label> (<source>, <ts>) — fork <card-id>: <Pattern>, passed over
Unvoted:
- <id> <label> (<source>, <ts>)
Leans: <taste_line for the current person>     | Leans: none yet
```
The fork join comes from `soul-card-choice` atoms carrying that museum id and the matching
`soul-choice` pick. Reading only: no museum record, memory item or atom changes.

---

## D. The margin (the Soul in the tab)

**M8-D1 — `bridge/margin.js` is pure DOM.** `installMargin(document, api)` where
`api = {enabled(): Promise<{enabled, app}>, send(payload): Promise, onState(cb)}`. Behaviour:
- `enabled()` false → nothing is added to the page (no node, no listener).
- enabled → a glyph `#iter-margin-glyph` (`✦`, fixed bottom-right, ~14 px, opacity 0.35, 0.9 on hover,
  `aria-label="Iter"`, `title="Ask Iter about this page"`), and a `mousemove` listener that remembers the
  last element pointed at outside the margin as `{selector, tag, text}` (`text` ≤ 80 chars; selector:
  `#id` when the element has one, else `tag.class1.class2`, else a `nth-of-type` path of ≤ 4 levels).
- Click → panel `#iter-margin` with `#iter-margin-target` ("pointing at: <selector>" or "pointing at:
  the page"), `textarea#iter-margin-text`, `button#iter-margin-ask` ("Ask about this"),
  `button#iter-margin-jam` ("Jam on this"), `button#iter-margin-close`. Esc or close hides the panel.
- A button calls `api.send({intent, text, element})` once, disables both buttons until it resolves,
  then shows `sent` in `#iter-margin-status` and clears the textarea; a rejected send shows the error
  text and re-enables. Empty text with intent `ask` is refused in place (`say what you'd like to ask`);
  empty text with `jam` is allowed (`jam on this` alone is a full request).
- `onState({enabled: false})` removes the glyph, the panel and the listener; `{enabled: true}` installs
  again if absent.
- Styles are inline on the created nodes (no stylesheet injected; the page's CSS is not touched);
  everything lives under one root `#iter-margin-root` so removal is one node.
- The module exports `installMargin` for CommonJS (the preload) and, when `module` is absent, sets
  `window.IterMargin = {installMargin}` so a plain page can load it (the tests do).

**M8-D2 — Wiring.** `bridge/app_preload.js` installs the margin on `DOMContentLoaded` with an IPC-backed
api (`margin:enabled`, `margin:send`, `margin:state`). `main.js`:
- `ipcMain.handle('margin:enabled', (event))` → the tab owning `event.sender`; `enabled` iff the tab
  has an `appScope`, is not locked, and `margin` is on for `loadSoulSettings().person`; returns
  `{enabled, app}`.
- `ipcMain.handle('margin:send', (event, payload))` → the same checks (a locked tab or a tab without
  app scope throws `This tab is locked` / `Not an app tab`; feature off throws `Margin is off`), then
  `chatBridge.sendMargin({app, tab: tab.id, intent, text, element})` and `recordSoulMargin(...)` (best
  effort). The person is never taken from the page.
- Lock toggles and Soul-panel saves push `margin:state {enabled}` to every app tab's webContents
  (`tabs.onTabsChanged` is the hook for locks; `soul:save` for the feature).

**M8-D3 — Bridge and sidebar.** `chat_bridge.js` exports `marginLine(payload)` and the bridge gains
`sendMargin(payload)`: validates `intent ∈ {ask, jam}`, `app` an identifier, `tab` an integer, `text` a
string (may be empty only for `jam`), `element.selector` a string ≤ 200; writes the inbox line and
journals the message with `margin: {app, tab, intent, element}`. The sidebar renders such a user row with
a `.margin-note` line above the body: `from <app> · <selector>` (or `from <app>`), and the body shows
the text (or *jam on this* in italics when empty). `bridge/soul_choice.js` exports
`recordSoulMargin({socket, person, app, intent, messageId, at})` → `{written}` (no queue; a miss is a
log line).

**M8-D4 — The recipe.** With `margin` on, the presence block's margin line reads
`margin (people reach you from inside app tabs: [margin …] lines; "jam on this" → three riffs on that
element as browser_tab_variants and a fork card)`.

**M8-D5 — Honest count.** `authority_counts` adds `soul_margin`; the dashboard shows `margin asks <n>`.

---

## E. End-to-end (real loop, real service, fake model)

**M8-E1** — Script: start in `quiet` (settings file) and assert the first request carries no `## Soul (`
block and no `felt` tool; `soul_mode("jam")` → the next request carries `Mode: jam`; a margin message
sent through the real bridge (`sendMargin`) arrives in Iter's experience as the `[margin …]` user line;
`soul_absent_test` with two moments records one `soul-critique` atom with count 2 and the app directory
hash is unchanged; `museum_night` lists a kept and a rejected entry from pre-seeded museum records with
M7-style votes. No `soul-*` atom lands outside `state:soul_*`.

---

## Out of scope (next)

Wonder jar, the browsing ally and the service-before-growth voice (M9); the app inheriting the ally
(M10); the Muse (the twin and the deep person-read) as a separate build.
