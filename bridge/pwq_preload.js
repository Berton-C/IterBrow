// Scoped preload for the PWQ board tab ONLY. The board can read its canonical
// projection and submit narrow protocol commands; it cannot write files or
// synchronize a caller-supplied whole-board snapshot. Navigation is locked by
// the tab owner in main.js.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('iterApi', {
  pwqRead: () => ipcRenderer.invoke('pwq:read'),
  pwqCommand: (request) => ipcRenderer.invoke('pwq:command', request),
});
