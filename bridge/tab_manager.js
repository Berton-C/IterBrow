// Tab manager — the single source of truth for "tabs" inside the Iter
// Browser window. Both the UI (renderer, via IPC in main.js) and Iter's
// own tools (via the Unix socket server in browser_bridge_server.js)
// drive the exact same tabs through this module, so what Iter does and
// what you see in the window are never out of sync.
//
// Deliberately does NOT rely on chrome.debugger/CDP for the common
// operations. Because this *is* the browser process (not a guest
// extension inside someone else's Chrome), Electron's webContents API
// already gives native, unrestricted access to everything a debugger
// attach would otherwise be needed for:
//   navigate  -> webContents.loadURL()
//   screenshot-> webContents.capturePage()
//   eval      -> webContents.executeJavaScript()
//   type      -> webContents.insertText() / sendInputEvent()
//   click     -> webContents.sendInputEvent()
//   scroll    -> executeJavaScript(window.scrollBy(...))
// No attach step, no "this tab is being debugged" banner, no MV3
// service-worker eviction to fight. A raw CDP passthrough (cdp()) is
// still exposed for advanced cases (network interception, emulation)
// that really do need the DevTools Protocol.
const { WebContentsView } = require('electron');

let nextId = 1;

class TabManager {
  constructor(win, { getContentBounds }) {
    this.win = win;
    this.getContentBounds = getContentBounds; // () => {x,y,width,height} for the tab area
    this.tabs = new Map(); // id -> { id, view, title, url }
    this.activeId = null;
    this.attachedId = null; // bookkeeping only, mirrors the old extension's "attached tab" concept
    this.onTabsChanged = null; // set by main.js to push updates to the sidebar UI
    this.onTabClosed = null; // set by main.js: (snapshot) => void, fired just before a tab is actually removed
  }

  _notify() {
    if (this.onTabsChanged) this.onTabsChanged(this.list());
  }

  list() {
    const all = [...this.tabs.values()].map((t) => ({
      id: t.id,
      title: t.title || t.url || 'New Tab',
      url: t.url || '',
      active: t.id === this.activeId,
      locked: !!t.locked,
      pinned: !!t.pinned,
    }));
    // Pinned tabs float to the front of the strip, exactly like Safari/Chrome.
    // Array.prototype.sort is stable in V8, so relative order within each
    // group (pinned vs. not) is preserved — this is the one place tab order
    // is decided; closeOtherTabs/closeTabsToRight/menu code in main.js all
    // read this same list() so what's visible always matches what gets acted on.
    return all.sort((a, b) => (a.pinned === b.pinned ? 0 : a.pinned ? -1 : 1));
  }

  // Locking is enforced only at the bridge layer (browser_bridge_server.js),
  // i.e. it blocks Iter's own agent tools, never the human user driving the
  // renderer UI directly. See setLocked().
  setLocked(id, locked) {
    const tab = this.tabs.get(Number(id));
    if (!tab) throw new Error(`No such tab: ${id}`);
    tab.locked = !!locked;
    this._notify();
    return { id: tab.id, locked: tab.locked };
  }

  isLocked(id) {
    const tab = this.tabs.get(Number(id));
    return !!(tab && tab.locked);
  }

  // Pinning is a human-only organizational feature (like lock, never exposed
  // over the agent bridge) that also doubles as a safety guard: pinned tabs
  // are deliberately skipped by closeOtherTabs()/closeTabsToRight() in
  // main.js, so pinning a tab is a lightweight way to protect it from bulk
  // close mishaps without going as far as a full lock.
  setPinned(id, pinned) {
    const tab = this.tabs.get(Number(id));
    if (!tab) throw new Error(`No such tab: ${id}`);
    tab.pinned = !!pinned;
    this._notify();
    return { id: tab.id, pinned: tab.pinned };
  }

  isPinned(id) {
    const tab = this.tabs.get(Number(id));
    return !!(tab && tab.pinned);
  }

  createTab(url = 'https://www.google.com') {
    const id = nextId++;
    const view = new WebContentsView({
      webPreferences: { contextIsolation: true, sandbox: true },
    });
    const tab = { id, view, title: 'New Tab', url, locked: false, pinned: false };
    this.tabs.set(id, tab);
    view.webContents.on('page-title-updated', (_e, title) => {
      tab.title = title;
      this._notify();
    });
    view.webContents.on('did-navigate', (_e, navUrl) => {
      tab.url = navUrl;
      this._notify();
    });
    view.webContents.on('did-navigate-in-page', (_e, navUrl) => {
      tab.url = navUrl;
      this._notify();
    });
    view.webContents.loadURL(url);
    this.switchTab(id);
    // A new tab also becomes the implicit target for bare navigate/eval/
    // click/type/scroll calls, matching what browser_new_tab.py already
    // tells the model to expect. Fixes a bug where a stale attach() to an
    // older tab silently hijacked those calls after a fresh tab was created
    // for something else (see AGENTS.md, 2026-09-14 note).
    this.attachedId = id;
    return id;
  }

