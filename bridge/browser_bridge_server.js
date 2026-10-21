// Unix domain socket server that exposes the TabManager to Iter's own
// Python tools (tools/browser_*.py), running as a normal separate
// process on the same machine. Protocol is intentionally identical to
// the earlier "iter-browser-bridge" Chrome-extension host, so the same
// tool files work unchanged — this server just replaces the
// extension+native-messaging-host relay with a direct in-process call.
//
//   Iter tool  --(unix socket, one line JSON in/out)-->  this server
//   this server --(Electron webContents API, in-process)--> the tab
const fs = require('fs');
const path = require('path');
const net = require('net');
const { validateProbeSpec } = require('./foundry_apps');
const { probeScript, checkScript, ledgerWritesScript } = require('./page_scripts');

const SOCKET_PATH = process.env.ITER_BRIDGE_SOCKET || '/tmp/iter-browser-bridge.sock';

function inspectSocketPath(socketPath, timeoutMs = 500) {
  return new Promise((resolve) => {
    if (!fs.existsSync(socketPath)) return resolve({ status: 'missing' });
    const probe = net.createConnection(socketPath);
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      probe.removeAllListeners();
      probe.destroy();
      resolve(result);
    };
    probe.once('connect', () => finish({ status: 'live' }));
    probe.once('error', (error) => {
      if (error && error.code === 'ENOENT') return finish({ status: 'missing' });
      if (error && error.code === 'ECONNREFUSED') return finish({ status: 'stale' });
      finish({ status: 'error', error });
    });
    // A listener that accepts slowly is still live. Startup must fail closed
    // instead of unlinking an endpoint merely because its owner is busy.
    probe.setTimeout(timeoutMs, () => finish({ status: 'live' }));
  });
}

// Tabs the user has locked (padlock icon in the tab strip) are off-limits to
// Iter's own tools below — this is the ONLY enforcement point for locking.
// It deliberately does not touch main.js's IPC handlers, so the human user
// can always still close/navigate their own tabs regardless of lock state;
// only Iter's agent-driven bridge calls are blocked here.
function assertUnlocked(tabs, id, action) {
  if (tabs.isLocked(id)) {
    throw new Error(
      `Tab ${id} is locked by the user and cannot be ${action}. Ask the user to click the tab's lock icon to release it first.`
    );
  }
}

// M14-H1: the newest modification time (ms) of any file under an app folder (dot-files and node_modules skipped).
function newestFileTime(dir, depth = 0) {
  let newest = 0;
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch (_) { return 0; }
  for (const entry of entries) {
    if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
    const full = path.join(dir, entry.name);
    try {
      if (entry.isDirectory()) { if (depth < 4) newest = Math.max(newest, newestFileTime(full, depth + 1)); }
      else if (entry.isFile()) newest = Math.max(newest, fs.statSync(full).mtimeMs);
    } catch (_) { /* a file that vanished mid-scan */ }
  }
  return newest;
}

// M15-C1: the contract check in an app tab (see page_scripts.checkScript): the ask's named selectors come from
// Iter's tool. Never on a locked tab (the check clicks submit buttons); a failure is a missing check (null),
// never a failed open or probe. When the check's clicks changed storage it was put back and the page is
// reloaded, so the app's memory matches its storage again.
function selectorList(value) {
  return (Array.isArray(value) ? value : []).filter((item) => typeof item === 'string' && item.trim() && item.length <= 200).slice(0, 40);
}

async function contractCheck(tabs, tab, appId, selectors) {
  try {
    if (!tab || !tab.view || tabs.isLocked(tab.id)) return null;
    let timer;
    let result;
    try {
      result = await Promise.race([
        tab.view.webContents.executeJavaScript(checkScript({ appId, selectors: selectorList(selectors) }), true),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('contract check timed out')), 4000); }),
      ]);
    } finally { clearTimeout(timer); }
    if (!result || typeof result !== 'object' || !result.selectors) return null;
    if (result.restored) {
      await tabs.awaitLoad(tab.id, (contents) => contents.reload());
      await tab.view.webContents.executeJavaScript(ledgerWritesScript(appId, true), true);
    }
    return result;
  } catch (_) {
    return null;
  }
}

