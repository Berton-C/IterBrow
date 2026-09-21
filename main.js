const { app, BaseWindow, WebContentsView, ipcMain, dialog, Menu, systemPreferences, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execFile } = require('child_process');
const net = require('net');

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
// Height of the full-width tab strip, sitting above everything else
// (sidebar, toolbar, page). Unlike TOOLBAR_HEIGHT this is NOT fixed --
// tabstrip.js measures its own real rendered height (which grows/shrinks
// as tabs wrap into more or fewer rows) and reports it via the
// 'tabstrip:height' IPC message; tabstripHeight below always reflects the
// latest reported value. DEFAULT_TABSTRIP_HEIGHT is just the pre-report
// starting size for one row. Added 2026-09-17 so tabs get the full window
// width instead of being squeezed into the sidebar column.
const DEFAULT_TABSTRIP_HEIGHT = 42;
const MIN_TABSTRIP_HEIGHT = 30;
const MAX_TABSTRIP_HEIGHT = 200; // sane ceiling so a runaway report can't eat the whole window
const ITER_DIR = path.join(__dirname, 'iter');
const SETTINGS_PATH = path.join(ITER_DIR, '.runtime', 'settings.json');
// Tab session — which tabs were open, their URLs, and their lock state.
// Kept alongside settings.json (same .runtime/ folder). This is
// local-machine UI state rather than accumulated agent memory, so it stays
// out of STATE_PATHS / resetState (resetting the agent's memory should
// never wipe your open tabs) -- but it IS carried along by export/import
// via PERSONAL_STATE_PATHS below (which now captures the whole .runtime/
// folder), so tabs travel with you between machines.
// Added 2026-09-14 because before this, restarting Iter Browser for ANY code
// change silently threw away every open tab with no way to recover them --
// discovered while adding the tab-lock feature, which itself needs a
// restart to load.
const TABS_SESSION_PATH = path.join(ITER_DIR, '.runtime', 'tabs_session.json');
// Ring buffer of recently-closed tabs, independent of TABS_SESSION_PATH (which
// only ever holds what's CURRENTLY open). Backs the History menu's "Recently
// Closed" submenu and "Reopen Last Closed Tab" -- added 2026-09-14 alongside
// the menu system, same local-UI-state reasoning as TABS_SESSION_PATH (kept
// out of STATE_PATHS/resetState, included in export/import via
// PERSONAL_STATE_PATHS). Capped at CLOSED_TABS_LIMIT, newest first.
const CLOSED_TABS_PATH = path.join(ITER_DIR, '.runtime', 'closed_tabs.json');
const CLOSED_TABS_LIMIT = 20;
// Named, saved sets of tabs the user can open/switch-to/close as a unit --
// e.g. "Research" vs "Work" vs "Recipes" -- added 2026-09-14 per user
// request. Same local-UI-state reasoning as TABS_SESSION_PATH/CLOSED_TABS_PATH
// (kept out of STATE_PATHS/resetState, included in export/import via
// PERSONAL_STATE_PATHS).
const TAB_GROUPS_PATH = path.join(ITER_DIR, '.runtime', 'tab_groups.json');
const VENV_PYTHON = path.join(ITER_DIR, '.venv', 'bin', 'python3');
const SIDEBAR_BG = '#0d0f12'; // matches renderer/style.css --bg
// Persistent MeTTa atomspace server (metta_server.py) -- see startMettaServer()
// below. Unix socket, same protocol shape as ITER_BRIDGE_SOCKET above.
const ITER_METTA_SOCKET = process.env.ITER_METTA_SOCKET || '/tmp/iter-metta-bridge.sock';

let win = null;
let sidebarView = null;
let toolbarView = null;
let tabstripView = null;
let tabs = null;
let chatBridge = null;
let iterProcess = null;
let mettaProcess = null;
let iterLog = [];
let sidebarWidth = DEFAULT_SIDEBAR_WIDTH;
let tabstripHeight = DEFAULT_TABSTRIP_HEIGHT;
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