  // Creates a tab like createTab(), then moves it to sit immediately after
  // `afterId` in iteration order instead of at the end. Only affects plain
  // (unpinned-vs-unpinned or pinned-vs-pinned) relative ordering — list()'s
  // pinned-first sort still applies on top of this.
  createTabAfter(afterId, url = 'https://www.google.com') {
    const id = this.createTab(url);
    if (afterId != null && afterId !== id && this.tabs.has(Number(afterId))) {
      const target = Number(afterId);
      const ids = [...this.tabs.keys()].filter((x) => x !== id);
      const idx = ids.indexOf(target);
      if (idx !== -1) {
        ids.splice(idx + 1, 0, id);
        const reordered = new Map();
        for (const k of ids) reordered.set(k, this.tabs.get(k));
        this.tabs = reordered;
        this._notify();
      }
    }
    return id;
  }

  closeTab(id) {
    const tab = this.tabs.get(id);
    if (!tab) return false;
    // Snapshot before any mutation so main.js can push it onto the
    // recently-closed list even though the tab object itself is about to be
    // destroyed. Fires for every close path (menu, IPC from the UI, or the
    // bridge) since they all funnel through this one method.
    if (this.onTabClosed) {
      this.onTabClosed({ url: tab.url, title: tab.title, locked: !!tab.locked, pinned: !!tab.pinned });
    }
    if (this.win.contentView.children.includes(tab.view)) {
      this.win.contentView.removeChildView(tab.view);
    }
    tab.view.webContents.close();
    this.tabs.delete(id);
    if (this.attachedId === id) this.attachedId = null;
    if (this.activeId === id) {
      const remaining = [...this.tabs.keys()];
      this.activeId = remaining.length ? remaining[remaining.length - 1] : null;
      if (this.activeId) this.switchTab(this.activeId);
    }
    this._notify();
    return true;
  }

  // Bulk-close helpers used by the Tabs menu. Both skip pinned tabs (the
  // whole point of pinning) and locked tabs (closeTab() would silently
  // no-op on those anyway via the bridge's assertUnlocked, but locked tabs
  // can still be closed by the human via closeTab() directly — excluding
  // them here specifically for these *bulk* operations, since "close 10
  // tabs at once" is exactly the kind of mishap locking/pinning exists to
  // prevent, and a bulk action should never silently take a locked tab with it).
  closeOtherTabs(keepId) {
    const keep = Number(keepId);
    const victims = [...this.tabs.values()].filter((t) => t.id !== keep && !t.pinned && !t.locked).map((t) => t.id);
    for (const id of victims) this.closeTab(id);
    return { closed: victims };
  }

  closeTabsToRight(id) {
    // Uses list()'s pinned-first display order, not raw Map insertion order,
    // so "to the right" always matches what's actually visible in the strip.
    const ordered = this.list();
    const idx = ordered.findIndex((t) => t.id === Number(id));
    if (idx === -1) return { closed: [] };
    const victims = ordered.slice(idx + 1).filter((t) => !t.pinned && !t.locked).map((t) => t.id);
    for (const vid of victims) this.closeTab(vid);
    return { closed: victims };
  }

  duplicateTab(id) {
    const tab = this.tabs.get(Number(id));
    if (!tab) throw new Error(`No such tab: ${id}`);
    return this.createTabAfter(tab.id, tab.url);
  }

  selectAdjacentTab(direction) {
    // direction: 1 for next, -1 for previous. Cycles through tabs in the
    // same pinned-first order the UI shows, so "next" in the menu always
    // matches "next" visually in the strip.
    const ordered = this.list();
    if (!ordered.length) return null;
    const idx = ordered.findIndex((t) => t.id === this.activeId);
    const nextIdx = idx === -1 ? 0 : (idx + direction + ordered.length) % ordered.length;
    const target = ordered[nextIdx].id;
    this.switchTab(target);
    return target;
  }

  switchTab(id) {
    const tab = this.tabs.get(id);
    if (!tab) throw new Error(`No such tab: ${id}`);
    for (const other of this.tabs.values()) {
      if (other.id !== id && this.win.contentView.children.includes(other.view)) {
        this.win.contentView.removeChildView(other.view);
      }
    }
    if (!this.win.contentView.children.includes(tab.view)) {
      this.win.contentView.addChildView(tab.view);
    }
    tab.view.setBounds(this.getContentBounds());
    this.activeId = id;
    this._notify();
    return true;
  }

  relayout() {
    const active = this.tabs.get(this.activeId);
    if (active) active.view.setBounds(this.getContentBounds());
  }

