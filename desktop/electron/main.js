const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const { autoUpdater } = require('electron-updater');
const { LLMEngine } = require('./llm-engine');
const { MCPClient } = require('./mcp-client');

let mainWindow;
let setupWindow;
let backendProcess = null;
let mcpClient = null;
const llmEngine = new LLMEngine();

const API_PORT = 8765;

// ─── Data Storage ────────────────────────────────────────────────────────────

function getUserDataDir() {
  return app.getPath('userData');
}

let appConversations = [];
const CONV_FILE = path.join(getUserDataDir(), 'conversations.json');

function loadConversations() {
  try {
    if (fs.existsSync(CONV_FILE)) {
      appConversations = JSON.parse(fs.readFileSync(CONV_FILE, 'utf8'));
    }
  } catch (e) {
    logMain(`Failed to load conversations: ${e.message}`);
  }
}

function saveConversations() {
  try {
    fs.writeFileSync(CONV_FILE, JSON.stringify(appConversations, null, 2), 'utf8');
  } catch (e) {
    logMain(`Failed to save conversations: ${e.message}`);
  }
}

function initConversations() {
  loadConversations();
}

if (process.platform === 'win32') {
  app.disableHardwareAcceleration();
}

app.setName('Thia');

// ─── Logging ─────────────────────────────────────────────────────────────────

function getMainLogPath() {
  try {
    return path.join(app.getPath('userData'), 'main.log');
  } catch {
    return path.join(process.cwd(), 'thia-main.log');
  }
}

function logMain(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try { fs.appendFileSync(getMainLogPath(), line, 'utf8'); } catch { }
}

// ─── Python Backend ──────────────────────────────────────────────────────────

function findBackendBinary() {
  const isWin = process.platform === 'win32';
  const binName = isWin ? 'thia-lite.exe' : 'thia-lite';

  const packagedPath = path.join(process.resourcesPath, 'bin', binName);
  if (fs.existsSync(packagedPath)) {
    logMain(`Found bundled backend at: ${packagedPath}`);
    return packagedPath;
  }

  const devPath = path.resolve(__dirname, '..', '..', 'dist', binName);
  if (fs.existsSync(devPath)) {
    logMain(`Found dev backend at: ${devPath}`);
    return devPath;
  }

  return null;
}

async function findPython() {
  const { execSync } = require('child_process');
  const isWin = process.platform === 'win32';
  const cmd = isWin ? 'where' : 'which';
  const candidates = isWin ? ['py', 'python3', 'python'] : ['python3', 'python'];

  for (const py of candidates) {
    try {
      const result = execSync(`${cmd} ${py}`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] });
      if (result?.trim()) {
        const pythonPath = result.trim().split('\n')[0].trim();
        logMain(`Found Python at: ${pythonPath}`);
        return pythonPath;
      }
    } catch { continue; }
  }
  return null;
}

