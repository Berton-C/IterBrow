# PWQ — Pending Work Queue: Build Design Document
*(Generated 2026-09-19 by Iter from the live shipped build. Everything below was verified against the real files this session.)*

## 1. What PWQ is
PWQ is the negotiation surface between the user and Iter: a dark-gold dashboard
where Iter proposes work items and the user answers with clicks (choose option /
give orders / counter-propose / set alarm / mark done). It is NOT an app feature
that computes anything — it is a **renderer page + one hand-curated JSON file + an
agent-side convention**. That tri-partite nature is exactly why it does not
"transfer": the page and button ship with the app, but the data file is a local
runtime artifact that each Iter must curate.

## 2. Architecture (3 layers + 1 convention)
| Layer | File | Role |
|---|---|---|
| App shell | `main.js`, `preload.js`, `renderer/toolbar.{html,js}` | PWQ toolbar button → IPC `pwq:open` → opens the page in a tab |
| Page | `iter/pwq.html` (16.9KB, self-contained) | All rendering + interaction logic, zero dependencies |
| Data | `iter/.runtime/pwq.json` | The queue itself |
| Convention | (none — agent behavior) | Iter writes proposals into pwq.json; reads user answers back each cycle |

### 2.1 App-shell wiring (all verified present at app root, 2026-09-19)
- `main.js:1434` — `ipcMain.handle('pwq:open', () => tabs.createTab('file://' + path.join(ITER_DIR, 'pwq.html')));`
- `preload.js:68` — `openPWQ: () => ipcRenderer.invoke('pwq:open'),`
- `preload.js:60` — `fsRead: (relPath) => ipcRenderer.invoke('fs:read', relPath),` (fsWrite analogous)
- `preload.js:3` — `contextBridge.exposeInMainWorld('iterApi', {...})`
- `renderer/toolbar.js:37` — `btn-pwq` click → `window.iterApi.openPWQ()`

## 3. Why her tab exists but stays empty (diagnosis)
1. **pwq.json is not shipped code** — `.runtime/` is runtime state. A fresh
   install has the button + page, but no queue file, and nothing populates it
   until *her* Iter writes one. Page load falls through to
   `data = {version:1, items:[]}` and renders the empty state. This is the
   primary cause: **PWQ populates only when the local Iter actively curates it.**
2. Session restore: `tabs_session.json` pins the tab, but with an absolute
   `file://` path — if a session file was copied between machines, the tab points
   at a nonexistent path until re-opened via the toolbar button.
3. Secondary: older app builds (pre pwq:open patch) lack the IPC handler → the
   toolbar button silently does nothing. Verify her `main.js` has `pwq:open`.

## 4. Data schema — `.runtime/pwq.json`
```json
{
  "version": 1,
  "items": [
    {
      "id": "pwq-<slug>",
      "title": "short title",
      "ask": "1-3 sentence plain-language question to the user",
      "proposed_shape": "Iter's recommended execution shape",
      "options": [ { "label": "A — ...", "desc": "what it does" } ],
      "status": "proposed | negotiating | orders given | in progress | done",
      "user_input": "",
      "orders_given": false,
      "selected_option": null,
      "created": "2026-09-14 20:29:00",
      "alarm": null,
      "negotiation_log": [ { "time": "2026-09-14 20:29:00", "who": "iter|user", "text": "..." } ]
    }
  ]
}
```
- `created` format is `YYYY-MM-DD HH:MM:SS` (space separator — the page
  replaces it with 'T' for Date parsing).
- Append log entries on EVERY state change, from both sides. The log renders
  newest-first. Timestamps local.

## 5. Page rendering logic (pwq.html)
- **Load cascade**: `window.iterApi.fsRead('.runtime/pwq.json')` (bridge) →
  fallback `fetch('.runtime/pwq.json')` (works under file:// because the JSON
  sits one directory below the page) → final fallback empty queue.
- **Stats/filter bar**: counts waiting (status != done), orders given
  (orders_given && !done), done, total + oldest-age. Clicking a filter re-renders.
- **Card states**: age classes `fresh` (<1.5d) / `warming` (1.5–3d) / `hot`
  (>=3d, gold glow), `done` dimmed. Status chips: proposed (blue) /
  negotiating (amber) / orders given (green) / in progress (blue) / done (green).
- **Interactions** (each = state change + log + save):
  - click an option → `selected_option=i`, status→`negotiating`, log "Leaning toward: ..."
  - textarea + ORDERS GIVEN checkbox → `user_input`, status→`orders given`, log
  - Counter-propose (💬, prompt) → status `negotiating`, log user text
  - Alarm (⏰, prompt: free text like "tomorrow 9am") → `alarm` chip shown
  - Mark done (✔) → status `done`
- **Save cascade**: `iterApi.fsWrite` when the bridge exists; ALWAYS also mirrors
  to `localStorage['pwq_mirror']`. **Known wart**: without the bridge the page
  cannot write the JSON back to disk — the agent must be told to pull the mirror.
- Theme tokens: bg `#0f0d1a`, panels `#1a1730/#221d3d`, gold `#d4a94e`, serif
  (Georgia). No build step, no dependencies — one file.

## 6. Faithful recreation on her laptop
**Fast path (exact copy):**
1. Copy `iter/pwq.html` to her `iter/` directory.
2. Create `iter/.runtime/pwq.json` — easiest: copy `iter/pwq_seed.json` (this repo) to `iter/.runtime/pwq.json`. It contains a self-teaching welcome proposal that exercises the full interaction chain; delete it after answering.
3. Restart IterBrow; click the PWQ toolbar button (re-opens the tab with a
   correct absolute path); the card should render immediately.
4. Teach her Iter the convention: proposals → write pwq.json; each cycle → read
   it back; execute `orders given` items; mark `done` when finished.

**From-scratch path:** build the page per §4–5 (a single HTML file, ~300 lines:
theme, stats bar, card renderer, 5 interactions, load/save cascades) — no other
dependency. The JSON is the only contract.

## 7. Verification checklist (machine-verify discipline)
1. **Reload the tab first** — renderer pages serve cached pre-edit state
   indefinitely; a stale tab is not evidence of failure (learned 2026-09-18).
2. DOM card count == items in pwq.json payload.
3. Stats bar counts match (waiting/orders/done/total).
4. Click each filter — counts stay consistent, empty-state message when zero.
5. Click an option → verify pwq.json changed on disk (bridge build) or
   localStorage `pwq_mirror` (standalone) — then reload and confirm persistence.
6. Screenshot for visual confirmation.
