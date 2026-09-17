const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iterApi', {
  listTabs: () => ipcRenderer.invoke('tabs:list'),
  newTab: (url) => ipcRenderer.invoke('tabs:new', url),
  closeTab: (id) => ipcRenderer.invoke('tabs:close', id),
  switchTab: (id) => ipcRenderer.invoke('tabs:switch', id),
  toggleLockTab: (id) => ipcRenderer.invoke('tabs:toggleLock', id),
  togglePinTab: (id) => ipcRenderer.invoke('tabs:togglePin', id),
  showTabContextMenu: (id) => ipcRenderer.invoke('tabs:contextMenu', id),
  reorderTabs: (orderedIds) => ipcRenderer.invoke('tabs:reorder', orderedIds),

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
  onChatIncoming: (cb) => ipcRenderer.on('chat:incoming', (_e, content) => cb(content)),

  startIter: () => ipcRenderer.invoke('iter:start'),
  stopIter: () => ipcRenderer.invoke('iter:stop'),
  iterStatus: () => ipcRenderer.invoke('iter:status'),
  recentLog: () => ipcRenderer.invoke('iter:recentLog'),
  onIterLog: (cb) => ipcRenderer.on('iter:log', (_e, line) => cb(line)),
  onIterStatus: (cb) => ipcRenderer.on('iter:status', (_e, status) => cb(status)),

  loadSettings: () => ipcRenderer.invoke('settings:load'),
  saveSettings: (settings) => ipcRenderer.invoke('settings:save', settings),

  permissionsStatus: () => ipcRenderer.invoke('permissions:status'),
  requestPermission: (kind) => ipcRenderer.invoke('permissions:request', kind),
  openPermissionSettings: (kind) => ipcRenderer.invoke('permissions:openSystemSettings', kind),

  exportState: () => ipcRenderer.invoke('state:export'),
  importState: () => ipcRenderer.invoke('state:import'),
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
  onTerminalData: (cb) => ipcRenderer.on('terminal:data', (_e, chunk) => cb(chunk)),
  onTerminalDone: (cb) => ipcRenderer.on('terminal:done', (_e, info) => cb(info)),
});
