const { app, BaseWindow, WebContentsView, ipcMain, dialog, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execFile } = require('child_process');

const { TabManager } = require('./bridge/tab_manager');
const { startBridgeServer } = require('./bridge/browser_bridge_server');
const { makeChatBridge } = require('./bridge/chat_bridge');

const DEFAULT_SIDEBAR_WIDTH = 420;
const MIN_SIDEBAR_WIDTH = 260;
const MIN_BROWSER_WIDTH = 240; // keep the tab area from being squeezed to nothing
// Height of the full-width navigation toolbar (back/forward/reload/address
// bar) that sits directly above the browsed-page view, spanning from the
// sidebar's right edge to the window's right edge -- added 2026-09-14
// because those controls used to live squeezed inside the narrow sidebar
// column instead of above the actual page, which is not how any
// conventional browser (Chrome/Safari/Firefox) presents them.
// Split into two stacked rows on 2026-09-14: row 1 (back/forward/reload/
// lock/Dashboards) and row 2 (address bar + Go), so the URL field always
// has its own dedicated row instead of competing for space with the nav
// buttons. 72px fits two ~36px button/input rows plus their 1px divider.
const TOOLBAR_HEIGHT = 72;
const ITER_DIR = path.join(__dirname, 'iter');
const SETTINGS_PATH = path.join(ITER_DIR, '.runtime', 'settings.json');
// Tab session — which tabs were open, their URLs, and their lock state.
// Kept alongside settings.json (same .runtime/ folder, same reasoning: this
// is local-machine UI state, not accumulated agent memory, so it's
// deliberately NOT in STATE_PATHS / export-import-reset below). Added
// 2026-09-14 because before this, restarting Iter Browser for ANY code
// change silently threw away every open tab with no way to recover them --
// discovered while adding the tab-lock feature, which itself needs a
// restart to load.
const TABS_SESSION_PATH = path.join(ITER_DIR, '.runtime', 'tabs_session.json');
// Ring buffer of recently-closed tabs, independent of TABS_SESSION_PATH (which
// only ever holds what's CURRENTLY open). Backs the History menu's "Recently
// Closed" submenu and "Reopen Last Closed Tab" -- added 2026-09-14 alongside
// the menu system, same local-UI-state reasoning as TABS_SESSION_PATH (not in
// STATE_PATHS). Capped at CLOSED_TABS_LIMIT, newest first.
const CLOSED_TABS_PATH = path.join(ITER_DIR, '.runtime', 'closed_tabs.json');
const CLOSED_TABS_LIMIT = 20;
// Named, saved sets of tabs the user can open/switch-to/close as a unit --
// e.g. "Research" vs "Work" vs "Recipes" -- added 2026-09-14 per user
// request. Same local-UI-state reasoning as TABS_SESSION_PATH/CLOSED_TABS_PATH
// (not accumulated agent memory, so not in STATE_PATHS / export-import-reset).
const TAB_GROUPS_PATH = path.join(ITER_DIR, '.runtime', 'tab_groups.json');
const VENV_PYTHON = path.join(ITER_DIR, '.venv', 'bin', 'python3');
const SIDEBAR_BG = '#0d0f12'; // matches renderer/style.css --bg

let win = null;
let sidebarView = null;
let toolbarView = null;
let tabs = null;
let chatBridge = null;
let iterProcess = null;
let iterLog = [];
let sidebarWidth = DEFAULT_SIDEBAR_WIDTH;
let resizingSidebar = false;