  resolveTabId(explicitId) {
    if (explicitId) return Number(explicitId);
    if (this.attachedId && this.tabs.has(this.attachedId)) return this.attachedId;
    if (this.activeId && this.tabs.has(this.activeId)) return this.activeId;
    throw new Error('No tab available. Call browser_new_tab first.');
  }

  _tab(id) {
    const tab = this.tabs.get(this.resolveTabId(id));
    if (!tab) throw new Error(`No such tab: ${id}`);
    return tab;
  }

  attach(id) {
    const tab = this._tab(id);
    this.attachedId = tab.id;
    return { attached: tab.id, url: tab.url, title: tab.title };
  }

  detach(id) {
    const target = id ? Number(id) : this.attachedId;
    if (this.attachedId === target) this.attachedId = null;
    return { detached: target || null };
  }

  navigate(id, url) {
    const tab = this._tab(id);
    // Deliberately do NOT just `await webContents.loadURL(url)` — Electron's
    // returned promise is keyed to "whichever load event fires next", so if
    // a previous navigation (e.g. the tab's initial page) is still in
    // flight, calling loadURL again can reject THIS call with the OLD
    // navigation's aborted error. We instead correlate against the actual
    // load events ourselves, and treat ERR_ABORTED (-3, "superseded by a
    // newer navigation") as a non-error, since the tab's url/title are kept
    // in sync separately via the did-navigate listeners set up in createTab.
    return new Promise((resolve) => {
      let done = false;
      const cleanup = () => {
        tab.view.webContents.removeListener('did-finish-load', onFinish);
        tab.view.webContents.removeListener('did-fail-load', onFail);
        clearTimeout(timer);
      };
      const finish = (info) => {
        if (done) return;
        done = true;
        cleanup();
        resolve(info);
      };
      const onFinish = () => finish({ navigated: url });
      const onFail = (_e, errorCode, errorDescription, validatedURL) => {
        if (errorCode === -3) return; // ERR_ABORTED — superseded, not a real failure
        finish({ navigated: url, warning: `${errorCode} ${errorDescription} (${validatedURL})` });
      };
      tab.view.webContents.once('did-finish-load', onFinish);
      tab.view.webContents.once('did-fail-load', onFail);
      const timer = setTimeout(
        () => finish({ navigated: url, warning: 'timed out waiting for a load event; navigation may still be in progress' }),
        15000
      );
      tab.view.webContents.loadURL(url).catch(() => { /* real outcome handled by the listeners above */ });
    });
  }

  async screenshot(id) {
    const tab = this._tab(id);
    const image = await tab.view.webContents.capturePage();
    return { dataUrl: 'data:image/png;base64,' + image.toPNG().toString('base64') };
  }

  async evaluate(id, expression) {
    const tab = this._tab(id);
    return tab.view.webContents.executeJavaScript(expression, true);
  }

  async getText(id) {
    return this.evaluate(id, "document.body ? document.body.innerText.slice(0, 20000) : ''");
  }

  async elementCenter(id, selector) {
    const rectJson = await this.evaluate(
      id,
      `(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return null; const r = el.getBoundingClientRect(); return JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2}); })()`
    );
    if (!rectJson) throw new Error(`No element matched selector: ${selector}`);
    return JSON.parse(rectJson);
  }

  async click({ id, x, y, selector }) {
    const tab = this._tab(id);
    if (selector) {
      const center = await this.elementCenter(tab.id, selector);
      x = center.x;
      y = center.y;
    }
    if (x === undefined || y === undefined) throw new Error('click requires either selector or x,y.');
    tab.view.webContents.focus();
    tab.view.webContents.sendInputEvent({ type: 'mouseMove', x, y });
    tab.view.webContents.sendInputEvent({ type: 'mouseDown', x, y, button: 'left', clickCount: 1 });
    tab.view.webContents.sendInputEvent({ type: 'mouseUp', x, y, button: 'left', clickCount: 1 });
    return { clicked: selector || `${x},${y}` };
  }

  async type({ id, text, selector }) {
    const tab = this._tab(id);
    if (selector) {
      await this.click({ id: tab.id, selector });
    }
    tab.view.webContents.insertText(text);
    return { typed: text.length + ' chars' };
  }

  async scroll({ id, x, y }) {
    return this.evaluate(id, `window.scrollBy(${Number(x) || 0}, ${Number(y) || 0})`);
  }

  async cdp(id, method, params = {}) {
    // Advanced/raw escape hatch. Attaches the real DevTools Protocol on
    // demand for anything the native webContents API doesn't cover.
    const tab = this._tab(id);
    const dbg = tab.view.webContents.debugger;
    if (!dbg.isAttached()) dbg.attach('1.3');
    return dbg.sendCommand(method, params);
  }
}

module.exports = { TabManager };
