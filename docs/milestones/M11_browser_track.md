# Milestone 11 — Browser track II: a browser people leave open

Status: **scoped 2026-10-17**. Base: M6–M10. Tests: `tests/test_m11_*.py`; helpers in
`tests/m11_support.py`. Every test starts `@pending("M11-xx")`; remove the decorator as each passes.
`M11_IMPLEMENTED` is keyed on `bridge/location.js` (A1, the first file this milestone creates).
No end-to-end run: nothing in this milestone passes through the loop, the AtomSpace or a model.

## Why

The Soul series (M6–M10) is complete. The roadmap's browser track is the other half of the bet:
"together they make IterBrow something people leave open, which is what the Soul needs to be worth
having." M9 did find-in-page. This milestone does the rest Berton listed — bookmarks, history search,
reader mode, picture-in-picture — plus the one fix Iter ran into on Map Station: Electron's
`navigator.geolocation` goes through Google's network location service and needs a billed
`GOOGLE_API_KEY`, so it fails with Chromium's error 2 ("Failed to query location from network
service") no matter what macOS Location Services says. Section A gives Map Station a native route
instead: a small Core Location helper the main process runs on the person's click, exposed to that
one page only.

Principles unchanged. Everything here is the **person's** browser: no new tool, no new surface for
Iter, nothing gates or vetoes anything. The person's locks and switches are the only refusals:
a locked tab is never recorded in history (the lock is their "don't touch" line, and `.runtime/`
is readable by Iter's file tools), and a feature that is off leaves no trace (history off → the file
is deleted). Honest surfaces: a button that cannot act is disabled, a status line names the real
reason ("no location helper", "permission denied"), never a hopeful one.

## Vocabulary

- *Helper*: the native location program main.js runs. Resolution order (first that exists wins):
  `$ITERBROW_LOCATION_HELPER` (absolute path) → `ITER_DIR/.runtime/bin/iter_location` (built from
  `scripts/location/iter_location.swift` by `scripts/build_location_helper.sh` when `swiftc` is
  present) → `CoreLocationCLI` at `/opt/homebrew/bin` or `/usr/local/bin` (`brew install
  corelocationcli`). Either prints one JSON object with `latitude` and `longitude` (CoreLocationCLI's
  `-once -json` shape; the Swift helper prints the same keys plus `h_accuracy` and `time`).
- *Bookmark*: `{url, title, addedAt}` in `.runtime/bookmarks.json` (array, newest first, unique by
  URL). *History*: one `{at, url, title}` per line in `.runtime/history.jsonl`. Both are the person's
  application state: manifest entries like `closed_tabs.json` (`portable: true, reset: false`, owner
  `core.tabs`), kept across Factory Reset, carried by export/import.
- *Reader*: the extracted article of the active page, rendered as a `data:text/html` document in the
  same tab (Back returns to the page). *PiP*: the active page's largest playing video, in a
  picture-in-picture window, through Chromium's own `requestPictureInPicture`.

---

## A. Native location for Map Station

**M11-A1 — `bridge/location.js` (pure).**
- `parseLocation(text)` → `{lat, lon, accuracy, at}` or `null`. Accepts the first JSON object in
  `text` (CoreLocationCLI may print a leading line); `lat`/`lon` finite and in range, else `null`;
  `accuracy` from `h_accuracy` | `horizontalAccuracy` | `accuracy` (number, else `null`); `at` from
  `time` when it parses as a date (ISO string or epoch seconds/ms), else `null`.
- `helperCommand({env, runtimeDir, exists})` → `{file, args, source}` or `null`, in the order above:
  `{file: env.ITERBROW_LOCATION_HELPER, args: [], source: 'env'}`;
  `{file: <runtimeDir>/bin/iter_location, args: [], source: 'built'}`;
  `{file: '/opt/homebrew/bin/CoreLocationCLI' | '/usr/local/bin/CoreLocationCLI', args: ['-once', '-json'],
  source: 'brew'}`. `exists(path)` is injected (tests pass a set). An env value that does not exist is
  skipped, not an error.
- `failure(code, signal, stderr)` → one of `'denied'` (stderr mentions `denied`/`not authorized`/
  `kCLErrorDomain`), `'timeout'` (signal `SIGKILL`/`SIGTERM`), else `'unavailable'`.

**M11-A2 — main.js and the app preload.** `ipcMain.handle('location:current')`:
- The sender must be the Map Station page (`isMapStationPageOrigin(event.sender)`), else
  `{ok: false, reason: 'not-allowed'}` and nothing runs. No other page, tab or tool can reach the
  helper; Iter has no tool for it.
- No helper → `{ok: false, reason: 'no-helper', hint: 'brew install corelocationcli'}` (the hint
  names the Swift build too when `swiftc` is on the Mac — keep it to one line).