function loadSettings() {
  const defaults = {
    provider: 'openrouter',
    openrouter: { endpoint: 'https://openrouter.ai/api/v1', model: 'z-ai/glm-5.3', apiKey: '' },
    lmstudio: { endpoint: 'http://127.0.0.1:1234/v1', model: 'qwen/qwen3.8-27b' },
    sidebarWidth: DEFAULT_SIDEBAR_WIDTH,
  };
  try {
    return { ...defaults, ...JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8')) };
  } catch (_) {
    return defaults;
  }
}

function saveSettings(settings) {
  fs.mkdirSync(path.dirname(SETTINGS_PATH), { recursive: true });
  fs.writeFileSync(SETTINGS_PATH, JSON.stringify(settings, null, 2));
}

function pythonBin() {
  return fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3';
}

function pushLog(line) {
  iterLog.push(line);
  if (iterLog.length > 500) iterLog = iterLog.slice(-500);
  if (sidebarView) sidebarView.webContents.send('iter:log', line);
}

function startIter() {
  if (iterProcess) return { already: true };
  const settings = loadSettings();
  const cfg = settings.provider === 'lmstudio' ? settings.lmstudio : settings.openrouter;
  const env = {
    ...process.env,
    BASE_URL: cfg.endpoint,
    LLM_MODEL: cfg.model,
    AI_API_KEY: settings.provider === 'lmstudio' ? 'lm-studio' : cfg.apiKey || 'dummy',
    // Long-term-memory embeddings (tools/_petta_db.py, used by chroma_query) always need a real
    // OpenRouter key regardless of chat provider -- local LM Studio models don't do embeddings.
    // That key already lives in settings.openrouter.apiKey (the single "OpenRouter API Key" field
    // in Settings), but it was only ever forwarded to the chat client as AI_API_KEY above, never
    // under the OPENROUTER_API_KEY name _petta_db.py actually reads -- so embeddings stayed blocked
    // even after the user filled in Settings. Forward the same value under both names.
    OPENROUTER_API_KEY: (settings.openrouter && settings.openrouter.apiKey) || process.env.OPENROUTER_API_KEY || '',
    ITER_BRIDGE_SOCKET: process.env.ITER_BRIDGE_SOCKET || '/tmp/iter-browser-bridge.sock',
    PYTHONUNBUFFERED: '1',
  };
  iterProcess = spawn(pythonBin(), ['iter.py'], { cwd: ITER_DIR, env });
  pushLog(`[iter] started (pid ${iterProcess.pid}) provider=${settings.provider} model=${cfg.model} base_url=${cfg.endpoint}`);
  iterProcess.stdout.on('data', (d) => pushLog(d.toString()));
  iterProcess.stderr.on('data', (d) => pushLog('[stderr] ' + d.toString()));
  iterProcess.on('exit', (code) => {
    pushLog(`[iter] exited with code ${code}`);
    iterProcess = null;
    if (sidebarView) sidebarView.webContents.send('iter:status', { running: false });
  });
  if (sidebarView) sidebarView.webContents.send('iter:status', { running: true });
  return { started: true, pid: iterProcess.pid };
}

function stopIter() {
  if (!iterProcess) return { already: true };
  iterProcess.kill('SIGTERM');
  return { stopping: true };
}

// ---------------------------------------------------------------------
// Export / Import / Reset — state-management, ported from the old HTML
// app's "Export", "Import", "Reset" buttons.
//
// The old app kept everything (agent code + accumulated memory) inside a
// single opaque virtual-filesystem blob, so "export" zipped the whole
// thing and "reset" wiped the whole thing. In this build the agent's
// code (tools/, transformations/, channels/) are real, editable files on
// disk — self_improve.py can still rewrite them at runtime, but you can
// also hand-edit them yourself — so we now distinguish:
//   STATE  = everything the agent accumulates by living (memory/,
//            chroma_db/, backups/, uploads/, experience.json,
//            *.metta knowledge files, chat.txt, transcript.txt,
//            transformations/.runtime/, .improve_cooldown, etc.)
//   CODE   = tools/, transformations/, channels/, iter.py, AGENTS.md —
//            the editable program text itself.
// Export bundles STATE only (matches what you'd actually want to carry
// between machines or snapshot before an experiment). Reset clears STATE
// only and leaves CODE untouched — a deliberate improvement over the old
// single-blob model, since wiping hand-edited or self-improved code by
// accident would be far more destructive here than in the browser build.
// ---------------------------------------------------------------------
const STATE_PATHS = [
  'memory', 'chroma_db', 'backups', 'uploads', '_screenshots',
  'transformations/.runtime',
  'experience.json', 'history.metta', 'nace_beliefs.metta', 'nace_pending.metta',
  'nace_substrate.metta', 'space.metta', 'chat.txt', 'transcript.txt',
  '.improve_cooldown', '.stall_state.json', '.history_state', '.transcript_state',
];

function runCLI(cmd, args, cwd) {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { cwd, maxBuffer: 1024 * 1024 * 256 }, (err, stdout, stderr) => {
      if (err) reject(new Error(`${cmd} ${args.join(' ')} failed: ${err.message}\n${stderr}`));
      else resolve(stdout);
    });
  });
}

async function exportState() {
  if (!win) return { error: 'no window' };
  const { canceled, filePath } = await dialog.showSaveDialog(win, {
    title: 'Export Iter state',
    defaultPath: `iter-browser-state-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`,
    filters: [{ name: 'Zip archive', extensions: ['zip'] }],
  });
  if (canceled || !filePath) return { canceled: true };

  const existing = STATE_PATHS.filter((p) => fs.existsSync(path.join(ITER_DIR, p)));
  if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  await runCLI('zip', ['-r', filePath, ...existing], ITER_DIR);
  return { exported: filePath };
}

async function importState() {
  if (!win) return { error: 'no window' };
  const { canceled, filePaths } = await dialog.showOpenDialog(win, {
    title: 'Import Iter state',
    properties: ['openFile'],
    filters: [{ name: 'Zip archive', extensions: ['zip'] }],
  });
  if (canceled || !filePaths || !filePaths[0]) return { canceled: true };
  const zipPath = filePaths[0];

  const wasRunning = !!iterProcess;
  if (wasRunning) stopIter();

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'iter-import-'));
  try {
    await runCLI('unzip', ['-o', zipPath, '-d', tmpDir], ITER_DIR);
    // Tolerate a wrapper folder inside the zip (mirrors the old HTML app's
    // Import behavior), by descending until we find a recognizable state dir/file.
    let sourceRoot = tmpDir;
    let entries = fs.readdirSync(sourceRoot);
    if (entries.length === 1 && fs.statSync(path.join(sourceRoot, entries[0])).isDirectory()) {
      const inner = path.join(sourceRoot, entries[0]);
      const innerEntries = fs.readdirSync(inner);
      if (innerEntries.some((e) => STATE_PATHS.includes(e))) sourceRoot = inner;
    }
    for (const rel of STATE_PATHS) {
      const src = path.join(sourceRoot, rel);
      if (!fs.existsSync(src)) continue;
      const dest = path.join(ITER_DIR, rel);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.rmSync(dest, { recursive: true, force: true });
      fs.cpSync(src, dest, { recursive: true });
    }
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }

  if (wasRunning) startIter();
  return { imported: zipPath, restarted: wasRunning };
}

