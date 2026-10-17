# Milestone 9 — Wonder, the voice of growth, the browsing ally, find-in-page

Status: **implemented 2026-10-17** (all `@pending` decorators removed).
Implementation notes:
- `iterbrow_runtime/soul_wonder_store.py` holds the wonder atom format shared by the tool and
  `transformations/soul_wonder.py`. An unanswered wonder offer card silences the jar until the person
  answers or dismisses it (it stays in the sidebar).
- `auto_improve.py`: only the deferred branch changed; the path without the flag is identical to
  before (diffed). Deferred + pain writes `memory/.improve_pending` and asks once a day; a `now` pick
  newer than the flag file's mtime lets that cycle's proposal through. The flag file is never written.
- Find-in-page follows Electron 33's semantics: `findNext: true` starts a session, follow-ups pass
  `false`. Switching tabs (`tabs:switch`) closes the find and clears highlights.
- Ally lock suggestions are sent once per host per session; "No" is remembered for the session.
- Two test corrections, same intent: the growth "now" pick is seeded 1 ms (not 5 s) after the flag's
  mtime, since a future-dated pick legitimately postdates the deferral the second half rewrites; the
  toolbar ally probe captures the notice before clicking "Lock it" / "No" (it read it after). Roadmap: `docs/soul/SOUL_IN_THE_FOUNDRY.md`
