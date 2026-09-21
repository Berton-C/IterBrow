// Scoped preload for the PWQ board tab ONLY (write-through fix 2026-09-20).
// Mirrors crm_preload.js: exposes just pwqRead/pwqWrite -> main.js whitelists
// these to the single canonical .runtime/pwq.json file. No fs:*, no tab
// control, nothing else. restrictNavigation locks the tab to pwq.html.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iterApi', {
  fsRead: (rel) => ipcRenderer.invoke('pwq:read', rel),
  fsWrite: (rel, content) => ipcRenderer.invoke('pwq:write', rel, content),
});