function resetState() {
  const wasRunning = !!iterProcess;
  if (wasRunning) stopIter();
  for (const rel of STATE_PATHS) {
    const target = path.join(ITER_DIR, rel);
    fs.rmSync(target, { recursive: true, force: true });
  }
  return { reset: true, restarted: false };
}

// ---------------------------------------------------------------------
// Tab session persistence — see TABS_SESSION_PATH comment above. Saved on
// every tab change (create/close/navigate/lock, debounced) and flushed
// synchronously on window/app close so the very last state is never lost.
// ---------------------------------------------------------------------
let tabSessionSaveTimer = null;

function saveTabSession() {
  if (!tabs) return;
  try {
    const list = tabs.list(); // [{id, title, url, active, locked, pinned}]
    const session = {
      tabs: list.map((t) => ({ url: t.url, locked: t.locked, pinned: t.pinned })),
      activeIndex: list.findIndex((t) => t.active),
    };
    fs.mkdirSync(path.dirname(TABS_SESSION_PATH), { recursive: true });
    fs.writeFileSync(TABS_SESSION_PATH, JSON.stringify(session, null, 2));
  } catch (err) {
    pushLog(`[tabs] failed to save session: ${err.message}`);
  }
}

function loadClosedTabs() {
  try {
    const raw = fs.readFileSync(CLOSED_TABS_PATH, 'utf8');
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch (_) {
    return [];
  }
}

function saveClosedTabs(list) {
  try {
    fs.mkdirSync(path.dirname(CLOSED_TABS_PATH), { recursive: true });
    fs.writeFileSync(CLOSED_TABS_PATH, JSON.stringify(list, null, 2));
  } catch (err) {
    pushLog(`[tabs] failed to save closed-tabs history: ${err.message}`);
  }
}

// ---------------------------------------------------------------------
// Tab groups -- named, saved sets of tabs the user can reopen, switch to,
// or bulk-close as a unit. Added 2026-09-14.
// ---------------------------------------------------------------------
function loadTabGroups() {
  try {
    const raw = fs.readFileSync(TAB_GROUPS_PATH, 'utf8');
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch (_) {
    return [];
  }
}

function saveTabGroups(list) {
  try {
    fs.mkdirSync(path.dirname(TAB_GROUPS_PATH), { recursive: true });
    fs.writeFileSync(TAB_GROUPS_PATH, JSON.stringify(list, null, 2));
  } catch (err) {
    pushLog(`[tabs] failed to save tab groups: ${err.message}`);
  }
}

// Snapshots every currently open tab (URL/title/pinned) under `name` and
// appends it to the saved list. Overwrites an existing group of the same
// name rather than creating a duplicate.
function saveCurrentTabsAsGroup(name) {
  if (!tabs) return loadTabGroups();
  const snapshot = tabs.list().map((t) => ({ url: t.url, title: t.title, pinned: t.pinned }));
  const groups = loadTabGroups().filter((g) => g.name !== name);
  groups.push({ id: Date.now(), name, createdAt: new Date().toISOString(), tabs: snapshot });
  saveTabGroups(groups);
  return groups;
}

// Opens every tab in the group alongside whatever is already open --
// deliberately non-destructive (never closes existing tabs) since
// silently losing open tabs to "open a group" would be a nasty surprise.
function openTabGroup(groupId) {
  const group = loadTabGroups().find((g) => g.id === Number(groupId));
  if (!group || !tabs) return;
  for (const t of group.tabs) {
    const id = tabs.createTab(t.url);
    if (t.pinned) tabs.setPinned(id, true);
  }
}

// Closes every currently open, unpinned, unlocked tab, then opens the
// group -- i.e. "switch context". Pinned/locked tabs are left alone, same
// bulk-close safety convention as closeOtherTabs/closeTabsToRight.
function switchToTabGroup(groupId) {
  const group = loadTabGroups().find((g) => g.id === Number(groupId));
  if (!group || !tabs) return;
  const victims = [...tabs.tabs.values()].filter((t) => !t.pinned && !t.locked).map((t) => t.id);
  for (const id of victims) tabs.closeTab(id);
  openTabGroup(groupId);
}

// Closes any currently open tab whose URL matches one saved in the group
// (pinned/locked tabs are skipped, same convention as above). Tab ids
// aren't stable across sessions, so URL is the only reliable match.
function closeTabGroup(groupId) {
  const group = loadTabGroups().find((g) => g.id === Number(groupId));
  if (!group || !tabs) return;
  const urls = new Set(group.tabs.map((t) => t.url));
  const victims = [...tabs.tabs.values()].filter((t) => urls.has(t.url) && !t.pinned && !t.locked).map((t) => t.id);
  for (const id of victims) tabs.closeTab(id);
}

function deleteTabGroup(groupId) {
  const groups = loadTabGroups().filter((g) => g.id !== Number(groupId));
  saveTabGroups(groups);
  return groups;
}

// Called from tabs.onTabClosed (see TabManager.closeTab) for every close,
// whether triggered by the human, the menu, or Iter's own bridge tools --
// so "Recently Closed" always reflects reality regardless of who closed it.
// Skips URLs that are pointless to reopen (blank/new-tab placeholder).
function recordClosedTab(snapshot) {
  if (!snapshot || !snapshot.url || snapshot.url === 'about:blank') return;
  const list = loadClosedTabs();
  list.unshift({ url: snapshot.url, title: snapshot.title || snapshot.url, closedAt: Date.now() });
  saveClosedTabs(list.slice(0, CLOSED_TABS_LIMIT));
  Menu.setApplicationMenu(buildAppMenu()); // rebuild so the Recently Closed submenu picks up the new entry immediately
}

function saveTabSessionDebounced() {
  clearTimeout(tabSessionSaveTimer);
  tabSessionSaveTimer = setTimeout(saveTabSession, 400);
}

function loadTabSession() {
  try {
    const raw = fs.readFileSync(TABS_SESSION_PATH, 'utf8');
    const session = JSON.parse(raw);
    if (session && Array.isArray(session.tabs) && session.tabs.length) return session;
  } catch (_) {
    // No saved session yet (first launch after this feature) or unreadable --
    // fall back to a single default tab, same as pre-2026-09-14 behavior.
  }
  return null;
}

// Pops the most recent entry off the closed-tabs stack and reopens it as a
// new tab. Used by both "Reopen Last Closed Tab" (History menu) and the
// individual entries inside the "Recently Closed" submenu (which reopen by
// index rather than always popping index 0).
function reopenClosedTab(index = 0) {
  const list = loadClosedTabs();
  if (!list.length || index >= list.length) return null;
  const [entry] = list.splice(index, 1);
  saveClosedTabs(list);
  const id = tabs.createTab(entry.url);
  Menu.setApplicationMenu(buildAppMenu());
  return id;
}

// Right-click ('two-finger click' on a trackpad) menu for a tab pill in the
// sidebar's tab strip -- added 2026-09-14 alongside the tab-pill overflow
// fix, so closing/managing a tab never depends on the tiny 'x' being
// reachable. Mirrors the same actions already in the Tabs/History menus,
// just scoped to the tab that was actually clicked (which may not be the
// active tab).
function showTabContextMenu(id) {
  if (!win || !tabs) return;
  const tabId = Number(id);
  const tab = tabs.tabs.get(tabId);
  if (!tab) return;
  const locked = tabs.isLocked(tabId);
  const pinned = tabs.isPinned(tabId);
  const template = [
    {
      label: 'Close Tab',
      enabled: !locked,
      click: () => tabs.closeTab(tabId),
    },
    {
      label: 'Close Other Tabs',
      click: () => tabs.closeOtherTabs(tabId),
    },
    {
      label: 'Close Tabs to the Right',
      click: () => tabs.closeTabsToRight(tabId),
    },
    { type: 'separator' },
    {
      label: pinned ? 'Unpin Tab' : 'Pin Tab',
      click: () => tabs.setPinned(tabId, !pinned),
    },
    {
      label: locked ? 'Unlock Tab' : 'Lock Tab',
      click: () => tabs.setLocked(tabId, !locked),
    },
    { type: 'separator' },
    {
      label: 'Duplicate Tab',
      click: () => tabs.duplicateTab(tabId),
    },
    {
      label: 'New Tab to the Right',
      click: () => tabs.createTabAfter(tabId, 'https://www.google.com'),
    },
    { type: 'separator' },
    {
      label: 'Reload',
      click: () => tab.view.webContents.reload(),
    },
    {
      label: 'Reopen Last Closed Tab',
      enabled: loadClosedTabs().length > 0,
      click: () => reopenClosedTab(0),
    },
  ];
  Menu.buildFromTemplate(template).popup({ window: win });
}

function contentBounds() {
  const [w, h] = win.getContentSize();
  return {
    x: sidebarWidth,
    y: TOOLBAR_HEIGHT,
    width: Math.max(0, w - sidebarWidth),
    height: Math.max(0, h - TOOLBAR_HEIGHT),
  };
}

function toolbarBounds() {
  const [w] = win.getContentSize();
  return { x: sidebarWidth, y: 0, width: Math.max(0, w - sidebarWidth), height: TOOLBAR_HEIGHT };
}

// ---------------------------------------------------------------------
// Sidebar resize — drag the boundary between the Iter column and the
// browser tab area. WebContentsViews are native, disjoint surfaces, so a
// plain CSS/DOM drag handle can't track the mouse once the cursor crosses
// into the tab view. Instead, for the duration of the drag we temporarily
// grow the sidebar's own view to cover the full window (and raise it to
// the top of the z-order) with a transparent background, so its own page
// can see mousemove/mouseup anywhere — while the visible chrome inside
// that page stays pinned to the current width via #app-shell in
// renderer.js/style.css, and the actual tab view underneath (unmoved,
// still showing through the transparent overlay region) is live-resized
// via tabs.relayout() as the width changes. On release we shrink the
// sidebar view back down to the final width and restore normal z-order.
// ---------------------------------------------------------------------
function sidebarResizeStart() {
  if (!win || resizingSidebar) return { started: false };
  resizingSidebar = true;
  const [w, h] = win.getContentSize();
  win.contentView.addChildView(sidebarView); // re-adding an existing child bumps it to the top z-order
  sidebarView.setBackgroundColor('#00000000');
  sidebarView.setBounds({ x: 0, y: 0, width: w, height: h });
  return { started: true, width: sidebarWidth };
}

function sidebarResizeMove(newWidth) {
  if (!win || !resizingSidebar) return { width: sidebarWidth };
  const [w] = win.getContentSize();
  const maxWidth = Math.max(MIN_SIDEBAR_WIDTH, w - MIN_BROWSER_WIDTH);
  sidebarWidth = Math.max(MIN_SIDEBAR_WIDTH, Math.min(maxWidth, Math.round(newWidth)));
  toolbarView.setBounds(toolbarBounds());
  if (tabs) tabs.relayout();
  return { width: sidebarWidth };
}

function sidebarResizeEnd() {
  if (!win || !resizingSidebar) return { width: sidebarWidth };
  resizingSidebar = false;
  const [, h] = win.getContentSize();
  sidebarView.setBounds({ x: 0, y: 0, width: sidebarWidth, height: h });
  sidebarView.setBackgroundColor(SIDEBAR_BG);
  toolbarView.setBounds(toolbarBounds());
  if (tabs && tabs.activeId) tabs.switchTab(tabs.activeId); // restore normal z-order (tab on top)
  const settings = loadSettings();
  settings.sidebarWidth = sidebarWidth;
  saveSettings(settings);
  return { width: sidebarWidth };
}

// ---------------------------------------------------------------------
// Terminal & Files — ported from the old HTML app's "Terminal & Files"
// panel. Two independent pieces:
//   - Files: a sandboxed file browser/editor scoped to ITER_DIR (the
//     iter/ working directory). Plain fs calls, path-checked so nothing
//     can escape ITER_DIR via "..".
//   - Terminal: a single long-lived, non-interactive `bash` process with
//     stdin/stdout piped (no pty — see README for what that does and
//     doesn't support). Each submitted line is followed by a `printf`
//     sentinel carrying the exit code and $PWD, so the UI can tell where
//     one command's output ends and split cleanly for the next prompt.
// ---------------------------------------------------------------------
function safeResolve(relPath) {
  const root = path.resolve(ITER_DIR);
  const target = path.resolve(root, relPath || '.');
  if (target !== root && !target.startsWith(root + path.sep)) {
    throw new Error('Path escapes the iter/ working directory');
  }
  return target;
}

function fsList(relPath) {
  const dir = safeResolve(relPath || '.');
  const stat = fs.statSync(dir);
  if (!stat.isDirectory()) throw new Error('Not a directory');
  const items = fs.readdirSync(dir, { withFileTypes: true }).map((e) => ({
    name: e.name,
    isDir: e.isDirectory(),
  }));
  items.sort((a, b) => (a.isDir !== b.isDir ? (a.isDir ? -1 : 1) : a.name.localeCompare(b.name)));
  const rel = path.relative(ITER_DIR, dir);
  return { path: rel === '' ? '.' : rel, items };
}

const FS_READ_MAX_BYTES = 2 * 1024 * 1024;

function fsRead(relPath) {
  const target = safeResolve(relPath);
  const stat = fs.statSync(target);
  if (stat.isDirectory()) throw new Error('Cannot open a directory as a file');
  if (stat.size > FS_READ_MAX_BYTES) return { path: relPath, tooLarge: true, size: stat.size };
  const buf = fs.readFileSync(target);
  const sample = buf.subarray(0, Math.min(buf.length, 8000));
  if (sample.includes(0)) return { path: relPath, binary: true, size: stat.size };
  return { path: relPath, content: buf.toString('utf8'), size: stat.size };
}

function fsWrite(relPath, content) {
  const target = safeResolve(relPath);
  fs.writeFileSync(target, content, 'utf8');
  return { saved: true, path: relPath };
}

let termProcess = null;
let termBuffer = '';
let termCmdCounter = 0;
const TERM_MARKER_RE = /__ITERTERMDONE_(\d+)__::(.*?)::(-?\d+)\r?\n/;

function termEmit(channel, payload) {
  if (sidebarView) sidebarView.webContents.send(channel, payload);
}

function flushTerminalBuffer() {
  let match;
  while ((match = TERM_MARKER_RE.exec(termBuffer))) {
    const before = termBuffer.slice(0, match.index);
    if (before) termEmit('terminal:data', before);
    termEmit('terminal:done', { cwd: match[2], code: Number(match[3]) });
    termBuffer = termBuffer.slice(match.index + match[0].length);
  }
  // Hold back a tail that might be a marker still streaming in; flush
  // everything else immediately so normal output never waits on it.
  const tailGuardIdx = termBuffer.lastIndexOf('__ITERTERMDONE_');
  if (tailGuardIdx === -1) {
    if (termBuffer) { termEmit('terminal:data', termBuffer); termBuffer = ''; }
  } else if (tailGuardIdx > 0) {
    termEmit('terminal:data', termBuffer.slice(0, tailGuardIdx));
    termBuffer = termBuffer.slice(tailGuardIdx);
  }
}

function startTerminal() {
  if (termProcess) return { already: true };
  termProcess = spawn('/bin/bash', [], {
    cwd: ITER_DIR,
    env: { ...process.env, TERM: 'dumb' },
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  termBuffer = '';
  const onData = (d) => { termBuffer += d.toString(); flushTerminalBuffer(); };
  termProcess.stdout.on('data', onData);
  termProcess.stderr.on('data', onData);
  termProcess.on('exit', (code) => {
    termEmit('terminal:data', `\n[shell exited with code ${code}]\n`);
    termProcess = null;
  });
  return { started: true, cwd: ITER_DIR };
}

function runTerminalCommand(cmd) {
  if (!termProcess) startTerminal();
  termCmdCounter += 1;
  const marker = `__ITERTERMDONE_${termCmdCounter}__`;
  termProcess.stdin.write(cmd + '\n');
  termProcess.stdin.write(`printf '${marker}::%s::%d\\n' "$PWD" "$?"\n`);
  return { sent: true };
}

function interruptTerminal() {
  if (!termProcess) return { already: false };
  termProcess.kill('SIGINT');
  return { interrupted: true };
}

function stopTerminal() {
  if (!termProcess) return { already: true };
  termProcess.kill('SIGTERM');
  termProcess = null;
  return { stopping: true };
}

// ---------------------------------------------------------------------
// Application menu.
//
// Electron never showed a real menu here before — with no Menu.buildFromTemplate
// /setApplicationMenu call anywhere, macOS fell back to Electron's bare-bones
// built-in default (File > Close Window and nothing else useful). Worse, this
// app's window is a BaseWindow with several independent WebContentsViews (the
// sidebar + one per tab) rather than a single BrowserWindow, so even Electron's
// default role-based items that depend on BrowserWindow.getFocusedWindow()
// (Toggle Developer Tools, Close, zoom, fullscreen...) silently do nothing here
// — there's no "the" webContents to find. Every window/dev-tools item below is
// a plain click handler against the specific view it means (active tab vs the
// Iter sidebar) instead of a role, so it actually works. Only the OS-native
// text-editing roles (Edit menu) and app-level roles (about/hide/quit) are safe
// to keep as roles — those act on the focused webContents at the input layer /
// the app itself, not on BrowserWindow.getFocusedWindow().
//
// Developer Tools gets its own top-level menu (between Edit and View, exactly
// where it was asked to go) rather than living under View (the Chrome
// convention) or Window (the Safari convention): this app is a debugging tool
// for its own agent as much as it is a browser, so it earns dedicated,
// always-visible real estate. Because the sidebar (Iter's chat/controls) and
// each tab are separate views, there are two distinct explicit entries —
// "Active Tab" and "Iter Sidebar" — rather than one ambiguous "Toggle
// Developer Tools" that only ever covers one of them.
// ---------------------------------------------------------------------
function buildAppMenu() {
  const isMac = process.platform === 'darwin';
  const activeTab = () => (tabs && tabs.activeId != null ? tabs.tabs.get(tabs.activeId) : null);

  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    }] : []),
    {
      label: 'File',
      submenu: [
        {
          label: 'New Tab',
          accelerator: 'CmdOrCtrl+T',
          click: () => tabs && tabs.createTab('https://www.google.com'),
        },
        {
          label: 'Close Tab',
          accelerator: 'CmdOrCtrl+W',
          click: () => {
            const tab = activeTab();
            if (tab) tabs.closeTab(tab.id);
          },
        },
        { type: 'separator' },
        {
          label: 'Save Page As…',
          accelerator: 'CmdOrCtrl+S',
          click: () => {
            const tab = activeTab();
            if (!tab || !win) return;
            dialog.showSaveDialog(win, { defaultPath: (tab.title || 'page') + '.html' }).then((result) => {
              if (!result.canceled && result.filePath) {
                tab.view.webContents.savePage(result.filePath, 'HTMLComplete').catch(() => {});
              }
            });
          },
        },
        {
          label: 'Print…',
          accelerator: 'CmdOrCtrl+P',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.print();
          },
        },
        { type: 'separator' },
        {
          label: 'Close Window',
          accelerator: 'Shift+CmdOrCtrl+W',
          click: () => win && win.close(),
        },
        ...(isMac ? [] : [{ label: 'Exit', role: 'quit' }]),
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'Developer Tools',
      submenu: [
        {
          label: 'Toggle DevTools — Active Tab',
          accelerator: 'CmdOrCtrl+Alt+I',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.toggleDevTools();
          },
        },
        {
          label: 'Toggle DevTools — Iter Sidebar',
          accelerator: 'CmdOrCtrl+Alt+Shift+I',
          click: () => {
            if (sidebarView) sidebarView.webContents.toggleDevTools();
          },
        },
        { type: 'separator' },
        {
          label: 'Reload Active Tab',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.reload();
          },
        },
        {
          label: 'Force Reload Active Tab',
          accelerator: 'Shift+CmdOrCtrl+R',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.reloadIgnoringCache();
          },
        },
      ],
    },
    {
      label: 'History',
      submenu: [
        {
          label: 'Back',
          accelerator: 'CmdOrCtrl+[',
          click: () => {
            const tab = activeTab();
            if (tab && tab.view.webContents.navigationHistory.canGoBack()) tab.view.webContents.navigationHistory.goBack();
          },
        },
        {
          label: 'Forward',
          accelerator: 'CmdOrCtrl+]',
          click: () => {
            const tab = activeTab();
            if (tab && tab.view.webContents.navigationHistory.canGoForward()) tab.view.webContents.navigationHistory.goForward();
          },
        },
        { type: 'separator' },
        {
          label: 'Reopen Last Closed Tab',
          accelerator: 'Shift+CmdOrCtrl+T',
          enabled: loadClosedTabs().length > 0,
          click: () => reopenClosedTab(0),
        },
        {
          label: 'Recently Closed',
          // Rebuilt on every menu open (buildAppMenu runs fresh each time it's
          // called, and we call Menu.setApplicationMenu(buildAppMenu()) again
          // after every close/reopen) so this list is never stale.
          submenu: loadClosedTabs().length
            ? loadClosedTabs().map((entry, i) => ({
                label: (entry.title || entry.url).slice(0, 60),
                sublabel: new Date(entry.closedAt).toLocaleString(),
                click: () => reopenClosedTab(i),
              }))
            : [{ label: '(No recently closed tabs)', enabled: false }],
        },
      ],
    },
    {
      label: 'Tabs',
      submenu: [
        {
          label: 'New Tab to the Right',
          accelerator: 'Alt+CmdOrCtrl+T',
          click: () => {
            const tab = activeTab();
            tabs && tabs.createTabAfter(tab ? tab.id : null, 'https://www.google.com');
          },
        },
        {
          label: 'Duplicate Tab',
          click: () => {
            const tab = activeTab();
            if (tab) tabs.duplicateTab(tab.id);
          },
        },
        { type: 'separator' },
        {
          label: 'Select Next Tab',
          accelerator: 'Ctrl+Tab',
          click: () => tabs && tabs.selectAdjacentTab(1),
        },
        {
          label: 'Select Previous Tab',
          accelerator: 'Ctrl+Shift+Tab',
          click: () => tabs && tabs.selectAdjacentTab(-1),
        },
        { type: 'separator' },
        {
          label: (() => {
            const tab = activeTab();
            return tab && tab.pinned ? 'Unpin Tab' : 'Pin Tab';
          })(),
          click: () => {
            const tab = activeTab();
            if (tab) tabs.setPinned(tab.id, !tab.pinned);
          },
        },
        { type: 'separator' },
        {
          label: 'Close Other Tabs',
          click: () => {
            const tab = activeTab();
            if (tab) tabs.closeOtherTabs(tab.id);
          },
        },
        {
          label: 'Close Tabs to the Right',
          click: () => {
            const tab = activeTab();
            if (tab) tabs.closeTabsToRight(tab.id);
          },
        },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Actual Size',
          accelerator: 'CmdOrCtrl+0',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.setZoomLevel(0);
          },
        },
        {
          label: 'Zoom In',
          accelerator: 'CmdOrCtrl+Plus',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.setZoomLevel(tab.view.webContents.getZoomLevel() + 0.5);
          },
        },
        {
          label: 'Zoom Out',
          accelerator: 'CmdOrCtrl+-',
          click: () => {
            const tab = activeTab();
            if (tab) tab.view.webContents.setZoomLevel(tab.view.webContents.getZoomLevel() - 0.5);
          },
        },
        { type: 'separator' },
        {
          label: 'Toggle Full Screen',
          accelerator: isMac ? 'Ctrl+Cmd+F' : 'F11',
          click: () => win && win.setFullScreen(!win.isFullScreen()),
        },
      ],
    },
    {
      label: 'Window',
      submenu: [
        { label: 'Minimize', accelerator: 'CmdOrCtrl+M', click: () => win && win.minimize() },
        ...(isMac ? [{ label: 'Zoom', click: () => win && (win.isMaximized() ? win.unmaximize() : win.maximize()) }] : []),
      ],
    },
  ];

  return Menu.buildFromTemplate(template);
}

