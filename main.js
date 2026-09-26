const { app, BaseWindow, WebContentsView, ipcMain, dialog, Menu, powerMonitor, systemPreferences, shell, session } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const crypto = require('crypto');
const { pathToFileURL } = require('url');
const { spawn, execFile } = require('child_process');
const net = require('net');

// Exactly one Electron main process may own Iter's lifecycle and revision
// supervisor for this checkout.  A second `npm start` previously created a
// supervisor with no Iter child; it interpreted the live candidate as an
// exited process and rolled it back underneath the real owner.
const hasSingleInstanceLock = app.requestSingleInstanceLock({ iterRoot: __dirname });
if (!hasSingleInstanceLock) app.quit();

const { TabManager } = require('./bridge/tab_manager');
const { inspectSocketPath, startBridgeServer } = require('./bridge/browser_bridge_server');
const { makeChatBridge } = require('./bridge/chat_bridge');
const { retirePreviousIter } = require('./bridge/iter_process_owner');
const OPENAI_CATALOG = require('./iter/iterbrow_runtime/openai_models.json');

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
// Development runs directly from the checkout. A packaged app instead ships a
// clean, read-only Iter template and copies it once into a per-user writable
// workspace. This prevents build artifacts from capturing the developer's
// credentials/live cognition and prevents runtime writes from mutating the app
// bundle (which would also invalidate future code signatures).
const BUNDLED_ITER_DIR = path.join(__dirname, 'iter');
const ITER_DIR = app.isPackaged
  ? path.resolve(process.env.ITERBROW_WORKSPACE_DIR || path.join(app.getPath('userData'), 'iter'))
  : BUNDLED_ITER_DIR;

function bootstrapPackagedIterWorkspace() {
  if (!app.isPackaged) return;
  const manifest = path.join(ITER_DIR, 'state_manifest.json');
  if (fs.existsSync(ITER_DIR)) {
    if (!fs.existsSync(manifest)) {
      throw new Error(`Packaged Iter workspace is incomplete: ${ITER_DIR}`);
    }
    return;
  }
  fs.mkdirSync(path.dirname(ITER_DIR), { recursive: true });
  const temporary = `${ITER_DIR}.bootstrap-${process.pid}-${Date.now()}`;
  try {
    fs.cpSync(BUNDLED_ITER_DIR, temporary, {
      recursive: true,
      force: false,
      errorOnExist: true,
    });
    fs.renameSync(temporary, ITER_DIR);
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

bootstrapPackagedIterWorkspace();
const SETTINGS_PATH = path.join(ITER_DIR, '.runtime', 'settings.json');
const STATE_MANIFEST_PATH = path.join(ITER_DIR, 'state_manifest.json');
// Tab session — which tabs were open, their URLs, and their lock state.
// The state manifest classifies this as portable application state but not
// resettable cognitive state. Export/import therefore carries it between
// machines without a cognitive reset wiping the user's open tabs.
// Added 2026-09-14 because before this, restarting Iter Browser for ANY code
// change silently threw away every open tab with no way to recover them --
// discovered while adding the tab-lock feature, which itself needs a
// restart to load.
const TABS_SESSION_PATH = path.join(ITER_DIR, '.runtime', 'tabs_session.json');
// Ring buffer of recently-closed tabs, independent of TABS_SESSION_PATH (which
// only ever holds what's CURRENTLY open). Backs the History menu's "Recently
// Closed" submenu and "Reopen Last Closed Tab" -- added 2026-09-14 alongside
// the menu system, same local-UI-state reasoning as TABS_SESSION_PATH (kept
// out of cognitive reset, but included by manifest-driven export/import).
// Capped at CLOSED_TABS_LIMIT, newest first.
const CLOSED_TABS_PATH = path.join(ITER_DIR, '.runtime', 'closed_tabs.json');
const CLOSED_TABS_LIMIT = 20;
// Named, saved sets of tabs the user can open/switch-to/close as a unit --
// e.g. "Research" vs "Work" vs "Recipes" -- added 2026-09-14 per user
// request. Same local-UI-state reasoning as TABS_SESSION_PATH/CLOSED_TABS_PATH
// (kept out of cognitive reset, included by manifest-driven export/import).
const TAB_GROUPS_PATH = path.join(ITER_DIR, '.runtime', 'tab_groups.json');
const VENV_PYTHON = path.join(ITER_DIR, '.venv', 'bin', 'python3');
const SIDEBAR_BG = '#0d0f12'; // matches renderer/style.css --bg
// Persistent MeTTa atomspace server (metta_server.py) -- see startMettaServer()
// below. Unix socket, same protocol shape as ITER_BRIDGE_SOCKET above.
const ITER_INSTANCE_ID = crypto.createHash('sha256').update(__dirname).digest('hex').slice(0, 16);
const ITER_BRIDGE_SOCKET = process.env.ITER_BRIDGE_SOCKET || `/tmp/iter-browser-${ITER_INSTANCE_ID}.sock`;
const ITER_METTA_SOCKET = process.env.ITER_METTA_SOCKET || `/tmp/iter-metta-${ITER_INSTANCE_ID}.sock`;
const LEGACY_ITER_METTA_SOCKET = '/tmp/iter-metta-bridge.sock';
const CRM_SOURCE_URL = pathToFileURL(path.join(ITER_DIR, 'crm', 'index.html')).toString();
let activeAppRevisions = {
  crm: { revisionId: null, bundleHash: null, url: CRM_SOURCE_URL, status: 'source-fallback' },
};

function crmUrl() {
  return activeAppRevisions.crm.url;
}

function isCrmApplicationUrl(url) {
  const value = String(url || '');
  return value === CRM_SOURCE_URL
    || value.includes('/.runtime/app_revisions/apps/crm/bundles/');
}

function appTabOptions(appId = 'crm') {
  return {
    preload: path.join(__dirname, 'bridge', 'app_preload.js'),
    restrictNavigation: true,
    appId,
    consumerId: `${appId}-ui`,
  };
}

function registeredAppForUrl(url) {
  if (isCrmApplicationUrl(url)) return 'crm';
  return Object.keys(activeAppRevisions).find((appId) => (
    String(url || '').startsWith(pathToFileURL(path.join(ITER_DIR, '.runtime', 'app_revisions', 'apps', appId, 'bundles') + path.sep).toString())
  )) || null;
}

let win = null;
let sidebarView = null;
let sidebarResumeTimer = null;
let toolbarView = null;
let tabstripView = null;
let tabs = null;
let chatBridge = null;
let browserBridgeServer = null;
let browserBridgeReadyPromise = null;
let iterProcess = null;
let iterStartedAt = null;
let mettaProcess = null;
let mettaStartPromise = null;
let atomspaceLifecycleBusy = false;
let iterStartPromise = null;
let iterDesiredRunning = false;
let appQuitting = false;
let quitReady = false;
let quitPromise = null;
let iterStopPromise = null;
let iterIntentVersion = 0;
let revisionSupervisorBusy = false;
let appRevisionSupervisorBusy = false;
let iterLog = [];
let sidebarWidth = DEFAULT_SIDEBAR_WIDTH;
let tabstripHeight = DEFAULT_TABSTRIP_HEIGHT;
let resizingSidebar = false;

function loadSettings() {
  const defaults = {
    provider: 'openrouter',
    openrouter: { endpoint: 'https://openrouter.ai/api/v1', model: 'z-ai/glm-5.3', apiKey: '' },
    openai: { model: 'gpt-6-sol', apiKey: '', reasoning: 'low' },
    lmstudio: { endpoint: 'http://127.0.0.1:1234/v1', model: 'qwen/qwen3.8-27b' },
    sidebarWidth: DEFAULT_SIDEBAR_WIDTH,
    iterAutoStart: false,
  };
  try {
    const saved = JSON.parse(fs.readFileSync(SETTINGS_PATH, 'utf8'));
    return { ...defaults, ...saved,
      openrouter: { ...defaults.openrouter, ...saved.openrouter },
      openai: { ...defaults.openai, ...saved.openai },
      lmstudio: { ...defaults.lmstudio, ...saved.lmstudio },
    };
  } catch (_) {
    return defaults;
  }
}

function saveSettings(settings) {
  // Display-only catalog/usage never become saved preferences or credentials.
  const { openaiCatalog, lastModelUsage, ...stored } = settings;
  fs.mkdirSync(path.dirname(SETTINGS_PATH), { recursive: true });
  fs.writeFileSync(SETTINGS_PATH, JSON.stringify(stored, null, 2), { mode: 0o600 });
  fs.chmodSync(SETTINGS_PATH, 0o600);
}

function persistIterDesiredRunning(desired) {
  const settings = loadSettings();
  if (settings.iterAutoStart === desired) return;
  saveSettings({ ...settings, iterAutoStart: desired });
}

function pythonBin() {
  return fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3';
}

function pushLog(line) {
  iterLog.push(line);
  if (iterLog.length > 500) iterLog = iterLog.slice(-500);
  if (sidebarView && !sidebarView.webContents.isDestroyed()) sidebarView.webContents.send('iter:log', line);
}

function reconcileSidebarAfterSystemResume(reason) {
  clearTimeout(sidebarResumeTimer);
  const reconcile = (pass = 0) => {
    const view = sidebarView;
    if (!win || !view || !view.webContents || view.webContents.isDestroyed()) return;
    // Locking macOS can suspend a WebContentsView without a useful renderer
    // focus/visibility transition. The renderer can remain live while its
    // native child surface is blank, so reconcile both authorities: replay
    // renderer state and re-attach the existing view to the native hierarchy.
    // Never hide the view here: if macOS drops a follow-up compositor task,
    // a hidden/visible toggle can leave the sidebar permanently blank.
    view.webContents.send('ui:resume', { reason, at: Date.now() });
    win.contentView.addChildView(view);
    view.setVisible(true);
    view.setBounds(sidebarBounds());
    view.webContents.invalidate();
    if (tabs && tabs.activeId) tabs.switchTab(tabs.activeId);
    if (pass === 0) {
      // A second bounded pass covers the interval in which macOS has emitted
      // focus/unlock but has not yet re-established the WindowServer surface.
      sidebarResumeTimer = setTimeout(() => reconcile(1), 300);
    } else {
      sidebarResumeTimer = null;
      pushLog(`[ui] sidebar reconciled after ${reason}`);
    }
  };
  sidebarResumeTimer = setTimeout(() => reconcile(0), 50);
}

function runHotloadControl(action, options = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const args = ['hotload_control.py', action];
    if (Object.prototype.hasOwnProperty.call(options, 'iterRunning')) {
      args.push('--iter-running', options.iterRunning ? 'true' : 'false');
    }
    if (Number.isInteger(options.iterPid)) args.push('--iter-pid', String(options.iterPid));
    if (Number.isFinite(options.iterStartedAt)) args.push('--iter-started-at', String(options.iterStartedAt));
    if (options.reason) args.push('--reason', String(options.reason));
    execFile(
      pythonBin(), args,
      { cwd: ITER_DIR, env: { ...process.env, PYTHONUNBUFFERED: '1' }, timeout: timeoutMs, maxBuffer: 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) return reject(new Error(`hot-load control failed: ${error.message}${stderr ? `; ${stderr}` : ''}`));
        try { resolve(JSON.parse(stdout.trim())); }
        catch (parseError) { reject(new Error(`hot-load control returned invalid JSON: ${parseError.message}`)); }
      },
    );
  });
}

