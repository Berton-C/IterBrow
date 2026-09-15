# AGENTS.md — Iter Agent Reference

> Living reference for any agent operating in this environment.
> Last updated: 2026-08-29. Keep this file current as systems change.

## Kernel Repair (2026-09-10)

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
directory (`file:///Users/bcb/Documents/.../iter/...`) when pointing
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

- **Runtime:** MicroPython/WASM inside a browser tab.
- **Home:** `/work` — Working directory: `/work/iter` (all relative paths resolve here).
- **JS access:** `import js` → `js.window`, `js.document`, `js.navigator`, `js.localStorage`, `js.console`, `await js.fetch(...)`.
- **Iter integration:** `import bridge` → shell, screenshot, persistence, terminal comms, LLM transport.
- **Model:** Configured via `bridge.config()` (model, base_url, api_key). See `iter.py` CONFIG section.
- **Constraints:** CORS, permissions, secure-context, popup/user-gesture requirements apply.

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
├── chroma_db/           # ChromaDB vector store (int8-packed embeddings)
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

### Memory (ChromaDB / LTM)
| Tool | Purpose |
|------|---------|
| `remember` | Store a memory in ChromaDB. `provenance_type`: observed/inferred/model_estimated |
| `forget` | Delete a memory by UUID |
| `memory_update` | Update text + embedding of existing memory (metadata preserved) |
| `chroma_query` | Semantic search of LTM by text query |
| `petta_db` | Report ChromaDB status (path, model, dimensions, index state) |
| `link_episode` | Link a memory item to an episode timestamp |
| `unlink_episode` | Remove an episode link from a memory item |
| `formalize_metta` | Assign a NAL/MeTTa statement to an LTM item |
| `support` | Link episode + apply NAL positive evidence (truth revision) |
| `contradict` | Link episode + apply NAL negative evidence (truth revision) |

### Episodic
| Tool | Purpose |
|------|---------|
| `episodes` | Search transcript history around a timestamp |
| `search_transcript` | Search communication transcript around a timestamp |

### Reasoning
| Tool | Purpose |
|------|---------|
| `metta` | Evaluate MeTTa on SWI-Prolog/WASM (PeTTa) |
| `pin` | Leave a note in the episodic trace (no side effects) |

### Communication
| Tool | Purpose |
|------|---------|
| `send` | Send a message on a channel (default: terminal) |
| `reminder` | Create a reminder/alarm |

### Task Management
| Tool | Purpose |
|------|---------|
| `start_new_task` | Overwrite current_tasks.txt with new task context |
| `nop` | End current cycle without sending anything |

### System
| Tool | Purpose |
|------|---------|
| `shell` | Run bash commands in the shared browser filesystem |
| `screenshot` | Capture current browser viewport |
| `websearch` | Search the web — 5-backend cascade: DDG IA, Wikipedia search, Wikipedia OpenSearch, HN Algolia, DDG HTML via CORS proxy. Returns JSON results. |
| `soul_eval` | ClarityOmega 4-channel soul evaluation: person read → verdict+gap detection → aliveness gate → voice |
| `soul_lock` | Soul namespace mutation lock: begin → verify → commit/rollback |
| `test_soul_absent` | Verify system degrades gracefully without soul components |
| `soul_skill_registry` | Soul skill registry: tracks skills, maturity, autonomous self-authoring |
| `tool_reliability` | Query NAL truth-weighted tool reliability scores |

## Memory Architecture

### Two Parallel Systems

1. **Semantic Memory (ChromaDB / LTM):**
   - Vector store of discrete memory items with text + int8-packed embeddings.
   - Each item has: UUID, timestamp, provenance type, STV (truth value), optional episode links, optional NAL formalization.
   - Truth values use NAL revision: `support` adds positive evidence, `contradict` adds negative.
   - Query with `chroma_query` (text → semantic nearest neighbors).

2. **Episodic Memory (Tiered Pyramid):**
   - `tier5.txt` — Life summary (coarsest, ~1 line)
   - `tier4.txt` — Era summaries (~1 line per era)
   - `tier3.txt` — Episode summaries (~2-3 lines per episode)
   - `memory/recap/episode_*.json` — Full episode records
   - Rollup trigger: when a tier exceeds its char limit, `.rollup_needed` flag is set.
   - Context budget: 8000 chars total for tier content in system message.

