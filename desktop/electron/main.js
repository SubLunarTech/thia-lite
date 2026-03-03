const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess = null;

const API_PORT = 8765;
const API_BASE = `http://localhost:${API_PORT}`;

if (process.platform === 'win32') {
  // Avoid common startup crashes caused by unstable GPU drivers on Windows.
  app.disableHardwareAcceleration();
}

function getMainLogPath() {
  try {
    return path.join(app.getPath('userData'), 'main.log');
  } catch {
    return path.join(process.cwd(), 'thia-main.log');
  }
}

function logMain(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  try {
    fs.appendFileSync(getMainLogPath(), line, 'utf8');
  } catch {
    // Best effort logging only.
  }
}

// ─── Python Backend Management ───────────────────────────────────────────────

function findBackendBinary() {
  const isWin = process.platform === 'win32';
  const binName = isWin ? 'thia-lite.exe' : 'thia-lite';

  // 1. Packaged location (production)
  // electron-builder puts extraResources in process.resourcesPath
  const packagedPath = path.join(process.resourcesPath, 'bin', binName);
  logMain(`Looking for packaged backend at: ${packagedPath}`);
  if (fs.existsSync(packagedPath)) {
    logMain(`Found bundled backend at: ${packagedPath}`);
    return packagedPath;
  }

  // 2. Local dev dist folder (if running from source)
  const devPath = path.resolve(__dirname, '..', '..', 'dist', binName);
  logMain(`Looking for dev backend at: ${devPath}`);
  if (fs.existsSync(devPath)) {
    logMain(`Found local built backend at: ${devPath}`);
    return devPath;
  }

  return null;
}

function findPython() {
  const candidates = [];
  const projectRoot = path.resolve(__dirname, '..', '..');
  const venvPy = process.platform === 'win32'
    ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(projectRoot, '.venv', 'bin', 'python3');
  candidates.push(venvPy);

  if (process.platform === 'win32') {
    candidates.push('py', 'python3', 'python');
  } else {
    candidates.push('python3', 'python');
  }

  return candidates[0]; // fallback
}

function startBackend() {
  return new Promise((resolve, reject) => {
    const backendPath = findBackendBinary();

    if (backendPath) {
      logMain(`Starting bundled backend: ${backendPath} desktop`);
      // Make it executable on UNIX if needed
      if (process.platform !== 'win32') {
        try { fs.chmodSync(backendPath, '755'); } catch (e) { logMain(`Chmod warning: ${e.message}`); }
      }

      backendProcess = spawn(backendPath, ['desktop'], {
        cwd: path.dirname(backendPath),
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } else {
      const pythonPath = findPython();
      logMain(`Falling back to Python API server with: ${pythonPath}`);
      backendProcess = spawn(pythonPath, ['-m', 'thia_lite.api_server'], {
        cwd: path.resolve(__dirname, '..', '..'),
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    }

    let started = false;
    const timeout = setTimeout(() => {
      if (!started) {
        started = true;
        logMain('Backend start timeout — proceeding anyway');
        resolve(); // proceed, might just be slow
      }
    }, 15000);

    backendProcess.stdout.on('data', (data) => {
      const msg = data.toString();
      logMain(`[backend] ${msg.trim()}`);
      if (!started && msg.includes('ready')) {
        started = true;
        clearTimeout(timeout);
        logMain('Backend API server ready');
        resolve();
      }
    });

    backendProcess.stderr.on('data', (data) => {
      logMain(`[backend-err] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
      logMain(`Backend spawn error: ${err.message}`);
      if (!started) {
        started = true;
        clearTimeout(timeout);
        reject(err);
      }
    });

    backendProcess.on('exit', (code, signal) => {
      logMain(`Backend exited code=${code} signal=${signal}`);
      backendProcess = null;
      if (!started) {
        started = true;
        clearTimeout(timeout);
        reject(new Error(`Backend exited with code ${code}`));
      }
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

// ─── Window ──────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    icon: path.join(__dirname, 'icons/icon.png'),
    title: 'Thia-Lite — AI Astrology Assistant'
  });

  // Load renderer from packaged location first, with dev fallback.
  const packagedIndex = path.join(__dirname, 'src', 'index.html');
  const devIndex = path.join(__dirname, '..', 'src', 'index.html');
  const indexPath = fs.existsSync(packagedIndex) ? packagedIndex : devIndex;
  logMain(`Loading renderer from: ${indexPath}`);
  mainWindow.loadFile(indexPath);

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    logMain(`did-fail-load code=${errorCode} error=${errorDescription} url=${validatedURL}`);
    dialog.showErrorBox(
      'Thia Desktop Failed to Load',
      `Could not load UI.\nCode: ${errorCode}\nError: ${errorDescription}\nURL: ${validatedURL}`
    );
  });

  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    logMain(`render-process-gone reason=${details.reason} exitCode=${details.exitCode}`);
    dialog.showErrorBox(
      'Thia Desktop Renderer Crashed',
      `Renderer exited unexpectedly.\nReason: ${details.reason}\nExit code: ${details.exitCode}\n\nLog: ${getMainLogPath()}`
    );
  });

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ─── App Lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  logMain('App ready');

  // Start the Python API backend before creating the window
  try {
    await startBackend();
    logMain('Backend started successfully');
  } catch (err) {
    logMain(`Backend start failed: ${err.message}`);
    dialog.showErrorBox(
      'Thia Backend Failed to Start',
      `Could not start the Python API server.\n\n${err.message}\n\nMake sure Python 3.9+ and thia-lite are installed:\n  pip install -e .\n\nLog: ${getMainLogPath()}`
    );
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
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

app.on('before-quit', () => {
  stopBackend();
});

app.on('child-process-gone', (_event, details) => {
  logMain(`child-process-gone type=${details.type} reason=${details.reason} exitCode=${details.exitCode}`);
});

process.on('uncaughtException', (err) => {
  logMain(`uncaughtException: ${err && err.stack ? err.stack : String(err)}`);
});

process.on('unhandledRejection', (reason) => {
  logMain(`unhandledRejection: ${reason && reason.stack ? reason.stack : String(reason)}`);
});