- Otherwise `execFile(file, args, {timeout: 15000, killSignal: 'SIGKILL'})`; success →
  `{ok: true, lat, lon, accuracy, at, source}`; failure → `{ok: false, reason}` from `failure()`.
  Never more than one helper run at a time (a second call while one runs awaits the same promise).
  Log one line per run to `pushLog` (`[location] …`), never the coordinates.
- `bridge/app_preload.js` exposes `iterApp.locate()` (invoke `location:current`). Nothing else changes
  in the preload; `scripts/sync_margin_preload.js --check` stays green.

**M11-A3 — Map Station.** `iter/mapstation/index.html` `locate()` tries, in order: `window.iterApp &&
iterApp.locate` (native) → `navigator.geolocation` (unchanged) → approximate center. Status lines:
native success `Location locked · <lat>, <lon> (native)`; native refused with `reason`, then the
existing fallbacks, and the final status names the first real reason (`No location helper on this
Mac — brew install corelocationcli`; `Location permission was denied — allow it in System Settings →
Privacy & Security → Location Services`). The page itself makes no network request for location
(Leaflet tiles are not location). `reload: true` behaviour (sessionStorage hand-off) is unchanged except
that the hand-off carries `source`, so the restored status also ends in `(native)` when it was.

**M11-A4 — The helper on disk.** `scripts/location/iter_location.swift` (≈ 50 lines: CLLocationManager,
`requestWhenInUseAuthorization`, one fix, prints the JSON object, exits 0; exit 2 on denial with
`denied` on stderr; exit 3 after 20 s without a fix). `scripts/build_location_helper.sh`: with `swiftc`
present, compiles to `ITER_DIR/.runtime/bin/iter_location` (0o755) and prints the path; without, prints
`no swiftc; brew install corelocationcli works too` and exits 0 (`--check` only reports which route
exists). `install.sh repair` calls it best-effort (its exit never fails the repair).
`package.json`'s `NSLocationWhenInUseUsageDescription` stays. README: a short "Location" note.

Not testable from the cloud: the macOS permission prompt and the fix itself. Berton tests A on his
Mac; the tests cover everything up to the helper's stdout.

## B. Bookmarks

**M11-B1 — `bridge/bookmarks.js` (pure).** `normalizeUrl(url)` (trim; drop a trailing `#` fragment;
keep everything else), `isBookmarked(list, url)`, `add(list, {url, title, at})` → new list, newest
first, unique by normalized URL (re-adding moves it to the front with the new title), `remove(list,
url)`, `toggle(list, {url, title, at})` → `{list, bookmarked}`, `search(list, q, limit = 8)` (every
whitespace-separated word of `q` matches title or URL, case-insensitive; empty `q` → the first
`limit`). Only `http(s):` and `file:` URLs can be bookmarked (`add` of anything else returns the
list unchanged).

