const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iterApi', {
  crmRead: (fname) => ipcRenderer.invoke('crm:read', fname),
  crmWrite: (fname, data) => ipcRenderer.invoke('crm:write', fname, data),
  listTabs: () => ipcRenderer.invoke('tabs:list'),
  newTab: (url) => ipcRenderer.invoke('tabs:new', url),
  closeTab: (id) => ipcRenderer.invoke('tabs:close', id),
  switchTab: (id) => ipcRenderer.invoke('tabs:switch', id),
  toggleLockTab: (id) => ipcRenderer.invoke('tabs:toggleLock', id),
  togglePinTab: (id) => ipcRenderer.invoke('tabs:togglePin', id),
  showTabContextMenu: (id) => ipcRenderer.invoke('tabs:contextMenu', id),
  reorderTabs: (orderedIds) => ipcRenderer.invoke('tabs:reorder', orderedIds),
  popOutTab: (id) => ipcRenderer.invoke('tabs:popOut', id), // M16-A2
  popInTab: (id) => ipcRenderer.invoke('tabs:popIn', id),

  listTabGroups: () => ipcRenderer.invoke('tabGroups:list'),
  saveTabGroup: (name) => ipcRenderer.invoke('tabGroups:save', name),
  resaveTabGroup: (groupId) => ipcRenderer.invoke('tabGroups:resave', groupId),
  openTabGroup: (groupId) => ipcRenderer.invoke('tabGroups:open', groupId),
  switchToTabGroup: (groupId) => ipcRenderer.invoke('tabGroups:switch', groupId),
  closeTabGroup: (groupId) => ipcRenderer.invoke('tabGroups:close', groupId),
  deleteTabGroup: (groupId) => ipcRenderer.invoke('tabGroups:delete', groupId),

  listClosedTabs: () => ipcRenderer.invoke('closedTabs:list'),
  reopenClosedTab: (index) => ipcRenderer.invoke('closedTabs:reopen', index),
  navigate: (id, url) => ipcRenderer.invoke('tabs:navigate', { id, url }),
  back: (id) => ipcRenderer.invoke('tabs:back', id),
  forward: (id) => ipcRenderer.invoke('tabs:forward', id),
  reload: (id) => ipcRenderer.invoke('tabs:reload', id),

  sendChat: (content) => ipcRenderer.invoke('chat:send', content),
  // Card answers: main.js adds who is here (soul settings) and records the choice.
  sendChoice: (cardId, choiceId, label) => ipcRenderer.invoke('chat:choice', cardId, choiceId, label),
  chatHistory: () => ipcRenderer.invoke('chat:history'),
  onChatIncoming: (cb) => ipcRenderer.on('chat:incoming', (_e, message) => cb(message)),

  startIter: () => ipcRenderer.invoke('iter:start'),
  stopIter: () => ipcRenderer.invoke('iter:stop'),
  iterStatus: () => ipcRenderer.invoke('iter:status'),
  recentLog: () => ipcRenderer.invoke('iter:recentLog'),
  onIterLog: (cb) => ipcRenderer.on('iter:log', (_e, line) => cb(line)),
  onIterStatus: (cb) => ipcRenderer.on('iter:status', (_e, status) => cb(status)),
  onUiResume: (cb) => ipcRenderer.on('ui:resume', (_e, info) => cb(info)),

  loadSettings: () => ipcRenderer.invoke('settings:load'),
  loadSoulSettings: () => ipcRenderer.invoke('soul:load'),
  saveSoulSettings: (settings) => ipcRenderer.invoke('soul:save', settings),
  forgetSoulTaste: () => ipcRenderer.invoke('soul:forget'),
  // M9: the browsing ally (toolbar) and find-in-page.
  onAllySuggest: (cb) => ipcRenderer.on('ally:suggest', (_e, payload) => cb(payload)),
  allyLock: (tabId) => ipcRenderer.invoke('ally:lock', tabId),
  allyDecline: (host) => ipcRenderer.invoke('ally:decline', host),
  onCompassState: (cb) => ipcRenderer.on('compass:state', (_e, state) => cb(state)),
  onFindOpen: (cb) => ipcRenderer.on('find:open', () => cb()),
  onFindResult: (cb) => ipcRenderer.on('find:result', (_e, result) => cb(result)),
  onFindClosed: (cb) => ipcRenderer.on('find:closed', () => cb()),
  findQuery: (text) => ipcRenderer.invoke('find:query', text),
  findNext: () => ipcRenderer.invoke('find:next'),
  findPrev: () => ipcRenderer.invoke('find:prev'),
  findClose: () => ipcRenderer.invoke('find:close'),
  // M11-B: bookmarks (toolbar star and menu).
  bookmarks: () => ipcRenderer.invoke('bookmarks:list'),
  bookmarkToggle: (tabId) => ipcRenderer.invoke('bookmarks:toggle', tabId),
  bookmarkOpen: (url) => ipcRenderer.invoke('bookmarks:open', url),
  onBookmarkState: (cb) => ipcRenderer.on('bookmarks:state', (_e, state) => cb(state)),
  // M11-C: history search (toolbar history bar).
  historySearch: (q) => ipcRenderer.invoke('history:search', q),
  historyOpen: (url) => ipcRenderer.invoke('history:openUrl', url),
  historyClear: () => ipcRenderer.invoke('history:clear'),
  onHistoryOpen: (cb) => ipcRenderer.on('history:open', () => cb()),
  toolbarOverlay: (height) => ipcRenderer.send('toolbar:overlay', height),
  // M11-D: reader mode (toolbar button) and its notice.
  readerOpen: (tabId) => ipcRenderer.invoke('reader:open', tabId),
  onReaderNotice: (cb) => ipcRenderer.on('reader:notice', (_e, notice) => cb(notice)),
  saveSettings: (settings) => ipcRenderer.invoke('settings:save', settings),
  // M16-B2: run in main with the stored key when none is typed; keys never come back here.
  fetchModels: (args) => ipcRenderer.invoke('settings:fetchModels', args),
  testConnection: (args) => ipcRenderer.invoke('settings:test', args),

  permissionsStatus: () => ipcRenderer.invoke('permissions:status'),
  requestPermission: (kind) => ipcRenderer.invoke('permissions:request', kind),
  openPermissionSettings: (kind) => ipcRenderer.invoke('permissions:openSystemSettings', kind),

  exportState: () => ipcRenderer.invoke('state:export'),
  importState: () => ipcRenderer.invoke('state:import'),
  restoreState: () => ipcRenderer.invoke('state:restore'),
  resetState: () => ipcRenderer.invoke('state:reset'),

  onTabsUpdate: (cb) => ipcRenderer.on('tabs:update', (_e, list) => cb(list)),
  reportTabstripHeight: (height) => ipcRenderer.send('tabstrip:height', height),

  resizeSidebarStart: () => ipcRenderer.invoke('sidebar:resize-start'),
  resizeSidebarMove: (width) => ipcRenderer.invoke('sidebar:resize-move', width),
  resizeSidebarEnd: () => ipcRenderer.invoke('sidebar:resize-end'),

  fsList: (relPath) => ipcRenderer.invoke('fs:list', relPath),
  fsRead: (relPath) => ipcRenderer.invoke('fs:read', relPath),
  fsWrite: (relPath, content) => ipcRenderer.invoke('fs:write', { path: relPath, content }),

  terminalStart: () => ipcRenderer.invoke('terminal:start'),
  terminalRun: (cmd) => ipcRenderer.invoke('terminal:run', cmd),
  terminalInterrupt: () => ipcRenderer.invoke('terminal:interrupt'),
  terminalStop: () => ipcRenderer.invoke('terminal:stop'),
  openDashboards: () => ipcRenderer.invoke('dashboards:open'),
  openPWQ: () => ipcRenderer.invoke('pwq:open'),
  openCRM: () => ipcRenderer.invoke('crm:open'),
  openApp: (appId) => ipcRenderer.invoke('apps:open', appId),
  listApps: () => ipcRenderer.invoke('apps:list'),
  appsCatalog: () => ipcRenderer.invoke('apps:catalog'),
  appsMenu: () => ipcRenderer.invoke('apps:menu'),
  chooseVault: () => ipcRenderer.invoke('vault:choose'), // M14-A5
  onTerminalData: (cb) => ipcRenderer.on('terminal:data', (_e, chunk) => cb(chunk)),
  onTerminalDone: (cb) => ipcRenderer.on('terminal:done', (_e, info) => cb(info)),
});
