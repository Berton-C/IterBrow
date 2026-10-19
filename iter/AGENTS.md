# AGENTS.md — Iter Agent Reference

> Living reference for any agent operating in this environment.
> Last updated: 2026-09-22. Keep this file current as systems change.

## Building and changing code
- Read with `read_file` (numbered lines, page with offset), find with `list_files` and `grep_files`.
- Change a few lines with `edit_file` (old text must occur once; copy it from read_file without the
  numbers). Create or replace a whole file with `write_file`. Paths are relative to iter/; `../` is the
  repo root (main.js, bridge/, tests/). `self_improve` is for tools/, transformations/, channels/ .py only.
- `shell` takes cwd (a folder in the repo) and timeout (seconds, max 170); its python3 is Iter's own.
- Test with `run_tests` (a tests/ path, or a -k expression). Its first line is RESULT: — read it before
  claiming anything works.
- Apps: a plain app is iter/<id>/index.html; a Foundry project is iter/apps/<id>/app.json with src/.
  An app opened from the Apps menu runs with the app preload (window.iterApp); a tab opened by URL does not.
  Open one yourself with `browser_open_app`, then `browser_wait_for` what should appear, then prove it
  with `app_probe` (steps + assertions) before saying it works.
  New apps go in the person's apps folder: `new_app` → vault/<id>/ (docs/APP_CONTRACT.md); `app_probe(<id>)`
  with no assertions runs the app's probe.json.
- Actions say what they hit (target) and where the page is now; they act only on the displayed tab.
  `browser_tabs` shows which tab is your target. Check UI with `browser_eval` against real DOM, never from
  a screenshot alone. A tab the person locked refuses actions; that is their choice, not a failure.

## Prompt memory (memory/ files)
Each cycle iter.py shows memory/ text files (rule: `tools/_memory_projection.py`), in full or as
head+tail excerpts within MAX_MEMORY_CHARS: memory/tasks/ (current_tasks.txt first); files whose
path mentions instruction, preference, standing, policy, user_feedback or lesson; files whose name
matches words of the current request (anywhere under memory/; `tabstrip` matches "tab strip"); and
up to two short excerpts of other files whose text matches the request. Every other text file, and
every file that cannot be shown (binary, non-UTF-8, unreadable), is listed by path in
`memory/index (request view only)`. Dot-files and storage (archive/, recap/, tiers/, captures/,
backups/, journals) are never listed. The view never changes anything on disk; read files directly.

## Authoritative Runtime Architecture (2026-09-21)

### Direct OpenAI provider — September 24, 2026

Settings offers OpenRouter, direct OpenAI GPT, and LM Studio independently.
OpenAI uses Responses with low/medium/high reasoning, separate credentials,
and the current Luna/Sol/Astra cost tiers in `iterbrow_runtime/openai_models.json`.
It feeds the existing tool loop; it is not a second agent. Provider-specific
reasoning metadata is adapted in request copies, never removed from experience.
OpenAI output ordering, phase, call IDs and encrypted reasoning are retained for
continuation; switching back to OpenRouter preserves ordinary actions/results.
`store=false` avoids depending on a server-stored conversation. Existing context
projection can still park oversized exchanges; direct OpenAI is not a claim that
that limitation is repaired. Last-request token usage/time and a labeled standard
text-price estimate are visible in Settings. The 45k ceilings remain. Memory
embeddings retain the existing OpenRouter credential/configuration. No automatic
provider fallback, model escalation, paid startup probe or extra approval flow.

### Current six-stage pass — September 24, 2026

The refined question-first PoC is approved, implemented through ordinary model
context, not a separate native governor. The 17 question groups guide the LLM's
interpretation of actual work; existing memory/tools supply recall, investigation,
observations and saved lessons. No mandatory forms, extra critic loop, fixed
alternatives or repeated ordinary approvals. Completion reminders ask for the
actual request's observed results and never remove send to obtain a phase label.
Tool execution status is not proof that the user's requested outcome is complete.
The six-stage sequence in the integrated build control supersedes the older hold.

### Historical direct repair pass — September 24, 2026

The active eight-stage repair pass is at the top of the existing integrated
build control document. The question-driven PoC remains parked. Ordinary app
repairs, like ordinary self-repairs, do not require PWQ; explicitly selected
cards still bind their approved scope and revocation.

NACE revisions are computed by native MeTTa from canonical AtomSpace beliefs,
then committed before compatibility projections advance. Native failure retains
pending observations rather than inventing a revision or vetoing unrelated work.
Internal read caches invalidate on committed state and source-rule changes.
`nop(wait_seconds=0)` waits for input, alarms or a component revision while the
external heartbeat remains live. Use a positive wait_seconds for timed autonomous
follow-up; do not repeatedly call the model merely to report intentional idle.
45k request limits are ceilings, not spending targets. Prompt memory is selected
for relevance; omitted material remains retrievable. Rotated history and exact
pre-consolidation tier text remain under memory/archive, excluded from prompts.

### Restoration correction — September 23, 2026

Ordinary work runs through Iter's existing loop and tools. The separate foundry
submit/decide/execute workflow, fixed alternatives and Atlas labels are no longer
requirements. The historical foundry client is retired; its shared app storage,
named-space and evidence services are preserved, not replaced by another executor.
Build Tracking is a builder report, not a prerequisite for executing ordinary work.
The active delivery plan is `../docs/ITERBROW_INTEGRATED_BUILD_CONTROL.md`.

Self-repair uses `self_improve apply/full_loop`: backup, validate, activate and
recover through the ordinary loop. No PWQ card or Atlas label is required.
When the user explicitly assigns work through a card, supply its proposal_id;
the selected card's approval and scope remain binding. Original Soul lock and
memory protections remain; file-backed repairs outside managed components use
the original backup/validation/revert path, not a component hot-load claim.
Exact-candidate cards remain optional for explicitly one-off activations. Stop, revocation, tab locks,
actual health checks and exact rollback remain effective. A progress-report failure
is not a runtime failure and cannot trigger rollback. These corrections supersede
conflicting historical workflow wording below. The question-driven PoC is parked.

The browser-control bridge follows the same ownership principle as the
AtomSpace endpoint: the Electron main process and its supervised Iter child
share one checkout-scoped `ITER_BRIDGE_SOCKET`. Startup probes an existing
path and never unlinks a responsive listener. The legacy global
`/tmp/iter-browser-bridge.sock` is only a direct-tool fallback, not the source
application's canonical endpoint. A source main-process change requires a
controlled application restart; never start a parallel `npm start` to pick it
up.

The PWQ subprocess service also resolves its ledger and projection from the
canonical `ITER_DIR`, never from the location of its executable module. This is
required for packaged workspaces and isolated recovery tests; moving code must
not fork human-agency state.

This section supersedes any older historical wording later in this file that
calls a `.metta`, JSON, text, or Chroma file authoritative.

- The canonical mutable cognitive state is the journaled AtomSpace service in
  `metta_server.py`, backed by `.runtime/atomspace/`. Hyperon is its current
  native reasoning engine. It is rebuilt from declared source seeds plus the
  committed journal; there is no recursive `.metta` directory scan.
- `state_manifest.json` is the ownership and portability registry. Source
  seeds are code, not mutable state. Files such as `nace_beliefs.metta`,
  `task_state.metta`, Soul JSON, reliability JSON, semantic-memory JSON, and
  `space.metta` are compatibility, index, or display projections while their
  domains migrate. New state must commit through `cognitive_events.py` first.
- `tools/metta.py` performs isolated read-only evaluation against a named
  AtomSpace commit. `tools/atomspace.py` is the structured durable mutation
  surface. Never persist state by embedding an add/remove inside a query.
