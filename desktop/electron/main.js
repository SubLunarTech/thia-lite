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

const https = require('https');
const { exec } = require('child_process');
const decompress = require('decompress');

async function ensureOllama() {
  return new Promise((resolve, reject) => {
    // 1. Check if Ollama is already running on port 11434
    const req = require('http').get('http://localhost:11434/api/tags', (res) => {
      if (res.statusCode === 200) {
        logMain('Ollama is already running. Proceeding.');
        resolve();
      } else {
        startInstallFlow();
      }
    }).on('error', () => {
      startInstallFlow();
    });

    req.setTimeout(2000, () => { req.abort(); startInstallFlow(); });

    function startInstallFlow() {
      // Create installer window instead of main window
      let installWindow = new BrowserWindow({
        width: 600, height: 400,
        frame: false, resizable: false, show: false,
        webPreferences: {
          preload: path.join(__dirname, 'preload.js'),
          nodeIntegration: false,
          contextIsolation: true
        }
      });
      installWindow.loadFile(path.join(__dirname, 'src', 'installer.html'));
      installWindow.once('ready-to-show', () => installWindow.show());

      const updateUI = (status, percent, indeterminate = false) => {
        if (installWindow && !installWindow.isDestroyed()) {
          installWindow.webContents.send('install-progress', { status, percent, indeterminate });
        }
      };

      const platform = process.platform;
      const downloadsDir = app.getPath('downloads');
      let downloadUrl, installerPath, installCmd;

      if (platform === 'win32') {
        downloadUrl = 'https://ollama.com/download/OllamaSetup.exe';
        installerPath = path.join(downloadsDir, 'OllamaSetup.exe');
        installCmd = `"${installerPath}" \/SILENT \/ALLUSERS`; // Silent install
      } else if (platform === 'darwin') {
        downloadUrl = 'https://ollama.com/download/Ollama-darwin.zip';
        installerPath = path.join(downloadsDir, 'Ollama-darwin.zip');
        installCmd = `unzip -o "${installerPath}" -d /Applications && open /Applications/Ollama.app`;
      } else {
        downloadUrl = 'https://ollama.com/install.sh';
        installerPath = path.join(downloadsDir, 'ollama-install.sh');
        installCmd = `sh "${installerPath}"`;
      }

      logMain(`Starting Ollama auto-install. URL: ${downloadUrl}`);
      updateUI('Downloading Local AI Engine...', 0, true);

      const file = fs.createWriteStream(installerPath);
      https.get(downloadUrl, (response) => {
        if (response.statusCode !== 200) {
          logMain(`Download failed: ${response.statusCode}`);
          reject(new Error(`Download failed: ${response.statusCode}`));
          return;
        }

        const totalBytes = parseInt(response.headers['content-length'], 10);
        let downloadedBytes = 0;

        response.on('data', (chunk) => {
          downloadedBytes += chunk.length;
          if (totalBytes) {
            const percent = Math.min(100, Math.round((downloadedBytes / totalBytes) * 100));
            updateUI(`Downloading Installer (${Math.round(downloadedBytes / 1024 / 1024)}mb)`, percent);
          }
        });

        response.pipe(file);

        file.on('finish', () => {
          file.close();
          updateUI('Installing AI Engine (May prompt for password)...', 100, true);
          logMain(`Download complete. Executing: ${installCmd}`);

          // Need special handling for Mac Zip
          if (platform === 'darwin') {
            updateUI('Extracting AI Engine...', 100, true);
            decompress(installerPath, '/Applications').then(() => {
              logMain('Mac Zip Extracted to /Applications');
              exec('open -a Ollama', (err) => {
                if (err) logMain(`Mac Open Error: ${err}`);
                pullModel();
              });
            }).catch(err => reject(err));
          } else {
            exec(installCmd, (error, stdout, stderr) => {
              if (error) {
                logMain(`Install error: ${error.message}`);
                // Don't completely fail, sometimes silent installs exit badly but still work
              }
              logMain('Installer finished. Waiting for daemon to start.');
              pullModel();
            });
          }
        });
      }).on('error', (err) => {
        fs.unlink(installerPath, () => { });
        logMain(`Download error: ${err.message}`);
        reject(err);
      });

      function pullModel() {
        updateUI('Downloading AI Knowledge Model (qwen3.5:4b)...', 100, true);
        logMain('Pulling qwen3.5:4b model');

        // Wait 5 seconds for Ollama daemon to hook in
        setTimeout(() => {
          const pullProcess = spawn('ollama', ['pull', 'qwen3.5:4b'], {
            env: { ...process.env }
          });

          // Poor man's progress bar via stdout
          let lastPercent = 0;
          pullProcess.stdout.on('data', (data) => {
            const out = data.toString();
            // Ollama outputs something like: "pulling 3042456453... 45%"
            const match = out.match(/(\\d{1,3})%/);
            if (match) {
              lastPercent = parseInt(match[1], 10);
              updateUI(`Downloading Model (${lastPercent}%)`, lastPercent);
            } else {
              updateUI(out.substring(0, 40) + '...', lastPercent);
            }
          });

          pullProcess.on('close', (code) => {
            logMain(`Model pull exited with code ${code}`);
            updateUI('Setup Complete!', 100);
            setTimeout(() => {
              if (installWindow && !installWindow.isDestroyed()) installWindow.close();
              resolve();
            }, 1500);
          });

          pullProcess.on('error', (err) => {
            logMain(`Pull spawn error: ${err}`);
            // If pulling fails, just resolve and let chat UI handle error
            if (installWindow && !installWindow.isDestroyed()) installWindow.close();
            resolve();
          });
        }, 5000);
      }
    }
  });
}

app.whenReady().then(async () => {
  logMain('App ready');

  try {
    await ensureOllama();
  } catch (e) {
    logMain(`Ollama Auto-Install failed: ${e.message}`);
    // We continue anyway, so the user can see the error in the chat UI
  }

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