// Checks whether metta_server.py is already alive and answering, by making
// one real request over its socket rather than just checking the socket
// file exists (a stale file from a previous crash would otherwise look
// like "running"). Mirrors the same trust boundary as the browser bridge:
// local-machine only, short timeout, fails closed.
function pingMettaServer(timeoutMs = 1500) {
  return new Promise((resolve) => {
    if (!fs.existsSync(ITER_METTA_SOCKET)) return resolve(false);
    const sock = net.createConnection(ITER_METTA_SOCKET);
    let done = false;
    const finish = (ok) => {
      if (done) return;
      done = true;
      try { sock.destroy(); } catch (_) {}
      resolve(ok);
    };
    const timer = setTimeout(() => finish(false), timeoutMs);
    sock.on('connect', () => sock.write(JSON.stringify({ method: 'status', params: {} }) + '\n'));
    sock.on('data', (chunk) => {
      clearTimeout(timer);
      try {
        finish(!!JSON.parse(chunk.toString().split('\n')[0]).ok);
      } catch (_) {
        finish(false);
      }
    });
    sock.on('error', () => { clearTimeout(timer); finish(false); });
  });
}

// Starts (or confirms) the persistent MeTTa atomspace server -- see
// metta_server.py's own docstring for the full design rationale. Called
// once from createWindow() below, satisfying the "npm start starts it, or
// checks it's already running and starts it if not -- one command to
// remember" requirement (2026-09-19).
//
// Launched detached + unref()'d so it deliberately OUTLIVES this Electron
// process: the whole point is persistence across app restarts (real atoms
// accumulating in memory across many npm-start/quit cycles), not just
// within one session, so window-all-closed / app quit does NOT kill it --
// see that handler below, which only kills iterProcess/termProcess.
async function startMettaServer() {
  const alreadyRunning = await pingMettaServer();
  if (alreadyRunning) {
    pushLog('[metta] persistent MeTTa server already running, reusing it');
    return { already: true };
  }
  // Stale socket file with nothing listening on it -- clear it so the new
  // process can bind cleanly.
  try { fs.unlinkSync(ITER_METTA_SOCKET); } catch (_) {}
  const logPath = path.join(ITER_DIR, '.runtime', 'metta_server.log');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const logFd = fs.openSync(logPath, 'a');
  try {
    mettaProcess = spawn(pythonBin(), ['metta_server.py'], {
      cwd: ITER_DIR,
      env: { ...process.env, ITER_METTA_SOCKET, ITER_DIR, PYTHONUNBUFFERED: '1' },
      detached: true,
      stdio: ['ignore', logFd, logFd],
    });
    mettaProcess.unref();
    pushLog('[metta] started persistent MeTTa server (pid ' + mettaProcess.pid + '); log: ' + logPath);
    return { started: true, pid: mettaProcess.pid };
  } catch (e) {
    pushLog('[metta] FAILED to start MeTTa server: ' + e.message);
    return { error: e.message };
  }
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
  // Added 2026-09-18: these were siblings of files already above (same
  // accumulated-learning role) but had been left out since whenever they
  // were introduced, so Reset State/Export/Import silently skipped them.
  'capability_lifecycle.metta', 'self_map.metta', 'task_state.metta', 'atomspace_data.json',
];
// Everything that makes up your personal running environment on THIS
// machine -- open tabs, tab groups, closed-tab history, UI settings, the
// PWQ queue, CRM contacts/tasks/events, and your private notes -- as
// opposed to STATE_PATHS above, which is the agent's accumulated
// memory/learning. Kept separate so Reset State (which wipes STATE_PATHS to
// clear the agent's memory/personality) never touches any of this. Export
// and Import bundle STATE_PATHS + PERSONAL_STATE_PATHS together, so moving
// to a new machine (or restoring a snapshot) brings your whole working
// environment along, not just the agent's memory.
//
// '.runtime' is captured WHOLESALE (the whole folder, not individual
// filenames) specifically so that anything new added under .runtime/ later
// -- another JSON file, another dated backup -- is automatically included
// in every future Export without needing a code change here. This directory
// never holds login/cookie data (Electron keeps that in its own userData
// path, entirely outside this repo), so capturing it wholesale cannot leak
// credentials. Renamed from TAB_STATE_PATHS and broadened 2026-09-18: the
// old exact-filename list silently dropped settings.json, pwq.json,
// .runtime/pages/, .runtime/electron_ui/, and any dated backup/journal
// file -- none of those ever showed up in an export and there was no
// warning that they were missing.
const PERSONAL_STATE_PATHS = [
  '.runtime', 'private', 'crm/data',
];

