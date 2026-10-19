# Milestone 13 — The builder's eyes: Iter can see what it did

Status: **implemented 2026-10-19** (all `@pending` decorators removed).
Implementation notes:
- **A regression the full run caught: the loader's tool cap.** `iter.py` loads at most `MAX_TOOLS - 1`
  tools (protected first, then alphabetically) and drops the rest silently; M13's three tools took the count
  to 81 and `write_file` fell off the end (the M12 e2e answered "Unknown tool: 'write_file'"). The builder's
  hands and eyes are now in `PROTECTED_TOOL_NAMES`, `MAX_TOOLS` is 96, and `tests/test_tool_cap.py` fails as
  soon as the next tool would cross the cap — the same failure once hid `send`.
- **One fixture fix (B1).** The page fixture's zero-size `#zero` was a `<span>`; `width`/`height` do not
  apply to inline elements, so it rendered 27×17 and visible. It is `display: inline-block` now; the
  assertion (`visible` is false) is unchanged.
- **Source-shape tests and helpers.** B2/B5 check strings in `click` and in each tool, so the displayed
  check, the post-action `stateScript()` read and `tabId` are written inline there (`type`, `scroll` and
  `waitFor` share a small `_displayed(tab)`).
- **`stateScript` also returns `activeEditable`** (the summary keeps exactly `{tag, id, text}`), which is how
  `type` knows a field has focus.
- **`openApp` makes the app tab Iter's target** (it is Iter's own action, like `newTab`), so the next
  click/probe lands in the app; the person opening an app from the menu still never moves the target.
- **`waitFor` requires the tab on screen**, as the spec's vocabulary says for actions (timers in a page that
  is not displayed are throttled), and is allowed on a locked tab (it only reads). An invalid selector
  ends the wait at once and the bridge's error says `(invalid selector)`.
- **`probe` returns `tabId`** besides the specified fields; `scroll` with a selector reports invalid/missing
  like `click`.
- **Commit split.** `bridge/browser_bridge_server.js` carries B3/B4 (waitFor, newTab) and all of C, so it is in
  the C commit; the A tests key on `bridge/page_scripts.js`, which lands in the B commit.
- **README.** Its tool tables are generated from `DESCRIPTION`s; the nine browser rows this milestone changed
  were regenerated from the new descriptions, the three new tools added, the tool count updated.
- **Not verifiable here:** real input events, focus and `capturePage` need Electron. Berton's first check on
  the Mac: open Map Station with `browser_open_app`, have Iter click "Locate me" and report what it hit.

Base: M6–M12. Base: M6–M12. Tests: `tests/test_m13_*.py`; helpers in `tests/m13_support.py`.
Every test starts `@pending("M13-xx")`; remove the decorator as each passes. `M13_IMPLEMENTED` is keyed on
`bridge/page_scripts.js` (B1, the first file this milestone creates). No end-to-end run through the loop:
the eyes need Electron, which the e2e harness does not have; the page scripts are tested in a real
Chromium (Playwright), the bridge with a fake tab manager (node), the tools with a fake bridge socket.

## Why

M12 gave Iter hands and found its own gate had tied them. What remains is that Iter cannot see what it
did, verified in code in the 2026-10-18 audit:

- `click` resolves a selector with `document.querySelector` only (`tab_manager.js:580-587`): an invalid
  selector is an opaque "Script failed to execute"; a hidden or zero-size element is clicked at the page
  corner and reported as `clicked`; nothing scrolls into view; a covered element is "clicked" through
  its cover. `type` calls `insertText` without checking that anything editable has focus (604-611).
  `scroll` is `window.scrollBy`, which does nothing for a scrolling container (613-615). All three
  return a string and no state: Iter must call eval/screenshot separately to learn anything.
- Input is sent to a tab that is not displayed (`sendInputEvent` on a view outside the window) and
  reported as success; `screenshot` already admits this ("Attaching a tool target does not bring the
  tab into view").
- There is no wait-for anywhere; `newTab` returns before the page loads (`createTab` → `loadURL`
  without waiting), so the next click races the load.
- Every `createTab` moves Iter's target (`attachedId`) — including tabs the person opens (⌘T, a link,
  reopen-closed), links leaving an app tab, and every tab of a session restore, which leaves the target
  on the *last restored* tab rather than the one on screen. `browser_tabs` hides `locked`, `app` and
  which tab is the target, so Iter cannot notice.
- The only scripted probe (`inspectApp`) requires an exact `apprev-` revision id, which plain apps never
  have, and no tool calls it; `openApp` is on the bridge with no tool either.
- Reading code: a tool result over 4,500 characters reaches the model as a 1,800-character excerpt
  (`tool_results.py:21, 380`), so `read_file`'s 200-line page is cut unless it is the newest result.
  A tool with no track record carries a ~250-character `[NACE advisory: … trust_stage=candidate …]`
  prefix on every result.
- `browser_cdp` cannot attach while DevTools is open on the tab, and says so unhelpfully.

