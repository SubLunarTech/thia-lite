const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

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

app.whenReady().then(() => {
  logMain('App ready');
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    logMain('All windows closed, quitting');
    app.quit();
  }
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