function buildMethods(tabs, apps = {}) {
  return {
    async openApp(params) {
      if (!apps.open) throw new Error('Application factory is unavailable');
      // M13-C3: the app as the person sees it (an app tab, with its preload), loaded before we answer, and
      // Iter's target from now on (it opened it to work in it).
      const opened = await apps.open(params.appId);
      let loaded;
      let reloaded = false;
      if (opened.focused) {
        const tab = tabs.tabs.get(opened.tabId);
        // M14-H1: an open app whose files changed since the page loaded is reloaded, so what Iter looks at is
        // what is on disk (otherwise an edit never shows and the stale page looks like a mystery).
        if (opened.dir && newestFileTime(opened.dir) > (tab.loadedAt || 0) && !tabs.isLocked(opened.tabId)) {
          loaded = await tabs.awaitLoad(opened.tabId, (contents) => contents.reload());
          reloaded = true;
        } else {
          loaded = { url: tab.url };
        }
      } else {
        loaded = await tabs.awaitLoad(opened.tabId);
      }
      tabs.attach(opened.tabId);
      const { dir, ...rest } = opened;
      const check = params.check ? await contractCheck(tabs, tabs.tabs && tabs.tabs.get(opened.tabId), params.appId, params.selectors) : null;  // M15-C1 (apps being built)
      return { ...rest, focused: !!opened.focused, reloaded, ...loaded, check: check || null };
    },
    // M13-C4: a scripted probe of any open app tab (plain apps included; no revision id). `ready` is the
    // app's data-iter-ready flag, reported and never required. A locked app tab refuses, like every action.
    async probe(params) {
      const spec = validateProbeSpec(params);
      const tab = [...tabs.tabs.values()].find((item) => item.appScope && item.appScope.appId === spec.appId);
      if (!tab) throw new Error(`No open app tab for ${spec.appId}; browser_open_app("${spec.appId}") first`);
      assertUnlocked(tabs, tab.id, 'probed');
      const check = params.check ? await contractCheck(tabs, tab, spec.appId, params.selectors) : null;  // M15-C1: before the steps
      let timer;
      let facts;
      try {
        facts = await Promise.race([
          tab.view.webContents.executeJavaScript(probeScript(spec), true),
          new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Browser probe timed out')), spec.timeoutMs + 1000); }),
        ]);
      } finally { clearTimeout(timer); }
      const observations = (facts.observations || []).map((item) => ({ ...item, passed: item.actual === item.expected }));
      const passed = observations.filter((item) => item.passed).length;
      if (check) {
        // M15-C1: what the page wrote during the steps is this app's own storage, attributed by the recorder.
        try {
          const after = await tab.view.webContents.executeJavaScript(ledgerWritesScript(spec.appId), true);
          if (after && Array.isArray(after.writes)) {
            const prefix = `iter:${spec.appId}:`;
            const other = new Set([...(check.storage.other || []), ...after.writes.filter((key) => !key.startsWith(prefix))]);
            check.storage = { prefixed: Number(after.prefixed) || 0, other: [...other].sort() };
          }
        } catch (_) { /* the check before the steps stands */ }
      }
      return { observations, passed, failed: observations.length - passed, ready: facts.ready === true, title: facts.title, tabId: tab.id, check: check || null };
    },
    // M13-B3: wait until a selector is visible, the page shows some text, or the URL contains a string (all
    // given must hold). A read: allowed on locked tabs.
    async waitFor(params) {
      const id = tabs.resolveTabId(params.tabId);
      const timeoutMs = Math.min(30000, Math.max(100, Number(params.timeoutMs) || 10000));
      const result = await tabs.waitFor({ id, selector: params.selector, text: params.text, url: params.url, timeoutMs });
      if (!result || !result.found) {
        const wanted = [['selector', params.selector], ['text', params.text], ['url', params.url]]
          .filter(([, value]) => value).map(([name, value]) => `${name} ${value}`).join(', ');
        const why = result && result.error ? ` (${result.error})` : '';
        throw new Error(`timed out after ${Math.round(timeoutMs / 1000)}s waiting for ${wanted || 'nothing'}${why}`);
      }
      return result;
    },
    async inspectApp(params) {
      if (!apps.inspect) throw new Error('Application probe is unavailable');
      return apps.inspect(params);
    },
    async getTabs() {
      return tabs.list();
    },
    async attach(params) {
      return tabs.attach(params.tabId);
    },
    async detach(params) {
      return tabs.detach(params.tabId);
    },
    async newTab(params) {
      // M13-C1: Iter's own tab becomes its target; M13-B4: answer once it has loaded.
      const id = tabs.createTab(params.url || 'https://www.google.com', { agent: true });
      const loaded = await tabs.awaitLoad(id);
      return { created: id, url: loaded.url, title: loaded.title, ...(loaded.warning ? { warning: loaded.warning } : {}) };
    },
    async closeTab(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'closed');
      return { closed: tabs.closeTab(id) };
    },
    async switchTab(params) {
      if (!params.tabId) throw new Error('switchTab requires tabId (see getTabs).');
      tabs.switchTab(Number(params.tabId));
      // Agent selection must target what it displays. Human UI switching still
      // calls switchTab directly and does not redirect an attached agent.
      tabs.attach(Number(params.tabId));
      return { switched: Number(params.tabId) };
    },
    async navigate(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'navigated');
      // M13-C5: an app tab holds the app preload; it never loads another page (will-navigate does not fire
      // for a programmatic load, so the rule is checked here too). Its own URL and its folder are fine.
      const tab = tabs.tabs && tabs.tabs.get(id);
      if (tab && tab.appScope && params.url !== tab.allowedUrl && !tabs._insideAppDir(tab, params.url)) {
        throw new Error(`App tab ${id} stays on its app; open another page in a new tab`);
      }
      return tabs.navigate(id, params.url);
    },
    async screenshot(params) {
      const id = tabs.resolveTabId(params.tabId);
      return tabs.screenshot(id);
    },
    async eval(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'modified');
      const value = await tabs.evaluate(id, params.expression);
      return value;
    },
    async getText(params) {
      const id = tabs.resolveTabId(params.tabId);
      return tabs.getText(id);
    },
    async click(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'modified');
      return tabs.click({ id, x: params.x, y: params.y, selector: params.selector });
    },
    async type(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'modified');
      return tabs.type({ id, text: params.text, selector: params.selector });
    },
    async scroll(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'modified');
      return tabs.scroll({ id, x: params.x, y: params.y, selector: params.selector });
    },
    async cdp(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'modified');
      return tabs.cdp(id, params.method, params.cdpParams || {});
    },
  };
}

