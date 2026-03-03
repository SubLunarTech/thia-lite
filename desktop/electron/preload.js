const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  getVersions: () => process.versions,
  getPlatform: () => process.platform,

  // IPC events sent from main to installer window
  onInstallProgress: (callback) => ipcRenderer.on('install-progress', (_event, data) => callback(data)),

  // IPC events sent from installer window to main
  sendInstallChoice: (choice) => ipcRenderer.send('install-choice', choice)
});
