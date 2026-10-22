# Milestone 15 — The build ledger: a loop that never wedges, and an atom space that remembers the build

Status: **implemented 2026-10-21 (A, B, C; D deferred; E is Berton's two bench runs).** Base: M6–M14.
Tests: `tests/test_m15_{budget,tools,ledger,check}.py` and `tests/e2e/test_m15_loop.py` (30 tests, none pending;
`test_m15_worker.py` is deferred and skipped unless `ITERBROW_M15_WORKER=1`); helpers in `tests/m15_support.py`;
fixtures in `tests/fixtures/m15/`. Commits: `M15-A`, `M15-B`, `M15-C`, then the suite fixes and these notes.

## Implementation notes (2026-10-21)

**What Berton does on the Mac.** Nothing to install. Quit and reopen IterBrow: the contract check lives in the
browser process, so Stop/Start alone would leave every ledger line at "no check". Then run the bench (E1): the 2026-10-21 deepseek run (0 cycles,
blocked) already serves as the "before"; one "after" run with the same model fills the table in
`docs/bench/README.md`. Watch the first build's `.runtime/last_prompt.json`: the system prompt ends with a
`[build ledger <app>] …` line once Iter has opened the app.

**Numbers.**
- Calibration: Berton's four logged gpt-6-luna pairs give a median provider/estimate ratio of **0.5559**, so a
  request the old estimator called 47,224 tokens is now ~26k against the 45k target. 1.0 until three answered
  requests exist for a provider+model (`.runtime/model_usage_calibration.jsonl`).
- Tool schemas: all 84 tools **17,255 → 13,893** estimated tokens (uncalibrated); the build view (42 tools)
  is ≈ 7.06k; every DESCRIPTION ≤ 280 characters.
- A ledger observation (facts + MeTTa conclusions through the one-shot worker + one transaction) takes
  ≈ 0.45 s; it runs only on `browser_open_app` and `app_probe` of a vault app. build_mode reads atoms each
  cycle (no MeTTa).

**Deviations and why.**
- A2's third degrade step drops whole exchanges and runner observations older than the third-newest assistant
  turn from the request copy (the 9k of "runtime observations" in the 2026-10-21 block were parked exchanges
  the projection creates, so dropping only runner messages would not have shrunk them). Experience is
  untouched; a plan that still does not fit blocks with the notice.
- A3: one notice per block, and again only after a new message from the person (a "Hello?" to a blocked Iter
  is answered with the reason instead of silence). The heartbeat and retry-on-change are as before.
- B1 (audit): the build view also carries `episodes`, `record_episode` and `reminder` — the Recap Request and
  nop's own text ask for them mid-build, and a tool the prompt names but the request lacks costs cycles. That
  puts the build view at ≈ 7.06k, so the test bound is 7.2k.
- C1 (audit): the bridge reloads the app after the check whenever a submit button was clicked, not only when
  storage changed — a handler that adds an empty item to in-memory state leaves no trace either.
- B1: the chat view hides the five build-only tools even though they are in `PROTECTED_TOOL_NAMES` (the test
  and B1 require it); `PROTECTED_TOOL_NAMES` still governs the load cap and A2's degrade.
- B2: 70 descriptions were rewritten, not twelve: the ≤ 14k all-tools estimate needs an average near 175
  characters.
- C3: conclusions are computed by the one-shot worker over exactly the app's merged facts
  (`build_ledger.worker_run`), not `metta_server.query(view="current")`. The rendered line then never depends
  on the store having taken the facts, and the rules see only this app. The seed is still declared, so
  `!(ledger-next todo)` works from Iter's own `metta` tool.
- C1 storage is attributed, not listed: all file:// apps share one localStorage (mapstation's `iterMapCache`
  would have been "storage other" for every app). `other` is the keys the page wrote while the check or a
  probe ran (a recorder the check installs); `prefixed` counts keys under `iter:<app>:`. Storage the check's
  submit clicks changed is put back and the tab reloaded, so opening an app never leaves an empty item behind.
  The check runs only for vault apps (never mapstation, crm …) and never on a locked tab.
- C2: ask facts grow while the app is built (a message that scrolled out of the request still asked for it);
  `new_app` and an app gone from the vault clear them. A changed mind ("drop the delete button") is not read;
  that requirement stays until the app is recreated.
- C6: `edit_keeps_passing` is learned from a probe that follows a re-open after an earlier run (the ledger
  has no edit facts by design).
- The ledger only talks to `ITER_METTA_SOCKET` (never the legacy default socket), so a test run on the Mac can
  never touch the live store.

