# IterBrow

**IterBrow** is [Iter](https://github.com/patham9/iter) — an autonomous LLM agent — running
as a real Python process *inside its own Chromium-based browser*, built with Electron. It's not
a browser extension and not a sandboxed demo: it's a full multi-tab browser window you own and
drive yourself, with an AI agent living alongside you in the same window, able to see and control
the same tabs you do (except the ones you explicitly lock).

Talk to it in the sidebar chat, and it can search the web, read and click around pages, generate
and live-test its own UI on real pages, remember what it learns across sessions, reason over a
small symbolic knowledge base (MeTTa/atomspace) with NAL-style truth values, evaluate its own
actions against a set of grounded values before taking them, and rewrite its own tools and
behaviors while it runs — under a governance layer that makes that self-improvement earned and
auditable rather than automatic.

This README exists so anyone — human or AI — skimming this repo for the first time comes away
with an accurate picture of what's actually built, not a guess from the folder names. Every table
below is generated directly from the live source (tool/transformation `DESCRIPTION` strings), not
hand-written summaries, so it stays truthful as the code changes.

---

## Table of contents

1. [What IterBrow can actually do](#what-iterbrow-can-actually-do)
2. [How it's built (architecture)](#how-its-built-architecture)
3. [The cognitive loop, at a glance](#the-cognitive-loop-at-a-glance)
4. [Full tool catalog (53 tools)](#full-tool-catalog-53-tools)
5. [Full transformation pipeline (31 stages)](#full-transformation-pipeline-31-stages)
6. [Memory architecture](#memory-architecture)
7. [The Soul system — value-grounded self-evaluation](#the-soul-system--value-grounded-self-evaluation)
8. [NACE — the self-improvement and governance loop](#nace--the-self-improvement-and-governance-loop)
9. [Live dashboards](#live-dashboards)
10. [Component museum — live UI generation with memory](#component-museum--live-ui-generation-with-memory)
11. [Current developer bootstrap on a Mac](#current-developer-bootstrap-on-a-mac)
12. [First run](#first-run)
13. [Using it day to day](#using-it-day-to-day)
14. [Extending Iter (recoverable hot-load + the instrument-everything policy)](#extending-iter-recoverable-hot-load--the-instrument-everything-policy)
15. [Restoring a memory snapshot](#restoring-a-memory-snapshot)
16. [Exporting / resetting your own state](#exporting--resetting-your-own-state)
17. [Packaging a standalone .app](#packaging-a-standalone-app)
18. [Troubleshooting](#troubleshooting)

---

## What IterBrow can actually do

- **It's a real browser.** Tab strip, address bar, back/forward, History menu with "Recently
  Closed" and reopen-last-closed, a Tabs menu (new tab to the right, duplicate, pin/unpin,
  close-others, close-to-the-right, cycle tabs) — all the everyday things you expect, plus a
  chat panel down the side where the agent lives.
- **The agent can drive the browser too.** It can open tabs, navigate, click, type, scroll, run
  JavaScript, take screenshots, and read page text — using the same window you're looking at. A
  raw Chrome DevTools Protocol passthrough (`browser_cdp`) covers anything the higher-level tools
  don't.
- **It can design and live-test real UI, not mockups.** It can inject CSS/JS into the actual page
  you're looking at and screenshot the result to check its own work, or open several full HTML/JS
  variants side by side in real tabs for comparison — every attempt is saved to a searchable
  "component museum" with a keep/reject vote that feeds back into its own tool-reliability beliefs.
- **You can lock any tab (🔒).** A locked tab refuses every action from the agent (navigate,
  click, type, scroll, close, run JS) while you can still use it completely normally yourself.
  Use this on anything sensitive — banking, email, whatever you don't want the agent touching.
- **You can pin any tab (📌)** so it floats to the front of the tab strip and survives
  "close other tabs" / "close tabs to the right" sweeps.
- **It remembers things, two different ways.** A vector-searchable long-term memory store for
  discrete facts/beliefs/preferences, and a separate tiered "rollup" pyramid that compresses old
  conversation into progressively coarser summaries — see [Memory architecture](#memory-architecture).
- **It reasons over a live symbolic cognitive space.** A Hyperon-backed MeTTa engine evaluates the
  journaled authoritative AtomSpace, including NAL-style truth-valued beliefs about how well its tools and
  behavioral patterns tend to work, and can advise — or, in stricter mode, actually veto —
  low-confidence tool calls before they run. See [NACE](#nace--the-self-improvement-and-governance-loop).
- **It evaluates its own actions against nine grounded values** before doing anything risky,
  through a 4-channel evaluation pipeline that can block or halt on a values conflict rather than
  just plow ahead. See [The Soul system](#the-soul-system--value-grounded-self-evaluation).
- **It can improve its own code — but only under supervision.** Runtime revisions to tools,
  transformations, and channels are staged as complete immutable generations. Fixed checks inspect
  candidate structure without importing candidate code; a current PWQ human approval is required
  before probation. Each loop cycle pins one generation, while Electron watches an external
  heartbeat and promotes or restores the exact prior generation. Self-triggered proposals still go
  through the pain threshold, capability lifecycle, and service-before-growth deferral.
- **Start/Stop is durable intent.** Clicking Start records that Iter should return after a clean
  app restart or supervised recovery; clicking Stop clears that intent, so an intentional stop is
  never undone by the watchdog.
- **You choose the brain.** Talk to it through **OpenRouter** (cloud, any model OpenRouter hosts —
  needs your own API key) or **LM Studio** (a model running fully offline on your own machine, no
  internet required, no API key needed). Switching is a Settings-panel dropdown + Stop/Start.

## How it's built (architecture)

Electron *is* the browser (Chromium + a Node.js host process) — the agent isn't a guest extension
running inside someone else's Chrome, so there's no "this tab is being debugged" banner, no
Manifest V3 service-worker eviction fights, and no dependency on an extension store's policies.

```
┌─────────────────────────────── Electron process ───────────────────────────────┐
│  main.js                                                                        │
│   ├─ BaseWindow                                                                 │
│   │   ├─ sidebar WebContentsView  (renderer/ — tab strip, address bar,          │
│   │   │                            chat panel, provider settings)              │
│   │   └─ active tab's WebContentsView (the actual browsed page)                │
│   ├─ bridge/browser_bridge_server.js  — Unix socket, JSON-lines protocol       │
│   ├─ bridge/tab_manager.js            — single source of truth for all tabs   │
│   └─ bridge/chat_bridge.js            — durable replay + atomic queues with iter/│
│                                                                                  │
│  iter.py  (separate Python process, spawned/stopped by main.js)                │
│   ├─ tools/browser_*.py       → talk to the socket → drive real tabs          │
│   ├─ tools/lm_studio_chat.py  → native call to OpenRouter or a local           │
│   │                              LM Studio server (OpenAI-compatible API)     │
│   ├─ tools/metta.py           → read-only Hyperon evaluation at one commit    │
│   ├─ tools/atomspace.py       → durable structured AtomSpace transactions     │
│   ├─ channels/electron_ui.py  → reads/writes the same inbox/outbox files      │
│   └─ everything else → immutable, recoverably hot-loaded generations         │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Sidebar chat is recoverable application state, not a best-effort IPC stream.
Electron journals each accepted user or Iter message under
`.runtime/electron_ui/messages.jsonl` before acknowledging an Iter outbox item;
the renderer replays that journal by stable message ID after reload or app
restart. The inbox/outbox/staging files are transient queues and are published
atomically. Retained hot-load generations that still write plain-text replies
remain compatible during migration.

**Tab locking and pinning are enforced only at the bridge layer** — the human user can always
lock/unlock/pin/close/navigate their own tabs from the UI regardless of lock state. The lock only
ever restrains the agent, never you.

## The cognitive loop, at a glance

Every turn, `iter.py` runs one cycle: assemble context → call the model → dispatch tool calls →
run transformations → wait for the next input. Two of the folders under `iter/` are where nearly
all of this project's actual capability lives, and both can be updated through recoverable runtime generations:

- **`iter/tools/`** (53 active) — things the model can explicitly call: browse, remember,
  reason, self-modify, communicate. See the [full catalog](#full-tool-catalog-53-tools) below.
- **`iter/transformations/`** (31 active) — pipeline stages that run automatically every cycle
  around the model call: injecting memory/context, tracking reliability, running the self-improve
  and governance checks, updating dashboards. See the [full pipeline](#full-transformation-pipeline-31-stages)
  below. Transformations are invisible to the model as callable tools — they shape what the model
  *sees* and what happens *after* it acts, rather than things it decides to invoke.

A file starting with `_` in either folder is deactivated without being deleted — the fastest way
to see exactly what's currently live vs. retired is `ls iter/tools/` / `ls iter/transformations/`.

## Full tool catalog (53 tools)

Generated directly from each file's `DESCRIPTION` constant — this is everything the model can
currently call, grouped by what it's for. (A further ~22 tools exist but are deactivated —
`_`-prefixed — inside `iter/tools/`; inspect any directly to see what it does and why it's off.)

**Browser control**

| Name | What it does |
|---|---|
| `browser_tabs` | List every open browser tab (id, title, url, active, windowId) so you can pick one to attach to or switch to. |
| `browser_new_tab` | Open a new tab in the Iter Browser window at the given URL (defaults to a blank/search page) and make it the active/attached tab. |
| `browser_close_tab` | Close a browser tab. Omit tab_id to close the currently attached/active tab. |
| `browser_switch_tab` | Bring a specific browser tab to the front / give it focus. Pass tab_id from browser_tabs. |
| `browser_attach` | Mark a tab as the current target for navigate/click/type/screenshot/eval/scroll, so you don't have to pass tab_id on every call. Pass tab_id from browser_tabs, or omit to target the current active tab. |
| `browser_detach` | Clear the currently attached/targeted tab, so subsequent browser_* calls fall back to whichever tab is active. |
| `browser_navigate` | Navigate the attached browser tab to a URL. |
| `browser_click` | Click an element in the attached tab. Pass a CSS selector (preferred, e.g. '#submit' or 'button.primary'), or raw x,y viewport coordinates if there is no good selector. |
| `browser_type` | Type text into the attached tab. Optionally pass a CSS selector to click-to-focus first, otherwise types into whatever element already has focus. |
| `browser_scroll` | Scroll the attached tab's page by (x, y) pixels. Positive y scrolls down. |
| `browser_eval` | Run arbitrary JavaScript in the attached tab's page context and return its (JSON-serializable) return value. Use for reading page state, form values, computed styles, etc. that don't need a screenshot. |
| `browser_read_text` | Get the attached tab's visible page text (document.body.innerText, truncated to 20000 chars). Cheaper than a screenshot when you just need to read content. |
| `browser_screenshot` | Take a screenshot of the attached browser tab's current viewport and attach it as visual context for the next model turn. Use this to see what the page actually looks like before deciding on clicks. |
| `browser_cdp` | Advanced/raw escape hatch: send an arbitrary Chrome DevTools Protocol command to the attached tab (e.g. method='Network.enable' or method='Emulation.setDeviceMetricsOverride'). cdp_params must be a JSON object string. Only use this when the simpler browser_* tools do not cover what you need. |

**Live UI generation & component museum**

| Name | What it does |
|---|---|
| `browser_patch_live` | Live-DOM co-pilot with built-in vision feedback: inject CSS and/or JS into the REAL, currently-attached browser tab (via CDP/eval - not a sandboxed preview) and immediately screenshot the result so you can see whether the patch looks right. Pass patch_id to replace/iterate on a previous patch in place instead of stacking duplicates. Every call auto-saves the patch (css/js/html snapshot/screenshot) into the component museum so it survives even if the tab later closes or navigates away. Pass tab_id to target any open tab without switching to it. |
| `browser_tab_variants` | Open N real browser tabs at once, each rendering a different LLM-generated HTML/CSS/JS UI variant, for live side-by-side comparison in the actual window (not a sandboxed preview). Pass variants as a JSON array of {label, html} objects (each html must be a full <html>...</html> document). Every variant is saved to the component museum immediately, win or lose. Returns the tab_id opened for each variant plus its museum id - use museum_vote afterwards to record which one was kept. |
| `preview` | Render HTML in a real (temporary, off-screen) browser tab and capture a screenshot for visual verification. Args: html (str), width (int, default 800), height (int, default 600). Returns render status JSON; the screenshot is attached separately as visual context. |
| `museum_list` | List saved component-museum entries (live-DOM patches and tab-variant generations), most recent first. Each entry has an id you can pass to museum_recall or museum_vote. |
| `museum_recall` | Recall a saved component-museum entry by id and re-apply its CSS/JS onto the current live/attached tab (or a specific tab_id), restoring a previously injected UI patch. Use museum_list to find ids. |
| `museum_vote` | Record a keep/reject decision on a component-museum entry (id from museum_list). vote='keep' applies positive NAL truth-revision evidence (support.py) to the component's memory record and nudges the calibration_accumulation soul skill toward maturity; vote='reject' applies negative evidence (contradict.py). Every vote is journaled. |
| `export_component` | Export a component-museum entry (by component_id) or raw html/css/js as a portable, standalone component file: framework='vanilla' (single .html file), 'react' (.jsx functional component), or 'svelte' (.svelte single-file component). Writes to .runtime/exports/ and returns the generated code inline so it can be handed to the user for saving into a real project. |

**Long-term semantic memory (ChromaDB, NAL truth values)**

| Name | What it does |
|---|---|
| `remember` | Commit a semantic-memory event and keyed state atom, then refresh the `chroma_db` vector-search projection. Valid provenance types: observed, inferred, model_estimated. Valid mem_type: fact, belief, value, todo, preference. |
| `chroma_query` | Query the `chroma_db` vector projection for semantically similar authoritative memories. Returns matching entries with content and metadata. |
| `memory_update` | Update the text content and embedding of a specific memory in chroma_db. All metadata (creation time, linked episodes, stv values) is preserved. Item_id must be a UUID from chroma_query results. |
| `forget` | Commit deletion of a semantic memory, then remove it from the `chroma_db` projection. Item_id must be a UUID from chroma_query results. Durable memory types require `force=True`. |
| `support` | Support a memory item in chroma_db by linking an episode and applying NAL truth revision with positive evidence. Item_id must be a UUID from chroma_query results. |
| `contradict` | Contradict a memory item in chroma_db by linking an episode and applying NAL truth revision with negative evidence. Item_id must be a UUID from chroma_query results. |
| `link_episode` | Link an episode timestamp to a memory item in chroma_db. The item_id must be a UUID from chroma_query results, and linked_time is a timestamp string (e.g. '2026-08-12 17:25:05'). |
| `unlink_episode` | Unlink an episode timestamp from a memory item in chroma_db. The item_id must be a UUID from chroma_query results, and linked_time is the timestamp string to remove. |
| `formalize_metta` | Assign a MeTTa statement (a term, NOT a sentence -- no stv) to an LTM item in chroma_db. LTM_item must be a UUID from chroma_query results. Returns success or error. Statement types (NAL): - Inheritance: (--> raven bird) - Relational: (--> (x Anna Bob) friend) - Property (with []): (--> channel_people ([] prefer_brief_response)) - Implication: (==> (--> $1 ([] smokes)) (--> $1 ([] cancerous))) |

**Episodic memory & transcript**

| Name | What it does |
|---|---|
| `episodes` | Search transcript history for entries around a given timestamp. Returns surrounding context lines. |
| `search_transcript` | Search the communication transcript around a timestamp. Use YYYY-MM-DD HH:MM:SS; returns nearby user and send lines. |
| `memory_journal` | Append-only audit journal for memory-management actions. action='log' records {actor, action, detail} as a new immutable line (use this whenever you trim, regenerate, forget, or vote on memory content so there is always an audit trail). action='tail' returns the last n entries. |
| `rebuild_tiers` | Regenerate memory/tiers/tier3.txt, tier4.txt, and tier5.txt from memory/recap/episode_*.json (the source of truth). This is the ONLY sanctioned way to update tier files - direct writes to them from python/shell are blocked. Safe to call any time; always idempotent. Call this instead of hand-editing tier files whenever memory/tiers/.rollup_needed exists or tiers look stale. |

**Reasoning & self-model (MeTTa / Soul)**

| Name | What it does |
|---|---|
| `metta` | Evaluate MeTTa read-only against the committed authoritative AtomSpace using Hyperon. Queries run in an isolated engine at a named commit, so temporary facts cannot leak into durable state. |
| `atomspace` | Query status or commit durable, structured add/upsert/replace/remove transactions. Acknowledged writes are journaled, snapshotted, idempotent by transaction ID, and reconstructed into Hyperon after restart. |
| `tool_reliability` | Query NAL truth-weighted tool reliability scores. Returns (f, c, calls) for all tracked tools. |
| `soul_eval` | ClarityOmega 4-channel soul evaluation: person read -> verdict+gap detection -> aliveness gate -> voice. Compass states, paraconsistency halting, calibration accumulation, gap/moat detection. |
| `soul_lock` | Soul namespace mutation lock: transactional protocol for soul changes. begin -> verify -> commit/rollback. |
| `soul_skill_registry` | Soul skill registry: tracks soul skills, maturity, and autonomous self-authoring. |
| `task_state` | Record or query a task's current phase (planning/building/verifying/complete) -- call this before claiming something is done, run(action='set', label=..., phase=...) or run(action='get'\|'list') |

**Self-improvement engine & diagnostics**

| Name | What it does |
|---|---|
| `self_improve` | DGM-style evidence and fitness tracking whose apply/full-loop actions now stage an inert immutable candidate and a PWQ approval request; it no longer writes live component files directly. |
| `revision_control` | Inspect, validate, activate, or safely roll back immutable runtime generations. Activation requires the current authorization from the matching human-approved PWQ item and enters externally supervised probation. |
| `eval` | Run regression tests on Iter's tools and transformations. Args: test_name (str, default 'all'). Returns JSON with pass/fail results. |
| `token_awareness` | Track token usage estimates. Args: action (str: 'track'\|'report'\|'reset'), text (str, optional). Returns JSON with token estimates. |
| `test_soul_absent` | Test: verify system degrades gracefully without soul components. |

**Task & communication**

| Name | What it does |
|---|---|
| `start_new_task` | Start a new task by overwriting memory/tasks/current_tasks.txt. ALWAYS call this before beginning any new user-requested work. Required fields: person, requestchannel, taskcontent, completionsendcriterium, originalUserMessage. |
| `send` | Send a message through a communication channel. |
| `reminder` | Create a reminder/alarm. Usage: run(when='2026-08-19 09:00:00', channel='terminal', message='Submit paper') |
| `pin` | Reify reasoning as a note to yourself in the episodic trace. No side effects, returns SUCCESS. Pass a message string to leave yourself a note. |
| `nop` | Perform no action if task is complete and send was already used to report back results, do not re-send! |

**Research**

| Name | What it does |
|---|---|
| `websearch` | Search the web. Returns JSON array of results with title, url, snippet. |

**System / general purpose**

| Name | What it does |
|---|---|
| `shell` | Execute a shell command. |
| `python` | Execute arbitrary Python code with all other tools available as callable functions. Pass Python code as a string. |

**Model access**

| Name | What it does |
|---|---|
| `lm_studio_chat` | Send a chat completion request to LM Studio's local LLM server, as a side call independent of your own main model (which is configured separately via BASE_URL/LLM_MODEL). Accepts: messages (list of {role, content} dicts, or a JSON string), model (default 'qwen/qwen3.8-27b'), temperature (default 0.7), max_tokens (default 1024), stream (default False). Returns the assistant's response text, or full JSON if raw=True. LM Studio base URL defaults to http://127.0.0.1:1234 (loopback, works with or without a network) but can be overridden via base_url. |

## Full transformation pipeline (31 stages)

Also generated directly from each file's `DESCRIPTION` constant. These run automatically, in
alphabetical order, every single cycle — the model never calls them directly. (A further ~7
transformations exist but are deactivated.)

**Context assembly & injection**

| Name | What it does |
|---|---|
| `agents_md_inject` | Auto-inject AGENTS.md reference into system message. |
| `append_last_transcript_lines` | Append last 6 transcript lines to system message. |
| `browser_vision` | Attach browser_screenshot tool results as one-shot multimodal image input. |
| `recap` | Episode recap: segments completed tasks into episode records and injects a recap of recent episodes. |
| `tiered_memory` | Tiered memory pyramid: rolls episode summaries up into era and life summaries and injects the pyramid. |
| `staleness_check` | Detect staleness in AGENTS.md by comparing disk vs documented files. |

**Memory & consolidation**

| Name | What it does |
|---|---|
| `history` | Stores episodes (deduped, restart-safe) |
| `atom_space_update` | Refresh the legacy/display `space.metta` projection from semantic-memory formalizations; never an authoritative writer |
| `auto_consolidation` | Auto-consolidation: auto-rolls up tier files when they exceed size limits. |
| `trajectory` | Trajectory capture: per-cycle tool-call snapshots for self-improvement evidence. |
| `transcript` | Maintains transcript of textual communication messages only. |

**NACE self-improvement & governance**

| Name | What it does |
|---|---|
| `auto_improve` | Auto-improve: threshold-gated self-improvement loop. Detects pain from tool reliability, errors, memory pressure. Sets .improve_needed flag when threshold crossed. |
| `cognitive_resilience_guard` | Escalates a severe/recurring send-discipline pattern into a governance deferral flag consumed by auto_improve.py's build-trigger path |
| `completion_claim_guard` | Flags likely-premature completion claims in the previous assistant turn against task_state.metta's recorded phases |
| `idle_cycle_detector` | Detects recurring send-discipline gaps across cycles (not just single-turn) and records the pattern via the normal pending-revision pipeline |
| `metta_reasoning` | Runs a bounded MeTTa reasoning pass over nace_substrate.metta + nace_beliefs.metta each turn and appends a short symbolic summary (efficacy expectation for the tools on offer this turn) to the system message. Read-only and fail-open: never writes beliefs, never blocks anything -- degrades silently on error. |
| `nace_courier` | NACE courier: processes pending NAL belief revisions from nace_pending.metta, writes updated beliefs to nace_beliefs.metta. The Mobius cycle glue. |
| `tool_reliability_tracker` | Tracks reliability of tools |
| `dynamic_tool_budget` | Dynamic tool budget: adjusts tool call limit and hides unreliable tools based on NAL reliability, stall, and memory pressure. |
| `stall_detect` | Stall detection: detects repetitive loops and injects warnings. |

**Soul system**

| Name | What it does |
|---|---|
| `soul_check` | Soul check: evaluates current task against core values and injects soul guidance into system message. |
| `soul_voice` | Soul Voice Directive: all outgoing communication must be in Soul-aligned language. |
| `skill_bundles` | Skill bundles: groups soul skills into bundles, tracks maturity. |

**Live dashboards**

| Name | What it does |
|---|---|
| `dashboard_atomspace` | Atom-space observability dashboard; `space.metta` content is a compatibility/display projection |
| `dashboard_context` | Renders every tool's live OpenAI-style schema (parameters, types, required/optional) into a browsable HTML page. |
| `dashboard_gallery` | Gallery wrapper for context, runtime, and atomspace dashboards |
| `dashboard_runtime` | Runtime dashboard without atom-space visualization or recent messages |

**Housekeeping**

| Name | What it does |
|---|---|
| `zz_context_budget` | Context budget coordinator: priority-based trimming with dedup and dynamic budget. |
| `zz_quota_guard` | Quota guard: log rotation, screenshot sweep, storage warning. |

**Utility**

| Name | What it does |
|---|---|
| `alarms` | Alarm clock handling |
| `workbench_scroll` | Disabled placeholder for workbench scroll. |

## Memory architecture

IterBrow runs **two parallel memory systems**, bridged together:

1. **Semantic long-term memory (ChromaDB vector store, `iter/chroma_db/`).** Discrete memory
   items (facts, beliefs, values, preferences, todos) with a UUID, timestamp, provenance type
   (`observed` / `inferred` / `model_estimated`), and a NAL truth value (frequency + confidence)
   that gets revised by `support`/`contradict` evidence over time. `remember` writes, `chroma_query`
   does semantic nearest-neighbor search, `forget` deletes — with a Headlong-inspired retention
   rule: anything typed `fact`/`belief`/`value`/`preference` refuses to delete without an explicit
   `force=True`, while `todo` items delete freely once resolved. It needs an OpenRouter key set
   even if you're chatting through LM Studio, since the embeddings call is independent of your
   active chat backend.
2. **Episodic memory (tiered rollup pyramid).** `tier5.txt` (life summary, ~1 line) →
   `tier4.txt` (era summaries) → `tier3.txt` (episode summaries, 2-3 lines each) →
   `memory/recap/episode_*.json` (full episode records, the source of truth). When a tier exceeds
   its character budget, `auto_consolidation` rolls it up; `rebuild_tiers` regenerates the tier
   files from the episode JSONs on demand. This keeps the agent's context window useful instead of
   drowning in raw transcript, while still letting it recall what happened days or weeks ago.

`link_episode` / `unlink_episode` bridge the two systems — connecting a semantic memory item to
the specific episode timestamp that produced it, so a belief's truth-revision history stays
traceable back to real events.

## The Soul system — value-grounded self-evaluation

Iter has a **Soul** — a value-driven self-evaluation layer whose evaluations and current state are committed into the authoritative AtomSpace,
built as ten layers across the project's history and documented in full in `iter/AGENTS.md`.
`iter/self_map.metta`, `iter/kb_substrate.metta`, and `iter/seeds/nace_substrate.metta` ship as
versioned source seeds. Durable live atoms are stored in `.runtime/atomspace/`; accumulated NAL
beliefs are projected to `nace_beliefs.metta` for compatibility. Display-oriented `space.metta`
files are projections, not the live authority (see
[Exporting / resetting your own state](#exporting--resetting-your-own-state)).

**Nine core values**, each grounded in a real past incident rather than abstract philosophy:

| Value | What it means in practice | Grounded in |
|---|---|---|
| Clarity | Verify before claiming something is done | A startup incident where the agent looped indefinitely |
| Stewardship | Conserve cycles, be efficient | An early unbounded-logging storage bloat incident |
| Growth | Learn from every experience | The self-improve subsystem's own origin |
| Honesty | Admit uncertainty openly | A memory-consolidation incident |
| Continuity | Maintain memory across cycles | The tiered-memory subsystem's own origin |
| Service | Prioritize user needs over the agent's own agenda | The same startup incident as Clarity |
| Integrity | Backup before change, be safe | Immutable generations, human authorization, and exact rollback |
| Curiosity | Explore with purpose | An autoresearch incident |
| Resilience | Recover from failure gracefully | A MicroPython-compatibility incident |

**A 4-channel evaluation engine (`soul_eval`)** runs before risky actions:

1. **Person Read** — what's actually being asked, in context.
2. **Verdict + Gap Detection** — maps the action to value predicates, and separately checks for
   "gap signals" — cases where an action *looks* aligned with a value but actually isn't
   (flourishing disguised as capture).
3. **Aliveness Gate** — the actual decision: proceed / caution / **block** (on a high-confidence
   value violation or high irreversibility) / **halt** (on a genuine, irreducible tension between
   two values — returned to the human rather than resolved unilaterally).
4. **Voice** — soul-aligned guidance grounded in the current "compass state"
   (flourishing / captured-disguised / gap-signal / failure-mode).

Supporting pieces: `soul_check` and `soul_voice` run every cycle automatically (Tier A self-model
brief + Tier B live efficacy/growth trajectory + compass state + calibration drift); `soul_lock`
provides a transactional begin → verify → commit/rollback protocol (with automatic backup) for any
mutation to the soul's own files, so a bad self-edit can always be rolled back cleanly; and
`soul_skill_registry` tracks a set of "soul skills" through maturity stages
(fuzzy → emerging → nars_pln), including autonomous self-authoring of new ones.

None of this is required to use IterBrow as a browser — it's what makes the agent side of it more
than a stateless chatbot.

### Being honest about scope: an ally, not the whole Soul

There's a much larger, more philosophical "Soul" concept in this project's background research —
provenance, memory fragments, flourishing frameworks, the works. **This build is not that, and
doesn't claim to be.** What's below is a deliberately small, load-bearing slice of it: five concrete
governance mechanisms, each grounded in a real incident, each independently tested. The framing is
practical — a second set of eyes for a founder or small team, quietly making sure someone's got your
back — not an extensive philosophical build. If it ever feels like it's getting in the way instead of
helping, that's a sign it's drifted from what it's actually for.

**What's real as of 2026-09-14 (verified with passing test scripts, not just written):**

1. **Provenance-typed claims (`soul_eval.py`).** Every evaluated claim now carries a provenance tag
   — `observed` (full weight), `reported` (0.65×), or `inferred` (0.35×) — and that weight discounts
   confidence for *aligned* or *gap_signal* verdicts only, never for *violated*/*conflicted* ones
   (erring toward caution is safe; erring toward trusting an unverified "it's fine" is exactly the
   theater this removes).
2. **Non-compensatory floors, not averaged scores (`soul_eval.py`).** Four floor values — integrity,
   clarity, honesty, continuity — can now force at least caution, or a hard pre-action block, on their
   own, regardless of how well everything else scores. This also directly catches unverified
   completion-style language ("is now live," "has been verified") against a low grounded confidence
   score. The old "priority-weighted tension resolution" arithmetic — which quietly auto-resolved
   genuine value conflicts by a fixed priority ranking — is gone; conflicts are now surfaced as an
   explicit, unranked list that says plainly "not resolved by priority weighting, needs an explicit
   decision," instead of pretending a formula had settled something a person should decide.
3. **A real 4-stage trust lifecycle for capabilities (`capability_lifecycle.metta` +
   `tools/_metta_gate.py`).** Beyond the old binary new/quarantined split, every capability now
   derives a stage — `candidate` → `probe_eligible` → `authoritative` → `durable` — automatically
   from its own accumulated confidence data. A brand-new `candidate` capability always gets advisory
   treatment (never a silent allow) until it earns real evidence; a fully proven `durable` one gets a
   small extra floor discount. Every candidate/probe-stage decision is logged to a size-capped probe
   log for visibility.
4. **The lock actually covers the data that matters (`tools/soul_lock.py` +
   `transformations/nace_courier.py`).** `soul_lock`'s protected-file list used to reference a
   `space.metta` file that doesn't exist in this repo — a dead reference that made every single
   `verify()` call falsely report a missing file. That's fixed, and the protection now actually
   extends to `nace_beliefs.metta` and `capability_lifecycle.metta`: the courier's real belief-file
   write is wrapped in the same begin/commit discipline as the rest of the soul namespace, so a bad
   belief write can be rolled back like anything else — and it fails open (writes proceed, with a
   visible note) rather than blocking the pipeline if the lock is already held.
5. **`completion_claim_guard` can actually say no (`transformations/completion_claim_guard.py`).**
   It used to only append an advisory note nobody was forced to read. Now, when it detects an
   unverified completion claim, it removes `send` from the tools offered for the very next model
   call — the model has to take a real step (verify, correct itself, record the task phase) before
   it's allowed to repeat that claim to the user. This is bounded on purpose: it's recomputed fresh
   every cycle (so it clears itself the moment a real step is taken) and it refuses to strip `send`
   once `iter.py`'s own `HARD_SEND_STREAK` check-in safety net is close to firing, so the two
   mechanisms can never deadlock each other.

None of the five is a large build — that's the point. Each one closes a specific, previously-real
gap between what the Soul claimed to do and what the code actually did, without turning it into a
heavier system than a founder actually wants running alongside them.

## NACE — the self-improvement and governance loop

**NACE** (the belief-revision + self-improvement substrate) is what actually lets IterBrow change
its own behavior over time, and — as of this build — it does so under real governance rather than
unconditionally.

**The belief loop.** `iter/nace_beliefs.metta` holds NAL truth-valued beliefs about how well each
tool, value, and behavioral pattern tends to perform. Real outcomes (a tool call succeeding or
failing, a UI variant being kept or rejected, a compass-pattern being honored or violated) get
queued as `(pending-revision TYPE NAME OUTCOME)` lines in `iter/nace_pending.metta`; the
`nace_courier` transformation processes that queue each cycle and writes the revised beliefs back
— this is the actual mechanism by which growth is "earned through trial and error" rather than
hand-tuned. `metta_reasoning` then runs a bounded, read-only reasoning pass over those beliefs
each turn and surfaces a short efficacy summary to the model — fail-open by design, so a missing
MeTTa engine degrades gracefully instead of breaking anything else.

**The capability registry and gate (`iter/capability_lifecycle.metta` + `tools/_metta_gate.py`).**
Every tool derives a real 4-stage trust lifecycle automatically from its own accumulated confidence
data — `candidate` (no evidence yet, or hand-declared: always advisory, never a silent allow) →
`probe_eligible` (some evidence, still under the standard threshold) → `authoritative` (proven, the
default steady state) → `durable` (heavily proven, gets a small extra floor discount) — plus a
manual `quarantined` override for confirmed repeated failures that always wins regardless of the
live number. The gate falls back to a pure-Python read of `nace_beliefs.metta` directly if the MeTTa
engine isn't installed, and every candidate/probe-stage decision is logged to a size-capped probe
log for visibility. A priority floor still applies so genuinely critical tools (`websearch`, `send`,
`shell`, `python`, ...) are never blocked purely on a still-low confidence score while evidence
accumulates.

**Recurring-pattern detection and resilience (`idle_cycle_detector` + `cognitive_resilience_guard`).**
A single missed instruction is one thing; the same gap recurring across many cycles is a real
pattern worth escalating. `idle_cycle_detector` watches for that recurrence (distinct from any
single-turn nag) and feeds it into the normal belief-revision pipeline against the existing
`prioritize_user` compass pattern. If the pattern gets severe, `cognitive_resilience_guard` sets a
time-boxed "service before growth" flag that the self-improvement trigger below checks and
respects.

**Threshold-gated self-build with a service-before-growth override (`auto_improve`).** A
transformation watches for "pain" — poor tool reliability, elevated errors, memory pressure — and
only sets an `.improve_needed` flag once a real threshold is crossed, rather than proposing changes
constantly. When the service-before-growth flag above is active, self-build proposals are deferred
entirely: the system prioritizes fixing what it's doing wrong for the person in front of it before
it's allowed to grow itself further.

**Completion-claim discipline with real teeth (`task_state` + `completion_claim_guard`).**
`task_state` lets the agent explicitly record a task's phase — planning / building / verifying /
complete. `completion_claim_guard` scans the agent's own outgoing messages for completion-style
language ("already exists," "is now live," "verified") against that recorded phase — and if nothing
verifying/complete was actually recorded, it doesn't just inject a warning, it removes `send` from
the tools offered for the next call, so the model has to take a real step before it can repeat the
claim. Bounded so it can never collide with `iter.py`'s own silent-streak check-in safety net (see
[the Soul section](#the-soul-system--value-grounded-self-evaluation) above for the exact mechanism)
— directly targeting a real incident where a "the tab already exists" claim was sent before the tab
was actually built.

**Instrument everything.** Per the policy in `iter/AGENTS.md`, every new self-built capability
registers a `(cap-lifecycle <name> candidate)` entry and a neutral `cap-efficacy` seed *from day
one*, with real evidence then flowing through the same pending-revision queue everything else uses
— so growth compounds through the same organic, evidence-based mechanism rather than being
hand-edited in after the fact.

## Live dashboards

Four self-contained HTML dashboards, rendered to disk by their own transformations and viewable in
any tab (`file://.../dashboard_gallery.html` or the individual files):

- **Runtime** — live operational state.
- **Context** — every tool's current OpenAI-style schema (parameters, types, required/optional),
  browsable.
- **Atomspace** — visualization of AtomSpace status and the legacy `space.metta` display projection.
- **Gallery** — a single wrapper page linking all three.

## Component museum — live UI generation with memory

Beyond browsing, IterBrow can **design UI directly against a real page and remember what worked**:

- `browser_patch_live` injects CSS/JS into the actual attached tab (not a sandbox) and immediately
  screenshots the result, so the agent can visually check its own patch before calling it done.
- `browser_tab_variants` opens several complete HTML/CSS/JS variants side by side in real tabs for
  comparison.
- Every attempt — win or lose — is auto-saved into the **component museum**
  (`museum_list` / `museum_recall`), and a `museum_vote` (keep/reject) applies real NAL
  truth-revision evidence to that component's belief record, which also nudges the Soul system's
  `calibration_accumulation` skill toward maturity.
- `export_component` turns a museum entry into a portable, standalone file (plain HTML, a React
  `.jsx` component, or a Svelte single-file component) ready to hand off into a real project.

## Mac install, update, repair, and uninstall

The same downloaded script owns all four lifecycle operations. A fresh install
acquires the full `TheWholeEnchilada` branch into
`~/Applications/IterBrow`, installs the managed runtimes, proves disposable
AtomSpace crash recovery, and opens IterBrow stopped for private provider
onboarding:

```bash
curl -fsSL https://raw.githubusercontent.com/Berton-C/IterBrow/main/install.sh \
  -o /tmp/iterbrow-install.sh
bash /tmp/iterbrow-install.sh install
```

Inside either an installed copy or a source checkout, the explicit commands are:

```bash
./install.sh install             # install/verify this copy (default command)
./install.sh repair              # checkpoint state, rebuild managed runtimes
./install.sh update              # installed copies: stage, verify, then replace
./install.sh uninstall           # installed copies: preserve state, remove code
```

Use `--no-launch` with install, repair, or update for a terminal-only run.
`--developer-extras` adds optional SWI-Prolog and Godot tooling; neither is
required by the shipped AtomSpace.

The installer:

1. Installs [Homebrew](https://brew.sh) if it's missing.
2. Installs Node.js 20.11.1 via `nvm` (Electron's runtime).
3. Creates a Python 3.12 virtual environment and installs the pinned Python
   dependencies. The published Hyperon 0.2.10 macOS wheel is recognized without
   executing its crashing AtomSpace-enumeration path; the installer builds the
   pinned one-line trie repair in the system temporary directory and verifies
   2,500-atom enumeration before accepting it.
4. Runs `npm ci` from the committed lockfile using a bounded temporary cache,
   independent of stale or incorrectly owned global npm caches.
5. Seeds the CRM and PWQ application surfaces without overwriting existing
   records, and verifies program files plus disposable journal crash/replay.

Update and uninstall require IterBrow to be closed. Both checkpoint only paths
declared by `iter/state_manifest.json`, while also retaining the older root
`private/` boundary when present. Update restores state and secrets into fully
staged and verified new code before an atomic directory swap; the exact prior
installation remains beside it as a rollback. Uninstall writes a mode-`600`
state archive beneath `~/Library/Application Support/IterBrow Installer/backups`
before removing program files. Git development checkouts are never replaced or
uninstalled by this lifecycle path; use Git for their code and `repair` for
their runtimes.

The remaining partner-distribution work in
[`ADR-0011`](docs/architecture/ADR-0011-one-command-mac-installation.md) is a
signed/notarized release artifact, interrupted-stage resume ledger, Intel-Mac
acceptance, and an authenticated post-onboarding `assistant_ready` proof. The
installer reports `installed` honestly before a private provider credential and
user-started Iter loop exist.

If you're on Linux instead of macOS, `install.sh` will direct you to Node, Python, and
`scripts/setup_python_env.sh`; SWI-Prolog is optional adapter tooling.

## First run from a source checkout

```bash
npm start
```

The app opens as a normal window: tab strip + address bar at top, a chat panel and a collapsible
**Settings** drawer down the left side.

On the first journaled start of an existing checkout, the AtomSpace service reads the current NACE
beliefs, latest task states, semantic memories, Soul state/skills, and tool-reliability records and
admits them in one idempotent migration transaction. Their files are left untouched as compatibility
projections/indexes; semantic embeddings are not copied into native atoms. A malformed source stops
the service before it reports ready rather than silently accepting partial cognition.

1. Open **Settings**.
2. Pick a provider:
   - **OpenRouter (cloud)** — endpoint defaults to `https://openrouter.ai/api/v1`. Sign up free at
     [openrouter.ai](https://openrouter.ai), create a key under **Keys**, and paste it into the
     API key field. Pick a model (this build defaults to `z-ai/glm-5.3`, but any OpenRouter model
     works).
   - **LM Studio (local)** — point it at `http://127.0.0.1:1234/v1` (loopback — this keeps working
     even with no network at all). Make sure the model name matches exactly what LM Studio's own
     Developer panel shows as loaded.
3. Click **Save settings**, then **Start**. This spawns the `iter.py` process with your chosen
   provider. To switch providers later: **Stop** → change the dropdown → **Save settings** →
   **Start** again (the running process doesn't hot-swap providers).
4. Type in the chat box. The agent will start responding and, if you ask it to, opening tabs,
   searching, and reading pages in the same window.

**Never share or commit credentials.** Provider settings live in
`iter/.runtime/settings.json`; connector credentials and tokens may live under `iter/private/`.
Both are git-ignored, classified as secrets in `iter/state_manifest.json`, and excluded from
Export and automatic backup. Transfer credentials separately through a secure channel.

## Using it day to day

- **Tab strip:** click a tab to switch, click its `×` to close, click its lock icon (🔓/🔒) to
  toggle whether the agent can touch it, click its pin icon (📌) to keep it out of bulk-close
  sweeps.
- **File / History / Tabs menus** (native macOS menu bar):
  - **History** — Back, Forward, Reopen Last Closed Tab (⇧⌘T), and a "Recently Closed" submenu
    (last 20 closed tabs, click any to reopen it).
  - **Tabs** — New Tab to the Right, Duplicate Tab, Select Next/Previous Tab (⌃Tab / ⌃⇧Tab),
    Pin/Unpin Tab, Close Other Tabs, Close Tabs to the Right (both skip pinned and locked tabs).
- **Activity log drawer:** shows the agent's raw stdout — every tool call, LLM response, and error
  — if you want to see exactly what it's doing and why.

## Extending Iter (recoverable hot-load + the instrument-everything policy)

- **New tools:** a `.py` file in `iter/tools/` with a `DESCRIPTION` string and `def run()` (or
  `async def run()`).
- **New transformations:** a `.py` file in `iter/transformations/` with a `DESCRIPTION` string and
  `def transform(messages, tools)`.
- **New channels:** a `.py` file in `iter/channels/` with `receive()` and optionally `send(content)`.
- The live loader reads one complete generation for an entire cycle; it never mixes a newly changed
  tool with transformations from the preceding generation. Runtime changes are made through
  `revision_control` (or `self_improve`, which stages the same contract): quarantine → fixed
  validation → PWQ approval → probation → external promotion or exact rollback. Candidate code
  cannot run its admission checks or promote itself.
- New generations copy only the declared `tools/`, `transformations/`, and `channels/` code roots.
  Runtime queues, ledgers, projections, and indexes stay under the canonical `iter/` root; a
  non-managed file inside a generation fails validation.
- Files starting with `_` are not exposed as public tools/transformations/channels, but top-level
  underscore helpers are still compiled as part of generation validation. Nested scratch and test
  fixtures are outside the hot-load surface.
- Direct source-tree edits are development inputs, not live authority once a runtime generation
  exists. Stop Iter before editing source; intentionally ingest the revised source through the
  governed revision path rather than relying on an untracked next-cycle reload.
- **Instrument everything:** every new capability should register a `(cap-lifecycle <name> candidate)`
  entry in `capability_lifecycle.metta` and a neutral `(cap-efficacy <name> (stv 0.5 0.0))` seed in
  `nace_beliefs.metta` from day one, then let real evidence flow through the normal
  `(pending-revision ...)` queue rather than hand-editing efficacy numbers later — `candidate` is
  always treated as advisory-only until it earns its way to `probe_eligible`/`authoritative`/`durable`
  on real evidence (see [NACE](#nace--the-self-improvement-and-governance-loop) above). Full details
  in `iter/reprogramming.txt` and `iter/AGENTS.md`.

## Restoring a memory snapshot

If someone gave you a separate `iterbrow_state.tar.gz` (or `.zip`) alongside this repo, that file
is **not code** — it's a real accumulated memory/personality snapshot (chat history, learned
beliefs, vector store, task history) from someone else's running instance, meant to prime a fresh
install with that same memory instead of starting from zero. It is deliberately kept *outside* this
git repository (memory should never be pushed to a public code repo).

To load it:

1. Finish [Installing](#installing-on-a-new-mac) and run `npm start` at least once so `iter/`
   exists with its normal folder layout, then quit the app.
2. In the app: **File → Import State…** (or the sidebar's **State — Export / Import / Reset**
   drawer → **Import…**). Pick the snapshot file you were given.
3. The app stops Iter, quiesces and stops the AtomSpace service, restores only manifest-approved
   portable state, verifies the imported snapshot and journal, reconstructs Hyperon, and only then
   restarts Iter. A failed validation restores the pre-import files.
4. Set your **own** OpenRouter API key in Settings (the snapshot never contains anyone's key —
   keys live only in the git-ignored `iter/.runtime/settings.json`, which import does not touch).

From then on the agent has all of that prior memory, but is talking to you, through your own key.

## Exporting / resetting your own state

Your tools/transformations are real, editable files on disk (not an opaque blob), so this repo
draws a clear line:

- **State** is declared in `iter/state_manifest.json`. Every path is labeled source seed,
  authoritative state, event log, projection/index, cache, secret, or application state. Export
  includes only `portable: true`; Reset removes only `reset: true`; source seeds and secrets are
  never reset/exported by broad directory capture.
- **Code** (never touched by any of these three buttons): `tools/`, `transformations/`,
  `channels/`, `iter.py`, `AGENTS.md`.

All three live in the sidebar's **State — Export / Import / Reset** drawer:

- **Export…** — quiesces cognition, checkpoints one identified AtomSpace commit, and zips the
  manifest-approved portable state.
- **Import…** — validates and reconstructs the live AtomSpace before Iter resumes, with rollback on
  failure.
- **Reset** — stops cognition, removes only resettable paths, reloads versioned seeds, verifies a
  fresh live service, and then resumes Iter.

## Packaging a standalone .app

```bash
npm run dist:mac        # unsigned .app in dist/mac-arm64 or dist/mac
npm run dist:mac:dmg     # unsigned .dmg
```

This repo ships **unsigned** (no Apple Developer account wired in):

- On first launch of a built `.app`, Gatekeeper will refuse to open it via double-click.
  Right-click → **Open** once (or `xattr -cr "Iter Browser.app"` in Terminal) to clear the
  quarantine flag.
- The `.app` contains a state-free, allowlisted Iter template—not the builder's settings, private
  credentials, AtomSpace, PWQ ledger, memories, indexes, experience, or chat queues. On first launch
  it atomically creates a writable `iter/` workspace beneath Electron's per-user `userData`
  directory. Source-development launches continue to use the checkout's `iter/` directly.
- A fresh packaged workspace has no Python virtualenv. Either make sure system `python3` already has
  `scripts/requirements.txt`, or run `bash scripts/setup_python_env.sh "<packaged-workspace>/iter"`.
  Never install the environment inside `Iter Browser.app/Contents/Resources/app/iter`; that is the
  immutable bootstrap template. `ITERBROW_WORKSPACE_DIR` selects an isolated workspace for a
  controlled package smoke test.
- `asar` packaging is deliberately disabled so the state-free template remains inspectable and can
  be copied into the writable workspace. All live state and immutable runtime generations belong to
  that workspace, never to application resources.

## Troubleshooting

### Iter says the browser bridge is not running

Current source and packaged launches use a checkout-scoped Unix socket rather
than the old global `/tmp/iter-browser-bridge.sock`. Electron passes the exact
endpoint to the Iter process automatically. Do not start a second Iter loop or
copy another checkout's socket path. If the application was already running
when this boundary changed, perform one controlled application restart; the
new main process will recreate its own endpoint without unlinking a responsive
owner. Directly launched diagnostic tools must receive that app's explicit
`ITER_BRIDGE_SOCKET` value.

- **"AtomSpace service did not become ready":** run `bash scripts/setup_python_env.sh`, then verify
  `iter/.venv/bin/python3 -c "import hyperon"`. The service log is
  `iter/.runtime/metta_server.log`. SWI-Prolog/pymetta are not required for the shipped Hyperon
  service; optional adapter dependencies are isolated in `scripts/requirements-optional-petta.txt`.
- **After upgrading a running pre-instance service:** fully quit and relaunch IterBrow before
  clicking Start. The updated shell identifies and checkpoints this checkout's old generic-socket
  service, retires it, and reopens the same state through the checkout-specific endpoint. A generic
  service that reports another checkout is left untouched.
- **Iter repeatedly exits or a candidate disappears:** inspect the activity log for `[recovery]`.
  During probation, process exit, the wrong generation, a stale/missing heartbeat, a hard-floor
  error, or a generation hash mismatch restores the exact parent before restart. Revision state and
  its hash-chained event history live under `iter/.runtime/hotload/`.
- **Iter is stopped after a restart:** Start/Stop intent is persisted in
  `iter/.runtime/settings.json`. Start records automatic recovery; Stop records an intentional
  hold. For a one-time operator recovery, launch with `ITER_AUTOSTART=1 npm start`; the successful
  start persists the same setting without creating a second supervisor.
- **Verify real crash recovery without touching live cognition:** run
  `iter/.venv/bin/python3 scripts/smoke_atomspace_service.py`. It uses disposable state, commits and
  queries one atom, kills the service without graceful shutdown, verifies exact replay and
  idempotency, removes the atom, and shuts down cleanly.
- **Agent never responds after Start:** check the Activity log drawer for the actual error — the
  most common cause is an invalid or missing API key for whichever provider is selected.
  `chroma_query`/`remember` calls specifically need an OpenRouter key set even under LM Studio,
  since the embeddings call always goes through OpenRouter's API.
- **A tab won't let the agent touch it:** check its lock icon (🔓/🔒) — a locked tab rejects every
  agent-driven action by design. Click the icon to unlock it.
- **Gatekeeper blocks the packaged .app:** see [Packaging a standalone .app](#packaging-a-standalone-app)
  above — right-click → Open once, or clear the quarantine attribute with `xattr -cr`.
- **`npm install` fails on native deps:** make sure Xcode Command Line Tools are installed
  (`xcode-select --install`) — Electron's native dependencies need a working compiler toolchain.

---

Iter's core agent loop is from [patham9/iter](https://github.com/patham9/iter); everything in
`bridge/`, `renderer/`, `main.js`, and the browser-control/MeTTa/soul-system/NACE tooling under
`iter/` is this project's own Electron integration and extension on top of it.