function createWindow() {
  const initialSettings = loadSettings();
  sidebarWidth = initialSettings.sidebarWidth || DEFAULT_SIDEBAR_WIDTH;

  win = new BaseWindow({ width: 1400, height: 900, title: 'Iter Browser' });

  sidebarView = new WebContentsView({
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: false,
    },
  });
  win.contentView.addChildView(sidebarView);
  sidebarView.setBackgroundColor(SIDEBAR_BG);
  sidebarView.setBounds({ x: 0, y: 0, width: sidebarWidth, height: win.getContentSize()[1] });
  sidebarView.webContents.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  // Full-width navigation toolbar (back/forward/reload/address bar), sitting
  // directly above the browsed-page view -- see TOOLBAR_HEIGHT above.
  toolbarView = new WebContentsView({
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: false,
    },
  });
  win.contentView.addChildView(toolbarView);
  toolbarView.setBackgroundColor(SIDEBAR_BG);
  toolbarView.setBounds(toolbarBounds());
  toolbarView.webContents.loadFile(path.join(__dirname, 'renderer', 'toolbar.html'));

  tabs = new TabManager(win, { getContentBounds: contentBounds });
  tabs.onTabsChanged = (list) => {
    sidebarView.webContents.send('tabs:update', list);
    toolbarView.webContents.send('tabs:update', list);
    saveTabSessionDebounced();
  };
  // Fires just before a tab is actually removed (see TabManager.closeTab),
  // for every close path -- menu, sidebar UI, or Iter's bridge tools alike.
  tabs.onTabClosed = (snapshot) => recordClosedTab(snapshot);
  // Restore whatever tabs were open last time (added 2026-09-14) instead of
  // always opening a single blank google.com tab -- see TABS_SESSION_PATH.
  const savedSession = loadTabSession();
  if (savedSession) {
    let restoredActive = null;
    savedSession.tabs.forEach((t, i) => {
      const id = tabs.createTab(t.url || 'https://www.google.com');
      if (t.locked) tabs.setLocked(id, true);
      if (t.pinned) tabs.setPinned(id, true);
      if (i === savedSession.activeIndex) restoredActive = id;
    });
    if (restoredActive) tabs.switchTab(restoredActive);
    pushLog(`[tabs] restored ${savedSession.tabs.length} tab(s) from last session`);
  } else {
    tabs.createTab('https://www.google.com');
  }

  Menu.setApplicationMenu(buildAppMenu());

  win.on('resize', () => {
    if (resizingSidebar) return; // bounds are being driven by the drag handlers instead
    const [w, h] = win.getContentSize();
    sidebarView.setBounds({ x: 0, y: 0, width: sidebarWidth, height: h });
    toolbarView.setBounds(toolbarBounds());
    tabs.relayout();
  });

  win.on('closed', () => {
    clearTimeout(tabSessionSaveTimer);
    saveTabSession(); // flush the last state synchronously, don't rely on the debounce timer surviving shutdown
    for (const tab of tabs.tabs.values()) tab.view.webContents.close();
    sidebarView.webContents.close();
    toolbarView.webContents.close();
    win = null;
  });

  chatBridge = makeChatBridge(ITER_DIR, (content) => {
    if (sidebarView) sidebarView.webContents.send('chat:incoming', content);
  });

  startBridgeServer(tabs, pushLog);
}