function startBridgeServer(tabs, log = () => {}, socketPath = SOCKET_PATH, apps = {}) {
  const methods = buildMethods(tabs, apps);
  const server = net.createServer((connection) => {
    let buffer = '';
    connection.on('data', async (chunk) => {
      buffer += chunk.toString('utf8');
      const newlineIndex = buffer.indexOf('\n');
      if (newlineIndex === -1) return;
      const line = buffer.slice(0, newlineIndex);
      buffer = '';
      let response;
      try {
        const request = JSON.parse(line);
        const fn = methods[request.method];
        if (!fn) throw new Error(`Unknown method: ${request.method}`);
        const result = await fn(request.params || {});
        response = { ok: true, result };
      } catch (error) {
        response = { ok: false, error: String((error && error.message) || error) };
        log('bridge error:', response.error);
      }
      connection.end(JSON.stringify(response) + '\n');
    });
    connection.on('error', (err) => log('bridge connection error:', err.message));
  });

  server.bridgeSocketPath = socketPath;
  server.bridgeReady = new Promise((resolve) => {
    server._resolveBridgeReady = resolve;
  });
  server.on('error', (error) => {
    log('Iter browser bridge server error:', error.message);
    if (server._resolveBridgeReady) {
      server._resolveBridgeReady({ status: 'error', error: error.message, socketPath });
      server._resolveBridgeReady = null;
    }
  });

  inspectSocketPath(socketPath).then((inspection) => {
    if (inspection.status === 'live') {
      log('Iter browser bridge endpoint is already live; refusing to replace it:', socketPath);
      server._resolveBridgeReady({ status: 'conflict', socketPath });
      server._resolveBridgeReady = null;
      return;
    }
    if (inspection.status === 'error') {
      log('Iter browser bridge endpoint inspection failed closed:', inspection.error.message);
      server._resolveBridgeReady({ status: 'error', error: inspection.error.message, socketPath });
      server._resolveBridgeReady = null;
      return;
    }
    if (inspection.status === 'stale') {
      try {
        fs.unlinkSync(socketPath);
      } catch (error) {
        if (!error || error.code !== 'ENOENT') throw error;
      }
    }
    server.listen(socketPath, () => {
      let identity = null;
      try {
        const stat = fs.statSync(socketPath);
        identity = { dev: stat.dev, ino: stat.ino };
      } catch (_) {}
      server.bridgeSocketIdentity = identity;
      log('Iter browser bridge socket listening at', socketPath);
      server._resolveBridgeReady({ status: 'listening', socketPath });
      server._resolveBridgeReady = null;
    });
  }).catch((error) => {
    log('Iter browser bridge startup failed closed:', error.message);
    if (server._resolveBridgeReady) {
      server._resolveBridgeReady({ status: 'error', error: error.message, socketPath });
      server._resolveBridgeReady = null;
    }
  });

  return server;
}

module.exports = { inspectSocketPath, startBridgeServer, buildMethods, SOCKET_PATH };