// ---------------------------------------------------------------------
// Automatic rolling backups -- independent of the user-triggered Export
// button, so there's always a recent safety net even if you never click
// Export yourself. Runs every AUTO_BACKUP_INTERVAL_MS in the background
// (started from app.whenReady() below) and keeps only the newest
// AUTO_BACKUP_KEEP zips, deleting older ones as new ones land -- 6h x 4
// kept = a rolling 24h window. Stored under Electron's own userData path,
// NOT inside this git repo, so these can never end up committed/pushed
// by accident regardless of .gitignore correctness. The Restore button
// (below) lets you pick any of the kept backups, not just the newest, in
// case the most recent one turns out to be bad.
// ---------------------------------------------------------------------
const AUTO_BACKUP_DIR = path.join(app.getPath('userData'), 'auto_backups');
const AUTO_BACKUP_INTERVAL_MS = 6 * 60 * 60 * 1000; // 6 hours
const AUTO_BACKUP_KEEP = 4; // -> 24h rolling window at the interval above
let autoBackupTimer = null;

async function runAutoBackup() {
  try {
    fs.mkdirSync(AUTO_BACKUP_DIR, { recursive: true });
    saveTabSession();
    const wanted = [...STATE_PATHS, ...PERSONAL_STATE_PATHS];
    const existing = wanted.filter((p) => fs.existsSync(path.join(ITER_DIR, p)));
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const zipPath = path.join(AUTO_BACKUP_DIR, `autobackup-${stamp}.zip`);
    await runCLI('zip', ['-r', zipPath, ...existing], ITER_DIR);
    pruneAutoBackups();
    pushLog(`[auto-backup] saved ${existing.length} item(s) -> ${path.basename(zipPath)}`);
  } catch (e) {
    pushLog(`[auto-backup] failed: ${e.message}`);
  }
}

function listAutoBackupsSorted() {
  if (!fs.existsSync(AUTO_BACKUP_DIR)) return [];
  return fs.readdirSync(AUTO_BACKUP_DIR)
    .filter((f) => f.startsWith('autobackup-') && f.endsWith('.zip'))
    .map((f) => {
      const full = path.join(AUTO_BACKUP_DIR, f);
      const stat = fs.statSync(full);
      return { file: f, full, mtimeMs: stat.mtimeMs, size: stat.size };
    })
    .sort((a, b) => b.mtimeMs - a.mtimeMs);
}

function pruneAutoBackups() {
  const all = listAutoBackupsSorted();
  for (const old of all.slice(AUTO_BACKUP_KEEP)) fs.rmSync(old.full, { force: true });
}

function startAutoBackupTimer() {
  if (autoBackupTimer) return;
  // Take one shortly after launch if none exist yet (fresh install, or the
  // folder was cleared), so there's a safety net soon instead of waiting a
  // full interval.
  if (!listAutoBackupsSorted().length) setTimeout(runAutoBackup, 30 * 1000);
  autoBackupTimer = setInterval(runAutoBackup, AUTO_BACKUP_INTERVAL_MS);
}

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

  // Flush the latest tab session synchronously first -- saveTabSession is
  // normally debounced 400ms after the last tab change, so without this an
  // export taken right after opening/closing a tab could bundle stale data.
  saveTabSession();
  const wanted = [...STATE_PATHS, ...PERSONAL_STATE_PATHS];
  const existing = wanted.filter((p) => fs.existsSync(path.join(ITER_DIR, p)));
  // Report anything expected-but-missing instead of silently dropping it --
  // this used to fail silent, which is exactly how the tab-export gap and
  // several other missing paths went unnoticed for days. Not finding a path
  // isn't necessarily wrong (e.g. you may have no private/ folder yet), but
  // you should be able to see it happened.
  const missing = wanted.filter((p) => !fs.existsSync(path.join(ITER_DIR, p)));
  if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
  await runCLI('zip', ['-r', filePath, ...existing], ITER_DIR);
  return { exported: filePath, itemCount: existing.length, missing };
}