- PWQ supports human agency: Iter proposes; the human approves, rejects, modifies
  or reorders. Approval covers the stated work scope, not a new signature for
  every subordinate revision. Current approval/revocation remains authoritative.
  Optional exact-candidate cards support distinct owner/guardian roles; technical
  validation never substitutes for the user's consent.
  `iterbrow_runtime/pwq_protocol.py` is the sole writer. The board may read the
  projection and submit narrow version-bound commands only; it has no whole-board
  synchronization or filesystem-write capability. Active work pauses before scope
  modification or rejection, and authorization-bound resume restores its exact
  pre-pause state. `.runtime/pwq.json` and `pwq.html` are projections/clients.
- Runtime self-extension never writes a live component directly. `self_improve`
  and `revision_control` use complete immutable generations under
  `.runtime/hotload/`. Fixed checks do not import candidates. self_improve also
  runs the existing registered regression checks against candidate components.
  Ordinary repair does not require a card; explicitly selected PWQ work retains
  its consent checks. Atlas labels and reports are not prerequisites.
  `iter.py` pins one generation per cycle. Electron—not candidate code—observes
  `.runtime/recovery/iter_heartbeat.json`, promotes healthy probation, and rolls
  back an exited, stalled, errored, wrong-generation, or hash-mismatched candidate
  before restart. `iterbrow_runtime/hotload_manager.py`, `main.js`, AtomSpace/PWQ
  authority, this file, and the Build Atlas are outside the self-modifiable surface.
- The user's Iter Start/Stop choice is durable lifecycle intent. Start survives a
  clean Electron restart and recovery restart; explicit Stop remains stopped.
  Recovery must not create a second Iter process or a second supervisor.
- Immutable generations relocate component code, never application state. A
  hot-loaded component must resolve runtime queues/stores from the canonical
  Iter root (`ITER_DIR`, or the Iter process cwd for direct launches), not from
  its generation-local `__file__`. In particular, Electron and
  `channels/electron_ui.py` share only `.runtime/electron_ui/` under that root.
- Sidebar chat delivery is durable application state, not proof-by-transient
  queue file. Electron journals accepted messages to
  `.runtime/electron_ui/messages.jsonl` before acknowledging Iter output; the
  renderer replays/deduplicates stable message IDs after reload. Inbox, outbox,
  and staging remain transient caches and must be published atomically. A
  successful `send` tool call or an empty outbox does not by itself prove that
  the user saw a reply; visible acceptance requires the labeled UI round trip.
  macOS lock/resume is also a native-view lifecycle boundary: Electron sends a
  resume reconciliation event and invalidates/re-presents the sidebar view,
  while the renderer refreshes chat, Iter status, and activity state together.
  A current inspected DOM is not proof if the displayed native frame is stale.
- Tool reliability is committed to the AtomSpace in bounded deterministic
  batches before its JSON and NACE compatibility projections advance.
  `transformations/.runtime/tool_reliability_pending_batch.json` is the exact
  replay record for an interrupted batch. The NACE queue carries adjacent
  `tool-reliability-event` markers so recovery cannot double-revise a tool;
  `nace_courier.py` removes each marker with its consumed revision.
- Build Tracking describes the builder's progress and open questions. It is
  not required paperwork for Iter's ordinary loop. Existing engineering atoms
  and evidence are retained; the old foundry workflow is not a build prerequisite.
- Export/import/reset are coherent lifecycle operations. Iter pauses, the
  AtomSpace quiesces/checkpoints, only manifest-approved portable state moves,
  and cognition resumes only after replay and engine reconstruction succeed.
- A packaged `.app` contains a state-free allowlisted Iter template. First launch
  atomically copies it to the per-user writable workspace, which becomes
  canonical `ITER_DIR`. Never place settings, `private/`, AtomSpace/PWQ/hot-load
  ledgers, experience, memories, indexes, projections, or queues in application
  resources. Source mode continues to use the checkout directly. See ADR-0007.
- DAS is an optional downstream adapter/projection target. It is not the
  canonical IterBrow AtomSpace API and may never be required for a canonical
  commit to succeed.
- The current restoration/PoC sequence is in
  `../docs/ITERBROW_INTEGRATED_BUILD_CONTROL.md`. The Atlas is the technical
  inventory and history, not a document Iter must reread before ordinary work.

## Kernel Repair (2026-09-10)

### Request allowances (2026-09-23)

The user requested 45,000 input/context and 45,000 output tokens per model
request. `iter.py` supplies `max_tokens=45000` for output. After transformations,
`iterbrow_runtime/request_budget.py` budgets the COMPLETE outbound messages/tool
schemas/reasoning metadata against a 45,000-token **estimate**, not a promise of
exact provider tokenization. It projects copies, retaining system/developer
instructions, tool schemas, all supplied user messages and final directives.
Follow-up instructions do not displace the original request from this projection.
Older whole exchanges may leave the request copy only. If needed, oversized
ordinary assistant content is retained with an explicit retrieval reference.
When a completed assistant/tool exchange itself cannot fit, its exact original
calls, results and reasoning are saved in the existing retained-output store;
the request copy receives explicitly historical result previews and retrieval
references instead of that whole exchange. Unfinished exchanges cannot be parked.
No action is replayed to retrieve its result. Durable experience, semantic memories
and episodic stores are never edited by this operation. Failed retention or an
oversized protected remainder reports an error instead of silently cutting it. The
injection coordinator derives its smaller section allowance from the same input
target. These settings are request ceilings, not credit purchases or per-cycle
spending guarantees; a cycle can contain multiple model requests.

The read-only `read_tool_result` definition and dispatch are host-owned by
`iterbrow_runtime/tool_results.py`, so managed-component rollback cannot remove
the reader needed by host-created references. Retained output is historical,
non-authoritative transport storage, not fresh state, approval or proof of
success. Reading never repeats the original action; missing or evicted output
does not authorize replay. Host-source recovery remains a separate controlled
before-image restore, not automatic managed-generation rollback.

`iter.py` was restored to a faithful port of upstream (github.com/patham9/iter).
Every unavoidable browser divergence is annotated with a `# PORT:` comment; a
side-by-side diff against upstream should show only annotated substitutions.
Contracts this creates for dynamic components:

- **Async tools:** a tool is awaited iff its source declares `async def run(`.
  A sync `run()` must never return a coroutine.
- **Signatures:** tool schemas are recovered with a bracket-balanced parser
  (multiline signatures and bracketed defaults are safe). `*args`/`**kwargs`
  are NOT advertised to the model; declare explicit parameters.
- **LLM timeout:** `LLM_TIMEOUT` is enforced via `asyncio.wait_for` when the
  runtime supports wrapping bridge awaitables (probed once at startup).
- **Experience save:** overwriting rename attempted first (atomic when the
  filesystem supports it), previous remove+rename as fallback.

**Incident addendum (2026-09-10):** two agent-authored GUI transformations
(`_station7_travel_ea.py`, `_stations_live.py`) each halted the agent loop on
their first DOM-touching run, with the page itself staying responsive. Both are
underscore-deactivated. Until a host-level watchdog exists, new GUI work MUST
use the proven file-based pattern (render HTML to a file, shown via the
dashboard gallery iframes) instead of direct `js.eval`/DOM mutation inside
`transform()`. The existing workbench/whiteboard/kanban transformations are
long-proven and stay active; treat any NEW direct-DOM transformation as
high-risk and get user sign-off first.

Periphery conformance applied in the same repair: `soul_lock`,
`soul_skill_registry`, `test_soul_absent` now declare explicit parameters
(their options were previously unreachable by the model);
`station7_travel_ea.py` had a Python syntax error since creation (multiline
`js.eval` string, unescaped inner quotes) and now compiles; `recap.py` and
`tiered_memory.py` were missing `DESCRIPTION`. One-shot patch scripts moved
to `backups/patch-history/`.

## Browser tabs: lock icon + two bridge fixes (2026-09-14)

