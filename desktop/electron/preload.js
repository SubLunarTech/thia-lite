const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getVersions: () => process.versions,
  getPlatform: () => process.platform,

  // Tools & Settings
  getLocalModelsConfig: () => ipcRenderer.invoke('llm-get-local-models'),
  getLLMStatus: () => ipcRenderer.invoke('llm-status'),
  setupLocal: (modelId) => ipcRenderer.send('llm-setup-local', modelId),
  setupCloud: (provider, apiKey) => ipcRenderer.send('llm-setup-cloud', provider, apiKey),
  switchProvider: (provider, options) => ipcRenderer.send('llm-switch-provider', provider, options),

  // Commands
  chat: (messages, options) => ipcRenderer.invoke('llm-chat', messages, options),

  // Conversation & Memory Management
  getConversations: () => ipcRenderer.invoke('get-conversations'),
  getMessages: (convId) => ipcRenderer.invoke('get-messages', convId),
  saveMessage: (convId, msg) => ipcRenderer.invoke('save-message', convId, msg),
  deleteConversation: (convId) => ipcRenderer.invoke('delete-conversation', convId),
  getMemories: () => ipcRenderer.invoke('get-memories'),

  // ── LLM Events (main → renderer) ──
  onDownloadProgress: (cb) => ipcRenderer.on('llm-download-progress', (_e, data) => cb(data)),
  onSetupStatus: (cb) => ipcRenderer.on('llm-setup-status', (_e, data) => cb(data)),
  onSetupComplete: (cb) => ipcRenderer.on('llm-setup-complete', (_e, data) => cb(data)),
  onError: (cb) => ipcRenderer.on('llm-error', (_e, data) => cb(data)),
  onToolCall: (cb) => ipcRenderer.on('llm-tool-call', (_e, data) => cb(data)),

  // ── Log management ──
  openLogs: () => ipcRenderer.send('open-logs'),
  getLogContent: () => ipcRenderer.invoke('get-log-content'),
});