Principles unchanged: nothing gates or vetoes; the person's locks refuse and are reported as refusals
(M12-A3); honest surfaces — an action that could not have happened as asked says so in its first
line, never `clicked`. No new surface for Iter beyond its own tabs and the apps it builds.

## Test seams

`bridge/browser_bridge_server.js` exports `buildMethods` (the tests build the methods over a fake tab
manager); `bridge/foundry_apps.js` exports `validateProbeSpec`; `bridge/page_scripts.js` is pure.

## Vocabulary

- *Displayed tab*: `tabs.activeId`, the one in the window. *Target*: `attachedId` when set, else the
  displayed tab (`resolveTabId`). Actions (click, type, scroll, wait_for) require the target to be
  displayed; they never switch the view under the person — they say what to do instead.
- *Page script*: a self-contained JavaScript expression run in the page with `executeJavaScript`;
  all of them live in `bridge/page_scripts.js` (pure, no Electron), so Playwright can test them.
- *Element summary*: `{tag, id, text}` (`text` ≤ 60 chars of `innerText`, or `value` for inputs) —
  how an element is named back to Iter.

---

## A. Reading at size

**M13-A1 — Wire allowance for reading tools.** `iter.py` gives the reading tools a larger wire:
`READ_TOOLS = {"read_file", "grep_files", "list_files", "browser_read_text", "run_tests",
"read_tool_result"}` capture with `max_chars=READ_WIRE_CHARS` (24,000; `tool_results.READ_WIRE_CHARS`,
and `capture_tool_output`'s check becomes `512 <= max_chars <= READ_WIRE_CHARS`); every other tool keeps
4,500. A 24,000-character page is ~8k tokens; the request budget's working limit already adapts to the
active working set, so nothing else changes.

**M13-A2 — One short advisory line.** `iterbrow_runtime/advisory.py` `short_note(capability, detail)`
→ for a `trust_stage=candidate` detail: `[NACE: 'x' has no track record yet] `; for any other detail:
its first clause (up to the first ` -- ` or ` [decision=`), at most 160 characters, as
`[NACE advisory: …] `; empty detail → `""`. `iter.py` uses it for `gate_note`. The gate's own verdict
string and its recorded decision are unchanged (the governance tests cover them).

## B. Honest actions

**M13-B1 — `bridge/page_scripts.js` (pure).** Functions that return a JavaScript expression string:
- `locateScript(selector)` → in the page: `querySelector` inside try/catch (`{error: "invalid"}` on a
  `SyntaxError`); `{error: "missing"}` when nothing matches; otherwise `scrollIntoView({block:
  "center", inline: "center"})`, re-measure, and return `{rect: {x, y, width, height}` (viewport
  coordinates of the center), `visible` (client rects > 0, `visibility` not hidden, `display` not none,
  center inside the viewport), `covered` (the element at the center point is neither the element nor
  inside it; with `coveredBy` as an element summary), `summary` (element summary), `editable`
  (input/textarea/select or `contentEditable`)}`.
- `stateScript()` → `{url, title, active: <summary of document.activeElement or null>}`.
- `waitScript({selector, text, url, timeoutMs})` → an async expression that polls every 100 ms until
  the selector matches a visible element, `document.body.innerText` contains `text`, or
  `location.href` contains `url` (any given condition; all given must hold), resolving
  `{found: true, afterMs, match: <summary|snippet|href>}` or `{found: false, afterMs}` at the deadline.
- `scrollScript({selector, x, y})` → with a selector: `scrollIntoView` of the element and return
  `{target: summary}`; without: scroll the nearest scrollable ancestor of the focused element or the
  window by (x, y), returning `{before: {x, y}, after: {x, y}}` of what actually moved.
- `probeScript(spec)` moves here from `foundry_apps.js` unchanged (`foundry_apps.js` re-exports it).

**M13-B2 — Click and type in `tab_manager.js`.** `click({id, x, y, selector})`:
- the tab must be displayed: else throw `Tab N is not displayed; browser_switch_tab(N) first` (no
  input is sent);
- with a selector, `locateScript`: `invalid` → throw `Invalid CSS selector: <sel>`; `missing` → `No
  element matched selector: <sel>`; not visible → `Element matched <sel> but is not visible (<reason>)`;
  covered → `Element matched <sel> but is covered by <coveredBy summary>`; then the input events at the
  measured center;
- return `{clicked: <selector|x,y>, target: <summary>, url, title, active}` (state from `stateScript`
  after a 50 ms settle).
`type({id, text, selector})`: after the optional click, `stateScript` must show an editable active
element, else throw `Nothing editable is focused; pass a selector for the field`; after `insertText`,
return `{typed: n chars, target: <summary with the field's value after typing (≤ 60 chars)>, url,
title}`. `scroll({id, x, y, selector})` runs `scrollScript` and returns its result.

**M13-B3 — `waitFor` on the bridge and `browser_wait_for` tool.** `TabManager.waitFor({id, selector,
text, url, timeoutMs})` runs `waitScript` in the tab and returns its result. Bridge method
`waitFor({tabId, selector, text, url, timeoutMs})` (locked tabs allowed: it only reads) resolves the tab,
clamps `timeoutMs` to 100–30,000, calls `tabs.waitFor`, and throws a `{found: false}` result as
`timed out after <s>s waiting for <conditions>` (e.g. `selector #go, text x`). Tool `browser_wait_for(selector="", text="", url="", timeout="10")` (seconds) → `found
<what> after <ms> ms` or the timeout error (a failure, not a refusal).

**M13-B4 — `newTab` waits.** `TabManager.awaitLoad(id)` is the load correlation `navigate()` already
does (did-finish-load / did-fail-load, ERR_ABORTED ignored, 15 s cap), returning `{url, title,
warning?}`; `navigate()` uses it too. The bridge's `newTab` calls `createTab(url, {agent: true})` then
`awaitLoad` and returns `{created, url, title, warning?}`; `browser_new_tab` reports
`opened tab N: <title> <url>` and the warning when there is one.

**M13-B5 — `tab_id` everywhere.** `browser_click`, `browser_type`, `browser_scroll`, `browser_eval`,
`browser_read_text`, `browser_screenshot`, `browser_wait_for` take an optional `tab_id` (string),
passed as `tabId`; the tools' descriptions say so and `browser_attach`'s description no longer claims
the others lack it.

**M13-B6 — `browser_cdp` and DevTools.** `tab_manager.cdp` catches the attach error and throws
`DevTools is open on tab N; close it to use browser_cdp`.

## C. Targets and apps

**M13-C1 — Only Iter's own tabs move its target.** `TabManager.createTab(url, opts)` sets `attachedId`
only when `opts.agent === true`. The bridge's `newTab`, `browser_tab_variants` and `preview` paths pass
`agent: true` (they go through the bridge, so the bridge's `newTab` sets it); every `main.js` caller
(⌘T, menus, reopen-closed, links from UI views, `onExternalLink`, session restore, the Apps menu)
leaves the target alone. After session restore, `attachedId` is `null`, so the target is the
displayed tab. `switchTab` from the bridge still attaches (it already does).

**M13-C2 — `browser_tabs` tells the truth.** One line per tab: `tabId=3 displayed=true target=true
locked=false app=mapstation title='…' url=…` (`app=-` when not an app tab). `tabs.list()` gains
`attached` (boolean).

**M13-C3 — `browser_open_app(app_id)`.** Bridge `openApp` already exists (focus-or-open as an app tab,
with the preload); the tool calls it, waits for the load like B4, and returns `app <id>: tabId=N
<focused|opened> <url>`. `apps.py` and AGENTS.md point at it.

**M13-C4 — `app_probe` for every app.** Bridge method `probe({appId, steps, assertions, timeoutMs})`:
finds the app tab (`appScope.appId`), refuses a locked tab (the lock message), runs `probeScript` with
`validateProbe`'s rules minus the revision id (a new `validateProbeSpec` in `foundry_apps.js`; the
revisioned `inspectApp` keeps its own check). Returns `{observations: [{kind, selector, expected,
actual, passed}], passed: n, failed: m, ready, title}`; `ready` is reported, not required. Tool
`app_probe(app, steps="[]", assertions, timeout="3")` (JSON strings) → first line `PROBE <app>:
<n> passed, <m> failed` then one line per assertion `✓|✗ <kind> <selector>: expected … got …`.

**M13-C5 — App tabs stay on their app.** The bridge's `navigate` on an app tab refuses a URL outside
the app's folder (the same rule as `will-navigate`'s `_insideAppDir`) with `App tab N stays on its app;
open another page in a new tab` — a failure, not a lock refusal; reloading the app's own URL is allowed.

## D. Guidance

**M13-D1** — AGENTS.md's "Building and changing code" section (still ≤ 1,800 chars, still inside the
injected slice) adds: open an app with `browser_open_app`, wait with `browser_wait_for`, prove it with
`app_probe` before saying it works; actions tell you what they hit (`target`) and where the page is
now. Tool table rows for `browser_wait_for`, `browser_open_app`, `app_probe`; `browser_tabs`'s row
mentions target/locked/app. README rows likewise.

## E. Done means

`scripts/test_all.sh` (full) green with every `@pending` removed; `node -e` syntax check; the reliability
tracker and courier unchanged; no change to NACE's gate verdicts (governance tests green). Implementation
notes at the top of this file. Then on Berton's Mac: open Map Station from the Apps button, ask Iter to
click "Locate me" and report what it hit — the first click that is scored since September.

## Next (M14 — the vault and the foundry loop)

A vault the person chooses (default offered once, several allowed, carried by export/import) holding
their apps; shipped apps as read-only examples copied into the vault on first open; a snapshot before
every write with one-action rollback (file recovery, not git); `new_app` scaffold with the contract
baked in; a per-app probe spec run before "done" and after every edit; build mode (research → fork
card → plan card → build → probe → report card; `ally_sdk` when the app has a brief); a GitHub
search/read tool and a `websearch` reliability fix; the five-app benchmark, run before M13 lands for
the baseline.
