const tabstrip = document.getElementById('tabstrip');
const tabstripScroll = document.getElementById('tabstrip-scroll');
const tabAllBtn = document.getElementById('tab-all');
const tabAllMenu = document.getElementById('tab-all-menu');
const chat = document.getElementById('chat');
const chatInput = document.getElementById('chat-input');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const logView = document.getElementById('log-view');

let activeTabId = null;
let tabsCache = [];
let dragTabId = null;

// ---------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------
function renderTabs(list) {
  tabsCache = list;
  const active = list.find((t) => t.active);
  activeTabId = active ? active.id : null;

  tabstripScroll.innerHTML = '';
  for (const tab of list) {
    const pill = document.createElement('div');
    pill.className = 'tab-pill' + (tab.active ? ' active' : '') + (tab.locked ? ' locked' : '') + (tab.pinned ? ' pinned' : '');
    pill.title = tab.locked
      ? tab.url + ' (locked — Iter cannot alter or close this tab until you click the lock)'
      : tab.url;
    pill.draggable = true;
    pill.innerHTML = `<span class="pin" title="${tab.pinned ? 'Pinned — click to unpin' : 'Click to pin this tab (protects it from Close Other Tabs / Close Tabs to the Right)'}">${tab.pinned ? '📌' : '📍'}</span><span class="lock" title="${tab.locked ? 'Locked — click to release' : 'Click to lock this tab against Iter'}">${tab.locked ? '🔒' : '🔓'}</span><span class="title">${escapeHtml(tab.title || 'New Tab')}</span><span class="x">✕</span>`;
    pill.querySelector('.title').addEventListener('click', () => window.iterApi.switchTab(tab.id));
    pill.querySelector('.pin').addEventListener('click', (e) => {
      e.stopPropagation();
      window.iterApi.togglePinTab(tab.id);
    });
    pill.querySelector('.lock').addEventListener('click', (e) => {
      e.stopPropagation();
      window.iterApi.toggleLockTab(tab.id);
    });
    pill.querySelector('.x').addEventListener('click', (e) => {
      e.stopPropagation();
      if (tab.locked) return; // must release the lock first
      window.iterApi.closeTab(tab.id);
    });
    // Right-click / two-finger click -- a native menu with Close Tab and
    // friends, so closing (or managing) a tab never depends on the small
    // 'x' being reachable, e.g. when a long tab title pushes it tight
    // against the pill's max-width. Added 2026-09-14.
    pill.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      window.iterApi.showTabContextMenu(tab.id);
    });
    // Drag-to-reorder: drop a dragged pill onto another to swap them into
    // that position. Added 2026-09-14 per user request.
    pill.addEventListener('dragstart', (e) => {
      dragTabId = tab.id;
      e.dataTransfer.effectAllowed = 'move';
      pill.classList.add('dragging');
    });
    pill.addEventListener('dragend', () => pill.classList.remove('dragging'));
    pill.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (dragTabId != null && dragTabId !== tab.id) pill.classList.add('drag-over');
    });
    pill.addEventListener('dragleave', () => pill.classList.remove('drag-over'));
    pill.addEventListener('drop', (e) => {
      e.preventDefault();
      pill.classList.remove('drag-over');
      if (dragTabId == null || dragTabId === tab.id) return;
      const ids = tabsCache.map((t) => t.id);
      const from = ids.indexOf(dragTabId);
      const to = ids.indexOf(tab.id);
      if (from === -1 || to === -1) return;
      ids.splice(to, 0, ids.splice(from, 1)[0]);
      window.iterApi.reorderTabs(ids);
      dragTabId = null;
    });
    tabstripScroll.appendChild(pill);
  }
  renderAllTabsMenu(list);
}

// Lets a vertical two-finger swipe / mouse wheel scroll the tab strip
// sideways too, matching how most browsers' tab strips behave -- without
// this, reaching tabs off to the side required an explicit horizontal
// swipe, which is easy to fumble on a trackpad. Added 2026-09-14.
tabstripScroll.addEventListener(
  'wheel',
  (e) => {
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
      e.preventDefault();
      tabstripScroll.scrollLeft += e.deltaY;
    }
  },
  { passive: false }
);