function runAppRevisionControl(action, options = {}, timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const args = [
      'tools/app_revision_control.py', action,
      '--external-supervisor', 'electron-main',
      '--app-id', options.appId || 'crm',
    ];
    if (options.candidateId) args.push('--candidate-id', String(options.candidateId));
    if (options.proposalId) args.push('--proposal-id', String(options.proposalId));
    if (options.revisionId) args.push('--revision-id', String(options.revisionId));
    if (options.observationId) args.push('--observation-id', String(options.observationId));
    if (Object.prototype.hasOwnProperty.call(options, 'rendererPresent')) {
      args.push('--renderer-present', options.rendererPresent ? 'true' : 'false');
    }
    if (Object.prototype.hasOwnProperty.call(options, 'loadOk')) {
      args.push('--load-ok', options.loadOk ? 'true' : 'false');
    }
    if (Object.prototype.hasOwnProperty.call(options, 'visibleHandshake')) {
      args.push('--visible-handshake', options.visibleHandshake ? 'true' : 'false');
    }
    if (Object.prototype.hasOwnProperty.call(options, 'contextOk')) {
      args.push('--context-ok', options.contextOk ? 'true' : 'false');
    }
    if (Number.isInteger(options.contextCommit)) {
      args.push('--context-commit', String(options.contextCommit));
    }
    if (options.detail) args.push('--detail', String(options.detail));
    if (options.reason) args.push('--reason', String(options.reason));
    execFile(
      pythonBin(), args,
      { cwd: ITER_DIR, env: { ...process.env, ITER_DIR, PYTHONUNBUFFERED: '1' }, timeout: timeoutMs, maxBuffer: 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) return reject(new Error(`app revision control failed: ${error.message}${stderr ? `; ${stderr}` : ''}`));
        try { resolve(JSON.parse(stdout.trim())); }
        catch (parseError) { reject(new Error(`app revision control returned invalid JSON: ${parseError.message}`)); }
      },
    );
  });
}

function rememberResolvedAppRevision(status) {
  if (!status || !status.entrypoint_path || !status.revision_id) {
    throw new Error('app revision control did not return a resolved entrypoint');
  }
  const appId = status.active && status.active.app_id;
  if (!/^[a-z][a-z0-9-]{0,62}$/.test(appId || '')) throw new Error('Application revision has no valid identity');
  activeAppRevisions[appId] = {
    revisionId: status.revision_id,
    bundleHash: status.bundle_hash,
    url: pathToFileURL(status.entrypoint_path).toString(),
    status: (status.active && status.active.status) || 'stable',
  };
  return activeAppRevisions[appId];
}

async function recoverAppRevisionsBeforeTabs() {
  const registry = await runAppRevisionControl('list-apps');
  const results = [];
  for (const appId of registry.apps) {
    const recovered = await runAppRevisionControl('recover-startup', { appId });
    rememberResolvedAppRevision(recovered);
    results.push(recovered);
    if (recovered.action !== 'none') pushLog(`[app-recovery] ${appId}: ${recovered.action} ${recovered.revision_id}`);
  }
  return results;
}

async function loadCurrentAppRevision(appId = 'crm') {
  const status = await runAppRevisionControl('status', { appId });
  const resolved = rememberResolvedAppRevision(status);
  if (!tabs) return { rendererPresent: false, observations: [] };
  return tabs.loadAppRevision(appId, resolved.url, resolved.revisionId);
}

async function openRegisteredApp(appId) {
  if (!/^[a-z][a-z0-9-]{0,62}$/.test(appId || '')) throw new Error('Invalid application id');
  if (atomspaceLifecycleBusy) throw new Error('State maintenance is in progress');
  const status = await runAppRevisionControl('status', { appId });
  const resolved = rememberResolvedAppRevision(status);
  const started = await startMettaServer();
  if (started && started.error) throw new Error(started.error);
  await runPythonJson('iterbrow_runtime/app_contract.py', {
    action: appId === 'crm' ? 'bootstrap' : 'context', app_id: appId, consumer_id: `${appId}-ui`,
  });
  const tabId = tabs.createTab(resolved.url, appTabOptions(appId));
  return { appId, tabId, revisionId: resolved.revisionId };
}

