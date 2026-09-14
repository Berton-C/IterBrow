const tabstrip = document.getElementById('tabstrip');
const addr = document.getElementById('addr');
const chat = document.getElementById('chat');
const chatInput = document.getElementById('chat-input');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const btnStart = document.getElementById('btn-start');
const btnStop = document.getElementById('btn-stop');
const logView = document.getElementById('log-view');

let activeTabId = null;
let tabsCache = [];

// ---------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------
function renderTabs(list) {
  tabsCache = list;
  const active = list.find((t) => t.active);
  activeTabId = active ? active.id : null;
  if (active) addr.value = active.url;

  tabstrip.innerHTML = '';
  for (const tab of list) {
    const pill = document.createElement('div');
    pill.className = 'tab-pill' + (tab.active ? ' active' : '') + (tab.locked ? ' locked' : '') + (tab.pinned ? ' pinned' : '');
    pill.title = tab.locked
      ? tab.url + ' (locked — Iter cannot alter or close this tab until you click the lock)'
      : tab.url;
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
    tabstrip.appendChild(pill);
  }
  const newBtn = document.createElement('button');
  newBtn.id = 'tab-new';
  newBtn.textContent = '+';
  newBtn.addEventListener('click', () => window.iterApi.newTab('https://www.google.com'));
  tabstrip.appendChild(newBtn);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

window.iterApi.onTabsUpdate(renderTabs);
window.iterApi.listTabs().then(renderTabs);

document.getElementById('btn-back').addEventListener('click', () => activeTabId && window.iterApi.back(activeTabId));
document.getElementById('btn-forward').addEventListener('click', () => activeTabId && window.iterApi.forward(activeTabId));
document.getElementById('btn-reload').addEventListener('click', () => activeTabId && window.iterApi.reload(activeTabId));
document.getElementById('btn-go').addEventListener('click', go);
document.getElementById('btn-dashboards').addEventListener('click', () => window.iterApi.openDashboards());
addr.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });

function go() {
  if (!activeTabId) return;
  let url = addr.value.trim();
  if (!/^[a-z]+:\/\//i.test(url)) {
    url = url.includes('.') && !url.includes(' ') ? 'https://' + url : 'https://www.google.com/search?q=' + encodeURIComponent(url);
  }
  window.iterApi.navigate(activeTabId, url);
}

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

function sendChat() {
  const text = chatInput.value.trim();
  if (!text) return;
  addMessage('user', text);
  window.iterApi.sendChat(text);
  chatInput.value = '';
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
