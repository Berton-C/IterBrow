// Narrow collaboration contract for navigation-locked IterBrow tab/apps.
// The main process independently resolves the same scope from WebContents;
// these arguments identify the consumer to this isolated renderer only.
const { contextBridge, ipcRenderer } = require('electron');

function argument(name) {
  const prefix = `--${name}=`;
  const found = process.argv.find((value) => value.startsWith(prefix));
  if (!found) throw new Error(`Missing application scope: ${name}`);
  return found.slice(prefix.length);
}

argument('iter-app-id');
argument('iter-consumer-id');

contextBridge.exposeInMainWorld('iterApp', Object.freeze({
  appContext: () => ipcRenderer.invoke('app:context'),
  appCommand: (command) => ipcRenderer.invoke('app:command', command),
  appChanges: (afterCommit) => ipcRenderer.invoke('app:changes', afterCommit),
  subscribe: (afterCommit) => ipcRenderer.invoke('app:changes', afterCommit),
}));