// ---------------------------------------------------------------------
// IPC — everything the sidebar UI (renderer/renderer.js) can call.
// The exact same TabManager instance is driven by Iter's own tools via
// the Unix socket bridge above, so UI actions and agent actions are
// always looking at the same tabs.
// ---------------------------------------------------------------------
ipcMain.handle('tabs:list', () => tabs.list());
ipcMain.handle('tabs:new', (_e, url) => tabs.createTab(url));
ipcMain.handle('tabs:close', (_e, id) => tabs.closeTab(id));
ipcMain.handle('tabs:switch', (_e, id) => tabs.switchTab(id));
// User-only: toggles the padlock shown in the tab strip. Enforced against
// Iter's own tools in bridge/browser_bridge_server.js, not here — the human
// can always lock/unlock/close their own tabs from this IPC path.
ipcMain.handle('tabs:toggleLock', (_e, id) => tabs.setLocked(id, !tabs.isLocked(id)));
// User-only, same reasoning as toggleLock: pinning is a human organizational
// tool, not exposed to Iter over the bridge.
ipcMain.handle('tabs:togglePin', (_e, id) => tabs.setPinned(id, !tabs.isPinned(id)));
ipcMain.handle('tabs:contextMenu', (_e, id) => showTabContextMenu(id));
ipcMain.handle('tabs:reorder', (_e, orderedIds) => tabs.reorder(orderedIds));
ipcMain.handle('tabGroups:list', () => loadTabGroups());
ipcMain.handle('tabGroups:save', (_e, name) => saveCurrentTabsAsGroup(name));
ipcMain.handle('tabGroups:open', (_e, groupId) => openTabGroup(groupId));
ipcMain.handle('tabGroups:switch', (_e, groupId) => switchToTabGroup(groupId));
ipcMain.handle('tabGroups:close', (_e, groupId) => closeTabGroup(groupId));
ipcMain.handle('tabGroups:delete', (_e, groupId) => deleteTabGroup(groupId));
ipcMain.handle('tabs:navigate', (_e, { id, url }) => tabs.navigate(id, url));
ipcMain.handle('tabs:back', (_e, id) => {
  const tab = tabs.tabs.get(id);
  if (tab && tab.view.webContents.navigationHistory.canGoBack()) tab.view.webContents.navigationHistory.goBack();
});
ipcMain.handle('tabs:forward', (_e, id) => {
  const tab = tabs.tabs.get(id);
  if (tab && tab.view.webContents.navigationHistory.canGoForward()) tab.view.webContents.navigationHistory.goForward();
});
ipcMain.handle('tabs:reload', (_e, id) => {
  const tab = tabs.tabs.get(id);
  if (tab) tab.view.webContents.reload();
});