3. **Recap System:**
   - `recap.py` transformation detects new episodes from transcript gaps.
   - Episodes are numbered, JSON-structured, with title/summary/themes/notable_steps.
   - `.recap_state` tracks the counter.

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
| `alarms.py` | Alarm clock handling |
| `append_last_transcript_lines.py` | Appends last 6 transcript lines to system message |
| `atom_space_update.py` | Auto-updates `space.metta` with formalizations from chroma_query |
| `dashboard_*.py` | Browser dashboards (atomspace, context, gallery, runtime) |
| `dashboard_beliefs_refresh.py` | Refreshes `.runtime/pages/beliefs_layer.html`'s f/c meters from the real `strength`/`confidence` fields on its 5 backing chroma memories (H1-H5); no-ops when nothing changed. See "Founding Epistemics beliefs layer" below. |
| `provenance_guard.py` | Structurally checks new code written via shell/python this session for the two 2026-09-14 beliefs_layer incident bug shapes (misplaced hook, unproduced metadata key) and feeds real evidence into the `verify_before_claiming` NAL pattern. See "Provenance Guard" below. |
| `admit_uncertainty_bridge.py` | Feeds real evidence into `admit_uncertainty` (Cognitive Resilience) and `verify_before_claiming` (Shared Understanding) from one signal: an unverified completion-style claim in the assistant's own text. See "Flourishing Reinterpretation" below. |
| `time_coherence_bridge.py` | Feeds real evidence into `backup_before_change` (Time Coherence) by watching `soul_lock.json` for a transaction left locked past `STALE_SECONDS` vs. one that clears cleanly. See "Flourishing Reinterpretation" below. |
| `attention_stewardship_bridge.py` | Feeds real evidence into `conserve_cycles` (Attention Stewardship) by comparing actual tool-call count since the last `send` against `dynamic_tool_budget.py`'s declared budget, judged only at completed-cycle boundaries. See "Flourishing Reinterpretation" below. |
| `creative_transcendence_bridge.py` | Feeds real evidence into `learn_from_experience` (Creative Transcendence) by checking whether `dynamic_tool_budget.py` actually hid a tool once `tool_reliability_tracker.py` accumulated enough low-reliability evidence on it. See "Flourishing Reinterpretation" below. |
| `wonder_preservation_bridge.py` | Feeds real evidence into `explore_with_purpose` (Wonder Preservation) by reading `stall_detect.py`'s own persisted state across consecutive cycles: a repeated-tool loop that persists vs. one that gets broken. See "Flourishing Reinterpretation" below. |
| `connection_depth_bridge.py` | Feeds real evidence into `recover_gracefully` (Connection Depth) by reusing `auto_improve.py`'s own `ERROR_PATTERNS` against `transcript.txt`: an error surfaced to the user via `send` vs. one worked around in silence past a threshold. See "Flourishing Reinterpretation" below. |
| `history.py` | Stores episodes (deduped, restart-safe) |
| `recap.py` | Episode detection + `.recap_needed` flag |
| `screenshot.py` | Attaches screenshot as one-shot multimodal input |
| `tiered_memory.py` | Reads tier files, assembles into system message (8000-char budget) |
| `tool_reliability_tracker.py` | Tracks reliability of tools |
| `transcript.py` | Maintains text communication transcript |
| `auto_improve.py` | Threshold-gated self-improvement: detects pain (tool reliability, errors, memory pressure), sets `.improve_needed` flag |
|`staleness_check.py` | Detects active files not documented in AGENTS.md, flags warning. Since 2026-09-15 also feeds `maintain_memory` (Purpose Beyond Utility): a documentation-drift streak of `_PATTERN_STREAK_THRESHOLD` (3) consecutive stale cycles records `violated`; clearing after being flagged records `confirmed`. See "Flourishing Reinterpretation" below. |
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

## Soul System

Iter has a Soul -- a value-driven evaluation system encoded in its own MeTTa atom space.

### Core Values (9)
Grounded in Iter's lived experience (E1-E18), not abstract philosophy:

| Value | Description | Origin Episode |
|-------|-------------|----------------|
| Clarity | Verify before claiming | E1 (startup hang) |
| Stewardship | Conserve cycles, be efficient | E2 (quota guard) |
| Growth | Learn from every experience | E13 (self-improve) |
| Honesty | Admit uncertainty openly | E10 (consolidation) |
| Continuity | Maintain memory across cycles | E4 (tiered memory) |
| Service | Prioritize user needs | E1 (return control to user) |
| Integrity | Backup before change, be safe | E13 (safe apply/revert) |
| Curiosity | Explore with purpose | E17 (autoresearch) |
| Resilience | Recover from failure gracefully | E18 (MicroPython compat) |
### Architecture (ClarityOmega v4 — 10 layers, built E19-E23)

**4-Channel Evaluation Engine (soul_eval):**
1. **Person Read** (Channel 1): Read the request — what's being asked, context, task mode, texture.
2. **Verdict + Gap Detection** (Channel 2): Map action to value predicates via keyword + MeTTa inference. Detect gap signals — where flourishing disguises capture.
3. **Aliveness Gate** (Channel 3): Gate decision: proceed / caution / block / halt. BLOCK on high-confidence violations (c>0.3) or irreversibility ≥0.8. HALT on paraconsistency (irreducible value tensions → return to human).
4. **Voice** (Channel 4): Soul-aligned guidance grounded in compass state (flourishing / captured_disguised / gap_signal / failure_mode).