async function startBackend() {
  return new Promise(async (resolve, reject) => {
    const backendPath = findBackendBinary();

    if (backendPath) {
      logMain(`Starting bundled backend: ${backendPath} serve --mode stdio`);
      if (process.platform !== 'win32') {
        try { fs.chmodSync(backendPath, '755'); } catch { }
      }
      backendProcess = spawn(backendPath, ['serve', '--mode', 'stdio'], {
        cwd: path.dirname(backendPath),
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } else {
      let pythonPath = null;
      if (process.platform === 'win32') {
        const bundled = path.join(process.resourcesPath, 'python', 'python.exe');
        if (fs.existsSync(bundled)) pythonPath = bundled;
      }
      if (!pythonPath) pythonPath = await findPython();

      if (!pythonPath) {
        reject(new Error('Python not found. Install Python 3.9+ from https://www.python.org/downloads/'));
        return;
      }

      logMain(`Starting Python MCP server with: ${pythonPath}`);
      backendProcess = spawn(pythonPath, ['-m', 'thia_lite', 'serve', '--mode', 'stdio'], {
        cwd: process.resourcesPath || path.resolve(__dirname, '..', '..'),
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    }

    // Initialize MCP Client
    mcpClient = new MCPClient(backendProcess);

    // Pass the client to LLMEngine
    llmEngine.mcpClient = mcpClient;

    let started = false;
    const timeout = setTimeout(() => {
      if (!started) { started = true; logMain('Backend timeout — proceeding'); resolve(); }
    }, 15000);

    mcpClient.on('ready', (tools) => {
      logMain(`MCP Client ready with ${tools.length} tools`);
      if (!started) { started = true; clearTimeout(timeout); resolve(); }
    });

    mcpClient.on('error', (err) => {
      logMain(`MCP Client error: ${err.message}`);
    });

    backendProcess.stderr.on('data', (data) => {
      // Python's logging statements go to stderr in MCP server to avoid corrupting stdout
      logMain(`[backend-err] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
      logMain(`Backend spawn error: ${err.message}`);
      if (!started) { started = true; clearTimeout(timeout); reject(err); }
    });

    backendProcess.on('exit', (code, signal) => {
      logMain(`Backend exited code=${code} signal=${signal}`);
      backendProcess = null;
      if (!started) { started = true; clearTimeout(timeout); reject(new Error(`Backend exited: ${code}`)); }
    });

    // Start initialization
    mcpClient.initialize().catch(err => {
      logMain(`MCP Init error: ${err.message}`);
      if (!started) { started = true; clearTimeout(timeout); reject(err); }
    });
  });
}

function stopBackend() {
  if (backendProcess) {
    logMain('Stopping backend...');
    backendProcess.kill();
    backendProcess = null;
  }
}

// ─── Windows ─────────────────────────────────────────────────────────────────

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'icons/icon.png'),
    title: 'Thia — AI Astrology Assistant',
  });

  const packagedIndex = path.join(__dirname, 'src', 'index.html');
  const devIndex = path.join(__dirname, '..', 'src', 'index.html');
  const indexPath = fs.existsSync(packagedIndex) ? packagedIndex : devIndex;
  logMain(`Loading chat UI from: ${indexPath}`);
  mainWindow.loadFile(indexPath);

  mainWindow.webContents.on('did-fail-load', (_e, code, desc, url) => {
    logMain(`did-fail-load code=${code} error=${desc} url=${url}`);
    dialog.showErrorBox('Thia Failed to Load', `Could not load UI.\nCode: ${code}\nError: ${desc}`);
  });

  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => { mainWindow = null; });
}

function createSetupWindow() {
  setupWindow = new BrowserWindow({
    width: 600,
    height: 520,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'icons/icon.png'),
    title: 'Thia — Setup',
  });

  const setupPath = path.join(__dirname, 'src', 'setup.html');
  logMain(`Loading setup from: ${setupPath}`);
  setupWindow.loadFile(setupPath);

  setupWindow.on('closed', () => { setupWindow = null; });
}

// ─── LLM IPC Handlers ───────────────────────────────────────────────────────

function registerLLMHandlers() {
  // Forward LLM engine events to the active window
  const sendToWindow = (channel, data) => {
    const win = setupWindow || mainWindow;
    if (win && !win.isDestroyed()) {
      win.webContents.send(channel, data);
    }
  };

  llmEngine.on('download-start', (data) => sendToWindow('llm-download-progress', { percent: 0, ...data }));
  llmEngine.on('download-progress', (data) => sendToWindow('llm-download-progress', data));
  llmEngine.on('download-complete', () => sendToWindow('llm-setup-status', { message: 'Loading model...' }));
  llmEngine.on('status', (msg) => sendToWindow('llm-setup-status', { message: msg }));
  llmEngine.on('error', (err) => sendToWindow('llm-error', { message: err.message }));
  llmEngine.on('ready', (data) => {
    logMain(`LLM ready: provider=${data.provider}`);
    sendToWindow('llm-setup-complete', data);

    // If setup window is open, close it and open main window
    if (setupWindow && !setupWindow.isDestroyed()) {
      setupWindow.close();
      setupWindow = null;
    }
    if (!mainWindow) {
      createMainWindow();
    }
  });

  // Set up local model list query
  ipcMain.handle('llm-get-local-models', async () => {
    return llmEngine.getLocalModelsConfig();
  });

  // Setup commands from renderer
  ipcMain.on('llm-setup-local', async (_e, modelId) => {
    logMain(`User chose: local model (${modelId || 'recommended'})`);
    try {
      await llmEngine.setupLocal(modelId);
    } catch (e) {
      logMain(`Local setup failed: ${e.message}`);
      sendToWindow('llm-error', { message: e.message });
    }
  });

  ipcMain.on('llm-setup-cloud', async (_e, provider, apiKey) => {
    logMain(`User chose: cloud (${provider})`);
    try {
      await llmEngine.setupCloud(provider, apiKey);
    } catch (e) {
      logMain(`Cloud setup failed: ${e.message}`);
      sendToWindow('llm-error', { message: e.message });
    }
  });

  ipcMain.on('llm-switch-provider', async (_e, provider, options) => {
    logMain(`Switching provider to: ${provider}`);
    try {
      await llmEngine.switchProvider(provider, options);
    } catch (e) {
      logMain(`Provider switch failed: ${e.message}`);
    }
  });

  // Chat handler (used by renderer's chat flow)
  ipcMain.handle('llm-chat', async (_e, messages, options) => {
    try {
      return await llmEngine.chat(messages, options || {});
    } catch (e) {
      return { role: 'assistant', content: `LLM Error: ${e.message}`, tool_calls: null, done: true };
    }
  });

  // Status query
  ipcMain.handle('llm-status', async () => {
    return {
      configured: llmEngine.isConfigured,
      ready: llmEngine.isReady,
      provider: llmEngine.provider,
      config: llmEngine.config,
    };
  });

  // Memory Panel
  ipcMain.handle('get-memories', async () => {
    if (mcpClient) {
      try {
        const res = await mcpClient.callTool('get_all_memories', {});
        return res?.content?.[0]?.text ? JSON.parse(res.content[0].text) : null;
      } catch (e) {
        logMain(`Failed to get memories: ${e.message}`);
        return null;
      }
    }
    return null;
  });

  // Conversation Management
  ipcMain.handle('get-conversations', () => {
    return appConversations.map(c => ({ id: c.id, title: c.title, updated_at: c.updated_at })).sort((a, b) => b.updated_at - a.updated_at);
  });

  ipcMain.handle('get-messages', (_e, convId) => {
    const conv = appConversations.find(c => c.id === convId);
    return conv ? conv.messages : [];
  });

  ipcMain.handle('save-message', (_e, convId, messageData) => {
    let conv = appConversations.find(c => c.id === convId);
    if (!conv) {
      conv = {
        id: convId,
        title: messageData.content.substring(0, 30) + '...',
        created_at: Date.now(),
        updated_at: Date.now(),
        messages: []
      };
      appConversations.push(conv);
    }

    // Check if the message is already appended to prevent duplicates
    const lastMsg = conv.messages[conv.messages.length - 1];
    if (lastMsg && lastMsg.role === messageData.role && lastMsg.content === messageData.content) {
      return convId;
    }

    conv.messages.push(messageData);
    conv.updated_at = Date.now();
    saveConversations();
    return convId;
  });

  ipcMain.handle('delete-conversation', (_e, convId) => {
    appConversations = appConversations.filter(c => c.id !== convId);
    saveConversations();
    return true;
  });
}

// ─── App Lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  logMain('App ready');
  initConversations();
  registerLLMHandlers();

  // Setup Auto-Updater (silent check)
  autoUpdater.logger = {
    info(msg) { logMain(`autoUpdater: ${msg}`); },
    warn(msg) { logMain(`autoUpdater WARN: ${msg}`); },
    error(msg) { logMain(`autoUpdater ERROR: ${msg}`); }
  };
  try {
    autoUpdater.checkForUpdatesAndNotify();
  } catch (e) {
    logMain(`autoUpdater failed to check: ${e.message}`);
  }

  // Start Python backend (handles astrology tools)
  try {
    await startBackend();
    logMain('Backend started');
  } catch (err) {
    logMain(`Backend start failed: ${err.message}`);
    // Non-fatal: backend provides tools, but basic chat still works
  }

  // Check if LLM is already configured
  if (llmEngine.isConfigured) {
    logMain('LLM already configured, initializing...');
    createMainWindow();
    const ok = await llmEngine.initialize();
    if (!ok) {
      logMain('LLM init failed, user can reconfigure in settings');
    }
  } else {
    // First launch: show setup screen
    logMain('First launch — showing setup');
    createSetupWindow();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      if (llmEngine.isConfigured) {
        createMainWindow();
      } else {
        createSetupWindow();
      }
    }
  });

  // Log management IPC
  ipcMain.on('open-logs', () => {
    const logPath = getMainLogPath();
    if (fs.existsSync(logPath)) {
      shell.showItemInFolder(logPath);
    } else {
      shell.openPath(app.getPath('userData'));
    }
  });

  ipcMain.handle('get-log-content', async () => {
    try {
      const logPath = getMainLogPath();
      return fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8') : 'No log file.';
    } catch (err) {
      return `Error: ${err.message}`;
    }
  });
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') {
    logMain('All windows closed, quitting');
    app.quit();
  }
});

app.on('before-quit', async () => {
  stopBackend();
  await llmEngine.dispose();
});

process.on('uncaughtException', (err) => {
  logMain(`uncaughtException: ${err?.stack || String(err)}`);
});

process.on('unhandledRejection', (reason) => {
  logMain(`unhandledRejection: ${reason?.stack || String(reason)}`);
});