(this is the roadmap's M10 pulled forward, plus the first browser-track item). Base: M6–M8. Tests:
`tests/test_m9_*.py`, `tests/e2e/test_m9_loop.py`; helpers in `tests/m9_support.py`. Every test starts
`@pending("M9-xx")`; remove the decorator as each passes. `M9_IMPLEMENTED` is keyed on
`iter/tools/wonder.py`.

## Why

Three places the Soul is still silent. Ideas cut from a build vanish; the wonder jar keeps them and
offers one back, rarely. When Iter wants to work on itself while it should be serving, the deferral
is a flag in a file; it becomes a question to the person. And when IterBrow is used as a browser,
the Soul is absent; the ally (off by default) notices capture and hands the choice back, suggests a
lock where one belongs, and lights a compass only while a pair is live. Find-in-page makes IterBrow
a browser people leave open, which is what the ally needs to be worth having.

Principles unchanged: nothing gates, pauses or vetoes Iter; the person's own locks and switches are
the only things that refuse; a feature that is off leaves no trace (for the ally: no log on disk);
pattern text enters Python only through the lens; `state:soul_*` lives in the soul view only; surfaces
count from the authority; confidence is earned.

## Vocabulary

- *Card topic*: an optional `topic` on a card (`^[a-z][a-z0-9_:-]{0,63}$`), recorded by the card tool
  as `(soul-card-topic "<card-id>" "<topic>")` at `state:soul_card_topic:<card-id>`. The reducer
  turns any pick on a topic card (dismiss included) into `(soul-topic-pick "<topic>" "<pick>" <at-ms>)`
  at `state:soul_topic_pick:<topic>` (latest wins). One mechanism serves the jar (`wonder:<id>`),
  growth (`growth`) and the ally (`ally:<pair>`).
- *Wonder*: `(soul-wonder "<person>" "<app>" "<id>" "<idea>" "<status>" <at-ms>)` at
  `state:soul_wonder:<id>`; status `open` | `taken` | `let-go`. `(soul-wonder-offered "<person>" "<id>"
  <at-ms>)` at `state:soul_wonder_offer:<person>` is the last offer made to that person, and
  `(soul-wonder-last "<id>" <at-ms>)` at `state:soul_wonder_last:<id>` when each idea was last offered.
- *Browsing log*: `.runtime/browsing_log.jsonl`, lines `{"at", "tab", "domain", "title"}`, written by
  `main.js` only while `browsing_ally` is on; never for locked or app tabs; capped at 500 lines; deleted
  when the feature is switched off.

---

## A. The wonder jar

**M9-A1 — `wonder` tool.** `wonder.run(action, app=None, idea=None, id=None)`:
- `add` (app: a Foundry project or a plain app dir, as `brief` resolves them; `idea` ≤ 200 chars) →
  one `soul-wonder` atom with status `open`, id `wonder-<8 hex>`; returns `WONDER-KEPT: <id>`.
- `list` (optional app) → `Wonder jar (<n> open)` then `- <id> <app>: <idea>` lines, oldest first;
  `Wonder jar (0 open)` when empty. Only the current person's ideas.
- `take` / `let_go` (id) → status `taken` / `let-go`; returns `WONDER-TAKEN: <id>` / `WONDER-LET-GO:
  <id>`; unknown id → `ERROR: no idea <id>`.
The person is `soul_settings.person()`. Unknown action → `ERROR: action must be add, list, take or let_go`.

**M9-A2 — One back, rarely.** `iter/transformations/soul_wonder.py` (runs by name after
`soul_taste.py`): when `wonder` is on for the person, the mode is not `quiet`, at least one of their
ideas is `open`, no `wonder:` topic card is outstanding (a `soul-card-topic wonder:*` without a matching
`soul-topic-pick`), and the dial's cooldown has passed since their last `soul-wonder-offered`
(whisper 24 h, occasional 4 h, chatty 1 h; a first offer needs no wait), it appends to the last system
message:
```
## Wonder
One kept idea you may offer back now, as an offer card with topic wonder:<id> and choices take /
keep / let_go: <app>: <idea>
```
and records `soul-wonder-offered` for the person and `soul-wonder-last` for the idea (one transaction).
The idea chosen is the open one offered longest ago by `soul-wonder-last` (never offered first; ties by
age). Any other cycle it adds nothing. With `wonder`
off, or in quiet mode, it adds nothing and reads nothing.

**M9-A3 — Picks fold back.** `soul_taste.plan` emits `soul-topic-pick` for every pick on a card that
has a `soul-card-topic`; for `wonder:<id>` topics a `take` pick sets the idea's status to `taken`,
`let_go` to `let-go`, `keep` and `dismiss` leave it `open`. A `let-go` or `taken` idea is never
offered again. Nothing else in the reducer changes.

**M9-A4 — Honest count.** `authority_counts` adds `soul_wonder_open`; the Soul card shows
`wonder <n> open` when non-zero.

---

## B. Service before growth, with a voice

**M9-B1 — The deferral asks.** In `auto_improve.transform`, when `_service_before_growth_active()`
and the pain is at or above the threshold, the proposal is written to `memory/.improve_pending` (never
`.improve_needed`) and the appended note tells Iter to ask once, as an offer card with topic `growth`
and choices `now` / `later`: `I'd like to work on <worst tool or signal> for myself. Now, or later?`
It asks at most once per 24 h (`memory/.growth_asked` holds the last ask's time) and never while a
`growth` card is outstanding.

**M9-B2 — The person's answer is honored.** A `soul-topic-pick growth now` newer than the flag's
`expires_at` origin (its file mtime) lets this cycle proceed as if not deferred: the proposal goes to
`.improve_needed`, the cooldown is set, `.improve_pending` is removed. `later` keeps the deferral and
no further ask for 24 h. No pick: the existing behaviour (deferred, one note) stands. The flag file
itself is never touched by `auto_improve` (it belongs to `cognitive_resilience_guard`). Nothing here
gates Iter: a person who says `now` is choosing, not approving.

**M9-B3 — Without the flag, nothing changes.** The pre-M9 path (pain → `.improve_needed` + cooldown;
no pain → flag cleared) is byte-for-byte the same.

---

## C. The browsing ally (off by default)

**M9-C1 — `bridge/browsing_ally.js` is pure.**
- `suggestLock(url, title)` → `{reason}` or `null`. Conservative: hostname matches a bank/brokerage/
  payment/crypto list or contains `bank`/`banking`; a webmail host (`mail.google.com`, `outlook.live.com`,
  `outlook.office.com`, `mail.proton.me`, `mail.yahoo.com`, `icloud.com` with `/mail`); a health portal
  (`mychart`, `patient` in the host, or a `.gov` host with `health`/`medicare`/`irs`/`ssa`); reasons
  `looks like your bank` / `looks like your mail` / `looks like a health or government account`.
  Never for `localhost`, `file:`, or IterBrow's own pages.
- `shouldLog(tab, on)` → true only when `on`, the tab has no `appScope`, is not locked, and its URL is
  `http(s)`.
- `compassState(history)` → `{live, pair}` where `live` is true iff the history holds an Iter message
  with a card whose `topic` starts with `ally:` and no later user message with `choice.card` equal to
  that card's id. (`validCard` keeps `topic` when it matches the topic pattern.)
- `recentBrowsing(lines, now, windowMs = 30 min, limit = 8)` → `[{domain, minutes, title}]`, dwell
  from consecutive entries, newest first, merged per consecutive domain.

**M9-C2 — Wiring in `main.js`.** With `browsing_ally` on for the saved person: on tab activation and
`did-navigate` of a loggable tab, append to `.runtime/browsing_log.jsonl` (cap 500 lines, oldest
dropped); when a loggable tab's URL gets a `suggestLock` reason and the host was not already declined
this session, send `ally:suggest {tab, reason}` to the toolbar once per host; `ally:lock {tab}` locks it,
`ally:decline {host}` remembers the decline for the session. On `soul:save` with `browsing_ally` off:
delete the log. Compass: on every chat-history change, `compass:state` to the toolbar from
`compassState(chatBridge.history())`; `{live: false}` always when the feature is off.

**M9-C3 — Toolbar.** `#ally-notice` (hidden; text, `#ally-lock` "Lock it", `#ally-no` "No") and
`#compass` (`✦`, hidden unless the feature is on; class `live` while a pair is live; title
`A pair is live — Iter has handed you a choice` / `Compass`). Nothing else in the toolbar changes.

**M9-C4 — `soul_browsing.py`.** When `browsing_ally` is on and the mode is not quiet, appends
`## Browsing (ally)` with ≤ 8 lines `<domain> · <minutes> min · <title>` from the last 30 minutes of
the log and the rule: send a pause card (kind `offer`, topic `ally:<pair>`, pair one of
`wonder-time` (WonderPreservation / TimeCoherence) or `wonder-shared` (WonderPreservation /
SharedUnderstanding)) only when such a pair is live in what they are doing; hand the choice back;
otherwise say nothing; at most one ally card per 30 min (none while one is outstanding). Off, quiet, or
an empty window → nothing.

**M9-C5 — Honest count.** `authority_counts` adds `soul_ally_cards` (topic picks whose topic starts
with `ally:` plus outstanding ally cards is not needed: count `soul-card-topic` atoms with `ally:`).

---

## D. Find-in-page

**M9-D1 — Toolbar bar.** `#find-bar` (hidden) with `#find-text`, `#find-count` ("3 of 12" or "no
matches"), `#find-prev`, `#find-next`, `#find-close`. Typing sends `find:query {text}`; Enter / next →
`find:next`; Shift+Enter / prev → `find:prev`; Esc / close → `find:close` and hides the bar.
`find:open` from main focuses the bar with its text selected.

**M9-D2 — Main.** View menu: `Find…` `CmdOrCtrl+F` → `find:open` to the toolbar. Handlers call
`activeTab().view.webContents.findInPage(text, {findNext, forward})`, forward `found-in-page` as
`find:result {active, total}`, and `stopFindInPage('clearSelection')` on close. Works on locked tabs
(it is the person's own action, not Iter's). Switching tabs closes the find.

---

## E. End-to-end (real loop, real service, fake model)

**M9-E1** — wonder: `wonder add` through the loop → the next request carries `## Wonder` with the idea
and `topic wonder:<id>`; a simulated `take` pick (card with that topic sent by the loop, click via the
bridge) → status `taken`, `soul-topic-pick` present, and no `## Wonder` in later requests; browsing:
with `browsing_ally` on and a seeded log, the request carries `## Browsing (ally)` with the domains;
with it off, neither the block nor the log exists. Nothing leaks outside `state:soul_*`.

## Out of scope (next)

The app inheriting the ally (M10); bookmarks, reader mode, history search (browser track II); the Muse.
