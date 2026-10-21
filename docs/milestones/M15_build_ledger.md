# Milestone 15 — The build ledger: a loop that never wedges, and an atom space that remembers the build

Status: **scoped 2026-10-21, not implemented.** Base: M6–M14. Tests: `tests/test_m15_*.py` and
`tests/e2e/test_m15_loop.py` (written with the go); helpers in `tests/m15_support.py`. How to build it:
`CLAUDE.md`; check a section with `scripts/check_section.sh M15-A`. `M15_IMPLEMENTED` is keyed on
`iter/iterbrow_runtime/build_ledger.py` (C1). Implement A→E, one commit each.

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
3. **The last second per cycle is the isolated query worker.** `metta_reasoning` (1.0 s) and the courier's
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
- **D7 — the ledger is derived, never authored by the model.** Atoms come from parsing files, asks and
  probe results in Python; conclusions come from MeTTa rules; the model only reads the result.

## Test seams

`iterbrow_runtime/request_budget.py`: `calibration(records) → ratio`, `degrade(components, limit) →
plan` (pure); `iter.py`: `blocked_notice(error)` (pure text); `iterbrow_runtime/tool_view.py`:
`view(tools, mode) → tools` (pure); `iterbrow_runtime/build_ledger.py`: `facts_from_html(app, html)`,
`facts_from_ask(app, text)`, `facts_from_probe(app, result_text)`, `render(conclusions)` (pure);
`seeds/build_ledger.metta` (rules, queried through the existing `query` method with view `current`);
`metta_server`: `QueryWorker` with `apply(delta)` (tested with the fake MeTTa from `test_metta_service.py`
and with the real Hyperon for the timing assertion).

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

Tests: `tests/test_m15_tools.py`.

## C. The build ledger — the atom space as the working memory of a build

Files: `iter/iterbrow_runtime/build_ledger.py` (new), `iter/seeds/build_ledger.metta` (new, declared in
`state_manifest.json` like the other seeds), `iter/tools/{write_file,edit_file,new_app,app_probe}.py`
(record), `iter/transformations/build_mode.py` (render), `iter/tools/_files.py`.

- **C1 — facts.** Pure extractors, each returning `[(key, atom)]` for the store:
  `facts_from_ask(app, text)` — ids and classes the ask names (`#add`, `.toggle`), words that imply a
  requirement (`persist`/`reload` → `(ask-requires app persist)`, `dark mode` → `(ask-requires app
  "#theme-toggle")` when the ask names the id), as `(ask-requires app "<selector>")`;
  `facts_from_html(app, html)` — `(app-has-id app "add")`, `(app-has-class app "toggle")`,
  `(app-listens app "#add" click)` (`addEventListener`/`onclick`/`onsubmit` on an id, best effort),
  `(app-stores app "iter:app:")` or `(app-stores app other)`, `(app-ready-flag app true|false)`,
  `(app-form-submit app "#todo-form" unguarded)` when a form has no `preventDefault`, `(app-script app
  external "<host>")`, `(app-placeholder app present|gone)`;
  `facts_from_probe(app, text)` — from an `app_probe` result: `(probe-run app <stamp> n m)` and one
  `(probe-assertion app "<kind sel>" passed|failed)` each. Keys are `state:build:<app>:<fact>` so a new
  parse replaces the old (upsert) and `app_rollback`/deleting the app removes them.
- **C2 — recorded where the facts arise.** `write_file`/`edit_file` on `vault/<app>/index.html` (and
  `new_app`) transact `facts_from_html`; `app_probe` transacts `facts_from_probe`; `build_mode` transacts
  `facts_from_ask` for the newest person message that starts a build (once per ask, keyed by its hash).
  Every write is one `transact` through the existing client; a failure is logged and never fails the tool.
- **C3 — conclusions in MeTTa.** `seeds/build_ledger.metta` rules, evaluated with the existing `query`
  (view `current`), derive: `(missing app sel)` = asked and no matching id/class; `(unwired app sel)` =
  present, no listener, the ask names it as an action; `(unproven app)` = no probe run since the newest
  file fact; `(regressed app assertion)` = failed now, passed in an earlier run; `(contract app storage)`,
  `(contract app ready)`, `(contract app form-submit "#todo-form")`, `(contract app placeholder)`;
  `(next app probe|build|report)` = report when nothing is missing/unproven/regressed, probe when unproven,
  else build. One query per cycle in build mode (≈ 50 ms with D; without D the existing worker).
- **C4 — the ledger in front of the model.** `render(conclusions)` → at most 8 lines:
  ```
  [build ledger todo] missing: .delete, #theme-toggle · unwired: #add · contract: form-submit #todo-form
  unguarded · probe: 2 passed, 1 failed (count #list li: 2≠3) · next: build]
  ```
  `build_mode` appends it to the system prompt (replacing nothing; the loop text stays), and `write_file`
  /`edit_file`/`new_app` append a one-line `· ledger: …` to their own result for that app. When the ledger
  says `next: report` and the model sends, the report carries truth; when it says `missing`, a bare
  scaffold cannot read as done. Never a gate: the model may ignore all of it.
- **C5 — NACE learns from builds, through the courier's queue.** At each report (a `send` while the ledger
  says `next: report`) and at each regression, `build_ledger` appends `(pending-revision pattern
  probe_before_report confirmed|disconfirmed)` and `(pending-revision pattern edit_keeps_passing
  confirmed|disconfirmed)` to `nace_pending.metta`, exactly as `idle_cycle_detector` does today; the
  courier revises them on its normal cycle and the gate's advisory shows them. The two pattern names are
  seeded in `nace_substrate.metta`'s pattern list if absent. Courier and tracker code untouched.

Tests: `tests/test_m15_ledger.py` (extractors over the five bench apps' real HTML copied as fixtures and the
briefs' asks; rules with a fake query over fixed atoms and with the real engine; render; `app_probe` and
`write_file` results carry the ledger line in a throwaway ITER_DIR with the fake AtomSpace the e2e harness
provides).

## D. The warm query worker

Files: `iter/metta_server.py` (`QueryWorker`), `iter/metta_query_worker.py` (today's one-shot worker gains a
serve mode).

- **D1 — one worker per view, kept warm.** `QueryWorker(view)` starts the isolated process once with the
  view's seeds and atoms, then sends `{"apply": delta}` after every commit (the same delta `_rebuild_engine`
  computes, filtered to the view) and `{"query": code}` on demand; the worker answers on stdin/stdout
  JSON lines. The in-process engine, the journal and `query`'s result shape are unchanged; a worker that
  dies, times out, or whose applied state hash disagrees with the store's `view_hash` is discarded and
  the next query starts a fresh one (today's path). `status()` reports `query_workers: {view: pid}`.
- **D2 — measured.** With the real Hyperon at 20k atoms: a `current`-view query after one upsert ≤ 0.15 s
  (today ≈ 1 s); `[request preparation]` on the harness shows `metta_reasoning` under 0.2 s. Recorded in
  the implementation notes with the Mac's figures.

Tests: `tests/test_m15_worker.py`.

## E. The benchmark, run

- **E1 — two runs by Berton**, same five briefs, any model he likes, with `--baseline` before A–D and
  without after; `docs/bench/README.md` gains a "what changed" table template. The implementation notes
  carry both tables. The goal for the "after" run: five built, five kept, theatre ≤ 1 per app, no silent
  block, median cycles per app down from the baseline.

## Not in this milestone

Raising the ceiling; a fork-card requirement (watch it with an open-ended ask instead); any gate; new UI;
the Foundry project layer; model-specific prompting.
