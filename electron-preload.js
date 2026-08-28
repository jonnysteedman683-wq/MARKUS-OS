// MARKUS OS — secure preload (contextIsolation: true)
// Exposes a minimal, safe API via contextBridge. Never expose raw ipcRenderer.
const { contextBridge } = require('electron');

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
  })
});