ipcMain.handle('chat:send', (_e, content) => chatBridge.sendToIter(content));
ipcMain.handle('iter:start', () => startIter());
ipcMain.handle('iter:stop', () => stopIter());
ipcMain.handle('iter:status', () => ({ running: !!iterProcess }));
ipcMain.handle('iter:recentLog', () => iterLog.slice(-200));
ipcMain.handle('settings:load', () => loadSettings());
ipcMain.handle('settings:save', (_e, settings) => {
  saveSettings(settings);
  return { saved: true };
});

ipcMain.handle('state:export', () => exportState());
ipcMain.handle('state:import', () => importState());
ipcMain.handle('state:reset', () => resetState());

ipcMain.handle('sidebar:resize-start', () => sidebarResizeStart());
ipcMain.handle('sidebar:resize-move', (_e, w) => sidebarResizeMove(w));
ipcMain.handle('sidebar:resize-end', () => sidebarResizeEnd());

ipcMain.handle('fs:list', (_e, relPath) => fsList(relPath));
ipcMain.handle('fs:read', (_e, relPath) => fsRead(relPath));
ipcMain.handle('fs:write', (_e, { path: relPath, content }) => fsWrite(relPath, content));

ipcMain.handle('terminal:start', () => startTerminal());
ipcMain.handle('terminal:run', (_e, cmd) => runTerminalCommand(cmd));
ipcMain.handle('terminal:interrupt', () => interruptTerminal());
ipcMain.handle('terminal:stop', () => stopTerminal());
ipcMain.handle('dashboards:open', () => tabs.createTab('file://' + path.join(ITER_DIR, 'dashboard_gallery.html')));

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (iterProcess) iterProcess.kill('SIGTERM');
  if (termProcess) termProcess.kill('SIGTERM');
  if (chatBridge) chatBridge.stop();
  app.quit();
});
