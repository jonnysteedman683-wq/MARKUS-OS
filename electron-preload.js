// MARKUS OS — secure preload (contextIsolation: true)
// Exposes a minimal, safe API via contextBridge. Never expose raw ipcRenderer.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('markus', {
  platform: process.platform,
  versions: {
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  },
  // Extend here with narrow, validated IPC channels only — do NOT bridge ipcRenderer.
  appInfo: () => ({
    name: 'MARKUS OS',
    secure: true,
    contextIsolation: true
  }),
  // v1.1: window control IPC (validated channels only)
  minimizeWindow: () => ipcRenderer.invoke('system:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('system:maximize'),
  closeWindow: () => ipcRenderer.invoke('system:close')
});