**M11-B2 — main.js.** `.runtime/bookmarks.json` through `loadBookmarks()`/`saveBookmarks()` (same
shape as the closed-tabs pair; atomic write). A top-level **Bookmarks** menu after History:
`Bookmark This Tab` (`CmdOrCtrl+D`, toggles the active tab; label reads `Remove Bookmark` when it
is one), separator, then the bookmarks (newest first, 30 max, `label` = title or URL ≤ 60 chars,
click → focus an open tab with that URL else a new tab), or `(No bookmarks)` disabled. IPC
`bookmarks:list`, `bookmarks:toggle(tabId)` → `{bookmarked}`, `bookmarks:open(url)`; push
`bookmarks:state` `{bookmarked}` to the toolbar whenever the active tab or its URL changes (same
place the tabs update is pushed) and after a toggle. The menu is rebuilt after every change, like
Recently Closed. Manifest entry added. A locked tab can be bookmarked (the person's click).

**M11-B3 — Toolbar.** `#btn-bookmark` (☆, title "Bookmark this tab"; ★ with class `on` and title
"Bookmarked — click to remove") in row 1 after reload; click → `iterApi.bookmarkToggle(activeTabId)`;
reflects `iterApi.onBookmarkState`. Disabled when the active tab's URL is not bookmarkable.

## C. History and its search

**M11-C1 — `bridge/history.js` (pure).** `shouldRecord(tab, on)` — exactly the browsing ally's rule
(`on`, http(s), not locked, not an app tab) — implemented by calling `browsing_ally.shouldLog`.
`append(lines, entry, cap = 5000)` → new list; a navigation to the same URL within 5 s of the last
line replaces it (redirect chains, `did-navigate` double fire); older lines drop off the front at
`cap`. `search(lines, q, limit = 8)` → newest first, unique by URL (latest visit's title and time,
`visits` counted), every word of `q` matches title or URL case-insensitively; empty `q` → the
latest `limit`. `titled(lines, url, title)` → the list with the latest line for `url` retitled
(titles arrive after `did-navigate`).

**M11-C2 — main.js.** `.runtime/history.jsonl`, written on `did-navigate` (and retitled on
`page-title-updated`) only when `shouldRecord(tab, settings.keepHistory !== false)`; the file is
held in memory and rewritten whole (cap 5000) — not appended — so the cap and the 5 s rule hold.
`keepHistory` lives in `settings.json` (default `true`); saving it `false` deletes the file at once
and stops recording; `true` again starts an empty one. History menu gains `Search History…`
(`CmdOrCtrl+Y`, pushes `history:open` to the toolbar) and `Clear History` (deletes the file, keeps
the setting). IPC `history:search(q)` → results, `history:openUrl(url)` → focus-or-new-tab,
`history:clear`. Manifest entry added (`reset: false`). Settings panel: a checkbox
`#setting-history` "Keep browsing history (never locked tabs, never app tabs)" saved with the
other settings. `data:`, `about:` and `file:` URLs are never recorded (reader pages, internal
pages).

**M11-C3 — Toolbar.** `#history-bar` in row 2 beside the find bar (hidden by default): `#history-text`
input, `#history-results` list (≤ 8 `<li>` with title and host), opened by `iterApi.onHistoryOpen`
(focus + select, and the search re-runs for the current text), queries `iterApi.historySearch(q)` on input (debounced 120 ms) and renders the
results; `Enter` opens the highlighted result (first by default; ↑/↓ move) via
`iterApi.historyOpen(url)` and closes; `Escape` or `#history-close` closes. Opening the find bar
closes the history bar and vice versa.

## D. Reader mode and picture-in-picture

**M11-D1 — `bridge/reader.js` (pure).** `READER_SCRIPT` — a string of page JavaScript (an IIFE
returning JSON) that: picks `<article>`, else `main`, else `[role=main]`, else the block element
with the highest `textLength × (1 − linkDensity)` among `div/section/td` with ≥ 400 characters;
takes `document.title` (or the first `h1`); **clones** the pick and strips `script, style, iframe,
object, embed, nav, aside, footer, form, button, input, select, textarea, svg, canvas, noscript`,
every `on*` attribute, every `style` attribute, `javascript:` hrefs, and keeps only `href` (http(s))
on `a` and `src` (http(s)) + `alt` on `img`; returns `{title, html, textLength, byline}` (`byline`
= first `[rel=author]` / `.byline` / `[itemprop=author]` text, else `""`) or `{title, html: "",
textLength: 0}` when the best block has < 400 characters. `renderReader({title, byline, html, url})`
→ a complete HTML document: `<meta charset>`, an inline stylesheet (max-width 68ch, 19 px serif,
line-height 1.6, dark-aware via `prefers-color-scheme`), `<h1>` title, a byline line, a source line
linking the original URL, the article HTML as given. `title`, `byline` and `url` are HTML-escaped;
the document contains no `<script`.

**M11-D2 — main.js and the toolbar.** View menu `Reader Mode` (`Shift+CmdOrCtrl+R`) and
`#btn-reader` (📖, row 1, after bookmark; disabled unless the active tab's URL is http(s) and the
tab is not an app tab): `executeJavaScript(READER_SCRIPT)` on the active tab; when `textLength
≥ 400`, `loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(renderReader(...)))` in the
same tab, else a toolbar notice `No article found on this page` (reuse `#ally-notice`'s look: a
`#reader-notice` span that hides itself after 4 s). A locked tab is the person's: the button works
there (it is their click). `history:` never records the `data:` page (C2's rule). A reader page is
not re-readable (button disabled on `data:`).

**M11-D3 — Picture-in-picture.** `bridge/reader.js` also exports `PIP_SCRIPT`: finds the largest
`<video>` (by rendered area; prefers one that is playing), calls `requestPictureInPicture()`
(or `document.exitPictureInPicture()` when one is already in PiP) and returns `{ok, reason}`
(`'no-video'` | `'unsupported'` | the error name). View menu `Picture in Picture`
(`Shift+CmdOrCtrl+P`) runs it on the active tab with `executeJavaScript(PIP_SCRIPT, true)`
(user gesture); `'no-video'` → the reader notice `No video on this page`. Not on app tabs.

## E. Done means

`scripts/test_all.sh --fast` green with every `@pending` removed; `scripts/sync_margin_preload.js
--check` green; `node -e` syntax check of main.js and preload passes (test_all does it). README gains
one "Everyday browser" paragraph (bookmarks Cmd+D, history search Cmd+Y, reader Shift+Cmd+R, PiP
Shift+Cmd+P, location helper). AGENTS.md unchanged (no new tools).

## Out of scope (next)

Downloads panel and zoom per site (roadmap browser track); the parked NACE stage 1; the Muse
(person-read, twin) as a separate build; a `history` tool for Iter (if Berton ever wants one, it is a
switch of the person's, off by default, like `browsing_ally`).