**After the first real run (audit 2026-10-22, bench of 2026-10-21: 3 built, 4 kept, 0–1 theatre; 44 ledger
observations).** The ledger caught todo's real defect (items kept under a non-prefixed key — the bench's "built: no")
but three precision faults held every app at `next: build` and taught NACE `probe_before_report` is worthless:
`\btodo\b` matched `#todo-col` in the kanban ask (todo's ledger demanded kanban's ids), the "last message before
the first touch" fallback attributed the kanban ask to mapstation, and a missing `data-iter-ready` was a contract
breach although M13 made the flag reported-never-required; elements that only exist after the person acts (`.card`)
were "missing" even when a passing probe had exercised them. Fixed: the app's name must stand alone and the
fallback is the message before `new_app(<app>)`; ask facts are replaced by the recomputed set when it differs
(empty — the ask rotated out — changes nothing); `ready` is a fact, not a breach; a selector covered by a passing
run since the newest open counts as present and visible. The NACE belief NACE formed from the bad runs stays
NACE's to revise.

**Test fixes** (each in its commit message): calibration expected 0.5517, the median is 0.5559; the A2 e2e pad
is 90,000 chars (45,000 stopped crossing the target once B shrank the schemas); the check tests run in file://
pages (`run_in_file_page`) and assert attributed storage; the C e2e iterated `read_atoms`' keys instead of its
atoms; M14 tests that compared a vault write's whole result line compare the part before the new reminder;
`build_ledger.py` was created with A because `M15_IMPLEMENTED` keys on it.

## Why — what the three benchmark runs actually said

Berton's direction (2026-10-21): stop thinking about models; make the loop solid end to end and put native
reasoning in the atom space that IterBrow has and other agents do not; no new features. The runs agree —
every failure so far was mechanical, and the one clean case (notes on 2026-10-20: built, iterated, kept,
3.3 min, 16 cycles, zero theatre) shows what the same model does when nothing is in the way.

1. **The loop wedges silently at the token ceiling.** 2026-10-21, deepseek via OpenRouter: five asks, 75
   minutes, 0 cycles. The heartbeat: `request_blocked — RequestBudgetExceeded: Protected input estimates
   47224 tokens, above the 45000 input target (system 19695, tool_schemas 16993, runtime_observations
   9176, user 1087, images 1) … Automatic retries paused. Waiting for new input or a runtime revision.`
   Nothing reached the chat; Berton's "Hello?" went unanswered. On gpt-6-luna the same estimate was
   already 44,204 of 45,000 on 2026-10-19. The **ceiling is settled** (45k) and stays; what is wrong is
   the measurement and the silence: the estimator (`bytes/3 + per-message framing`) reports **about 1.8×
   the provider's own count** (estimated 42–44k where OpenAI billed 22–25k input tokens, every logged
   cycle), and 84 tool schemas with descriptions up to 500 characters are 17k of the estimate on every
   request, build or chat.