// "tabs ▾" button -- always visible regardless of how many tabs are open
// or how far the strip is scrolled, so every open tab can always be seen
// and closed/switched-to, even far past what fits in the narrow sidebar.
// Added 2026-09-14 per user feedback ("cannot see/access all open tabs").
function renderAllTabsMenu(list) {
  tabAllBtn.textContent = `${list.length} tab${list.length === 1 ? '' : 's'} \u25be`;
  tabAllMenu.innerHTML = '';
  for (const tab of list) {
    const row = document.createElement('div');
    row.className = 'row-item' + (tab.active ? ' active' : '');
    row.title = tab.url;
    row.innerHTML = `<span class="title">${tab.pinned ? '📌 ' : ''}${tab.locked ? '🔒 ' : ''}${escapeHtml(tab.title || 'New Tab')}</span><span class="x">✕</span>`;
    row.querySelector('.title').addEventListener('click', () => {
      window.iterApi.switchTab(tab.id);
      tabAllMenu.hidden = true;
    });
    row.querySelector('.x').addEventListener('click', (e) => {
      e.stopPropagation();
      if (tab.locked) return;
      window.iterApi.closeTab(tab.id);
    });
    tabAllMenu.appendChild(row);
  }
}
tabAllBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  tabAllMenu.hidden = !tabAllMenu.hidden;
});
document.addEventListener('click', (e) => {
  if (!tabAllMenu.hidden && !tabAllMenu.contains(e.target) && e.target !== tabAllBtn) {
    tabAllMenu.hidden = true;
  }
});
document.getElementById('tab-new').addEventListener('click', () => window.iterApi.newTab('https://www.google.com'));

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

window.iterApi.onTabsUpdate(renderTabs);
window.iterApi.listTabs().then(renderTabs);
// Back/forward/reload/address-bar/Go/Dashboards controls now live in the
// dedicated full-width toolbar view (renderer/toolbar.html + toolbar.js),
// which sits directly above the browsed page like a normal browser's nav
// bar, instead of being crammed into this sidebar. See main.js's
// toolbarView.

// ---------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------
function addMessage(role, text) {
  const row = document.createElement('div');
  row.className = 'msg ' + role;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

document.getElementById('btn-send').addEventListener('click', sendChat);
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});

// Auto-grow the chat textarea as the user types, up to ~9 rows, so long
// messages stay fully visible and editable instead of scrolling inside a
// fixed-height box. Added 2026-09-14.
const CHAT_INPUT_MAX_ROWS = 9;
function autoGrowChatInput() {
  const cs = window.getComputedStyle(chatInput);
  const lineHeight = parseFloat(cs.lineHeight) || 16;
  const paddingV = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
  const borderV = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
  const maxHeight = lineHeight * CHAT_INPUT_MAX_ROWS + paddingV + borderV;
  chatInput.style.height = 'auto';
  const needed = chatInput.scrollHeight;
  chatInput.style.height = Math.min(needed, maxHeight) + 'px';
  chatInput.style.overflowY = needed > maxHeight ? 'auto' : 'hidden';
}
chatInput.addEventListener('input', autoGrowChatInput);
autoGrowChatInput();

function sendChat() {
  const text = chatInput.value.trim();
  if (!text) return;
  addMessage('user', text);
  window.iterApi.sendChat(text);
  chatInput.value = '';
  autoGrowChatInput();
}

window.iterApi.onChatIncoming((content) => addMessage('iter', content));

// ---------------------------------------------------------------------
// Iter process controls
// ---------------------------------------------------------------------
function setRunning(running) {
  statusDot.classList.toggle('on', running);
  statusText.textContent = running ? 'running' : 'stopped';
  btnStart.disabled = running;
  btnStop.disabled = !running;
}

btnStart.addEventListener('click', async () => {
  await saveSettingsFromForm();
  await window.iterApi.startIter();
  setRunning(true);
  addMessage('sys', 'Iter starting…');
});
btnStop.addEventListener('click', async () => {
  await window.iterApi.stopIter();
  setRunning(false);
  addMessage('sys', 'Iter stopped.');
});

window.iterApi.onIterStatus((status) => setRunning(status.running));
window.iterApi.iterStatus().then((s) => setRunning(s.running));

window.iterApi.onIterLog((line) => {
  logView.textContent += line.endsWith('\n') ? line : line + '\n';
  logView.scrollTop = logView.scrollHeight;
});
window.iterApi.recentLog().then((lines) => { logView.textContent = lines.join(''); });

// ---------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------
const providerSel = document.getElementById('provider');
const orEndpoint = document.getElementById('or-endpoint');
const orModel = document.getElementById('or-model');
const orKey = document.getElementById('or-key');
const lmEndpoint = document.getElementById('lm-endpoint');
const lmModel = document.getElementById('lm-model');
const panelOR = document.getElementById('panel-openrouter');
const panelLM = document.getElementById('panel-lmstudio');