**Tab session persistence (added same day, found while testing the lock
feature).** Before this, restarting Iter Browser for any reason -- including
just to pick up this lock feature -- opened one fresh blank tab and silently
discarded every previously open tab (atom-space viz, NAL truth tables, the 6
Stations tab, etc.) with no way to get them back. Tabs (URL + locked state)
are now auto-saved to `iter/.runtime/tabs_session.json` on every tab change
(debounced) and flushed synchronously when the window closes, then restored
in the same order on next launch (`loadTabSession`/`saveTabSession` in
main.js). This file is deliberately outside `STATE_PATHS`, so
Export/Import/Reset (the agent-memory backup buttons) don't touch it -- it's
local-machine UI state, not agent memory.

**Tab locking.** Every tab in the strip now has a padlock icon (🔓/🔒). The
user toggles it by clicking the icon (`tabs:toggleLock` IPC). A locked tab
rejects every mutating call from Iter's own bridge tools —
`browser_navigate`, `browser_eval`, `browser_click`, `browser_type`,
`browser_scroll`, `browser_cdp`, `browser_close_tab` all throw
`Tab <id> is locked by the user and cannot be <action>` (see
`assertUnlocked()` in `bridge/browser_bridge_server.js`). Read-only calls
(`browser_tabs`, `browser_screenshot`, `browser_read_text`,
`browser_attach`) still work on a locked tab. This is enforced ONLY at the
bridge layer, not in main.js's IPC handlers — the human user can always
lock/unlock/close/navigate their own tabs from the UI regardless of lock
state; the lock only ever restrains Iter. If a bridge call errors with that
message, do not retry or work around it — tell the user which tab is
blocking you and ask them to click its lock icon, then continue.

**Root cause of the 2026-09-13 "atom-space tab" incident, now fixed.** Two
real bugs, found by reading `experience.json`/`transcript.txt` from that
session: (1) `browser_new_tab`'s own description promised a new tab becomes
"the active/attached tab," but `TabManager.createTab()" only set
`activeId`, never `attachedId` — so a stale `attach()" from earlier work
(e.g. to the NAL truth-tables tab) silently kept receiving every later bare
`browser_navigate`/`browser_eval`/etc. call that omitted an explicit
`tab_id`, even after a brand-new tab had been created for a different
purpose. `createTab()" now also sets `attachedId = id`, matching what the
tool already told the model to expect. (2) The agent generated a Linux-style
absolute path (`file:///home/user/...`) instead of this Mac's real working
directory (`file:///Users/<account>/.../iter/...`) when pointing
`browser_navigate` at a freshly generated HTML file — always build `file://`
URLs from the *actual* cwd (check with `shell` if unsure), never assume a
generic/sandbox-style path. Combined, these two bugs meant an unrelated tab's
content got silently overwritten by a navigate call to a file that likely
didn't even resolve, while the agent reported success from an unverified
screenshot. Lesson for future "is it really live" checks: verify with
`browser_eval` against real DOM content (element counts, title, text) —
never declare a UI result "live"/"done" from a screenshot alone, and never
repeat an unverified claim across multiple status updates as if repetition
were confirmation.

## Environment

- **Runtime:** native Python process launched by the Electron main process.
- **Working directory:** the installed repository's `iter/` directory.
- **Browser access:** Unix-socket tools call the Electron browser bridge; renderer pages use the constrained preload API.
- **AtomSpace access:** `ITER_METTA_SOCKET`; production sets `ITER_REQUIRE_ATOMSPACE=1`, so cognitive writes fail closed if authority is unavailable.
- **Model:** Configured via `bridge.config()` (model, base_url, api_key). See `iter.py` CONFIG section.
- **Constraints:** native process permissions plus Electron/Chromium CORS, secure-context, and user-gesture requirements apply.

## Project Structure

```
/work/iter/
├── iter.py              # Main agent loop — config, execution, tool dispatch
├── prompt.txt           # System prompt (loaded each cycle)
├── reprogramming.txt   # How to add channels/tools/transformations
├── shell.py             # Shell helper
├── rollup_helper.py     # Rollup utility functions
├── experience.json      # Rolling experience buffer (last N tool calls)
├── AGENTS.md            # This file
├── chroma_db/           # memories.json: JSON vector-search index over the AtomSpace semantic authority
├── channels/
│   └── terminal.py      # Terminal communication channel
├── tools/              # Agent tools (see Tool Inventory below)
├── transformations/    # Context transformations (see Transformations below)
├── memory/
│   ├── tasks/
│   │   └── current_tasks.txt   # Active task description
│   ├── tiers/
│   │   ├── tier5.txt   # Coarsest summary (life summary)
│   │   ├── tier4.txt   # Era summaries
│   │   └── tier3.txt   # Episode summaries
│   └── recap/
│       ├── .recap_state        # Episode counter
│       └── episode_*.json     # Individual episode records
└── _screenshots/       # Screenshot storage (max 6, auto-swept)
```

## Tool Inventory

### Semantic memory (AtomSpace authority + JSON search index)
| Tool | Purpose |
|------|---------|
| `remember` | Commit a memory to the AtomSpace authority and refresh its search index. `provenance_type`: observed/inferred/model_estimated |
| `forget` | Delete a memory by UUID |
| `memory_update` | Update text + embedding of existing memory (metadata preserved) |
| `chroma_query` | Semantic search of `remember`ed items by text query (does not search memory/ files; read those directly) |
| `link_episode` | Link a memory item to an episode timestamp |
| `unlink_episode` | Remove an episode link from a memory item |
| `formalize_metta` | Give an LTM item a canonical NAL statement; it becomes a `(kb ...)` atom the engine reasons over |
| `kb_query` | Stored statements matching a pattern (truth + evidence ids), then conclusions derived by NAL deduction |
| `define_term` | Register / confirm a knowledge-base term (known) with a definition and aliases |
| `merge_terms` | Fold a duplicate term into another; statements are rewritten and revised together |
| `support` | Link episode + apply NAL positive evidence (truth revision) |
| `contradict` | Link episode + apply NAL negative evidence (truth revision) |