async function inspectRegisteredApp(params) {
  const { validateProbe, probeScript, probeProofs } = require('./bridge/foundry_apps');
  const spec = validateProbe(params);
  const status = await runAppRevisionControl('status', { appId: spec.appId });
  const resolved = rememberResolvedAppRevision(status);
  if (resolved.revisionId !== spec.revisionId) throw new Error('Probe revision is stale');
  const tab = [...tabs.tabs.values()].find((item) => item.appScope && item.appScope.appId === spec.appId);
  if (!tab || tab.view.webContents.getURL() !== resolved.url) throw new Error('Exact app revision is not open');
  if (tabs.isLocked(tab.id)) throw new Error('App tab is locked by the user');
  let timer;
  let facts;
  try {
    facts = await Promise.race([
      tab.view.webContents.executeJavaScript(probeScript(spec), true),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Browser probe timed out')), spec.timeoutMs + 1000); }),
    ]);
  } finally { clearTimeout(timer); }
  const after = await runAppRevisionControl('status', { appId: spec.appId });
  if (after.revision_id !== spec.revisionId || tab.view.webContents.getURL() !== resolved.url) throw new Error('App revision changed during observation');
  return { ...facts, proofs: probeProofs(facts, spec), appId: spec.appId, revisionId: spec.revisionId, bundleHash: after.bundle_hash,
    tabId: tab.id, observer: 'electron-main', observedAt: Date.now() };
}

async function superviseAppRevision() {
  if (appQuitting || appRevisionSupervisorBusy || atomspaceLifecycleBusy || !tabs) return;
  appRevisionSupervisorBusy = true;
  try {
    const registry = await runAppRevisionControl('list-apps');
    for (const appId of registry.apps) {
    const rendererPresent = [...tabs.tabs.values()].some(
      (tab) => tab.appScope && tab.appScope.appId === appId,
    );
    const checked = await runAppRevisionControl(
      'supervisor-check', { appId, rendererPresent },
    );
    if (checked.action === 'rolled_back') {
      pushLog(`[app-recovery] ${appId} revision rolled back: ${checked.reason}`);
      await loadCurrentAppRevision(appId);
      continue;
    }
    const status = await runAppRevisionControl('status', { appId });
    rememberResolvedAppRevision(status);
    if (!status.active || status.active.status !== 'probation') continue;
    if (!rendererPresent) continue;
    const health = await tabs.loadAppRevision(
      appId, activeAppRevisions[appId].url, activeAppRevisions[appId].revisionId,
    );
    for (const observation of health.observations) {
      const result = await runAppRevisionControl('supervisor-report', {
        appId,
        revisionId: observation.revisionId,
        observationId: observation.observationId,
        loadOk: observation.loadOk,
        visibleHandshake: observation.visibleHandshake,
        contextOk: observation.contextOk,
        contextCommit: observation.contextCommit,
        detail: observation.detail,
      });
      if (result.action === 'promoted') {
        pushLog(`[app-revision] ${appId} revision ${observation.revisionId} promoted from external load/context proof`);
        rememberResolvedAppRevision(await runAppRevisionControl('status', { appId }));
        break;
      }
      if (result.action === 'rolled_back') {
        pushLog(`[app-recovery] ${appId} candidate rolled back: ${result.reason}`);
        await loadCurrentAppRevision(appId);
        break;
      }
    }
    }
  } catch (error) {
    pushLog('[app-recovery] revision supervisor check failed: ' + error.message);
  } finally {
    appRevisionSupervisorBusy = false;
  }
}

async function recoverRevisionBeforeStart() {
  const result = await runHotloadControl('recover-startup');
  if (result.action === 'rolled_back') {
    pushLog(`[recovery] abandoned candidate rolled back before start: ${result.reason}`);
  }
  return result;
}

function modelConfig(settings) {
  const directOpenAI = settings.provider === 'openai';
  const cfg = directOpenAI
    ? { ...settings.openai, endpoint: 'https://api.openai.com/v1' }
    : settings.provider === 'lmstudio' ? settings.lmstudio : settings.openrouter;
  if (directOpenAI) {
    if (typeof cfg.apiKey !== 'string' || !cfg.apiKey.trim()) throw new Error('Add your OpenAI API key in Settings before starting Iter.');
    if (!OPENAI_CATALOG.models.some((model) => model.id === cfg.model)
      || !['low', 'medium', 'high'].includes(cfg.reasoning)) {
      throw new Error('Choose an available OpenAI model and reasoning effort in Settings.');
    }
  }
  return cfg;
}

function startIterProcess() {
  if (iterProcess) return { already: true };
  const settings = loadSettings();
  const cfg = modelConfig(settings);
  const directOpenAI = settings.provider === 'openai';
  const env = {
    ...process.env,
    BASE_URL: cfg.endpoint,
    LLM_MODEL: cfg.model,
    LLM_PROVIDER: settings.provider,
    LLM_REASONING_EFFORT: directOpenAI ? cfg.reasoning : '',
    AI_API_KEY: settings.provider === 'lmstudio' ? 'lm-studio' : cfg.apiKey || 'dummy',
    // Long-term-memory embeddings (tools/_petta_db.py, used by chroma_query) always need a real
    // OpenRouter key regardless of chat provider -- local LM Studio models don't do embeddings.
    // That key already lives in settings.openrouter.apiKey (the single "OpenRouter API Key" field
    // in Settings), but it was only ever forwarded to the chat client as AI_API_KEY above, never
    // under the OPENROUTER_API_KEY name _petta_db.py actually reads -- so embeddings stayed blocked
    // even after the user filled in Settings. Forward the same value under both names.
    OPENROUTER_API_KEY: (settings.openrouter && settings.openrouter.apiKey) || process.env.OPENROUTER_API_KEY || '',
    // Immutable hot-load generations relocate executable component files, but
    // every queue, ledger, projection, and durable store still belongs to this
    // canonical Iter root.  Passing it explicitly keeps runtime data ownership
    // independent of both __file__ and whichever directory launched Electron.
    ITER_DIR,
    ITER_BRIDGE_SOCKET,
    ITER_METTA_SOCKET,
    ITER_REQUIRE_ATOMSPACE: '1',
    METTA_GATE_MODE: process.env.METTA_GATE_MODE || 'enforce',
    PYTHONUNBUFFERED: '1',
  };
  iterProcess = spawn(pythonBin(), ['iter.py'], { cwd: ITER_DIR, env });
  iterStartedAt = Date.now() / 1000;
  pushLog(`[iter] started (pid ${iterProcess.pid}) provider=${settings.provider} model=${cfg.model} base_url=${cfg.endpoint}`);
  iterProcess.stdout.on('data', (d) => pushLog(d.toString()));
  iterProcess.stderr.on('data', (d) => pushLog('[stderr] ' + d.toString()));
  iterProcess.on('exit', (code) => {
    pushLog(`[iter] exited with code ${code}`);
    iterProcess = null;
    iterStartedAt = null;
    if (sidebarView && !sidebarView.webContents.isDestroyed()) sidebarView.webContents.send('iter:status', { running: false, stopping: !!iterStopPromise || appQuitting });
  });
  if (sidebarView) sidebarView.webContents.send('iter:status', { running: true });
  return { started: true, pid: iterProcess.pid };
}

