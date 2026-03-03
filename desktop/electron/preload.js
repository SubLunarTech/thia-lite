const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  getVersions: () => process.versions,
  getPlatform: () => process.platform,
  onInstallProgress: (callback) => ipcRenderer.on('install-progress', (_event, data) => callback(data))
});
