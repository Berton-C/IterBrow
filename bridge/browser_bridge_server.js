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
const net = require('net');

const SOCKET_PATH = process.env.ITER_BRIDGE_SOCKET || '/tmp/iter-browser-bridge.sock';

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

function buildMethods(tabs) {
  return {
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
      const id = tabs.createTab(params.url || 'https://www.google.com');
      return { created: id };
    },
    async closeTab(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'closed');
      return { closed: tabs.closeTab(id) };
    },
    async switchTab(params) {
      if (!params.tabId) throw new Error('switchTab requires tabId (see getTabs).');
      tabs.switchTab(Number(params.tabId));
      return { switched: Number(params.tabId) };
    },
    async navigate(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'navigated');
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
      return tabs.scroll({ id, x: params.x, y: params.y });
    },
    async cdp(params) {
      const id = tabs.resolveTabId(params.tabId);
      assertUnlocked(tabs, id, 'modified');
      return tabs.cdp(id, params.method, params.cdpParams || {});
    },
  };
}

function startBridgeServer(tabs, log = () => {}) {
  const methods = buildMethods(tabs);
  try {
    fs.unlinkSync(SOCKET_PATH);
  } catch (_) {
    /* did not exist, fine */
  }

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

  server.listen(SOCKET_PATH, () => {
    log('Iter browser bridge socket listening at', SOCKET_PATH);
  });

  return server;
}

module.exports = { startBridgeServer, SOCKET_PATH };