async function startIter() {
  if (appQuitting || iterStopPromise) return { error: 'Iter is stopping' };
  // Missing credentials must not turn a stopped app into a recovery restart loop.
  if (!iterProcess) modelConfig(loadSettings());
  iterDesiredRunning = true;
  persistIterDesiredRunning(true);
  if (iterProcess) return { already: true };
  if (iterStartPromise) return iterStartPromise;
  iterStartPromise = (async () => {
    if (!browserBridgeReadyPromise) {
      throw new Error('Browser bridge ownership has not been initialized');
    }
    const bridge = await browserBridgeReadyPromise;
    if (!bridge || bridge.status !== 'listening') {
      throw new Error(`Browser bridge is not owned by this checkout (${(bridge && bridge.status) || 'unknown'})`);
    }
    await retirePreviousIter(ITER_DIR, pushLog);
    if (appQuitting || !iterDesiredRunning) return { cancelled: true };
    await recoverRevisionBeforeStart();
    if (appQuitting || !iterDesiredRunning) return { cancelled: true };
    return startIterProcess();
  })();
  try { return await iterStartPromise; }
  finally { iterStartPromise = null; }
}

function stopIter() {
  iterIntentVersion += 1;
  iterDesiredRunning = false;
  persistIterDesiredRunning(false);
  if (iterStopPromise) return iterStopPromise;
  iterStopPromise = (async () => {
    if (iterStartPromise) await iterStartPromise.catch(() => {});
    await stopIterAndWait(5000, { preserveDesired: true });
    await retirePreviousIter(ITER_DIR, pushLog);
    return { stopped: true };
  })().finally(() => { iterStopPromise = null; });
  return iterStopPromise;
}

function stopIterAndWait(timeoutMs = 5000, { preserveDesired = false } = {}) {
  return new Promise((resolve, reject) => {
    if (!preserveDesired) {
      iterDesiredRunning = false;
      persistIterDesiredRunning(false);
    }
    if (!iterProcess) return resolve({ already: true });
    const processToStop = iterProcess;
    let forceTimer = null;
    let failureTimer = null;
    const onExit = () => {
      clearTimeout(forceTimer);
      clearTimeout(failureTimer);
      resolve({ stopped: true });
    };
    processToStop.once('exit', onExit);
    processToStop.kill('SIGTERM');
    forceTimer = setTimeout(() => {
      try { processToStop.kill('SIGKILL'); } catch (_) {}
      failureTimer = setTimeout(() => {
        processToStop.removeListener('exit', onExit);
        reject(new Error('Iter process did not stop before cognitive state operation'));
      }, 1000);
    }, timeoutMs);
  });
}

async function startIterWithAtomspace() {
  if (appQuitting || iterStopPromise) return { error: 'Iter is stopping' };
  if (atomspaceLifecycleBusy) return { error: 'Cognitive state maintenance is in progress' };
  const intent = ++iterIntentVersion;
  const started = await startMettaServer();
  if (started.error) return { error: started.error };
  await waitForAtomspaceReady();
  if (intent !== iterIntentVersion || appQuitting || iterStopPromise) return { cancelled: true };
  return await startIter();
}

async function superviseIterRevision() {
  if (appQuitting || iterStopPromise || revisionSupervisorBusy || atomspaceLifecycleBusy) return;
  revisionSupervisorBusy = true;
  try {
    const result = await runHotloadControl(
      'supervisor-check', {
        iterRunning: !!iterProcess,
        iterPid: iterProcess ? iterProcess.pid : undefined,
        iterStartedAt,
      }, 10000,
    );
    if (result.action === 'promoted') {
      pushLog(`[hot-load] candidate ${result.candidate.candidate_id} promoted after external probation`);
    } else if (result.action === 'rolled_back') {
      pushLog(`[recovery] candidate rolled back: ${result.reason}`);
      if (iterProcess) await stopIterAndWait(5000, { preserveDesired: true });
      if (iterDesiredRunning) await startIterWithAtomspace();
    } else if (result.action === 'restart_required') {
      pushLog(`[recovery] Iter heartbeat requires restart: ${result.reason}`);
      if (iterProcess) await stopIterAndWait(5000, { preserveDesired: true });
      if (iterDesiredRunning) await startIterWithAtomspace();
    } else if (
      iterDesiredRunning && !iterProcess
      && result.active && result.active.status === 'stable'
    ) {
      pushLog('[recovery] Iter exited unexpectedly; restarting last-known-good generation');
      await startIterWithAtomspace();
    }
  } catch (error) {
    pushLog('[recovery] revision supervisor check failed: ' + error.message);
  } finally {
    revisionSupervisorBusy = false;
  }
}

function callAtomspaceAt(socketPath, method, params = {}, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(socketPath)) return reject(new Error('AtomSpace socket is not present'));
    const sock = net.createConnection(socketPath);
    let buffer = '';
    let done = false;
    const finish = (error, value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { sock.destroy(); } catch (_) {}
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => finish(new Error(`AtomSpace ${method} timed out`)), timeoutMs);
    sock.on('connect', () => sock.write(JSON.stringify({ method, params }) + '\n'));
    sock.on('data', (chunk) => {
      buffer += chunk.toString();
      const newline = buffer.indexOf('\n');
      if (newline < 0) return;
      try {
        const response = JSON.parse(buffer.slice(0, newline));
        if (!response.ok) finish(new Error(response.error || `AtomSpace ${method} failed`));
        else finish(null, response.result);
      } catch (error) {
        finish(error);
      }
    });
    sock.on('error', (error) => finish(error));
  });
}

function callAtomspace(method, params = {}, timeoutMs = 5000) {
  return callAtomspaceAt(ITER_METTA_SOCKET, method, params, timeoutMs);
}

// Checks whether metta_server.py is already alive and answering, by making
// one real request over its socket rather than just checking the socket
// file exists (a stale file from a previous crash would otherwise look
// like "running"). Mirrors the same trust boundary as the browser bridge:
// local-machine only, short timeout, fails closed.
function pingMettaServer(timeoutMs = 1500) {
  return callAtomspace('status', {}, timeoutMs).then(() => true, () => false);
}

function pingMettaServerAt(socketPath, timeoutMs = 1500) {
  return callAtomspaceAt(socketPath, 'status', {}, timeoutMs).then(() => true, () => false);
}

async function waitForAtomspaceReady(timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const status = await callAtomspace('status', {}, 1500);
      if (status && status.ready && status.epoch && Number.isInteger(status.commit)) return status;
      lastError = new Error('service answered but authoritative state is not ready');
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw lastError || new Error('AtomSpace did not become ready');
}

async function stopMettaServer() {
  let status = null;
  try { status = await callAtomspace('status', {}, 2000); } catch (_) {}
  if (!status) return { already: true };
  try {
    await callAtomspace('shutdown', {}, 10000);
  } catch (error) {
    // Migration path for a pre-journal server that has no shutdown RPC.
    if (status.pid && Number.isInteger(status.pid)) {
      try { process.kill(status.pid, 'SIGTERM'); } catch (_) {}
    } else {
      throw error;
    }
  }
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    if (!(await pingMettaServer(300))) return { stopped: true };
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error('AtomSpace service did not stop cleanly');
}

