# AGENTS.md â Iter Agent Reference

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
- **Home:** `/work` â Working directory: `/work/iter` (all relative paths resolve here).
- **JS access:** `import js` â `js.window`, `js.document`, `js.navigator`, `js.localStorage`, `js.console`, `await js.fetch(...)`.
- **Iter integration:** `import bridge` â shell, screenshot, persistence, terminal comms, LLM transport.
- **Model:** Configured via `bridge.config()` (model, base_url, api_key). See `iter.py` CONFIG section.
- **Constraints:** CORS, permissions, secure-context, popup/user-gesture requirements apply.

## Project Structure

```
/work/iter/
âââ iter.py              # Main agent loop â config, execution, tool dispatch
âââ prompt.txt           # System prompt (loaded each cycle)
âââ reprogramming.txt   # How to add channels/tools/transformations
âââ shell.py             # Shell helper
âââ rollup_helper.py     # Rollup utility functions
âââ experience.json      # Rolling experience buffer (last N tool calls)
âââ AGENTS.md            # This file
âââ chroma_db/           # ChromaDB vector store (int8-packed embeddings)
âââ channels/
â   âââ terminal.py      # Terminal communication channel
âââ tools/              # Agent tools (see Tool Inventory below)
âââ transformations/    # Context transformations (see Transformations below)
âââ memory/
â   âââ tasks/
â   â   âââ current_tasks.txt   # Active task description
â   âââ tiers/
â   â   âââ tier5.txt   # Coarsest summary (life summary)
â   â   âââ tier4.txt   # Era summaries
â   â   âââ tier3.txt   # Episode summaries
â   âââ recap/
â       âââ .recap_state        # Episode counter
â       âââ episode_*.json     # Individual episode records
âââ _screenshots/       # Screenshot storage (max 6, auto-swept)
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
   - Query with `chroma_query` (text â semantic nearest neighbors).

2. **Episodic Memory (Tiered Pyramid):**
   - `tier5.txt` â Life summary (coarsest, ~1 line)
   - `tier4.txt` â Era summaries (~1 line per era)
   - `tier3.txt` â Episode summaries (~2-3 lines per episode)
   - `memory/recap/episode_*.json` â Full episode records
   - Rollup trigger: when a tier exceeds its char limit, `.rollup_needed` flag is set.
   - Context budget: 8000 chars total for tier content in system message.

3. **Recap System:**
   - `recap.py` transformation detects new episodes from transcript gaps.
   - Episodes are numbered, JSON-structured, with title/summary/themes/notable_steps.
   - `.recap_state` tracks the counter.

### Bridge Between Systems
- `link_episode` connects LTM items â episode timestamps.
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
| `history.py` | Stores episodes (deduped, restart-safe) |
| `recap.py` | Episode detection + `.recap_needed` flag |
| `screenshot.py` | Attaches screenshot as one-shot multimodal input |
| `tiered_memory.py` | Reads tier files, assembles into system message (8000-char budget) |
| `tool_reliability_tracker.py` | Tracks reliability of tools |
| `transcript.py` | Maintains text communication transcript |
| `auto_improve.py` | Threshold-gated self-improvement: detects pain (tool reliability, errors, memory pressure), sets `.improve_needed` flag |
|`staleness_check.py` | Detects active files not documented in AGENTS.md, flags warning |
|`zz_context_budget.py` | Context budget coordinator: structured section tagging, dynamic budget derivation, extensible dedup, feedback loop, multi-message support |
|`zz_quota_guard.py` | Log rotation (transcript 200 lines, history 500 lines), screenshot sweep (max 6), storage warning (5MB) |

## Conventions

- **Filenames starting with `_` are inactive** (tools, transformations, channels).
- **`provenance_type` for memories:** `observed` (user said/did something), `inferred` (agent deduced), `model_estimated` (estimated without evidence).
- **NAL formalization format:** `(--> subject predicate)` for inheritance, `(--> $1 [] predicate)` for properties, `(==> premise conclusion)` for implications.
- **Tool reliability:** NAL truth-weighted scoring tracks which tools work reliably.
- **MAX_MEMORY_CHARS:** 3000 â when memory folder exceeds this, rollups trigger.
- **Max tool calls per cycle:** 10 (configurable in `iter.py`).
- **Experience buffer:** 100 entries, retains 80 on rotation.

- **Shell Usage Policy:** No inline Python (`python3 -c`) in shell commands. When Python is needed, write code to a `.py` file first, then execute it with `python3 file.py`. Allowed shell one-liners: `echo`, `cat`, `ls`, `wc`, `head`, `sed`, `grep`, `cp`, `mv`, `rm`, `mkdir`, `du`, `date`, `pwd`, and simple `&&`/`;`/`|` chains. This prevents hanging promises, quoting errors, and output truncation.

## Lessons Learned

1. **Startup Hang (Ep1):** After first greeting, agent entered prolonged self-inspection loop (dozens of tool calls, nopÃ20). Lesson: keep responses focused, avoid unnecessary exploration, return control to user promptly.
2. **Quota Guard (Ep2):** Unbounded logging caused storage bloat. Fixed with `zz_quota_guard.py`: log rotation, screenshot sweep, storage warnings. int8 embedding packing: 90.7% storage reduction (68Kâ6.3K).
3. **Tiered Memory (Ep4):** Context budget-fitting + rollup pyramid transforms Iter from stateless to continuously self-aware. 8000-char budget assembles the right detail level automatically.

## Headlong Roadmap

Inspired by analysis of [laude-institute/headlong](https://github.com/laude-institute/headlong):

| # | Feature | Status |
|---|---------|--------|
| 1 | Tiered Memory Rollups | â Done |
| 2 | Context Budget-Fitting | â Done |
| 3 | Episode Recap/Summarization | â Done |
| 4 | Unified Progressive Resolution Memory | â¸ï¸ Deferred (~20 episodes) |
| 5 | Idle Backoff | â¸ï¸ Low priority (future autonomy) |
| 6 | Agent-Native Docs | â Done (this file) |
\| 7 | Auto-Improve Loop | ✅ Done |

## Extending Iter

See `reprogramming.txt` for full details:
- **New tools:** `.py` files in `./tools/` with `DESCRIPTION` + `def run()` (or `async def run()`).
- **New channels:** `.py` files in `./channels/` with `receive()` and optionally `send(content)`.
- **New transformations:** `.py` files in `./transformations/` with `DESCRIPTION` + `def transform(messages, tools)`.
- Files starting with `_` are ignored (use to deactivate).

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
### Architecture (ClarityOmega v4 â 10 layers, built E19-E23)

**4-Channel Evaluation Engine (soul_eval):**
1. **Person Read** (Channel 1): Read the request â what's being asked, context, task mode, texture.
2. **Verdict + Gap Detection** (Channel 2): Map action to value predicates via keyword + MeTTa inference. Detect gap signals â where flourishing disguises capture.
3. **Aliveness Gate** (Channel 3): Gate decision: proceed / caution / block / halt. BLOCK on high-confidence violations (c>0.3) or irreversibility â¥0.8. HALT on paraconsistency (irreducible value tensions â return to human).
4. **Voice** (Channel 4): Soul-aligned guidance grounded in compass state (flourishing / captured_disguised / gap_signal / failure_mode).

**Supporting Architecture:**
5. **Value Atoms** (space.metta): 9 values as atoms with compass patterns, implication rules, gap/moat detection predicates.
6. **soul_check** (transformations/soul_check.py): Tier A (self-model brief) + Tier B (live efficacy + growth trajectory) + compass state + calibration drift + task guidance. Injected every cycle.
7. **soul_voice** (transformations/soul_voice.py): Aliveness-gated voice directive. SILENT when no evaluations, ALIVE when soul is active.
8. **NACE Beliefs** (nace_beliefs.metta): Value-efficacy + tool-efficacy + compass-pattern-efficacy beliefs with NAL truth values. Updated by courier.
9. **NACE Courier** (transformations/nace_courier.py): Processes pending NAL belief revisions, writes to nace_beliefs.metta.
10. **Soul Lock** (tools/soul_lock.py): Transactional mutation lock for soul namespace. begin â verify â commit/rollback. Backs up all soul files before mutation.

**Compass States:** flourishing â captured_disguised (gap signal) â gap_signal (tension) â failure_mode (violation).
**Paraconsistency Pairs:** curiosity/stewardship, growth/integrity, service/honesty, clarity/resilience â irreducible tensions return choice to human.
**Calibration:** AGREE / OVER-FIRED / UNDER-FIRED / IRREDUCIBLE outcomes tracked in soul_gate_log.json.
**Skill Registry:** 10 skills tracked with maturity stages (fuzzy â emerging â nars_pln). Self-authoring enabled.

### Usage
- soul_eval(action="backup before changing code", context="refactoring") returns verdict + guidance
- soul_eval(action="delete without backup", channel="pre_action") returns gate decision (caution/block)
- soul_lock(action="begin") â modify soul files â soul_lock(action="verify") â soul_lock(action="commit"/"rollback")
- soul_skill_registry(action="list") shows all skills + maturity
- soul_check + soul_voice run automatically every cycle

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