async function importState() {
  if (!win) return { error: 'no window' };
  const { canceled, filePaths } = await dialog.showOpenDialog(win, {
    title: 'Import Iter state',
    properties: ['openFile'],
    filters: [{ name: 'Zip archive', extensions: ['zip'] }],
  });
  if (canceled || !filePaths || !filePaths[0]) return { canceled: true };
  return restoreFromZipPath(filePaths[0]);
}

// Shared by importState() (user picks a zip via the file dialog) and
// restoreAutoBackup() (Restore button -- path is already known, one of
// the rolling AUTO_BACKUP_KEEP snapshots in AUTO_BACKUP_DIR, no dialog
// needed). Identical restore behavior either way.
async function restoreFromZipPath(zipPath) {
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
    const wanted = [...STATE_PATHS, ...PERSONAL_STATE_PATHS];
    var restored = [];
    for (const rel of wanted) {
      const src = path.join(sourceRoot, rel);
      if (!fs.existsSync(src)) continue;
      const dest = path.join(ITER_DIR, rel);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.rmSync(dest, { recursive: true, force: true });
      fs.cpSync(src, dest, { recursive: true });
      restored.push(rel);
    }
    // Report what this zip actually had vs. what this build of Iter Browser
    // knows to look for. If the zip is missing something this build expects
    // (e.g. it was exported by an older or newer build with a different
    // STATE_PATHS/PERSONAL_STATE_PATHS list), surface that now instead of
    // just silently ending up with a thinner restore than you expected --
    // this is exactly how a stale build on a different machine can look
    // like a broken Export when Export was actually fine.
    var notFoundInZip = wanted.filter((rel) => !restored.includes(rel));
    var importedSummary = { restored, notFoundInZip };
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }

  // An imported tabs_session.json won't take effect until the tab manager
  // re-reads it, which only happens at window creation -- if Iter Browser's
  // window is already open (import doesn't restart the window, only the
  // agent process), reload the saved session into the live tab bar now so
  // the imported tabs show up without requiring a full app restart.
  const importedSession = loadTabSession();
  if (importedSession && tabs) {
    for (const id of [...tabs.tabs.keys()]) tabs.closeTab(id);
    for (const t of importedSession.tabs) {
      const id = tabs.createTab(t.url);
      if (t.pinned) tabs.setPinned(id, true);
      if (t.locked) tabs.setLocked(id, true);
    }
  }

  if (wasRunning) startIter();
  return { imported: zipPath, restarted: wasRunning, itemCount: importedSummary.restored.length, notFoundInZip: importedSummary.notFoundInZip };
}

// Restore button: no file dialog -- the caller (renderer, after showing the
// user the rolling list from listAutoBackupsSorted()) already knows exactly
// which auto-backup zip to use.
async function restoreAutoBackup(backupFull) {
  if (!fs.existsSync(backupFull)) return { error: 'That backup no longer exists (it may have aged out of the rolling window).' };
  return restoreFromZipPath(backupFull);
}