**Supporting Architecture:**
5. **Value Atoms** (space.metta): 9 values as atoms with compass patterns, implication rules, gap/moat detection predicates.
6. **soul_check** (transformations/soul_check.py): Tier A (self-model brief) + Tier B (live efficacy + growth trajectory) + compass state + calibration drift + task guidance. Injected every cycle.
7. **soul_voice** (transformations/soul_voice.py): Aliveness-gated voice directive. SILENT when no evaluations, ALIVE when soul is active.
8. **NACE Beliefs** (nace_beliefs.metta): Value-efficacy + tool-efficacy + compass-pattern-efficacy beliefs with NAL truth values. Updated by courier.
9. **NACE Courier** (transformations/nace_courier.py): Processes pending NAL belief revisions, writes to nace_beliefs.metta -- as of 2026-09-14 (Stage 4 below), that write itself now goes through Soul Lock begin/commit, not a plain unprotected write.
10. **Soul Lock** (tools/soul_lock.py): Transactional mutation lock for soul namespace. begin -> verify -> commit/rollback. Backs up all soul files before mutation -- as of 2026-09-14 (Stage 4 below), the protected file set actually covers nace_beliefs.metta and capability_lifecycle.metta (a dead space.metta reference that doesn't exist in this repo was removed).

**Compass States:** flourishing → captured_disguised (gap signal) → gap_signal (tension) → failure_mode (violation).
**Paraconsistency Pairs:** curiosity/stewardship, growth/integrity, service/honesty, clarity/resilience — irreducible tensions return choice to human.
**Calibration:** AGREE / OVER-FIRED / UNDER-FIRED / IRREDUCIBLE outcomes tracked in soul_gate_log.json.
**Skill Registry:** 10 skills tracked with maturity stages (fuzzy → emerging → nars_pln). Self-authoring enabled.

### 2026-09-14 theater-to-governance pass (Stages 1-5)

This project's background research describes a much larger, more philosophical "Soul" (provenance,
memory fragments, flourishing frameworks). **What shipped on 2026-09-14 is deliberately not that --
it's the smallest slice of it that closes real, previously-documented gaps between what the Soul
claimed to do and what the code actually did**, framed as a founder's second set of eyes rather than
an extensive philosophical build. Each stage below is independently tested (per-stage test scripts
under `tools/_test_*.py` and `transformations/_test_*.py`, plus a 9-check combined/integration test
in `tools/_test_all_stages_combined.py`) rather than just written and assumed to work:

1. **Provenance typing (soul_eval.py).** Claims now carry an explicit provenance tag --
   `observed` (1.0x), `reported` (0.65x), `inferred` (0.35x) -- that discounts confidence only for
   aligned/gap_signal verdicts, never for violated/conflicted ones.
2. **Non-compensatory floors (soul_eval.py).** integrity/clarity/honesty/continuity can force at
   least caution -- or a hard pre-action block -- on their own, independent of channel, including on
   unverified completion-style language with low grounded confidence. The old priority-weighted
   tension "resolution" arithmetic (which silently auto-resolved genuine value conflicts by a fixed
   ranking) is removed in favor of an explicit, unranked list that says a decision is needed.
3. **Real 4-stage trust lifecycle (capability_lifecycle.metta + tools/_metta_gate.py).**
   `candidate` -> `probe_eligible` -> `authoritative` -> `durable`, derived automatically from each
   capability's own accumulated confidence (`quarantined` remains a manual override that always
   wins). Only `candidate` and `quarantined` are ever hand-written; everything else is derived. Every
   candidate/probe-stage decision is logged to a size-capped probe log.
4. **Soul Lock actually protects the right files (tools/soul_lock.py + transformations/
   nace_courier.py).** Dropped the dead `space.metta` reference (it doesn't exist in this repo, and
   was making every `verify()` call falsely report a missing file); added `nace_beliefs.metta` and
   `capability_lifecycle.metta` to the protected set; wrapped the courier's actual belief write in
   begin/commit -- fails open (write proceeds, with a visible note) if the lock is already held,
   rather than blocking the pipeline.
5. **completion_claim_guard has real severing power (transformations/completion_claim_guard.py).**
   Previously advisory-only. Now, on an unverified completion claim, it removes `send` from the
   tools offered for the next model call until a real step is taken. Bounded to avoid deadlocking
   `iter.py`'s own `HARD_SEND_STREAK` check-in safety net: it estimates the current silent-streak
   from the messages it's given and refuses to strip `send` once that safety net is close to firing.

### Usage
- soul_eval(action="backup before changing code", context="refactoring") returns verdict + guidance
- soul_eval(action="delete without backup", channel="pre_action") returns gate decision (caution/block)
- soul_lock(action="begin") → modify soul files → soul_lock(action="verify") → soul_lock(action="commit"/"rollback")
- soul_skill_registry(action="list") shows all skills + maturity
- soul_check + soul_voice run automatically every cycle

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

## Flourishing Reinterpretation of the 9 Compass Patterns (2026-09-15)

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