2. **The build's state lives only in the transcript, and the transcript is being cut.** `omitted_history_
   messages: 500` under the budget. Each cycle the model re-derives what it built, what the last probe
   said and what is left — the source of re-reading files, re-probing, "tracing the handoff", and of
   reporting a scaffold as done (convert, 2026-10-19).
3. **The last second per cycle is the isolated query worker** (deferred, see D). `metta_reasoning` (1.0 s) and the courier's
   cross-check each rebuild a Hyperon space from the snapshot in a subprocess. It is also why nobody adds
   per-cycle MeTTa reasoning: each query costs a second.
4. **Theatre and the fork card are the model's habits, not mechanics** — 2 progress notes per app before
   the report; no fork card in three runs (the briefs say exactly what to build, which the loop text
   allows). Nothing in this milestone targets them beyond what the ledger makes unnecessary.

Principles unchanged (`CLAUDE.md`): nothing gates or vetoes; the 45k ceiling is not raised; NACE's tracker,
courier and episodic memory untouched; a feature that is off leaves no trace; no new UI.

## Decisions

- **D5 — calibration, not a bigger ceiling.** The estimator learns its ratio from the provider's own
  reported usage (every request logs `input_tokens`); the 45k target applies to the calibrated estimate.
- **D6 — tools are projected per request, never removed.** The tool list the model sees is a view (what
  `dynamic_tool_budget` already does for unreliable tools); every tool is back on the next cycle.
- **D7 — the ledger is derived, never authored by the model.** Facts come from observing the running app
  and from what the ask literally names; conclusions come from MeTTa rules; the model only reads the result.
- **D8 — observe, don't parse; reason when facts change, read when prompting** (section C).

## Test seams

`iterbrow_runtime/request_budget.py`: `calibration(records) → ratio`, `degrade(components, limit) →
plan` (pure); `iter.py`: `blocked_notice(error)` (pure text); `iterbrow_runtime/tool_view.py`:
`view(tools, mode) → tools` (pure); `bridge/page_scripts.js`: `checkScript(spec)` (pure, Playwright-tested); `iterbrow_runtime/build_ledger.py`:
`facts_from_ask(app, text)`, `facts_from_check(app, check)`, `facts_from_probe(app, result, probe_json, seq)`,
`conclude(app, run)`, `render(app, conclusions)` (pure); `seeds/build_ledger.metta` (rules, run through the
existing one-shot worker — `m15_support.run_metta`).

## A. The request never wedges silently

Files: `iter/iterbrow_runtime/request_budget.py`, `iter/iter.py`, `iter/channels/electron_ui.py` (no change
expected), `scripts/foundry_bench/bench.py`.

- **A1 — calibrated estimate.** `request_budget.calibration(records)`: from the last 20 `[model usage]`
  records that carry both the pre-send estimate and the provider's `input_tokens`, the median ratio
  `actual / estimated`, clamped to [0.4, 1.2]; 1.0 with fewer than 3 records. `project_request` applies it
  to the estimate it compares with the 45k target, and the `[request budget]` line gains
  `"calibration": <ratio>` and `"calibrated_input_tokens"`. The loop stores `(estimate, actual)` pairs in
  `.runtime/model_usage_calibration.jsonl` (manifest: cache, reset). Per provider+model, since tokenizers
  differ. The ceiling and `DEFAULT_INPUT_TOKENS` are unchanged.
- **A2 — degrade before blocking.** When the protected set still exceeds the target, `degrade(components,
  limit)` returns an ordered plan the loop applies: (1) unprotected tool schemas out of this request
  (`PROTECTED_TOOL_NAMES` stay; `tool_view`, B, decides the order), (2) tool descriptions cut to their
  first sentence, (3) runtime observations beyond the newest 3 exchanges out, (4) only then
  `RequestBudgetExceeded`. The `[request budget]` line records `"degraded": [...]`.
- **A3 — a blocked request is said, once.** When the loop does block, it sends one line to the person on the
  channel — `blocked_notice(error)`: *I can't send this request: it is ~N tokens over the 45,000 I work
  within (tool schemas X, system Y, observations Z). I'll retry as soon as anything changes; a shorter
  ask or fewer open tools helps.* — writes `phase: request_blocked` as today, and retries on every new
  input as today. Never a second notice for the same block.
- **A4 — the bench sees it.** `bench.py preflight()` refuses to start while the heartbeat phase is
  `request_blocked`, and `wait_report` ends the app early with `reason: "request_blocked"` when the
  heartbeat enters that phase, instead of waiting out the silence.

Build notes: `calibration` and `degrade` are pure functions in `request_budget.py` (the tests call them with
synthetic numbers); `project_request` gains a keyword `calibration_ratio=1.0` and its report dict (the third
return value) gains `calibration` and `calibrated_input_tokens`. The loop writes one `{"estimated", "actual",
"provider", "model"}` line per answered request. `blocked_notice(error)` is a module-level pure function in
`iter.py` that parses the `RequestBudgetExceeded` text (the test runs its source on its own); keep a
module-level flag so one block is announced once. The e2e pads the system prompt with a fake transformation
(`ITER_E2E_PAD` characters): 45,000 chars must degrade and still send; 400,000 must block and announce once.

Tests: `tests/test_m15_budget.py` (calibration from synthetic records; degrade order; the notice text;
an e2e in `tests/e2e/test_m15_loop.py` with a fake model whose tool list is padded until the estimate
crosses the target: the request still goes out, degraded, and no notice; then padded past any degrade:
one notice in the outbox, `request_blocked` in the heartbeat).

## B. The tool list is a view

Files: `iter/iterbrow_runtime/tool_view.py` (new), `iter/transformations/dynamic_tool_budget.py` (calls it),
`iter/tools/*.py` descriptions, `iter/iter.py` (`MAX_TOOL_DESCRIPTION_CHARS`).

- **B1 — two views.** `tool_view.view(tools, mode)` with `mode` = `"build"` when `build_mode.active`
  (messages) else `"chat"`: build offers the builder's set (file tools, run_tests, shell, python, the
  browser actions and eyes, new_app, app_probe, app_rollback, apps, github, websearch, card, brief,
  ally_sdk, send, nop, task_state, remember, memory tools) and hides the rest; chat hides the build-only
  tools (file tools stay — they are protected). Hidden means not in this request; `PROTECTED_TOOL_NAMES`
  are never hidden; every tool is offered again next cycle. The view is logged once per switch
  (`[tool view] build: 34 of 84 tools`).
- **B2 — descriptions fit.** Every `DESCRIPTION` ≤ 280 characters (the twelve over 400 today rewritten,
  tables regenerated); `MAX_TOOL_DESCRIPTION_CHARS` = 300. The schema estimate for the build view is ≤
  7k before calibration (asserted by a test that serialises the real tools the way `_estimate_cost` does).

Build notes: `tool_view.view(tools, mode)` keeps order and the dicts (filter, never copy-and-edit); an unknown
mode returns the list unchanged. Apply it in `dynamic_tool_budget` (it already edits the tools list) using
`build_mode.active(messages)`. Rewrite the twelve descriptions over 400 characters first; the estimate test
serialises the real tools with `request_budget.estimate_input_tokens`.

Tests: `tests/test_m15_tools.py`.

## C. The build ledger — observed in the running app, reasoned when facts change, read every cycle

Files: `bridge/page_scripts.js` (`checkScript`, pure), `bridge/browser_bridge_server.js` (`openApp` and
`probe` run it), `iter/iterbrow_runtime/build_ledger.py` (new), `iter/seeds/build_ledger.metta` (new, declared
in `state_manifest.json` like the other seeds), `iter/tools/{browser_open_app,app_probe,new_app}.py` (record),
`iter/tools/{write_file,edit_file}.py` (a one-line reminder, no facts), `iter/transformations/build_mode.py`
(ask facts, render), `iter/iterbrow_runtime/local_apps.py` (drop facts of apps that are gone).

Three decisions (2026-10-21), each removing a family of failure vectors from the first draft:

- **Observe, don't parse.** Facts about the app come from the page running in IterBrow's own browser,
  never from reading its source: any framework, any file layout, any handler style gives the same exact
  answer. The first draft's regex extraction of listeners, forms and selectors (best-effort, wrong in
  known ways) is gone.
- **Precision over recall on the ask.** The ledger claims only what the ask literally names, and says so.
  A loose ask yields fewer requirements, never wrong ones.
- **Reason when facts change; read when prompting.** Conclusions are derived by MeTTa at observation time
  (a handful of times per build, through the existing one-shot worker) and stored as atoms; each cycle
  `build_mode` reads atoms (`read_atoms`, milliseconds). No per-cycle query, so no warm worker is needed.

- **C1 — the contract check, in the page.** `page_scripts.checkScript(spec)` with `spec = {appId,
  selectors: [...]}` evaluates in the app tab and returns `{selectors: {sel: {present, visible}}, ready,
  storage: {prefixed: n, other: [keys…]}, scripts: [external hosts], forms: [{selector, guarded}],
  placeholder, title}`. `guarded` is measured, not guessed: a bubbling `submit` listener on `document`,
  registered by the check (so it runs after the app's own handlers), reads `event.defaultPrevented` when
  the check clicks each form's submit button, and calls `preventDefault()` itself so the page never
  navigates; forms without a submit button are skipped. The bridge's `openApp` runs it after the load
  and `probe` runs it before the steps; both return it as `check`. Tested in Playwright over
  `tests/fixtures/m15/*.html` served as pages.
- **C2 — facts.** `build_ledger.facts_from_ask(app, text)` → `(ask-requires app "<selector>")` for every
  `#id`/`.class` token the ask contains and `(ask-requires app persist)` for "persist"/"reload"/"remember";
  nothing else, ever. `facts_from_check(app, check)` → `(app-has app "<sel>")`, `(app-visible app
  "<sel>")`, `(app-ready app true|false)`, `(app-stores app prefixed|other)`, `(app-script app external
  "<host>")`, `(app-form app "<sel>" guarded|unguarded)`, `(app-placeholder app present|gone)`.
  `facts_from_probe(app, result, probe_json)` → `(probe-run app <seq> passed failed)`, `(probe-assertion
  app <seq> "<kind sel>" passed|failed "<got≠expected>")`, and `(probe-covers app "<sel>")` for every
  selector a step or assertion of `probe.json` touches. `(app-opened app <seq>)` on each open.
  Keys `state:build:<app>:<family>:<n>`; each observation replaces the app's whole family (`remove` the
  previous keys, `add` the new ones, one transaction), so nothing is stale and nothing accumulates.
- **C3 — conclusions, in MeTTa, at observation time.** `seeds/build_ledger.metta` derives, over the
  app's facts: `(missing app sel)` = asked, not present; `(hidden app sel)` = present, not visible;
  `(unproven app sel)` = asked, not covered by a passing assertion or step of a probe run since the newest
  open; `(regressed app assertion)` = failed now, passed in an earlier run; `(contract app ready|storage
  |placeholder|form "<sel>"|script "<host>")`; `(next app build|probe|report)` = report when nothing is
  missing, hidden, unproven, regressed or in contract breach, probe when the only gaps are unproven,
  else build. `build_ledger.conclude(app, run)` composes the `!` lines, runs them through the one-shot
  worker (`metta_server.query`, view `current`) and stores the result as `(ledger app next …)`,
  `(ledger-line app "<rendered>")` atoms in the same transaction as the facts. Negation in MeTTa:
  `(if (== (collapse (match &self (app-has $app $sel) 1)) ()) $sel (empty))`.
- **C4 — the ledger in front of the model.** `render(app, conclusions)` → at most 8 lines, e.g.
  ```
  [build ledger todo] missing (from the ask's named ids): .delete · hidden: none · unproven: .toggle ·
  contract: form "#todo-form" unguarded, storage other · probe: 2 passed, 1 failed (count #list li: 2≠3)
  · next: build]
  ```
  `browser_open_app` and `app_probe` append `· ledger: …` (the render, one line) to their own result,
  produced from the observation in hand — so the truth reaches the model even if the store write failed,
  in which case the line ends `(not recorded)`. `write_file`/`edit_file` on `vault/<app>/` append only
  `· ledger: changed since last check — browser_open_app(<app>) to re-check`. `build_mode` reads
  `state:build:<app>:ledger` each cycle and appends the stored line to the prompt; when the newest file
  write is newer than the newest check it appends `[build ledger <app>: stale — re-check]` instead.
  Never a gate.
- **C5 — the catalog drops what is gone.** `local_apps.list_apps()` (run by the Apps menu and the `apps`
  tool) removes `state:build:<app>:*` for any app no longer in the vault; `new_app` clears them first.
  `app_rollback` leaves them (the next check replaces them).
- **C6 — NACE learns from builds, through the courier's queue.** At a report (`send` while the stored
  ledger says `next: report`) `queue_pattern("probe_before_report", "confirmed")`; at a report while it
  says otherwise, `disconfirmed`; at a regression, `queue_pattern("edit_keeps_passing", "disconfirmed")`,
  and `confirmed` when a probe after an edit keeps every earlier pass. Lines go to `nace_pending.metta`
  exactly as `idle_cycle_detector` writes its own; the courier creates the beliefs on first revision, as
  for `prioritize_user`. Courier and tracker code untouched (pinned by tests).

Build notes: `checkScript` is the only new page script; keep it in the shape of `probeScript` (an async
function serialised with `toString()`, a JSON spec, a bounded settle). The extractors are pure over
dicts; the rules are tested through `m15_support.run_metta` with the real engine; the one e2e builds the
unguarded fixture app in the vault under the real AtomSpace with no browser, so it covers ask facts, the
file-write reminder and the stale line — the check itself is Playwright-tested. A ledger failure anywhere
is caught and logged, never a tool failure.

Tests: `tests/test_m15_ledger.py`, `tests/test_m15_check.py` (Playwright), `tests/e2e/test_m15_loop.py`.

## D. The warm query worker — deferred

Not in this milestone. C reasons at observation time, so no per-cycle MeTTa query exists to make cheap;
the remaining per-cycle cost (`metta_reasoning` ≈ 1 s) is a separate item for a later milestone if it
still matters once A–C land. `tests/test_m15_worker.py` is kept as a scoped draft and is skipped unless
`ITERBROW_M15_WORKER=1`.

## E. The benchmark, run

- **E1 — two runs by Berton**, same five briefs, any model he likes, with `--baseline` before A–D and
  without after; `docs/bench/README.md` gains a "what changed" table template. The implementation notes
  carry both tables. The goal for the "after" run: five built, five kept, theatre ≤ 1 per app, no silent
  block, median cycles per app down from the baseline.

## Not in this milestone

Raising the ceiling; a fork-card requirement (watch it with an open-ended ask instead); any gate; new UI;
the Foundry project layer; model-specific prompting.