async function retireOwnedLegacyMettaServer() {
  if (ITER_METTA_SOCKET === LEGACY_ITER_METTA_SOCKET
      || !fs.existsSync(LEGACY_ITER_METTA_SOCKET)) return { already: true };
  let status = null;
  try {
    status = await callAtomspaceAt(LEGACY_ITER_METTA_SOCKET, 'status', {}, 1500);
  } catch (_) {
    // A dead legacy socket is harmless and cannot own the state lock.
    return { stale: true };
  }
  const expectedStateDir = path.resolve(ITER_DIR, '.runtime', 'atomspace');
  const ownsThisCheckout = Boolean(
    (status.state_dir && path.resolve(status.state_dir) === expectedStateDir)
    || (status.iter_dir && path.resolve(status.iter_dir) === path.resolve(ITER_DIR))
  );
  if (!ownsThisCheckout) {
    pushLog('[atomspace] legacy socket belongs to another checkout; leaving it untouched');
    return { foreign: true };
  }
  pushLog('[atomspace] retiring this checkout\'s legacy-socket service before endpoint migration');
  try {
    await callAtomspaceAt(LEGACY_ITER_METTA_SOCKET, 'shutdown', {}, 10000);
  } catch (error) {
    if (status.pid && Number.isInteger(status.pid)) {
      try { process.kill(status.pid, 'SIGTERM'); } catch (_) {}
    } else {
      throw error;
    }
  }
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    if (!(await pingMettaServerAt(LEGACY_ITER_METTA_SOCKET, 300))) {
      try { fs.unlinkSync(LEGACY_ITER_METTA_SOCKET); } catch (_) {}
      return { retired: true };
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error('Legacy AtomSpace service did not stop for endpoint migration');
}

// Starts (or confirms) the persistent MeTTa atomspace server -- see
// metta_server.py's own docstring for the full design rationale. Called
// once from createWindow() below, satisfying the "npm start starts it, or
// checks it's already running and starts it if not -- one command to
// remember" requirement (2026-09-19).
//
// Launched detached + unref()'d so it may outlive the Electron window, but
// durable authority is the journal/snapshot rather than process RAM. State
// operations explicitly quiesce or stop it and reconstruct it before Iter
// resumes.
function inspectAtomspaceLockOwner() {
  const lockPath = path.join(ITER_DIR, '.runtime', 'atomspace', 'service.lock');
  let pid = null;
  try {
    pid = Number.parseInt(fs.readFileSync(lockPath, 'utf8').trim(), 10);
  } catch (_) {
    return Promise.resolve({ status: 'missing', lockPath });
  }
  if (!Number.isInteger(pid) || pid <= 1) {
    return Promise.resolve({ status: 'stale', lockPath });
  }
  try {
    process.kill(pid, 0);
  } catch (_) {
    return Promise.resolve({ status: 'stale', lockPath, pid });
  }
  return new Promise((resolve) => {
    execFile(
      'ps', ['-p', String(pid), '-o', 'command='],
      { timeout: 2000, maxBuffer: 64 * 1024 },
      (error, stdout) => {
        if (error) return resolve({ status: 'error', lockPath, pid, error: error.message });
        const command = stdout.trim();
        const ownsService = /(^|\s|\/)metta_server\.py(\s|$)/.test(command);
        resolve({ status: ownsService ? 'owned-live' : 'foreign-live', lockPath, pid });
      },
    );
  });
}

async function waitForProcessExit(pid, timeoutMs = 5000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      process.kill(pid, 0);
    } catch (_) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

async function startMettaServerOwned() {
  await retireOwnedLegacyMettaServer();
  let currentStatus = null;
  try { currentStatus = await callAtomspace('status', {}, 1500); } catch (_) {}
  const expectedStateDir = path.resolve(ITER_DIR, '.runtime', 'atomspace');
  if (currentStatus && currentStatus.state_dir
      && path.resolve(currentStatus.state_dir) !== expectedStateDir) {
    return { error: `AtomSpace socket belongs to another checkout: ${currentStatus.state_dir}` };
  }
  if (currentStatus && currentStatus.ready && currentStatus.epoch && Number.isInteger(currentStatus.commit)) {
    return { already: true, status: currentStatus };
  }
  if (currentStatus) {
    pushLog('[atomspace] replacing pre-journal or unready service');
    await stopMettaServer();
  }

  // A failed status RPC is not evidence that the endpoint is stale. A live
  // listener may be busy, and unlinking its pathname would strand the
  // detached authoritative process while it still owns the state lock. Probe
  // transport ownership independently before any cleanup.
  const endpoint = await inspectSocketPath(ITER_METTA_SOCKET, 750);
  if (endpoint.status === 'live') {
    try {
      const status = await waitForAtomspaceReady(5000);
      pushLog(`[atomspace] authoritative service recovered at commit ${status.commit}`);
      return { already: true, status };
    } catch (error) {
      return { error: `AtomSpace endpoint is live but not ready; refusing to unlink it: ${error.message}` };
    }
  }
  if (endpoint.status === 'error') {
    return { error: `AtomSpace endpoint inspection failed closed: ${endpoint.error.message}` };
  }

  // If a previous supervisor already unlinked a live service socket, the
  // state-owned lock still names its process. Verify that PID is really a
  // metta_server.py owner before terminating it; durable journal replay then
  // reconstructs the exact authority behind a fresh endpoint.
  const owner = await inspectAtomspaceLockOwner();
  if (owner.status === 'foreign-live' || owner.status === 'error') {
    return { error: `AtomSpace state lock owner cannot be verified (${owner.status}); refusing recovery` };
  }
  if (owner.status === 'owned-live') {
    pushLog(`[atomspace] recovering missing/stale endpoint by retiring verified lock owner pid ${owner.pid}`);
    try { process.kill(owner.pid, 'SIGTERM'); } catch (_) {}
    if (!(await waitForProcessExit(owner.pid))) {
      return { error: `AtomSpace lock owner ${owner.pid} did not stop for endpoint recovery` };
    }
  }

  // Only an explicitly refused connection is a stale filesystem entry.
  if (endpoint.status === 'stale') {
    try { fs.unlinkSync(ITER_METTA_SOCKET); } catch (error) {
      if (!error || error.code !== 'ENOENT') throw error;
    }
  }
  const logPath = path.join(ITER_DIR, '.runtime', 'metta_server.log');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const logFd = fs.openSync(logPath, 'a');
  try {
    mettaProcess = spawn(pythonBin(), ['metta_server.py'], {
      cwd: ITER_DIR,
      env: { ...process.env, ITER_METTA_SOCKET, ITER_BRIDGE_SOCKET, ITER_DIR, PYTHONUNBUFFERED: '1' },
      detached: true,
      stdio: ['ignore', logFd, logFd],
    });
    mettaProcess.unref();
    mettaProcess.once('exit', () => { mettaProcess = null; });
    pushLog('[atomspace] started authoritative service (pid ' + mettaProcess.pid + '); log: ' + logPath);
    const status = await waitForAtomspaceReady();
    pushLog(`[atomspace] ready epoch=${status.epoch} commit=${status.commit} atoms=${status.runtime_atom_count}`);
    return { started: true, pid: mettaProcess && mettaProcess.pid, status };
  } catch (e) {
    pushLog('[atomspace] FAILED to start authoritative service: ' + e.message);
    return { error: e.message };
  } finally {
    try { fs.closeSync(logFd); } catch (_) {}
  }
}

async function startMettaServer() {
  if (mettaStartPromise) return mettaStartPromise;
  mettaStartPromise = startMettaServerOwned();
  try {
    return await mettaStartPromise;
  } finally {
    mettaStartPromise = null;
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
// disk. Runtime self-extension is activated through immutable generations;
// the source tree remains the development baseline and can still be edited
// manually while Iter is stopped. We therefore distinguish:
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
function loadStateManifest() {
  const manifest = JSON.parse(fs.readFileSync(STATE_MANIFEST_PATH, 'utf8'));
  if (manifest.schema_version !== 1 || !Array.isArray(manifest.entries)) {
    throw new Error('state_manifest.json has an unsupported shape');
  }
  const seen = new Set();
  for (const entry of manifest.entries) {
    if (!entry.path || path.isAbsolute(entry.path) || entry.path.split(/[\\/]/).includes('..')) {
      throw new Error(`unsafe state manifest path: ${entry.path}`);
    }
    if (seen.has(entry.path)) throw new Error(`duplicate state manifest path: ${entry.path}`);
    seen.add(entry.path);
    if (entry.role === 'source_seed' && entry.reset) {
      throw new Error(`source seed cannot be resettable: ${entry.path}`);
    }
    if (entry.role === 'secret' && entry.portable) {
      throw new Error(`secret cannot be portable: ${entry.path}`);
    }
  }
  return manifest;
}

const STATE_MANIFEST = loadStateManifest();
const STATE_PATHS = STATE_MANIFEST.entries.filter((entry) => entry.reset).map((entry) => entry.path);
const PORTABLE_STATE_PATHS = STATE_MANIFEST.entries.filter((entry) => entry.portable).map((entry) => entry.path);
const PORTABLE_ARCHIVE_PATHS = ['state_manifest.json', ...PORTABLE_STATE_PATHS];

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
  let pause = null;
  try {
    pause = await pauseCognition({ shutdownAtomspace: false });
    fs.mkdirSync(AUTO_BACKUP_DIR, { recursive: true });
    saveTabSession();
    await callAtomspace('checkpoint', {}, 10000);
    const wanted = PORTABLE_ARCHIVE_PATHS;
    const existing = wanted.filter((p) => fs.existsSync(path.join(ITER_DIR, p)));
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const zipPath = path.join(AUTO_BACKUP_DIR, `autobackup-${stamp}.zip`);
    await runCLI('zip', ['-r', zipPath, ...existing], ITER_DIR);
    pruneAutoBackups();
    pushLog(`[auto-backup] saved ${existing.length} item(s) -> ${path.basename(zipPath)}`);
  } catch (e) {
    pushLog(`[auto-backup] failed: ${e.message}`);
  } finally {
    if (pause) await resumeCognition(pause);
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

async function validateZipArchive(zipPath) {
  const listing = await runCLI('unzip', ['-Z1', zipPath], ITER_DIR);
  const entries = listing.split(/\r?\n/).filter(Boolean);
  if (!entries.length) throw new Error('State archive is empty');
  for (const raw of entries) {
    const normalized = raw.replace(/\\/g, '/');
    const parts = normalized.split('/').filter(Boolean);
    if (normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized) || parts.includes('..')) {
      throw new Error(`State archive contains an unsafe path: ${raw}`);
    }
  }
}

function assertNoArchiveSymlinks(root) {
  const pending = [root];
  while (pending.length) {
    const current = pending.pop();
    const stat = fs.lstatSync(current);
    if (stat.isSymbolicLink()) throw new Error(`State archive contains a symbolic link: ${current}`);
    if (stat.isDirectory()) {
      for (const child of fs.readdirSync(current)) pending.push(path.join(current, child));
    }
  }
}

function runPythonJson(scriptName, payload, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin(), [scriptName], {
      cwd: ITER_DIR,
      env: { ...process.env, ITER_DIR, ITER_METTA_SOCKET, PYTHONUNBUFFERED: '1' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error); else resolve(value);
    };
    const timer = setTimeout(() => {
      try { child.kill('SIGKILL'); } catch (_) {}
      finish(new Error(`${scriptName} timed out`));
    }, timeoutMs);
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', (error) => finish(error));
    child.on('exit', () => {
      try {
        const response = JSON.parse(stdout.trim());
        if (!response.ok) finish(new Error(response.error || `${scriptName} failed`));
        else finish(null, response.result);
      } catch (error) {
        finish(new Error(`${scriptName} returned invalid JSON: ${error.message}${stderr ? `; ${stderr}` : ''}`));
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

async function pauseCognition({ shutdownAtomspace = false } = {}) {
  if (atomspaceLifecycleBusy) throw new Error('Another cognitive state operation is already running');
  atomspaceLifecycleBusy = true;
  const state = { iterWasRunning: !!iterProcess, atomspaceWasRunning: false, shutdownAtomspace };
  try {
    if (state.iterWasRunning) await stopIterAndWait(5000, { preserveDesired: true });
    if (!(await pingMettaServer())) {
      const started = await startMettaServer();
      if (started.error) throw new Error(started.error);
    }
    state.atomspaceWasRunning = true;
    state.checkpoint = await callAtomspace('quiesce', {}, 10000);
    if (shutdownAtomspace) await stopMettaServer();
    return state;
  } catch (error) {
    if (state.iterWasRunning && !iterProcess) await startIter();
    atomspaceLifecycleBusy = false;
    throw error;
  }
}

async function resumeCognition(state) {
  if (!state) return;
  try {
    if (state.shutdownAtomspace) {
      const started = await startMettaServer();
      if (started.error) throw new Error(started.error);
    } else if (state.atomspaceWasRunning) {
      await callAtomspace('resume', {}, 5000);
    }
    if (state.iterWasRunning) await startIter();
  } finally {
    atomspaceLifecycleBusy = false;
  }
}

async function exportState() {
  if (!win) return { error: 'no window' };
  const { canceled, filePath } = await dialog.showSaveDialog(win, {
    title: 'Export Iter state',
    defaultPath: `iter-browser-state-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`,
    filters: [{ name: 'Zip archive', extensions: ['zip'] }],
  });
  if (canceled || !filePath) return { canceled: true };

  const pause = await pauseCognition({ shutdownAtomspace: false });
  try {
    // Flush UI state and publish a snapshot at the quiesced cognitive commit.
    saveTabSession();
    const checkpoint = await callAtomspace('checkpoint', {}, 10000);
    const wanted = PORTABLE_ARCHIVE_PATHS;
    const existing = wanted.filter((p) => fs.existsSync(path.join(ITER_DIR, p)));
    const missing = wanted.filter((p) => !fs.existsSync(path.join(ITER_DIR, p)));
    if (fs.existsSync(filePath)) fs.unlinkSync(filePath);
    await runCLI('zip', ['-r', filePath, ...existing], ITER_DIR);
    return { exported: filePath, itemCount: existing.length, missing, checkpoint };
  } finally {
    await resumeCognition(pause);
  }
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
  // Validate names before extraction and reject links after extraction. Only
  // manifest-approved paths are copied into ITER_DIR, but an archive must not
  // be able to escape the temporary directory while being inspected.
  await validateZipArchive(zipPath);
  const pause = await pauseCognition({ shutdownAtomspace: true });
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'iter-import-'));
  const rollbackDir = fs.mkdtempSync(path.join(os.tmpdir(), 'iter-rollback-'));
  let importedSummary = { restored: [], notFoundInZip: [] };
  try {
    await runCLI('unzip', ['-o', zipPath, '-d', tmpDir], ITER_DIR);
    assertNoArchiveSymlinks(tmpDir);
    // Tolerate a wrapper folder inside the zip (mirrors the old HTML app's
    // Import behavior), by descending until we find a recognizable state dir/file.
    let sourceRoot = tmpDir;
    let entries = fs.readdirSync(sourceRoot);
    if (entries.length === 1 && fs.statSync(path.join(sourceRoot, entries[0])).isDirectory()) {
      const inner = path.join(sourceRoot, entries[0]);
      const innerEntries = fs.readdirSync(inner);
      if (innerEntries.some((e) => PORTABLE_STATE_PATHS.some((rel) => rel.split('/')[0] === e))) sourceRoot = inner;
    }
    const wanted = PORTABLE_STATE_PATHS;
    const restored = [];
    const backedUp = [];
    for (const rel of wanted) {
      const current = path.join(ITER_DIR, rel);
      if (!fs.existsSync(current)) continue;
      const backup = path.join(rollbackDir, rel);
      fs.mkdirSync(path.dirname(backup), { recursive: true });
      fs.cpSync(current, backup, { recursive: true });
      backedUp.push(rel);
    }
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
    // state manifest), surface that now instead of
    // just silently ending up with a thinner restore than you expected --
    // this is exactly how a stale build on a different machine can look
    // like a broken Export when Export was actually fine.
    const notFoundInZip = wanted.filter((rel) => !restored.includes(rel));
    importedSummary = { restored, notFoundInZip, backedUp };

    // Starting the service is the restore validation: snapshot checksum,
    // journal replay, seed load, and engine reconstruction must all succeed.
    const started = await startMettaServer();
    if (started.error) throw new Error(started.error);
    await waitForAtomspaceReady();
  } catch (error) {
    await stopMettaServer().catch(() => {});
    for (const rel of PORTABLE_STATE_PATHS) {
      const dest = path.join(ITER_DIR, rel);
      fs.rmSync(dest, { recursive: true, force: true });
      const backup = path.join(rollbackDir, rel);
      if (fs.existsSync(backup)) {
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.cpSync(backup, dest, { recursive: true });
      }
    }
    await resumeCognition(pause);
    throw error;
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
    fs.rmSync(rollbackDir, { recursive: true, force: true });
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

  await resumeCognition(pause);
  return { imported: zipPath, restarted: pause.iterWasRunning, itemCount: importedSummary.restored.length, notFoundInZip: importedSummary.notFoundInZip };
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

async function resetState() {
  const pause = await pauseCognition({ shutdownAtomspace: true });
  try {
    for (const rel of STATE_PATHS) {
      const target = path.join(ITER_DIR, rel);
      fs.rmSync(target, { recursive: true, force: true });
    }
    const started = await startMettaServer();
    if (started.error) throw new Error(started.error);
    const status = await waitForAtomspaceReady();
    await resumeCognition(pause);
    return { reset: true, restarted: pause.iterWasRunning, atomspace: status };
  } catch (error) {
    // Leave Iter stopped if reset could not reconstruct authoritative state.
    atomspaceLifecycleBusy = false;
    throw error;
  }
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

async function createWindow() {
  // Finish orphan reconciliation before a window can claim "stopped" or Start.
  await retirePreviousIter(ITER_DIR, pushLog);
  if (appQuitting) return;
  // App-bundle recovery must finish before saved URLs are interpreted. An
  // abandoned probation or corrupted promoted bundle is returned to its exact
  // parent before any bridged renderer is allowed to load.
  await recoverAppRevisionsBeforeTabs();
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
  iterDesiredRunning = initialSettings.iterAutoStart === true || process.env.ITER_AUTOSTART === '1';

  win = new BaseWindow({ width: 1400, height: 900, title: 'Iter Browser' });

  sidebarView = new WebContentsView({
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: false,
      backgroundThrottling: false,
    },
  });
  win.contentView.addChildView(sidebarView);
  sidebarView.setBackgroundColor(SIDEBAR_BG);
  sidebarView.setBounds(sidebarBounds());
  // Establish the durable chat owner before renderer loading begins. Incoming
  // messages are journaled even if the renderer has not registered its IPC
  // listener yet; the renderer then replays them through chat:history.
  chatBridge = makeChatBridge(ITER_DIR, (message) => {
    if (sidebarView) sidebarView.webContents.send('chat:incoming', message);
  }, { log: pushLog });
  sidebarView.webContents.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  powerMonitor.on('unlock-screen', () => reconcileSidebarAfterSystemResume('unlock-screen'));
  powerMonitor.on('resume', () => reconcileSidebarAfterSystemResume('resume'));

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

  tabs = new TabManager(win, { getContentBounds: contentBounds, pwqPath: path.join(ITER_DIR, 'pwq.html') });
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
      const savedUrl = t.url || 'https://www.google.com';
      const appId = registeredAppForUrl(savedUrl);
      const restoredUrl = appId ? activeAppRevisions[appId].url : savedUrl;
      const id = tabs.createTab(
        restoredUrl,
        appId ? appTabOptions(appId) : {},
      );
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
  // Some unlock paths (including display-only wake and remote/local session
  // handoff) do not emit powerMonitor's unlock-screen event. Window focus is
  // the reliable user-visible boundary for repairing a lost child surface.
  win.on('focus', () => reconcileSidebarAfterSystemResume('window-focus'));
  win.on('show', () => reconcileSidebarAfterSystemResume('window-show'));
  win.on('restore', () => reconcileSidebarAfterSystemResume('window-restore'));

  win.on('closed', () => {
    clearTimeout(sidebarResumeTimer);
    clearTimeout(tabSessionSaveTimer);
    if (autoBackupTimer) { clearInterval(autoBackupTimer); autoBackupTimer = null; }
    saveTabSession(); // flush the last state synchronously, don't rely on the debounce timer surviving shutdown
    for (const tab of tabs.tabs.values()) tab.view.webContents.close();
    sidebarView.webContents.close();
    toolbarView.webContents.close();
    tabstripView.webContents.close();
    win = null;
  });

  browserBridgeServer = startBridgeServer(tabs, pushLog, ITER_BRIDGE_SOCKET, {
    open: openRegisteredApp, inspect: inspectRegisteredApp,
  });
  browserBridgeReadyPromise = browserBridgeServer.bridgeReady;
  startMettaServer().then((result) => {
    if (result.already) pushLog(`[atomspace] connected to ready service at commit ${result.status.commit}`);
    else if (result.error) pushLog('[atomspace] startup failed: ' + result.error);
  }).catch((error) => pushLog('[atomspace] startup failed: ' + error.message));
  if (iterDesiredRunning) {
    startIterWithAtomspace()
      .then((result) => {
        if (result && result.error) pushLog('[iter] automatic restart failed: ' + result.error);
      })
      .catch((error) => pushLog('[iter] automatic restart failed: ' + error.message));
  }
  // Watchdog: metta_server.py is a detached background process outside
  // Electron's own supervision -- if it crashes mid-session nothing else
  // in this app would ever notice or restart it, silently breaking every
  // transformation that depends on the MeTTa bridge (this happened for
  // real on 2026-09-20, cascading into 8 unrelated-looking "TIMEOUT after
  // 5s" failures). startMettaServer() already pings first and no-ops if
  // healthy, so calling it repeatedly here is safe.
  setInterval(() => {
    if (appQuitting || atomspaceLifecycleBusy) return;
    startMettaServer()
      .then((result) => { if (result && result.error) pushLog('[atomspace] watchdog restart failed: ' + result.error); })
      .catch((e) => pushLog('[atomspace] watchdog restart failed: ' + e.message));
  }, 60000);
  // Iter's self-modifiable components cannot judge their own promotion.
  // This Electron-side supervisor observes the immutable generation pointer
  // and Iter's cycle heartbeat.  It promotes only completed probation, and
  // rolls back before restart when the candidate exits, stalls, or reports a
  // hard health-floor failure. Manual Stop clears iterDesiredRunning, so an
  // intentional human stop is never undone by this watchdog.
  setInterval(() => { superviseIterRevision(); }, 5000);
  // Renderer bundles have their own external health boundary. Only this main
  // process may convert load + visible handshake + APP-1 context evidence into
  // probation observations or promotion; app code cannot self-report it.
  setInterval(() => { superviseAppRevision(); }, 5000);
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

ipcMain.handle('chat:send', (_e, content) => {
  if (!chatBridge) throw new Error('Chat bridge is not ready');
  return chatBridge.sendToIter(content);
});
ipcMain.handle('chat:history', () => (chatBridge ? chatBridge.history() : []));
ipcMain.handle('iter:start', () => startIterWithAtomspace());
ipcMain.handle('iter:stop', () => stopIter());
ipcMain.handle('metta:status', async () => ({ running: await pingMettaServer() }));
ipcMain.handle('metta:start', () => (
  atomspaceLifecycleBusy
    ? { error: 'Cognitive state maintenance is in progress' }
    : startMettaServer()
));
ipcMain.handle('iter:status', () => ({ running: !!iterProcess, stopping: !!iterStopPromise || appQuitting }));
ipcMain.handle('iter:recentLog', () => iterLog.slice(-200));
ipcMain.handle('settings:load', () => {
  let lastModelUsage = null;
  try { lastModelUsage = JSON.parse(fs.readFileSync(path.join(ITER_DIR, '.runtime', 'last_model_usage.json'), 'utf8')); } catch (_) {}
  return { ...loadSettings(), openaiCatalog: OPENAI_CATALOG, lastModelUsage };
});
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
ipcMain.handle('fs:write', (_e, { path: relPath, content }) => {
  if (atomspaceLifecycleBusy) throw new Error('State maintenance is in progress');
  return fsWrite(relPath, content);
});

// ===== PWQ human-agency protocol =====
// The board is a materialized projection. Every read/write crosses the one
// canonical Python protocol writer, which owns the hash-chained event ledger,
// state transitions, proposal versions, and dispatch authorization.
let pwqReadCache = null;
function pwqLedgerVersion() {
  try {
    const s = fs.statSync(path.join(ITER_DIR, '.runtime', 'pwq', 'events.jsonl'), { bigint: true });
    return `${s.ino}:${s.size}:${s.mtimeNs}`;
  } catch (e) { if (e.code === 'ENOENT') return 'missing'; throw e; }
}
ipcMain.handle('pwq:read', async (event) => {
  try {
    if (!tabs || !tabs.isPWQSender(event)) throw new Error('Refused: sender is not the local PWQ page');
    if (atomspaceLifecycleBusy) throw new Error('State maintenance is in progress');
    const version = pwqLedgerVersion();
    if (pwqReadCache && pwqReadCache.version === version) return pwqReadCache.response;
    const board = await runPythonJson('pwq_service.py', { action: 'read' });
    const response = { ok: true, content: JSON.stringify(board, null, 2) };
    if (pwqLedgerVersion() === version) pwqReadCache = { version, response };
    return response;
  } catch (err) { return { ok: false, error: String(err) }; }
});
ipcMain.handle('pwq:command', async (event, request) => {
  try {
    if (!tabs || !tabs.isPWQSender(event)) throw new Error('Refused: sender is not the local PWQ page');
    if (atomspaceLifecycleBusy) throw new Error('State maintenance is in progress');
    const command = request && typeof request === 'object' ? request : {};
    const allowed = new Set(['sign', 'approve', 'reject', 'reorder', 'modify', 'pause', 'resume', 'complete', 'archive', 'restore']);
    if (!allowed.has(command.action)) throw new Error('refused: unsupported human PWQ command');
    const board = await runPythonJson('pwq_service.py', {
      action: command.action,
      actor: 'human',
      proposal_id: command.proposal_id,
      payload: command.payload || {},
      expected_version: command.expected_version,
      command_id: command.command_id,
    });
    return { ok: true, content: JSON.stringify(board, null, 2) };
  } catch (err) { return { ok: false, error: String(err) }; }
});

// ===== Journaled AtomSpace-backed tab/application collaboration contract =====
const appChangePolls = new WeakMap();
const APP_POLL_INTERVAL_MS = 5000;

function pollScopedAppChanges(event, afterCommit) {
  const scope = tabs && tabs.appScopeForWebContentsId(event.sender.id);
  if (!scope) throw new Error('Refused: sender has no application scope');
  const cursor = Number(afterCommit || 0);
  if (!Number.isSafeInteger(cursor) || cursor < 0) throw new Error('Invalid application commit cursor');
  const active = tabs.tabs.get(tabs.activeId);
  if (appQuitting || !win || !win.isVisible() || win.isMinimized()
      || !active || active.view.webContents !== event.sender) {
    // Do not advance the cursor: the next visible poll catches every change.
    return { app_id: scope.appId, after_commit: cursor, commit: cursor, events: [], background: true };
  }
  const cached = appChangePolls.get(event.sender);
  if (cached && cached.cursor === cursor
      && (cached.pending || Date.now() - cached.at < APP_POLL_INTERVAL_MS)) return cached.promise;
  const entry = { cursor, at: Date.now(), pending: true };
  entry.promise = runScopedAppRequest(event, 'changes', { after_commit: cursor })
    .then((result) => { entry.at = Date.now(); entry.pending = false; return result; })
    .catch((error) => { appChangePolls.delete(event.sender); throw error; });
  appChangePolls.set(event.sender, entry);
  return entry.promise;
}

// The page never supplies either identity. Its actual WebContents is bound to
// scope by TabManager when the navigation-locked tab is created.
async function runScopedAppRequest(event, action, payload = {}) {
  if (atomspaceLifecycleBusy) throw new Error('State maintenance is in progress');
  const scope = tabs && tabs.appScopeForWebContentsId(event.sender.id);
  if (!scope) throw new Error('Refused: sender has no application scope');
  const started = await startMettaServer();
  if (started && started.error) throw new Error(started.error);
  return runPythonJson('iterbrow_runtime/app_contract.py', {
    action,
    ...payload,
    app_id: scope.appId,
    consumer_id: scope.consumerId,
  });
}

ipcMain.handle('app:context', (event) => runScopedAppRequest(event, 'context'));
ipcMain.handle('app:command', (event, command) => (
  runScopedAppRequest(event, 'command', { command })
));
ipcMain.handle('app:changes', pollScopedAppChanges);

ipcMain.handle('terminal:start', () => startTerminal());
ipcMain.handle('terminal:run', (_e, cmd) => runTerminalCommand(cmd));
ipcMain.handle('terminal:interrupt', () => interruptTerminal());
ipcMain.handle('terminal:stop', () => stopTerminal());
ipcMain.handle('dashboards:open', () => {
  const generated = path.join(ITER_DIR, 'dashboard_gallery.html');
  const target = fs.existsSync(generated)
    ? generated
    : path.join(__dirname, 'renderer', 'dashboard_empty.html');
  return tabs.createTab('file://' + target);
});
ipcMain.handle('pwq:open', () => tabs.createTab('file://' + path.join(ITER_DIR, 'pwq.html'), {
  preload: path.join(__dirname, 'bridge', 'pwq_preload.js'),
  restrictNavigation: true,
}));
ipcMain.handle('crm:open', async () => (await openRegisteredApp('crm')).tabId);
ipcMain.handle('apps:open', (_event, appId) => openRegisteredApp(appId));
ipcMain.handle('apps:list', () => runAppRevisionControl('list-apps'));

if (hasSingleInstanceLock) {
  app.on('before-quit', (event) => {
    if (quitReady) return;
    event.preventDefault();
    if (quitPromise) return;
    appQuitting = true;
    quitPromise = (async () => {
      if (win) saveTabSession();
      if (iterStartPromise) await iterStartPromise.catch(() => {});
      if (iterStopPromise) await iterStopPromise;
      await stopIterAndWait(5000, { preserveDesired: true });
      if (termProcess) termProcess.kill('SIGTERM');
      if (chatBridge) chatBridge.stop();
      quitReady = true;
      app.quit();
    })().catch((error) => {
      appQuitting = false;
      quitPromise = null;
      pushLog('[shutdown] Iter did not stop; application remains open: ' + error.message);
    });
  });
  app.on('second-instance', (_event, _argv, _workingDirectory, additionalData) => {
    if (additionalData && additionalData.iterRoot !== __dirname) return;
    if (win) {
      if (typeof win.isMinimized === 'function' && win.isMinimized()
          && typeof win.restore === 'function') win.restore();
      if (typeof win.isVisible !== 'function' || !win.isVisible()) win.show();
      // On macOS, showing a hidden BaseWindow does not necessarily activate
      // the Electron application. A repeated `npm start` is an explicit user
      // request to surface this checkout's existing owner.
      if (typeof app.focus === 'function') app.focus({ steal: true });
      if (typeof win.focus === 'function') win.focus();
    }
  });
  app.whenReady().then(createWindow).catch((error) => {
    pushLog('[startup] application revision recovery failed closed: ' + error.message);
    app.quit();
  });
  app.on('window-all-closed', () => {
    app.quit();
  });
}