function syncProviderPanels() {
  const local = providerSel.value === 'lmstudio';
  panelOR.style.display = local ? 'none' : 'flex';
  panelLM.style.display = local ? 'flex' : 'none';
}
providerSel.addEventListener('change', syncProviderPanels);

async function saveSettingsFromForm() {
  const settings = {
    provider: providerSel.value,
    openrouter: { endpoint: orEndpoint.value, model: orModel.value, apiKey: orKey.value },
    lmstudio: { endpoint: lmEndpoint.value, model: lmModel.value },
  };
  await window.iterApi.saveSettings(settings);
}
document.getElementById('btn-save-settings').addEventListener('click', () => {
  saveSettingsFromForm().then(() => addMessage('sys', 'Settings saved. Restart Iter (Stop, then Start) for changes to take effect.'));
});

window.iterApi.loadSettings().then((settings) => {
  providerSel.value = settings.provider || 'openrouter';
  orEndpoint.value = settings.openrouter.endpoint;
  orModel.value = settings.openrouter.model;
  orKey.value = settings.openrouter.apiKey || '';
  lmEndpoint.value = settings.lmstudio.endpoint;
  lmModel.value = settings.lmstudio.model;
  syncProviderPanels();
});

// ---------------------------------------------------------------------
// Permissions -- Camera & Microphone
// ---------------------------------------------------------------------
const PERM_LABELS = {
  'not-determined': 'not requested yet',
  granted: 'granted',
  denied: 'denied',
  restricted: 'restricted (managed by an org policy)',
  unknown: 'unknown',
};

function paintPermStatus(el, status) {
  el.textContent = PERM_LABELS[status] || status;
  el.style.color = status === 'granted' ? '#4caf7d' : status === 'denied' ? '#ff6b6b' : 'var(--muted)';
}

function refreshPermissions() {
  window.iterApi.permissionsStatus().then((s) => {
    paintPermStatus(document.getElementById('perm-camera-status'), s.camera);
    paintPermStatus(document.getElementById('perm-mic-status'), s.microphone);
  });
}
refreshPermissions();

document.getElementById('btn-perm-camera-request').addEventListener('click', () => {
  window.iterApi.requestPermission('camera').then(refreshPermissions);
});
document.getElementById('btn-perm-mic-request').addEventListener('click', () => {
  window.iterApi.requestPermission('microphone').then(refreshPermissions);
});
document.getElementById('btn-perm-camera-settings').addEventListener('click', () => {
  window.iterApi.openPermissionSettings('camera');
});
document.getElementById('btn-perm-mic-settings').addEventListener('click', () => {
  window.iterApi.openPermissionSettings('microphone');
});

// ---------------------------------------------------------------------
// State: Export / Import / Reset
// ---------------------------------------------------------------------
const stateStatus = document.getElementById('state-mgmt-status');

document.getElementById('btn-export-state').addEventListener('click', async () => {
  stateStatus.textContent = 'Exporting…';
  try {
    const result = await window.iterApi.exportState();
    if (result.canceled) { stateStatus.textContent = ''; return; }
    stateStatus.textContent = 'Exported to ' + result.exported;
    addMessage('sys', 'State exported to ' + result.exported);
  } catch (e) {
    stateStatus.textContent = 'Export failed: ' + e.message;
  }
});

document.getElementById('btn-import-state').addEventListener('click', async () => {
  const ok = confirm('Import will replace Iter\'s current memory, vector store, and knowledge files with the contents of the zip you pick. Continue?');
  if (!ok) return;
  stateStatus.textContent = 'Importing…';
  try {
    const result = await window.iterApi.importState();
    if (result.canceled) { stateStatus.textContent = ''; return; }
    stateStatus.textContent = 'Imported from ' + result.imported;
    addMessage('sys', 'State imported from ' + result.imported + (result.restarted ? ' (Iter restarted)' : ''));
    setRunning(result.restarted);
  } catch (e) {
    stateStatus.textContent = 'Import failed: ' + e.message;
  }
});

document.getElementById('btn-reset-state').addEventListener('click', async () => {
  const ok = confirm('This permanently deletes Iter\'s accumulated memory, vector store, backups, and knowledge files. Your tools/transformations code is NOT touched. This cannot be undone. Continue?');
  if (!ok) return;
  stateStatus.textContent = 'Resetting…';
  try {
    await window.iterApi.resetState();
    stateStatus.textContent = 'State reset.';
    addMessage('sys', 'State reset. Iter was stopped; press Start to begin fresh.');
    setRunning(false);
  } catch (e) {
    stateStatus.textContent = 'Reset failed: ' + e.message;
  }
});