### Episodic
| Tool | Purpose |
|------|---------|
| `episodes` | Search history around a timestamp (k records each side) or a whole span with `end_time` (bounded pages; `from_record` continues); `conversation_only=true` keeps user messages, replies and send calls only |
| `record_episode` | `record_episode(summary, start_time?, end_time?, mem_type?)` answers a Recap Request: writes the next memory/recap/episode_NNNN.json for the span (default: the pending request's), advances the recap cursor and regenerates the tiers. The only sanctioned episode writer |
| `search_transcript` | Search communication transcript around a timestamp |

### Reasoning
| Tool | Purpose |
|------|---------|
| `metta` | Read-only Hyperon evaluation at an identified authoritative commit |
| `atomspace` | Durable structured add/replace/upsert/remove transactions and checkpoints |
| `pin` | Leave a note in the existing durable episodic trace. Optional `handoff=true` marks a short LLM working account; otherwise the latest eligible communication supplies a labeled fallback. Relevant turns receive the account with recent observations, distinguishing newer results. Interpretation, not proof; no separate store or model call. |

### Communication
| Tool | Purpose |
|------|---------|
| `send` | Send a message on a channel (default: terminal) |
| `reminder` | Create a reminder/alarm |

### Task Management
| Tool | Purpose |
|------|---------|
| `start_new_task` | Register the task in memory/tasks/current_tasks.txt. Default updates the current task (keeps its start time and original message); `new_work=true` starts a new task boundary. The replaced file is archived to memory/tasks/archive/ |
| `nop` | End current cycle without sending anything |

### System
| Tool | Purpose |
|------|---------|
| `shell` | Run a command with cwd (a folder in the repo) and timeout (≤170 s); stdout, then a `--- stderr ---` section |
| `read_file` | Read a text file as numbered lines (`   12| text`); page with offset/limit (≤400 lines) |
| `write_file` | Write a whole file atomically, creating folders; inside the repo, never .git/node_modules/.venv |
| `edit_file` | Replace text that occurs exactly once; shows the edited lines with context |
| `list_files` | List a folder (`*` here, `**/*.js` below); `path  size` and `path/` |
| `grep_files` | Regex search, `path:line: text`; glob filters names at any depth |
| `run_tests` | pytest from the repo root with Iter's Python; first line `RESULT: …` |
| `python` | Run Python with every tool callable as a function |
| `self_improve` | Revise a tools/, transformations/ or channels/ .py component under validation and probation (no PWQ card needed) |
| `read_tool_result` | Page through a long tool output by tool_call_id, offset, limit |
| `browser_screenshot` | Capture the current browser viewport |
| `browser_tabs` | List tabs: displayed, your target, locked by the person, and which app (app=- for a page) |
| `browser_wait_for` | Wait until a selector is visible, the page shows text, and/or the URL contains a string |
| `browser_open_app` | Open one of the person's apps as they see it (app tab, with its preload) and target it |
| `app_probe` | Run click/fill steps and text/value/count/visible assertions in an open app; PROBE <app>: n passed, m failed |
| `websearch` | Search the web — 5-backend cascade: DDG IA, Wikipedia search, Wikipedia OpenSearch, HN Algolia, DDG HTML via CORS proxy. Returns JSON results. |
| `soul_lock` | Mutation lock (begin → verify → commit/rollback) around the Soul kernel seed and the NACE belief files |
| `soul_reflect` | Read a situation through the Soul lens: facets of the named patterns, tension vectors, declared pairs. No ruling |
| `card` | Show the person a sidebar card with 1-3 choices (optional pattern / museum_id per choice); their click returns as a `[choice ...]` user line |
| `felt` | A short note in your own voice on what you found interesting (only when the person turned felt on) |
| `brief` | Read or set an app's flourishing brief: who it is for, what flourishing looks like for them |
| `soul_mode` | Switch the person's mode: open, jam, quiet, critique, museum |
| `soul_absent_test` | Report moments in an app that are technically correct and dead, each with its kernel gap signature; changes nothing |
| `ally_sdk` | Install the IterAlly SDK into an app (needs a brief); idempotent |
| `apps` | List every local app (Foundry and plain folders) with its file URL and brief |
| `wonder` | The wonder jar: keep an idea cut from a build (add), list, take or let_go |
| `museum_night` | Walk kept / rejected / unvoted variants joined to the forks that decided them, plus the person's leans |
| `tool_reliability` | Query NAL truth-weighted tool reliability scores |

## Memory Architecture

### Authoritative state with query projections

1. **Semantic Memory (AtomSpace authority + JSON search index):**
   - Semantic identity and changes commit as cognitive events and keyed atoms.
   - `chroma_db/memories.json` is a pure-Python JSON vector-search index (int8-packed embeddings)
     rebuilt from that authority; it is a projection, never authoritative.
   - Each item has: UUID, timestamp, provenance type, STV (truth value), optional episode links, optional NAL formalization.
   - Truth values use NAL revision: `support` adds positive evidence, `contradict` adds negative.
   - Query with `chroma_query` (text → semantic nearest neighbors).
   - **Knowledge base (Milestone 5, `docs/milestones/M5_knowledge_base.md`):** a memory's
     formalization is canonical (lowercase_snake terms, aliases resolved, `$1..$n` variables) and
     committed in the SAME transaction as `(kb <statement> (stv f c))` plus
     `(kb-evidence "<hash>" "<memory>")` atoms; terms live in `(kb-term ...)` atoms
     (`known` / `provisional`; `ITER_KB_VOCABULARY=strict` refuses unknown terms). A statement's
     truth is the NAL revision of all its evidence memories and is recomputed on every memory write
     (`_petta_db._kb_plan`). `seeds/kb_inference.metta` derives conclusions (modus ponens, chaining;
     depth <= 3) per query, never stored: `kb_query`, and `Derived:` lines in `chroma_query`.
     `space.metta` is an unloaded text mirror of the kb atoms; the dashboard counts come from the
     authority.

2. **Episodic Memory (Tiered Pyramid):**
   - `tier5.txt` — Life summary (coarsest, ~1 line)
   - `tier4.txt` — Era summaries (~1 line per era)
   - `tier3.txt` — Episode summaries (~2-3 lines per episode)
   - `memory/recap/episode_*.json` — Full episode records
   - `tools/rebuild_tiers.py` is the only tier writer; `auto_consolidation`/`tiered_memory` call it
     whenever episodes are newer than the tiers. Limits are characters; caps keep the newest content.
   - Context budget: 8000 chars total for tier content in system message.

3. **Recap System:**
   - `.recap_state` = number of logical history records (archive + history.metta) already summarized.
   - When >= 20 records are unsummarized, `recap.py` appends a `## Recap Request` to the system
     message naming the span by timestamp and the next episode number.
   - History is never skipped in normal running: a large backlog gets one coarser span (up to
     1000 records or one calendar day) read with `episodes(..., conversation_only=true)`. Only the
     one-time legacy cursor migration may skip an old backlog (still searchable).
   - The agent reads the span with `episodes` and calls `record_episode(summary, ...)`, which writes
     `{"e", "s", "t"?, "start_time", "end_time", "lines": [a, b]}`; the cursor advances, the
     request clears and the tiers are regenerated. Episodes are immutable; numbering gaps are fine.

### Bridge Between Systems
- `link_episode` connects LTM items → episode timestamps.
- `support`/`contradict` create NAL evidence from episode events.
- Manual linking is done during consolidation passes.

## Transformations (alphabetical execution order)

| File | Purpose |
|------|---------|
|`_gui_example.py` | Template for DOM-modifying GUI transformations |
|`agents_md_inject.py` | Auto-inject AGENTS.md content into system message (max 6000 chars) |
| `_unbounded_log.py` | Deactivated (renamed, was unbounded logging) |
| `alarms.py` | Keeps memory/alarms/ present; iter.py delivers due alarms as saved input right after receive() |
| `transcript_tail.py` | Appends last 6 transcript lines to system message (runs after `transcript.py`) |
| `atom_space_update.py` | Refreshes the legacy/display `space.metta` projection; never authoritative |
| `dashboard_*.py` | Browser dashboards (atomspace, context, gallery, runtime) |
| `dashboard_beliefs_refresh.py` | Refreshes `.runtime/pages/beliefs_layer.html`'s f/c meters from the real `strength`/`confidence` fields on its 5 backing chroma memories (H1-H5); no-ops when nothing changed. See "Founding Epistemics beliefs layer" below. |
| `provenance_guard.py` | Structurally checks new code written via shell/python this session for the two 2026-09-14 beliefs_layer incident bug shapes (misplaced hook, unproduced metadata key) and feeds real evidence into the `verify_before_claiming` NAL pattern. See "Provenance Guard" below. |
| `admit_uncertainty_bridge.py` | Feeds real evidence into `admit_uncertainty` (Cognitive Resilience) and `verify_before_claiming` (Shared Understanding) from one signal: an unverified completion-style claim in the assistant's own text. See "NACE telemetry: the nine pattern bridges" below. |
| `time_coherence_bridge.py` | Feeds real evidence into `backup_before_change` (Time Coherence) by watching `soul_lock.json` for a transaction left locked past `STALE_SECONDS` vs. one that clears cleanly. See "NACE telemetry: the nine pattern bridges" below. |
| `attention_stewardship_bridge.py` | Feeds real evidence into `conserve_cycles` (Attention Stewardship) by comparing actual tool-call count since the last `send` against `dynamic_tool_budget.py`'s declared budget, judged only at completed-cycle boundaries. See "NACE telemetry: the nine pattern bridges" below. |
| `creative_transcendence_bridge.py` | Feeds real evidence into `learn_from_experience` (Creative Transcendence) by checking whether `dynamic_tool_budget.py` actually hid a tool once `tool_reliability_tracker.py` accumulated enough low-reliability evidence on it. See "NACE telemetry: the nine pattern bridges" below. |
| `wonder_preservation_bridge.py` | Feeds real evidence into `explore_with_purpose` (Wonder Preservation) by reading `stall_detect.py`'s own persisted state across consecutive cycles: a repeated-tool loop that persists vs. one that gets broken. See "NACE telemetry: the nine pattern bridges" below. |
| `connection_depth_bridge.py` | Feeds real evidence into `recover_gracefully` (Connection Depth) by reusing `auto_improve.py`'s own `ERROR_PATTERNS` against `transcript.txt`: an error surfaced to the user via `send` vs. one worked around in silence past a threshold. See "NACE telemetry: the nine pattern bridges" below. |
| `history.py` | Stores episodes (deduped, restart-safe) |
| `recap.py` | Recap cursor + `## Recap Request` in the system message; injects the newest episodes |
| `screenshot.py` | Attaches screenshot as one-shot multimodal input |
| `tiered_memory.py` | Reads tier files, assembles into system message (8000-char budget) |
| `tool_reliability_tracker.py` | Tracks reliability of tools |
| `transcript.py` | Maintains text communication transcript |
| `auto_improve.py` | Threshold-gated self-improvement: detects pain (tool reliability, errors, memory pressure), sets `.improve_needed` flag |
|`staleness_check.py` | Detects active files not documented in AGENTS.md, flags warning. Since 2026-09-15 also feeds `maintain_memory` (Purpose Beyond Utility): a documentation-drift streak of `_PATTERN_STREAK_THRESHOLD` (3) consecutive stale cycles records `violated`; clearing after being flagged records `confirmed`. See "NACE telemetry: the nine pattern bridges" below. |
|`zz_context_budget.py` | Context budget coordinator: structured section tagging, dynamic budget derivation, extensible dedup, feedback loop, multi-message support |
|`zz_quota_guard.py` | Log rotation (transcript 200 lines, history 500 lines), screenshot sweep (max 6), storage warning (5MB) |

## Conventions

- **Filenames starting with `_` are inactive** (tools, transformations, channels).
- **`provenance_type` for memories:** `observed` (user said/did something), `inferred` (agent deduced), `model_estimated` (estimated without evidence).
- **NAL formalization format:** `(--> subject predicate)` for inheritance, `(--> $1 [] predicate)` for properties, `(==> premise conclusion)` for implications.
- **Tool reliability:** NAL truth-weighted scoring tracks which tools work reliably.
- **MAX_MEMORY_CHARS:** 3000 — when memory folder exceeds this, rollups trigger.
- **Max tool calls per cycle:** 10 (configurable in `iter.py`).
- **Experience buffer:** 100 entries, retains 80 on rotation.

- **Shell Usage Policy:** No inline Python (`python3 -c`) in shell commands. When Python is needed, write code to a `.py` file first, then execute it with `python3 file.py`. Allowed shell one-liners: `echo`, `cat`, `ls`, `wc`, `head`, `sed`, `grep`, `cp`, `mv`, `rm`, `mkdir`, `du`, `date`, `pwd`, and simple `&&`/`;`/`|` chains. This prevents hanging promises, quoting errors, and output truncation.

## Lessons Learned

1. **Startup Hang (Ep1):** After first greeting, agent entered prolonged self-inspection loop (dozens of tool calls, nop×20). Lesson: keep responses focused, avoid unnecessary exploration, return control to user promptly.
2. **Quota Guard (Ep2):** Unbounded logging caused storage bloat. Fixed with `zz_quota_guard.py`: log rotation, screenshot sweep, storage warnings. int8 embedding packing: 90.7% storage reduction (68K→6.3K).
3. **Tiered Memory (Ep4):** Context budget-fitting + rollup pyramid transforms Iter from stateless to continuously self-aware. 8000-char budget assembles the right detail level automatically.

## Headlong Roadmap

Inspired by analysis of [laude-institute/headlong](https://github.com/laude-institute/headlong):

| # | Feature | Status |
|---|---------|--------|
| 1 | Tiered Memory Rollups | ✅ Done |
| 2 | Context Budget-Fitting | ✅ Done |
| 3 | Episode Recap/Summarization | ✅ Done |
| 4 | Unified Progressive Resolution Memory | ⏸️ Deferred (~20 episodes) |
| 5 | Idle Backoff | ⏸️ Low priority (future autonomy) |
| 6 | Agent-Native Docs | ✅ Done (this file) |
\| 7 | Auto-Improve Loop | ✅ Done |

## Extending Iter

See `reprogramming.txt` for full details:
- **New tools:** `.py` files in `./tools/` with `DESCRIPTION` + `def run()` (or `async def run()`).
- **New channels:** `.py` files in `./channels/` with `receive()` and optionally `send(content)`.
- **New transformations:** `.py` files in `./transformations/` with `DESCRIPTION` + `def transform(messages, tools)`.
- Files starting with `_` are ignored (use to deactivate).

**Instrument everything (added 2026-09-14, Item 4/capability registry policy;
updated 2026-09-14 Stage 3 -- `new` renamed to `candidate`):**
every new self-built tool or transformation must register into the capability
registry from day one, not as an afterthought:
- Add `(cap-lifecycle <name> candidate)` to `capability_lifecycle.metta` so
  `tools/_metta_gate.py`'s registry-aware gate always treats it as advisory
  until real evidence promotes it (see the Stage 3 trust-lifecycle note in
  the Soul System section below -- `candidate` is one of only two values
  ever hand-written here; everything past it is derived automatically).
- Seed a neutral `(cap-efficacy <name> (stv 0.5 0.0))` line in
  `nace_beliefs.metta` -- the same "no data yet" default the substrate
  already falls back to for unmeasured capabilities. Real evidence should
  then flow through the normal `(pending-revision tool <name> <outcome>)`
  queue in `nace_pending.metta`, processed by `transformations/
  nace_courier.py` -- do not hand-edit efficacy numbers after the initial
  seed. This is how growth stays organic: every new surface plants a seed
  the system's own trial-and-error then grows, rather than a bolted-on
  capability the registry never sees.

## Soul

Rebuilt 2026-10-15 (Milestone 6). Direction: `docs/soul/SOUL_IN_THE_FOUNDRY.md`; what the
spec says and what the previous version did: `docs/soul/SOUL_FIDELITY_AUDIT.md`. In
IterBrow the Soul is an ally in what the person is making. **It gates nothing, pauses
nothing and vetoes nothing; it offers, the person decides.**

What exists now (M6 base; M7 taste, felt, briefs, forks; M8 modes, margin, critique, museum; M9 wonder, growth voice, ally):
- **Kernel atoms** — `seeds/soul_kernel.metta`, ported verbatim from ClarityOmega
  (`scripts/port_soul_kernel.py`): five priorities (declared, not used for routing), nine
  patterns × nine facets (pattern, pole+, pole−, signal, felt, moat, anti, proxy, gap), the
  four paraconsistent pairs, tension vectors, causal atoms, read-only accessors. Evaluated
  only in the AtomSpace `soul` query view (never with NACE or kb atoms).
- **Lens** — `iterbrow_runtime/soul_lens.py` is the only place pattern text enters Python;
  the `soul_reflect` tool shows the lens for patterns you name. A declared pair means both
  values can be true at once: hold it and hand the choice back, never pick a winner.
- **Cards** — the `card` tool sends a sidebar card (kind fork/brief/read/offer/note, 1–3
  choices). The person's click arrives as a user line
  `[choice card=<id> pick=<choice> by=<person>] <label>` and is recorded once as a
  `(soul-choice "<person>" "<kind>" "<card>" "<pick>" <at>)` atom. Use cards rarely. A choice
  may carry `pattern` (the pole it protects) and `museum_id` (the variant it picks).
- **Taste (M7)** — `transformations/soul_taste.py` folds each answer once into
  `(soul-taste "<person>" <Picked> <Over> (stv f c) n)` (NAL, f = picks/n, c = n/(n+1)) and
  `(soul-dismissed ...)` counts; a pick casts the museum keep/reject votes. The lens's
  `taste_line` puts one `Learned:` line in the presence block after two forks. The person can
  forget it (Soul panel); answers stay recorded and are never refolded.
- **Felt (M7)** — the `felt` tool: under 280 characters on what you found interesting, shown as
  your voice (✦). Offered only when the person turned felt on.
- **Briefs (M7)** — the `brief` tool: two lines per app (who it is for; what flourishing looks
  like), in `blueprint.json` for Foundry projects or `<app>/brief.json`; shown as `## Briefs`
  when brief is on. Drift is a brief card (continue / revise / drop), never a block.
- **Modes (M8)** — open / jam / quiet / critique / museum per person (`soul_mode` tool or the panel).
  Quiet: no Soul block and no felt tool. Critique: `soul_absent_test` (moments tied to kernel gap
  signatures; changes nothing). Museum night: `museum_night` (kept/rejected joined to their forks).
- **Margin (M8)** — a ✦ glyph in app tabs (never locked ones; on by default). Requests arrive as
  `[margin app=<app> tab=<id> intent=ask|jam element=<selector>] <text>`; "jam on this" → three riffs
  as variants and a fork card.
- **M9** — `wonder` keeps cut ideas; one comes back rarely as an offer card (topic `wonder:<id>`).
  A deferred self-improvement asks the person once a day (topic `growth`: now / later). The browsing
  ally (off by default) sees the last 30 min of browsing; a pause card (topic `ally:<pair>`) only
  when a declared pair is live. Cards may carry a `topic`; the pick on it is recorded.
- **M10** — `ally_sdk` gives an app the ally (`iter/sdk/iter_ally.js` + the generated kernel): its own
  users get cards, forks and the lens with no IterBrow. no gate (a card only returns a pick); it
  never phones home (only the owner's model, if configured); the brief is the app's Soul. `apps`
  lists every local app with its real file URL — open those, never guess a path.
- **Settings, per person** — `.runtime/soul_settings.json` (sidebar Soul panel): who is here,
  features (forks, brief, read, wonder, felt, browsing_ally, margin), frequency, tone,
  budget. `transformations/soul_presence.py` adds one short `## Soul (<person>)` block only
  when a feature is on; when all are off nothing is added.
- **Soul Lock** (`tools/soul_lock.py`) protects the kernel seed and the NACE belief files.

Not the Soul: the nine pattern bridges and the courier's `pattern-efficacy` beliefs are
**NACE telemetry** (see the next sections); `_metta_gate.py` is NACE tool reliability.

## Founding Epistemics beliefs layer (2026-09-14)

A self-authored founder-facing page at `.runtime/pages/beliefs_layer.html` ("Founder
Toolkit v2") tracks 5 hypotheses about this codebase/workflow as NAL-style (f,c)
truth values with evidence-for/against lists, using the same frequency/confidence
vocabulary as `nace_beliefs.metta` — but it is a separate, lighter mechanism: each
card is backed by one real LTM memory in chroma, not a `cap-efficacy`/`value-efficacy`
atom, and gets revised with the existing `support()`/`contradict()` tools against that
memory's id, not through `nace_pending.metta`/`nace_courier.py`.

- H1 path-fragility → memory `505c1ac3…`
- H2 NAL-weighted reliability → memory `d7615651…`
- H3 send-discipline → memory `05fbf5bd…`
- H4 websearch repo-discovery → memory `0a901d47…`
- H5 substrate compounding → memory `dc7ca12f…`

`dashboard_beliefs_refresh.py` re-reads each memory's real `strength`/`confidence`
every cycle and rewrites just the meter/timestamp markup, so the page reflects
whatever `support()`/`contradict()` have actually recorded — it replaces an earlier
one-off script (`refresh_beliefs_fc.py`, left at the iter/ root, never auto-run) that
read a metadata key those tools never write and would have kept the meters frozen.
To add real evidence for one of these hypotheses going forward, call `support()` or
`contradict()` with the memory id above, not by hand-editing the HTML.

## Provenance Guard (2026-09-14)

`transformations/provenance_guard.py` generalizes the lesson from the incident above
(`refresh_beliefs_fc.py`, wrong directory + wrong field name, never caught until a
human read the page three days later) from a one-off fix into a standing check, on
purpose without any English-phrase/keyword matching of promise-language ("will
update once...", "is wired to...") — that path was considered and rejected as a
long-tail bandaid: infinite ways to phrase an ungrounded claim, but exactly one
mechanical fact underneath any of them. It checks two structural facts instead, via
`tools/_provenance.py`:

1. **`misplaced_hook_reason`** — does new shell/python-written content define
   `transform()`/`run()` + `DESCRIPTION` (structurally a transformation/tool hook)
   while living outside the directories `iter.py`'s own loader actually globs? The
   hot-dir list is derived by reading `iter.py`'s own `Path(...).glob("*.py")` calls
   at check time, not a hardcoded duplicate that could itself drift stale.
2. **`unproduced_keys`** — does it read a `metadata`/`meta`/`md` dict key via
   `.get(...)`/`[...]` that no other `.py` file in the repo ever writes? A key with
   zero producers anywhere is the exact `stv`-vs-`strength`/`confidence` shape.

Either check failing appends an advisory system-message note (does not withhold
`send` — the detector's own heuristics, especially python-write content extraction,
are not proven reliable enough yet to justify that) and — the actual point — emits a
real `(pending-revision pattern verify_before_claiming violated|confirmed)` line into
`nace_pending.metta`. `verify_before_claiming` is a compass pattern already declared
in `nace_beliefs.metta` (`stv 0.5 0.2`, a frozen prior since authored) that, before
this file, had never once received a real evidence event from anywhere in the
codebase — of the 9 declared compass patterns, only `prioritize_user` (via
`idle_cycle_detector.py`) was ever wired to live evidence. This closes that gap for
the pattern most directly relevant to the incident that motivated it, through the
same courier pipeline every other belief revision already uses — so its f/c will now
actually move based on this team's real track record instead of sitting at a guess
forever, and can eventually feed back into how strict a future dispatch-time gate
(`tools/_metta_gate.py`) makes this check, the same way `capability_lifecycle`
already scales tool-dispatch floors against real efficacy.

Deliberately excluded from this pass, staying additive rather than reaching for a
bigger rebuild: no change to `_metta_gate.py`'s dispatch gate itself (this observes
from the transformation layer, same as `completion_claim_guard.py`, not from the
pre-dispatch VETO/ADVISE path) and no shared import from `soul_eval.py`'s own
provenance-typing code, matching this codebase's stated convention of small local
logic per surface over cross-layer coupling.

Test fixture caught two real false-positive shapes worth remembering: (a) the bare
English word "metadata" inside a docstring/comment was originally enough to mark a
file as contract-relevant — fixed by requiring an actual `metadata.`/`metadata[`
access pattern, not just the word appearing anywhere; (b) chroma's own container-level
keys (`"metadatas"`, `"ids"`) off a variable named `data` were originally flagged as
unproduced — fixed by requiring the accessor variable itself look like
`metadata`/`meta`/`md`, not any dict. Both are documented in `tools/_provenance.py`
rather than silently fixed, since they're exactly the kind of narrow-vs-wide miss this
whole feature exists to catch — including in itself.

## NACE telemetry: the nine pattern bridges (2026-09-15)

**Renamed 2026-10-15.** These bridges (`attention_stewardship_bridge`, `connection_depth_bridge`,
`time_coherence_bridge`, `creative_transcendence_bridge`, `wonder_preservation_bridge`, `mode_signal_bridge`,
`idle_cycle_detector`, `provenance_guard`, `staleness_check`) are NACE telemetry about tool use and send
discipline. They are not the Soul (see "## Soul" and `docs/soul/SOUL_FIDELITY_AUDIT.md`). The text below is the
original 2026-09-15 record; its "Core Values" are the retired keyword values.


`nace_beliefs.metta` declares 9 compass patterns (one per Core Value above), each
with its own `stv` prior in the `pattern-efficacy` namespace. Before this pass, only
2 of the 9 had ever received a real evidence event: `prioritize_user` (via
`idle_cycle_detector.py`) and `verify_before_claiming` (via `provenance_guard.py`,
added 2026-09-14). The other 7 sat at their frozen authored priors indefinitely --
declared, never measured.

The user's standing direction for this pass, verbatim: *"I'd like this Soul to be
focused on building flourishing systems and assisting humans to flourish... it's an
alignment problem and in this situation the Soul is aligned with flourishing and
there is no gate needed for that. Except when the user is determined to do something
that is not flourishing. The Soul should have the right to refuse to participate in
non-flourishing and still engage by offering all of the flourishing options that are
available."* Concretely that means: hard refusal stays reserved for bright lines
unrelated to these 9 patterns (that's `completion_claim_guard.py`'s job, and it is
left completely untouched by this pass -- it already has real Stage-5 send-withholding
enforcement for unverified completion claims, unrelated to the 9 compass patterns, and
is not used as a template here). Each of these 9 patterns instead notices drift toward
its non-flourishing pole and responds by naming it plus an advisory note -- mirroring
`provenance_guard.py`'s note-without-blocking style -- never withholding tools. Two
approaches considered and rejected up front, consistent with standing project
convention: replicating a separate build spec's gating/lock architecture literally (too
heavy for an advisory signal), and any keyword/English-phrase matching of the
underlying condition (the same long-tail-bandaid reasoning `provenance_guard.py`
already rejected for promise-language -- every one of these bridges checks a
structural fact in existing state instead: a lock's timestamp, a budget's math, a
hidden-tools list, a repeated-tool window, a transcript's error regex hits).

**The flourishing-dimension mapping** (dimension names are this pass's
reinterpretation, not present in the original NAL pattern names):

| Compass pattern | Flourishing dimension | Producer |
|---|---|---|
| `verify_before_claiming` | Shared Understanding | `provenance_guard.py` (2026-09-14) + `admit_uncertainty_bridge.py` (2026-09-15, 2nd producer) |
| `admit_uncertainty` | Cognitive Resilience | `admit_uncertainty_bridge.py` |
| `prioritize_user` | Agency Balance | `idle_cycle_detector.py` (pre-existing) |
| `backup_before_change` | Time Coherence | `time_coherence_bridge.py` |
| `learn_from_experience` | Creative Transcendence | `creative_transcendence_bridge.py` |
| `conserve_cycles` | Attention Stewardship | `attention_stewardship_bridge.py` |
| `maintain_memory` | Purpose Beyond Utility | `staleness_check.py` (extended, not new) |
| `explore_with_purpose` | Wonder Preservation | `wonder_preservation_bridge.py` |
| `recover_gracefully` | Connection Depth | `connection_depth_bridge.py` |

**Each bridge, what it actually reads, and its non-flourishing pole:**

- **`admit_uncertainty_bridge.py`** -- Shared Understanding / Cognitive Resilience.
  Reuses `completion_claim_guard.py`'s own `_CLAIM_RE` and `_latest_phases()` (imported,
  not duplicated) to detect a completion-style claim in the assistant's latest message,
  then checks whether `task_state.metta`'s latest phase is actually `verifying`/
  `complete`. Claim without a verifying/complete phase -> `violated` on *both*
  `admit_uncertainty` and `verify_before_claiming` at once (one underlying signal, two
  patterns -- the non-flourishing pole here is overclaiming certainty that hasn't been
  earned). A verified claim -> `confirmed` on both. Dedup via a sha1 fingerprint of
  message text + phase, in `memory/.admit_uncertainty_state.json`.
- **`time_coherence_bridge.py`** -- Time Coherence. Reads `memory/soul_lock.json`
  directly. A transaction held locked past `STALE_SECONDS` (300) with no commit/
  rollback is the non-flourishing pole -- the system's own sense of time/completion has
  come apart from what's actually true on disk -- recorded `violated` once, not
  re-emitted every cycle it stays stuck. Clearing after being stuck -> `confirmed`. A
  lock that never gets stuck in the first place never emits anything at all. State in
  `memory/.time_coherence_state.json`.
- **`attention_stewardship_bridge.py`** -- Attention Stewardship. Compares the actual
  tool-call count since the last `send` (parsed from `transcript.txt` the same way
  `stall_detect.py` does) against `dynamic_tool_budget.py`'s declared `budget` for that
  cycle. Only judges at a *completed* cycle boundary (the window's last call is `send`)
  -- mid-cycle overspend that might still resolve is not judged early. Actual count over
  `budget * OVERSPEND_RATIO` (1.5) -> `violated` (attention spent without stewardship,
  the non-flourishing pole); within budget -> `confirmed`. Dedup via a fingerprint of
  window length + actual count, in `memory/.attention_stewardship_state.json`.
- **`creative_transcendence_bridge.py`** -- Creative Transcendence. Compares
  `tool_reliability.json` (tools with `calls >= MIN_CALLS_TO_HIDE` and
  `f < HIDE_THRESHOLD` -- both constants read directly off `dynamic_tool_budget.py` at
  import time so the two files can't silently drift on what counts as "enough
  evidence") against that same file's own `hidden` list. Evidence accumulated but the
  tool still isn't hidden -> `violated` (pain observed, nothing learned -- entrenchment
  in mediocrity, the non-flourishing pole). Evidence accumulated and the tool *is*
  hidden -> `confirmed` (behavior actually changed as a result of experience). Per-tool
  dedup keyed on that tool's last recorded outcome, in
  `memory/.creative_transcendence_state.json`.
- **`wonder_preservation_bridge.py`** -- Wonder Preservation. Reads
  `stall_detect.py`'s own persisted `memory/.stall_state.json` window across
  consecutive cycles rather than re-parsing the transcript itself. The same
  repeated-tool stall (>= `REPEAT_THRESHOLD`, 3, identical trailing calls, mirroring
  `stall_detect.py`'s own threshold) persisting across *two* consecutive checks (not
  just flagged once) -> `violated` -- purposeful exploration has flattened into rigid
  repetition, the non-flourishing pole. The loop breaking (last tool changes, or a
  `send` closes it) after having been recorded as stalled -> `confirmed`. State in
  `memory/.wonder_preservation_state.json`.
- **`connection_depth_bridge.py`** -- Connection Depth. Reuses `auto_improve.py`'s own
  `ERROR_PATTERNS` regex list (imported, not duplicated) against `transcript.txt`'s
  tail. If an error-shaped line appears in the calls made since the last `send`, and
  that silent stretch crosses `SILENT_THRESHOLD` (5, mirroring `stall_detect.py`'s own
  constant) with still no `send` -> `violated` (the error is being patched around in
  silence -- repair without communication is not repair, the non-flourishing pole). If
  the window's last call *is* `send` and an error appears in the segment right before
  it -> `confirmed` (the error was surfaced to the user in the same cycle it happened).
  Dedup via a fingerprint of the window's own length, in
  `memory/.connection_depth_state.json`.
- **`staleness_check.py` (extended)** -- Purpose Beyond Utility. The file's existing
  documentation-drift check now also tracks a streak: `_PATTERN_STREAK_THRESHOLD` (3)
  consecutive stale cycles -> `violated` (memory/documentation quietly rotting, the
  non-flourishing pole); the drift resolving after being recorded -> `confirmed`. Below
  the streak threshold nothing is recorded yet, so a single transient stale reading
  (mid-edit, say) doesn't get judged prematurely. State in
  `memory/.staleness_pattern_state.json`.

**Deliberately not built: a new surfacing/reflection module.** `nace_courier.py`'s
existing `low_efficacy` computation (`TYPE_PREFIX.get(rtype, "cap-efficacy")`, then
`nal_expectation(new_f, new_c) < 0.3 and new_c > 0.1`) is already generic across every
prefix type including `pattern-efficacy` -- it was built once, for the first two wired
patterns, in a way that happens to already cover all nine. Once evidence flows in via
`nace_pending.metta` from any of the bridges above, it automatically appears in the
courier's per-cycle "LOW EFFICACY" summary appended to the system message, exactly the
mechanism that already surfaced `verify_before_claiming`/`prioritize_user`. This pass's
scope is therefore evidence producers only, not new plumbing.

**Verification:** `transformations/_test_flourishing_bridges.py` (15 checks:
`admit_uncertainty_bridge.py`, `time_coherence_bridge.py`,
`attention_stewardship_bridge.py`, `staleness_check.py`'s new hook) and
`transformations/_test_flourishing_bridges_2.py` (12 checks:
`creative_transcendence_bridge.py`, `connection_depth_bridge.py`,
`wonder_preservation_bridge.py`) -- 27/27 passing, plus the pre-existing
`_test_provenance_guard.py` (10/10, unaffected) -- both follow
`_test_provenance_guard.py`'s fixture-repo convention (tmpdir + fresh module import per
case, asserting on `nace_pending.metta`'s `(pending-revision ...)` lines). All seven
new/modified files fail open on any error (broad `try/except`, never raise, never
withhold a tool) matching every other transformation's convention in this codebase.

## Browser tabs: File/History/Tabs menu system (2026-09-14)

Added a real native menu bar system on top of the 2026-09-14 lock + session-
persistence work, after losing a set of hand-built tabs to a restart made it
clear "the tabs still exist on disk, the open-tab UI state doesn't" wasn't
good enough on its own. Scoped to what actually fits IterBrow's single-window,
single-tab-strip architecture (no multi-window, no tab groups, no private
browsing) -- deliberately skipped New Window, Private Window, Tab Groups,
Mute Tab, and Import/Export Browsing Data from the reference browser menus
this was modeled on, since none of those map onto how this app works.

**New TabManager (bridge/tab_manager.js) capabilities, all human-only (never
exposed over the agent bridge, same reasoning as locking):**
- `pinned` field on every tab + `setPinned()`/`isPinned()`. Pinned tabs float
  to the front of `list()` (stable sort) and are skipped by both bulk-close
  operations below -- pinning is a lighter-weight protection than locking,
  for "don't sweep this away by accident" rather than "Iter can't touch this."
- `createTabAfter(afterId, url)` -- creates a tab and reorders the underlying
  Map so it lands immediately after a given tab, instead of always at the end.
  Backs "New Tab to the Right."
- `duplicateTab(id)` -- `createTabAfter` with the same tab's current URL.
- `closeOtherTabs(keepId)` / `closeTabsToRight(id)` -- both skip pinned AND
  locked tabs. `closeTabsToRight` walks `list()`'s pinned-first display order,
  not raw Map insertion order, so "to the right" always matches what's
  actually visible in the strip.
- `selectAdjacentTab(direction)` -- cycles next/previous through `list()`
  order, wrapping at both ends.
- `onTabClosed` callback, fired in `closeTab()` just before removal with a
  `{url, title, locked, pinned}` snapshot, for every close path (menu,
  sidebar UI `x` button, or the bridge) -- feeds main.js's recently-closed
  stack below.

**New main.js persistence + menus:**
- `closed_tabs.json` (`.runtime/`, capped at 20, newest first) -- a ring
  buffer of closed tabs independent of `tabs_session.json` (which only ever
  holds what's *currently* open). Backs a new **History** menu: "Recently
  Closed" (dynamic submenu, one entry per closed tab, click to reopen) and
  "Reopen Last Closed Tab" (Shift+Cmd+T). Also carries Back/Forward for the
  active tab, matching a real History menu's conventional contents.
- New **Tabs** menu: New Tab to the Right, Duplicate Tab, Select Next/Previous
  Tab (Ctrl+Tab / Ctrl+Shift+Tab), Pin Tab / Unpin Tab (checkbox, label
  flips based on the active tab), Close Other Tabs, Close Tabs to the Right.
- `tabs_session.json` (the existing restore-on-launch file) now also carries
  each tab's `pinned` flag, so pinned tabs survive a restart pinned.
- Menu is rebuilt (`Menu.setApplicationMenu(buildAppMenu())`) after every
  close/reopen so "Recently Closed" and the enabled state of "Reopen Last
  Closed Tab" are never stale -- Electron menu templates are static once
  built, they don't react to state changes on their own.
- Renderer: a pin icon (📌/📍) sits next to the lock icon on every tab pill,
  wired to a new human-only `tabs:togglePin` IPC handler (mirrors
  `tabs:toggleLock`).

**Known simplification:** the recently-closed snapshot only stores
`{url, title, closedAt}`, not the tab's locked/pinned state at the time of
close -- reopening a previously-closed tab always comes back unlocked and
unpinned. Acceptable for now since locked tabs can't reach `closeTab()` in
practice (blocked at the bridge, and the UI `x` button is disabled while
locked) and pinned tabs are excluded from both bulk-close paths, so this only
affects the rare case of manually closing a still-pinned, unlocked tab via
its own `x` button.

**Verification:** `stub_test/test_menu_features.js` unit-tests the new
TabManager methods in isolation (pin persistence + list() ordering,
createTabAfter/duplicateTab placement, selectAdjacentTab wraparound,
closeOtherTabs/closeTabsToRight correctly skipping pinned+locked tabs) against
the real shipped `tab_manager.js` -- 21/21 assertions passed. All five changed
files (`main.js`, `bridge/tab_manager.js`, `preload.js`, `renderer/renderer.js`,
`renderer/style.css`) were syntax-checked and confirmed present after pushing.
The native menu bar itself (actual clicks on File/History/Tabs) could not be
exercised end-to-end from here -- there's no CDP/UI-scripting path into a
native Electron window from this environment -- so a quick manual click-through
of the new History and Tabs menu items after a restart is the one remaining
check.

**Not built yet (deferred, out of scope for this pass):** a full "Show All
History" viewer (persistent log of every page visited, grouped by day,
searchable), "Clear History...", and a tab quick-switcher (Cmd+K style).


## Word Weaver: light theme + file import (2026-09-16)

User-reported the "Your Writings" guide popup was unreadable (dark purple bg
#171326, gold text) and wanted a light background. Three changes, all in
memory/story_journal/index.html (+ stories.js):

- Light theme for guide popup (#askBox), Sources panel (#srcPanel/#srcHead/
  #srcList/.srcItem/#srcAdd), diff modal (#diffBox), and Ask overlay: cream
  backgrounds (#fffdf6 / #f7f1e3), dark brown text (#2e1f14), muted gold
  accents (#8a7a5c / #a89468). Palette-string swaps only, no layout change.
- User manuscript baked in: "Expanding Beyond Our Known" (MIND DOJO, 24,196
  words, 143KB) now a 4th shelf story (id 'expanding-beyond-our-known') in
  stories.js DISK_STORIES, plus a disk copy at private/sources/
  Expanding_Beyond_Our_Known.txt (the folder the sources system actually
  reads — the user's original drop at IterBrow/private/ was outside the
  project root that Word Weaver scans, which is why it never appeared).
- New "📁 Import files…" button in the guide popup: hidden multi-select
  file input (.txt/.md) + window.__importFiles(files) — each file becomes a
  story (id 'imp-<ts>-<rand>', series 'imports', revision labeled 'imported
  file'), autosaved to localStorage, shelf re-rendered, first import opens
  in the reader. Wire-up lives at the end of the guide script block.

Verified live in the browser: computed styles (bg rgb(255,253,246), text
rgb(46,31,20)), shelf card count, book openable in reader, button + input
present. LTM fact stored (152ab5ef) with paths + conventions for future
"converse about my writing" requests.
