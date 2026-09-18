// Scoped preload for the CRM tab ONLY. Deliberately exposes just crmRead/
// crmWrite -- nothing else the full preload.js gives the chrome views (no
// tab control, no terminal, no fs:*, no state export/import/restore). Even
// though crm:read/crm:write are already server-side whitelisted to the 4
// known CRM JSON files (see main.js CRM_FILES), keeping this preload minimal
// means a compromised/malicious page loaded in this tab (see the
// restrictNavigation guard in tab_manager.js -- this tab can never navigate
// away from crm/index.html) has nothing extra to reach for either.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iterApi', {
  crmRead: (fname) => ipcRenderer.invoke('crm:read', fname),
  crmWrite: (fname, data) => ipcRenderer.invoke('crm:write', fname, data),
});
