const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('markusAPI', {
  platform: process.platform,
  version: '1.0.0',
  minimizeWindow: () => ipcRenderer.invoke('system:minimize'),
  maximizeWindow: () => ipcRenderer.invoke('system:maximize'),
  closeWindow: () => ipcRenderer.invoke('system:close')
});