// Restore button entry point: shows a native picker over the up-to-4 kept
// auto-backups (newest first) so you can fall back to an older one if the
// newest turns out to be bad, then restores the chosen one. No file-picker
// dialog -- these are the app's own rolling snapshots, not a user-chosen zip.
async function restoreState() {
  if (!win) return { error: 'no window' };
  const backups = listAutoBackupsSorted();
  if (!backups.length) {
    await dialog.showMessageBox(win, {
      type: 'warning',
      title: 'No auto-backups yet',
      message: 'No auto-backups exist yet. They start after the app has been running about 30 seconds, then every 6 hours after that.',
      buttons: ['OK'],
    });
    return { canceled: true, reason: 'no-backups' };
  }
  const labels = backups.map((b) => {
    const when = new Date(b.mtimeMs).toLocaleString();
    const mb = (b.size / (1024 * 1024)).toFixed(1);
    return `${when}  (${mb} MB)`;
  });
  const buttons = [...labels, 'Cancel'];
  const { response } = await dialog.showMessageBox(win, {
    type: 'question',
    title: 'Restore from auto-backup',
    message: 'Choose a backup to restore. This replaces your current state -- pick an earlier one if the most recent looks wrong.',
    buttons,
    cancelId: buttons.length - 1,
    defaultId: 0,
  });
  if (response === buttons.length - 1) return { canceled: true };
  const chosen = backups[response];
  const result = await restoreAutoBackup(chosen.full);
  return { ...result, restoredFrom: chosen.file };
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

// Re-snapshots the CURRENTLY open tabs into an EXISTING group, identified
// by id rather than retyped name -- added 2026-09-17 per user report that
// the only way to update a saved group (e.g. after removing 2 tabs you no
// longer want in it) was to retype its exact name into the text field,
// which silently creates a second group instead of an overwrite on any
// typo. This keeps the group's original id/name/createdAt-of-first-save,
// only replacing its `tabs` snapshot and bumping `updatedAt`.
function resaveTabGroup(groupId) {
  if (!tabs) return loadTabGroups();
  const groups = loadTabGroups();
  const group = groups.find((g) => g.id === Number(groupId));
  if (!group) return groups;
  group.tabs = tabs.list().map((t) => ({ url: t.url, title: t.title, pinned: t.pinned }));
  group.updatedAt = new Date().toISOString();
  saveTabGroups(groups);
  return groups;
}

// Opens every tab in the group alongside whatever is already open --
// deliberately non-destructive (never closes existing tabs) since
// silently losing open tabs to "open a group" would be a nasty surprise.
// Skips any URL that's already open in some tab -- added 2026-09-17 to fix
// a duplication bug: closeTabGroup() intentionally leaves pinned/locked
// tabs open (see below), so re-opening the same group later used to
// recreate those survivors as brand-new duplicate tabs every time,
// compounding on each open/close cycle (9 tabs -> 11 -> 13 -> ...).
function openTabGroup(groupId) {
  const group = loadTabGroups().find((g) => g.id === Number(groupId));
  if (!group || !tabs) return;
  const openUrls = new Set([...tabs.tabs.values()].map((t) => t.url));
  for (const t of group.tabs) {
    if (openUrls.has(t.url)) continue;
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

// Reopens a specific "Recently Closed" entry by index (0 = most recent),
// without removing it from the stack -- unlike reopenClosedTab(), this is
// for the sidebar's Recently Closed panel where the user may want to
// reopen the same entry more than once. Added 2026-09-17 alongside
// surfacing that panel in the UI (the data already existed via
// CLOSED_TABS_PATH/loadClosedTabs, it just wasn't reachable from inside
// the app -- only from the native History menu / tab right-click).
function reopenClosedTabAt(index) {
  const list = loadClosedTabs();
  const entry = list[Number(index)];
  if (!entry || !tabs) return;
  tabs.createTab(entry.url);
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
  const top = tabstripHeight + TOOLBAR_HEIGHT;
  return {
    x: sidebarWidth,
    y: top,
    width: Math.max(0, w - sidebarWidth),
    height: Math.max(0, h - top),
  };
}

function toolbarBounds() {
  const [w] = win.getContentSize();
  return { x: sidebarWidth, y: tabstripHeight, width: Math.max(0, w - sidebarWidth), height: TOOLBAR_HEIGHT };
}

// Full-width tab strip -- spans x:0 to the window's right edge (unlike the
// toolbar/content views, it is NOT offset by sidebarWidth, since it sits
// above the sidebar too). Height is whatever tabstrip.js last reported.
function tabstripBounds() {
  const [w] = win.getContentSize();
  return { x: 0, y: 0, width: w, height: tabstripHeight };
}

// Sidebar's resting (non-drag) bounds -- pushed down by the tab strip's
// current height, same as the toolbar/content views.
function sidebarBounds() {
  const [, h] = win.getContentSize();
  return { x: 0, y: tabstripHeight, width: sidebarWidth, height: Math.max(0, h - tabstripHeight) };
}

// Re-applies every view's bounds from the current sidebarWidth/tabstripHeight
// -- called on window resize and whenever tabstrip.js reports a new height.
// Skipped mid-drag: the sidebar-resize handlers below drive bounds directly
// while dragging, and calling this partway through would fight them.
function layoutAll() {
  if (!win || resizingSidebar) return;
  tabstripView.setBounds(tabstripBounds());
  sidebarView.setBounds(sidebarBounds());
  toolbarView.setBounds(toolbarBounds());
  if (tabs) tabs.relayout();
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
  // Starts below the tab strip (y: tabstripHeight), not y: 0 -- the strip
  // has its own dedicated full-width view now and must stay visible and
  // interactive throughout the drag, not get covered by this temporary
  // transparent full-window overlay.
  sidebarView.setBounds({ x: 0, y: tabstripHeight, width: w, height: Math.max(0, h - tabstripHeight) });
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
  sidebarView.setBounds(sidebarBounds());
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

// Scope camera/mic access to only the local device-capture page --
// otherwise, once macOS has granted this app camera/mic access at the
// process level, any regular browsing tab (a real website) could also
// silently request it. file:// + capture.html is the only origin allowed;
// everything else (including 'display-capture', 'geolocation', etc.) is
// denied here regardless of what a tab asks for. Registered inside
// createWindow() (not at module scope) because session.defaultSession is
// only usable after app.whenReady() has fired, and createWindow only ever
// runs via app.whenReady().then(createWindow) below.
function isCapturePageOrigin(webContents) {
  const url = (webContents && webContents.getURL && webContents.getURL()) || '';
  return url.startsWith('file://') && url.includes('/renderer/capture.html');
}

const MAC_PRIVACY_PANES = {
  camera: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Camera',
  microphone: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone',
};

function createWindow() {
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media') return callback(isCapturePageOrigin(webContents));
    callback(false);
  });
  session.defaultSession.setPermissionCheckHandler((webContents, permission) => {
    if (permission === 'media') return isCapturePageOrigin(webContents);
    return false;
  });

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
  sidebarView.setBounds(sidebarBounds());
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

  // Full-width tab strip, sitting above everything -- sidebar, toolbar, and
  // the browsed page. Added last so it's naturally on top of the z-order by
  // default; sidebarResizeStart()/End() above also keep its vertical space
  // clear during the sidebar-width drag so it's never covered either way.
  tabstripView = new WebContentsView({
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: false,
    },
  });
  win.contentView.addChildView(tabstripView);
  tabstripView.setBackgroundColor(SIDEBAR_BG);
  tabstripView.setBounds(tabstripBounds());
  tabstripView.webContents.loadFile(path.join(__dirname, 'renderer', 'tabstrip.html'));

  tabs = new TabManager(win, { getContentBounds: contentBounds });
  tabs.onTabsChanged = (list) => {
    tabstripView.webContents.send('tabs:update', list);
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

  win.on('resize', () => layoutAll());

  win.on('closed', () => {
    clearTimeout(tabSessionSaveTimer);
    if (autoBackupTimer) { clearInterval(autoBackupTimer); autoBackupTimer = null; }
    saveTabSession(); // flush the last state synchronously, don't rely on the debounce timer surviving shutdown
    for (const tab of tabs.tabs.values()) tab.view.webContents.close();
    sidebarView.webContents.close();
    toolbarView.webContents.close();
    tabstripView.webContents.close();
    win = null;
  });

  chatBridge = makeChatBridge(ITER_DIR, (content) => {
    if (sidebarView) sidebarView.webContents.send('chat:incoming', content);
  });

  startBridgeServer(tabs, pushLog);
  startMettaServer();
  // Watchdog: metta_server.py is a detached background process outside
  // Electron's own supervision -- if it crashes mid-session nothing else
  // in this app would ever notice or restart it, silently breaking every
  // transformation that depends on the MeTTa bridge (this happened for
  // real on 2026-09-20, cascading into 8 unrelated-looking "TIMEOUT after
  // 5s" failures). startMettaServer() already pings first and no-ops if
  // healthy, so calling it repeatedly here is safe.
  setInterval(() => {
    startMettaServer().catch((e) => pushLog('[metta] watchdog restart failed: ' + e.message));
  }, 60000);
  startAutoBackupTimer();
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
ipcMain.handle('tabGroups:resave', (_e, groupId) => resaveTabGroup(groupId));
ipcMain.handle('tabGroups:open', (_e, groupId) => openTabGroup(groupId));
ipcMain.handle('tabGroups:switch', (_e, groupId) => switchToTabGroup(groupId));
ipcMain.handle('tabGroups:close', (_e, groupId) => closeTabGroup(groupId));
ipcMain.handle('tabGroups:delete', (_e, groupId) => deleteTabGroup(groupId));

// Recently Closed -- surfaces the same closed_tabs.json history already
// used by the History menu / tab right-click, but as a browsable panel
// inside the app itself. Added 2026-09-17 per user report that there was
// no way to recover an accidentally-closed tab without going through the
// native menu bar. list() never mutates the stack; reopen() re-creates a
// tab without removing the entry, so the same item can be reopened again.
ipcMain.handle('closedTabs:list', () => loadClosedTabs());
ipcMain.handle('closedTabs:reopen', (_e, index) => { reopenClosedTabAt(index); return loadClosedTabs(); });
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
ipcMain.handle('metta:status', async () => ({ running: await pingMettaServer() }));
ipcMain.handle('metta:start', () => startMettaServer());
ipcMain.handle('iter:status', () => ({ running: !!iterProcess }));
ipcMain.handle('iter:recentLog', () => iterLog.slice(-200));
ipcMain.handle('settings:load', () => loadSettings());
ipcMain.handle('settings:save', (_e, settings) => {
  saveSettings(settings);
  return { saved: true };
});

// Permissions panel -- human-facing status/grant/revoke-shortcut controls.
// Independent of Iter's own device_capture.py tool: that tool's tab
// triggers the same macOS getUserMedia prompt on its own the first time it
// runs, whether or not the user has opened this panel. This panel just
// gives the user visibility and a one-click way to (re)request or jump to
// System Settings to revoke.
ipcMain.handle('permissions:status', () => ({
  camera: systemPreferences.getMediaAccessStatus('camera'),
  microphone: systemPreferences.getMediaAccessStatus('microphone'),
}));
ipcMain.handle('permissions:request', async (_e, kind) => {
  if (kind !== 'camera' && kind !== 'microphone') throw new Error('unknown permission kind: ' + kind);
  const granted = await systemPreferences.askForMediaAccess(kind);
  return { granted, status: systemPreferences.getMediaAccessStatus(kind) };
});
ipcMain.handle('permissions:openSystemSettings', (_e, kind) => {
  const url = MAC_PRIVACY_PANES[kind];
  if (!url) throw new Error('unknown permission kind: ' + kind);
  return shell.openExternal(url);
});

ipcMain.handle('state:export', () => exportState());
ipcMain.handle('state:import', () => importState());
ipcMain.handle('state:restore', () => restoreState());
ipcMain.handle('state:reset', () => resetState());

ipcMain.handle('sidebar:resize-start', () => sidebarResizeStart());
ipcMain.handle('sidebar:resize-move', (_e, w) => sidebarResizeMove(w));
ipcMain.handle('sidebar:resize-end', () => sidebarResizeEnd());

// One-way: tabstrip.js reports its real rendered height every time it
// changes (tabs added/removed/reflowed into more or fewer rows), and this
// repositions the sidebar/toolbar/page to make room. Clamped to a sane
// range and a no-op if unchanged, so a duplicate or bogus report can't
// cause layout thrash or swallow the window.
ipcMain.on('tabstrip:height', (_e, height) => {
  const h = Math.max(MIN_TABSTRIP_HEIGHT, Math.min(MAX_TABSTRIP_HEIGHT, Math.round(Number(height) || DEFAULT_TABSTRIP_HEIGHT)));
  if (h === tabstripHeight) return;
  tabstripHeight = h;
  layoutAll();
});

ipcMain.handle('fs:list', (_e, relPath) => fsList(relPath));
ipcMain.handle('fs:read', (_e, relPath) => fsRead(relPath));
ipcMain.handle('fs:write', (_e, { path: relPath, content }) => fsWrite(relPath, content));

// ===== PWQ board bridge (write-through fix 2026-09-20) — disk is the API =====
// Whitelisted to the single canonical board file so order-clicks persist
// (previously clicks landed only in localStorage and were lost).
const PWQ_PATH = path.join(ITER_DIR, '.runtime', 'pwq.json');
// Read access is whitelisted to the board file + its seed; anything else is refused.
const PWQ_READ_PATHS = { 'pwq.json': PWQ_PATH, 'pwq_seed.json': path.join(ITER_DIR, 'pwq_seed.json') };
ipcMain.handle('pwq:read', (_e, rel) => {
  const target = PWQ_READ_PATHS[rel] || PWQ_PATH;
  try { return { ok: true, content: fs.readFileSync(target, 'utf8') }; }
  catch (err) { return { ok: false, error: String(err) }; }
});
ipcMain.handle('pwq:write', (_e, rel, content) => {
  try {
    if (rel !== 'pwq.json' && rel !== '.runtime/pwq.json') throw new Error('refused: not the board file');
    JSON.parse(content); // reject non-JSON garbage before touching disk
    fs.writeFileSync(PWQ_PATH, content, 'utf8');
    return { ok: true };
  } catch (err) { return { ok: false, error: String(err) }; }
});

// ===== CRM bridge (COS Command Center) — disk is the API =====
const CRM_DIR = path.join(ITER_DIR, 'crm', 'data');
const CRM_FILES = ['contacts.json','tasks.json','events.json','captures.json'];
ipcMain.handle('crm:read', (_e, fname) => {
  if (!CRM_FILES.includes(fname)) return { ok: false, error: 'bad file' };
  try { return { ok: true, data: JSON.parse(fs.readFileSync(path.join(CRM_DIR, fname), 'utf8')) }; }
  catch (err) { return { ok: false, error: String(err) }; }
});
ipcMain.handle('crm:write', (_e, fname, data) => {
  if (!CRM_FILES.includes(fname)) return { ok: false, error: 'bad file' };
  try { fs.writeFileSync(path.join(CRM_DIR, fname), JSON.stringify(data, null, 2), 'utf8'); return { ok: true }; }
  catch (err) { return { ok: false, error: String(err) }; }
});

ipcMain.handle('terminal:start', () => startTerminal());
ipcMain.handle('terminal:run', (_e, cmd) => runTerminalCommand(cmd));
ipcMain.handle('terminal:interrupt', () => interruptTerminal());
ipcMain.handle('terminal:stop', () => stopTerminal());
ipcMain.handle('dashboards:open', () => tabs.createTab('file://' + path.join(ITER_DIR, 'dashboard_gallery.html')));
ipcMain.handle('pwq:open', () => tabs.createTab('file://' + path.join(ITER_DIR, 'pwq.html'), {
  preload: path.join(__dirname, 'bridge', 'pwq_preload.js'),
  restrictNavigation: true,
}));
// CRM opens through a scoped, navigation-locked tab (see bridge/tab_manager.js
// createTab's opts.preload/opts.restrictNavigation) so window.iterApi.crmRead/
// crmWrite actually exist there -- a plain tabs.createTab(url) call, like the
// two lines above, never gets a preload and would leave the CRM page's saves
// permanently failing (this was the case until this fix; see crm/HANDOFF.md).
ipcMain.handle('crm:open', () => tabs.createTab('file://' + path.join(ITER_DIR, 'crm', 'index.html'), {
  preload: path.join(__dirname, 'bridge', 'crm_preload.js'),
  restrictNavigation: true,
}));

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (iterProcess) iterProcess.kill('SIGTERM');
  if (termProcess) termProcess.kill('SIGTERM');
  if (chatBridge) chatBridge.stop();
  app.quit();
});
