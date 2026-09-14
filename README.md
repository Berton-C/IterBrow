# IterBrow

**IterBrow** is [Iter](https://github.com/patham9/iter) — an autonomous LLM agent — running
as a real Python process *inside its own Chromium-based browser*, built with Electron. It's not
a browser extension and not a sandboxed demo: it's a full multi-tab browser window you own and
drive yourself, with an AI agent living alongside you in the same window, able to see and control
the same tabs you do (except the ones you explicitly lock).

Talk to it in the sidebar chat, and it can search the web, read and click around pages, remember
what it learns across sessions, reason over a small symbolic knowledge base (MeTTa/atomspace), and
even rewrite its own tools while it runs.

---

## Table of contents

1. [What IterBrow can actually do](#what-iterbrow-can-actually-do)
2. [How it's built (architecture)](#how-its-built-architecture)
3. [Installing on a new Mac](#installing-on-a-new-mac)
4. [First run](#first-run)
5. [Using it day to day](#using-it-day-to-day)
6. [The agent's tool inventory](#the-agents-tool-inventory)
7. [Memory, reasoning, and the "Soul" system](#memory-reasoning-and-the-soul-system)
8. [Restoring a memory snapshot](#restoring-a-memory-snapshot)
9. [Exporting / resetting your own state](#exporting--resetting-your-own-state)
10. [Packaging a standalone .app](#packaging-a-standalone-app)
11. [Troubleshooting](#troubleshooting)

---

## What IterBrow can actually do

- **It's a real browser.** Tab strip, address bar, back/forward, History menu with "Recently
  Closed" and reopen-last-closed, a Tabs menu (new tab to the right, duplicate, pin/unpin,
  close-others, close-to-the-right, cycle tabs) — all the everyday things you expect, plus a
  chat panel down the side where the agent lives.
- **The agent can drive the browser too.** It can open tabs, navigate, click, type, scroll, run
  JavaScript, take screenshots, and read page text — using the same window you're looking at.
- **You can lock any tab (🔒).** A locked tab refuses every action from the agent (navigate,
  click, type, scroll, close, run JS) while you can still use it completely normally yourself.
  Use this on anything sensitive — banking, email, whatever you don't want the agent touching.
- **You can pin any tab (📌)** so it floats to the front of the tab strip and survives
  "close other tabs" / "close tabs to the right" sweeps.
- **It remembers things.** Conversation history, a vector-searchable long-term memory store, and
  a tiered "rollup" system that compresses old context into summaries so the agent stays aware of
  what happened days or weeks ago without blowing its context budget every turn.
- **It reasons over a small symbolic knowledge base.** A MeTTa (Prolog-backed logic language)
  atom space tracks belief-style facts about how well each of its own tools tends to work, and
  can advise (or, if you turn on a stricter mode, actually veto) low-confidence tool calls before
  they run. See [Memory, reasoning, and the "Soul" system](#memory-reasoning-and-the-soul-system).
- **It can improve its own code.** New tools and behaviors are plain `.py` files it (or you) can
  drop into `iter/tools/` or `iter/transformations/` — no restart needed, they're picked up on the
  next loop iteration.
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
│   └─ bridge/chat_bridge.js            — file-based inbox/outbox with iter/     │
│                                                                                  │
│  iter.py  (separate Python process, spawned/stopped by main.js)                │
│   ├─ tools/browser_*.py       → talk to the socket → drive real tabs          │
│   ├─ tools/lm_studio_chat.py  → native call to OpenRouter or a local           │
│   │                              LM Studio server (OpenAI-compatible API)     │
│   ├─ tools/metta.py           → real MeTTa evaluation via SWI-Prolog          │
│   ├─ channels/electron_ui.py  → reads/writes the same inbox/outbox files      │
│   └─ everything else (tools/, transformations/) → hot-reloadable .py files    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

A raw Chrome DevTools Protocol passthrough tool (`browser_cdp`) is exposed for anything the native
API doesn't cover (network interception, emulation, etc.).

**Tab locking and pinning are enforced only at the bridge layer** — the human user can always
lock/unlock/pin/close/navigate their own tabs from the UI regardless of lock state. The lock only
ever restrains the agent, never you.

## Installing on a new Mac

```bash
git clone https://github.com/Berton-C/IterBrow.git
cd IterBrow
./install.sh
```

`install.sh` is a one-shot bootstrapper that:

1. Installs [Homebrew](https://brew.sh) if it's missing.
2. Installs Node.js 20.11.1 via `nvm` (Electron's runtime).
3. Installs SWI-Prolog via Homebrew (optional — powers real MeTTa reasoning; everything else works
   fine without it, it just prints a warning and moves on if this step fails).
4. Creates a Python 3.12 virtual environment inside `iter/` and installs the exact pinned
   dependencies from `scripts/requirements.txt`.
5. Runs `npm install` to fetch Electron and its native dependencies.

It's safe to re-run — every step checks what's already installed and skips it. It doesn't touch
any accumulated chat/memory data (a fresh clone doesn't have any yet).

If you're on Linux instead of macOS, `install.sh` will tell you the three manual commands to run
(Node 18+, Python 3.12, optionally your distro's SWI-Prolog package) since Homebrew paths differ.

## First run

```bash
npm start
```

The app opens as a normal window: tab strip + address bar at top, a chat panel and a collapsible
**Settings** drawer down the left side.

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

**Never share or commit your API key.** It lives only in `iter/.runtime/settings.json`, which is
git-ignored — it is never written into any file this repo tracks.

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
- **Hot-reloadable behavior:** drop a new `.py` file into `iter/tools/` (a tool) or
  `iter/transformations/` (a message-pipeline step) and it's picked up on the agent's very next
  loop iteration — no restart. A leading underscore (`_name.py`) disables a file without deleting
  it.

## The agent's tool inventory

Browser control:

| Tool | What it does |
|---|---|
| `browser_tabs` | List all open tabs |
| `browser_new_tab` / `browser_close_tab` / `browser_switch_tab` | Manage tabs |
| `browser_attach` / `browser_detach` | Pin a tab as the implicit target for the tools below |
| `browser_navigate` | Load a URL in the attached (or active) tab |
| `browser_screenshot` | Capture the tab's viewport as an image for the next turn |
| `browser_eval` | Run arbitrary JS in the page and get the return value |
| `browser_read_text` | Get the page's visible text |
| `browser_click` / `browser_type` | Click/type via a CSS selector or explicit x,y |
| `browser_scroll` | Scroll the page |
| `browser_cdp` | Raw DevTools Protocol passthrough for advanced cases |

Beyond browsing, the agent ships with roughly 70 other tools across memory (`remember`, `forget`,
`pin`, `link_episode`, vector search via `chroma_query`), self-improvement (`self_improve`,
`soul_lock`, `soul_skill_registry`), reasoning (`metta`, `formalize_metta`), research
(`websearch` across DuckDuckGo/Wikipedia/HN/GitHub/Crossref/OpenLibrary), and general-purpose
system access (`shell`, `python`). Every locked/disabled tool is just a file starting with `_` in
`iter/tools/` — inspect any of them directly to see exactly what it does.

## Memory, reasoning, and the "Soul" system

- **Long-term memory** is a local vector store (`iter/chroma_db/`) the agent writes to and searches
  via embeddings — this is what lets it recall something you told it weeks ago. It needs an
  OpenRouter key set even if you're chatting through LM Studio, since the embeddings call is
  independent of your active chat backend.
- **Tiered memory rollups** compress older conversation into progressively coarser summaries so
  the agent's context window stays useful instead of drowning in raw transcript.
- **MeTTa reasoning substrate:** a small NAL-style truth-revision system tracks a belief about how
  well each tool tends to work (`nace_beliefs.metta`). Before each turn, a pre-decision pass
  annotates any low-confidence tool with a note the model can see; a separate gate can (if you
  turn on `METTA_GATE_MODE=enforce`, off by default) actually veto a tool call below a confidence
  threshold instead of just flagging it. This needs SWI-Prolog installed (see install steps above)
  — without it, the reasoning tool degrades gracefully rather than breaking anything else.
- **Soul system:** a value-driven self-evaluation layer (`iter/AGENTS.md` has the full writeup) —
  nine values grounded in the agent's own past experience (clarity, stewardship, growth, honesty,
  continuity, service, integrity, curiosity, resilience), used to gate risky actions and explain
  its own reasoning about a request.

None of this is required to use IterBrow as a browser — it's what makes the agent side of it more
than a stateless chatbot.

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
3. The app stops the agent if it's running, replaces the state files (`memory/`, `chroma_db/`,
   `experience.json`, the `.metta` knowledge files, `chat.txt`, `transcript.txt`, etc.), and
   restarts it. You'll be asked to confirm before this happens.
4. Set your **own** OpenRouter API key in Settings (the snapshot never contains anyone's key —
   keys live only in the git-ignored `iter/.runtime/settings.json`, which import does not touch).

From then on the agent has all of that prior memory, but is talking to you, through your own key.

## Exporting / resetting your own state

Your tools/transformations are real, editable files on disk (not an opaque blob), so this repo
draws a clear line:

- **State** (what Export/Import/Reset operate on): `memory/`, `chroma_db/`, `backups/`,
  `uploads/`, `transformations/.runtime/`, `experience.json`, the `.metta` knowledge files,
  `chat.txt`, `transcript.txt`, and a few small runtime flag files.
- **Code** (never touched by any of these three buttons): `tools/`, `transformations/`,
  `channels/`, `iter.py`, `AGENTS.md`.

All three live in the sidebar's **State — Export / Import / Reset** drawer:

- **Export…** — save-dialog, zips your current state wherever you choose.
- **Import…** — file-picker for a state zip, stops the agent first if running, replaces state,
  restarts if it was running. Confirms before proceeding.
- **Reset** — permanently deletes all accumulated state (your code is never touched). Confirms
  first, since this can't be undone.

## Packaging a standalone .app

```bash
npm run dist:mac        # unsigned .app in dist/mac-arm64 or dist/mac
npm run dist:mac:dmg     # unsigned .dmg
```

This repo ships **unsigned** (no Apple Developer account wired in):

- On first launch of a built `.app`, Gatekeeper will refuse to open it via double-click.
  Right-click → **Open** once (or `xattr -cr "Iter Browser.app"` in Terminal) to clear the
  quarantine flag.
- A packaged `.app`'s `iter/` folder won't have its own Python virtualenv. Either make sure your
  system `python3` already has the packages from `scripts/requirements.txt`, or run
  `bash scripts/setup_python_env.sh "/path/to/Iter Browser.app/Contents/Resources/app/iter"` to
  create one inside the bundle.
- `asar` packaging is deliberately disabled so `iter/` stays a normal folder on disk — a Python
  interpreter can't be spawned against a path inside an asar archive, and this keeps every
  hot-reloadable tool/transformation file directly editable even in a packaged build.

## Troubleshooting

- **"pymetta install failed" / MeTTa tool doesn't work:** SWI-Prolog isn't installed, or is older
  than 9.3. Run `brew install swi-prolog`, then re-run `./install.sh` (or
  `iter/.venv/bin/pip install 'pymetta[engine]'` directly). Everything else in the app works fine
  without this.
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
`bridge/`, `renderer/`, `main.js`, and the browser-control/MeTTa/soul-system tooling under `iter/`
is this project's own Electron integration on top of it.