// ---------------------------------------------------------------------
// Tab Groups -- save the currently open tabs under a name, then later
// open/switch-to/close/delete that saved group. Added 2026-09-14.
// ---------------------------------------------------------------------
const tabGroupsList = document.getElementById('tab-groups-list');
const tabGroupNameInput = document.getElementById('tab-group-name');

function renderTabGroups(groups) {
  tabGroupsList.innerHTML = '';
  if (!groups.length) {
    tabGroupsList.innerHTML = '<div style="font-size:10px;color:var(--muted)">No saved groups yet.</div>';
    return;
  }
  for (const g of groups) {
    const row = document.createElement('div');
    row.className = 'tab-group-item';
    row.innerHTML = `<span class="name" title="${escapeHtml(g.name)}">${escapeHtml(g.name)}</span><span class="count">${g.tabs.length} tab${g.tabs.length === 1 ? '' : 's'}</span><span class="actions"><button data-act="open">Open</button><button data-act="switch">Switch</button><button data-act="close">Close</button><button data-act="delete">Delete</button></span>`;
    row.querySelector('[data-act="open"]').addEventListener('click', async () => {
      await window.iterApi.openTabGroup(g.id);
    });
    row.querySelector('[data-act="switch"]').addEventListener('click', async () => {
      const ok = confirm(`Switch to "${g.name}"? This closes your current unpinned/unlocked tabs first.`);
      if (!ok) return;
      await window.iterApi.switchToTabGroup(g.id);
    });
    row.querySelector('[data-act="close"]').addEventListener('click', async () => {
      await window.iterApi.closeTabGroup(g.id);
    });
    row.querySelector('[data-act="delete"]').addEventListener('click', async () => {
      const ok = confirm(`Delete the saved group "${g.name}"? This does not close any open tabs.`);
      if (!ok) return;
      const updated = await window.iterApi.deleteTabGroup(g.id);
      renderTabGroups(updated);
    });
    tabGroupsList.appendChild(row);
  }
}

document.getElementById('btn-save-tab-group').addEventListener('click', async () => {
  const name = tabGroupNameInput.value.trim();
  if (!name) return;
  const updated = await window.iterApi.saveTabGroup(name);
  tabGroupNameInput.value = '';
  renderTabGroups(updated);
});

window.iterApi.listTabGroups().then(renderTabGroups);
document.getElementById('tab-groups').addEventListener('toggle', (e) => {
  if (e.target.open) window.iterApi.listTabGroups().then(renderTabGroups);
});

// ---------------------------------------------------------------------
// Sidebar resize
// ---------------------------------------------------------------------
const appShell = document.getElementById('app-shell');
const resizeHandle = document.getElementById('resize-handle');
const dragCatcher = document.getElementById('drag-catcher');
let resizing = false;
let pendingWidth = null;

resizeHandle.addEventListener('mousedown', async (e) => {
  e.preventDefault();
  resizing = true;
  dragCatcher.classList.add('active');
  await window.iterApi.resizeSidebarStart();
  appShell.style.width = appShell.getBoundingClientRect().width + 'px';
});

dragCatcher.addEventListener('mousemove', (e) => {
  if (!resizing) return;
  pendingWidth = e.clientX;
  requestAnimationFrame(flushResizeMove);
});

function flushResizeMove() {
  if (!resizing || pendingWidth === null) return;
  const width = pendingWidth;
  pendingWidth = null;
  window.iterApi.resizeSidebarMove(width).then((res) => {
    if (res && res.width) appShell.style.width = res.width + 'px';
  });
}

window.addEventListener('mouseup', async () => {
  if (!resizing) return;
  resizing = false;
  dragCatcher.classList.remove('active');
  await window.iterApi.resizeSidebarEnd();
  appShell.style.width = ''; // back to the CSS default (100%), now matching the shrunk native view
});

// ---------------------------------------------------------------------
// Terminal & Files
// ---------------------------------------------------------------------
const tfBreadcrumb = document.getElementById('tf-breadcrumb');
const tfTree = document.getElementById('tf-tree');
const tfUp = document.getElementById('tf-up');
const tfRefresh = document.getElementById('tf-refresh');
const tfCurrentFile = document.getElementById('tf-current-file');
const tfEditor = document.getElementById('tf-editor');
const tfSave = document.getElementById('tf-save');
const tfTermOutput = document.getElementById('tf-term-output');
const tfTermInput = document.getElementById('tf-term-input');
const tfTermCwd = document.getElementById('tf-term-cwd');
const tfTermInterrupt = document.getElementById('tf-term-interrupt');
const tfTermStop = document.getElementById('tf-term-stop');
const termfilesDetails = document.getElementById('termfiles');

