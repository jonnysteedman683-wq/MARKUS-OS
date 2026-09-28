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
  // Narrow, validated IPC: query live server health through main process.
  // Only this single allow-listed channel is bridged — never raw ipcRenderer.
  health: () => ipcRenderer.invoke('markus:health'),
  // Extend here with narrow, validated IPC channels only — do NOT bridge ipcRenderer.
  appInfo: () => ({
    name: 'MARKUS OS',
    secure: true,
    contextIsolation: true
  })
});