let tfCurrentDir = '.';
let tfOpenFile = null;
let tfDirty = false;
let termStarted = false;

async function tfLoadDir(relPath) {
  try {
    const res = await window.iterApi.fsList(relPath);
    tfCurrentDir = res.path;
    tfBreadcrumb.textContent = '/' + (tfCurrentDir === '.' ? '' : tfCurrentDir);
    tfTree.innerHTML = '';
    for (const item of res.items) {
      const row = document.createElement('div');
      row.className = 'tf-entry ' + (item.isDir ? 'dir' : 'file');
      row.textContent = item.name;
      const childRel = tfCurrentDir === '.' ? item.name : tfCurrentDir + '/' + item.name;
      row.addEventListener('click', () => {
        if (item.isDir) tfLoadDir(childRel);
        else tfOpenFileAt(childRel);
      });
      tfTree.appendChild(row);
    }
  } catch (e) {
    tfTree.innerHTML = '';
    const err = document.createElement('div');
    err.className = 'tf-muted';
    err.textContent = 'Error: ' + e.message;
    tfTree.appendChild(err);
  }
}

async function tfOpenFileAt(relPath) {
  if (tfDirty && !confirm('Discard unsaved changes to ' + tfOpenFile + '?')) return;
  try {
    const res = await window.iterApi.fsRead(relPath);
    if (res.tooLarge) {
      tfEditor.value = '';
      tfEditor.disabled = true;
      tfSave.disabled = true;
      tfCurrentFile.textContent = relPath + ' (too large to edit — ' + res.size + ' bytes)';
      tfOpenFile = null;
      return;
    }
    if (res.binary) {
      tfEditor.value = '';
      tfEditor.disabled = true;
      tfSave.disabled = true;
      tfCurrentFile.textContent = relPath + ' (binary file, not shown)';
      tfOpenFile = null;
      return;
    }
    tfEditor.value = res.content;
    tfEditor.disabled = false;
    tfSave.disabled = false;
    tfCurrentFile.textContent = relPath;
    tfOpenFile = relPath;
    tfDirty = false;
  } catch (e) {
    tfCurrentFile.textContent = 'Error: ' + e.message;
  }
}

tfEditor.addEventListener('input', () => { tfDirty = true; });

tfSave.addEventListener('click', async () => {
  if (!tfOpenFile) return;
  try {
    await window.iterApi.fsWrite(tfOpenFile, tfEditor.value);
    tfDirty = false;
    tfCurrentFile.textContent = tfOpenFile + ' (saved)';
    setTimeout(() => { if (!tfDirty && tfOpenFile) tfCurrentFile.textContent = tfOpenFile; }, 1500);
  } catch (e) {
    tfCurrentFile.textContent = 'Save failed: ' + e.message;
  }
});

tfUp.addEventListener('click', () => {
  if (tfCurrentDir === '.' || tfCurrentDir === '') return;
  const parts = tfCurrentDir.split('/');
  parts.pop();
  tfLoadDir(parts.length ? parts.join('/') : '.');
});
tfRefresh.addEventListener('click', () => tfLoadDir(tfCurrentDir));

function tfAppendTerm(text) {
  tfTermOutput.textContent += text;
  tfTermOutput.scrollTop = tfTermOutput.scrollHeight;
}

window.iterApi.onTerminalData((chunk) => tfAppendTerm(chunk));
window.iterApi.onTerminalDone((info) => {
  if (info.cwd) tfTermCwd.textContent = info.cwd;
  tfAppendTerm('\n$ ');
});

tfTermInput.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const cmd = tfTermInput.value;
  tfTermInput.value = '';
  if (!termStarted) { await window.iterApi.terminalStart(); termStarted = true; }
  tfAppendTerm(cmd + '\n');
  await window.iterApi.terminalRun(cmd);
});

tfTermInterrupt.addEventListener('click', () => window.iterApi.terminalInterrupt());
tfTermStop.addEventListener('click', async () => {
  await window.iterApi.terminalStop();
  termStarted = false;
  tfAppendTerm('\n[terminal stopped]\n');
});

// Lazily start the shell and load the file tree the first time the panel
// is opened, rather than at page load (keeps startup light).
let termfilesInitialized = false;
termfilesDetails.addEventListener('toggle', async () => {
  if (!termfilesDetails.open || termfilesInitialized) return;
  termfilesInitialized = true;
  tfLoadDir('.');
  await window.iterApi.terminalStart();
  termStarted = true;
  tfAppendTerm('$ ');
});
