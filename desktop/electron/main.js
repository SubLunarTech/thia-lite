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

app.setName('Thia');

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

const getOllamaPath = () => {
  const platform = process.platform;
  if (platform === 'win32') {
    // Check multiple common Windows locations
    const paths = [
      path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama.exe'),
      path.join(process.env.PROGRAMFILES || '', 'Ollama', 'ollama.exe'),
      path.join(process.env['PROGRAMFILES(X86)'] || '', 'Ollama', 'ollama.exe'),
      path.join(process.env.LOCALAPPDATA || '', 'Ollama', 'ollama.exe'),
      path.join(process.env.USERPROFILE || '', 'AppData', 'Local', 'Programs', 'Ollama', 'ollama.exe'),
    ];

    // Check filesystem paths first
    for (const p of paths) {
      if (fs.existsSync(p)) {
        logMain(`Found Ollama at: ${p}`);
        return p;
      }
    }

    // Try using where.exe to find ollama in PATH
    try {
      const { execSync } = require('child_process');
      const result = execSync('where ollama.exe', { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }).trim();
      if (result) {
        const foundPath = result.split('\n')[0].trim();
        logMain(`Found Ollama via PATH: ${foundPath}`);
        return foundPath;
      }
    } catch (e) {
      logMain(`Ollama not found in PATH: ${e.message}`);
    }

    logMain('Ollama executable not found on system');
    return null;
  }
  if (platform === 'darwin') {
    return '/Applications/Ollama.app/Contents/Resources/ollama';
  }
  return 'ollama';
};

async function ensureOllama() {
  return new Promise((resolve) => {
    const platform = process.platform;

    // Safety Timeout: Don't let the app hang forever if Ollama check is stuck
    const safetyTimeout = setTimeout(() => {
      logMain('Ollama check timed out - force proceeding to main window');
      resolve();
    }, 45000);

    const done = () => {
      clearTimeout(safetyTimeout);
      resolve();
    };

    // 1. Check if Ollama is already running on port 11434
    logMain('Checking if Ollama is running on port 11434...');
    const req = require('http').get('http://localhost:11434/api/tags', (res) => {
      logMain(`Ollama HTTP check response: ${res.statusCode}`);
      if (res.statusCode === 200) {
        logMain('Ollama is already running. Proceeding.');
        done();
      } else {
        logMain(`Ollama responded with ${res.statusCode}, checking disk...`);
        checkDisk();
      }
    }).on('error', (err) => {
      logMain(`Ollama HTTP check error: ${err.message}, checking disk...`);
      checkDisk();
    });

    req.setTimeout(2000, () => {
      logMain('Ollama HTTP check timeout, checking disk...');
      req.abort();
      checkDisk();
    });

    function checkDisk() {
      const ollamaExe = getOllamaPath();

      if (ollamaExe && fs.existsSync(ollamaExe)) {
        logMain(`Ollama found at ${ollamaExe} but not running. Attempting start...`);
        if (platform === 'win32') {
          exec(`start "" "${ollamaExe}"`, (err) => {
            if (err) logMain(`Failed to start Ollama: ${err.message}`);
            else logMain('Ollama start command executed');
          });
        } else if (platform === 'linux') {
          exec('ollama serve &', (err) => {
            if (err) logMain(`Failed to start Ollama: ${err.message}`);
            else logMain('Ollama start command executed');
          });
        }
        waitForOllamaAndPull(true);
      } else {
        logMain('Ollama not found on disk, starting install flow');
        startInstallFlow();
      }
    }

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

      const { ipcMain } = require('electron');

      // ── Hoisted helpers (visible from checkDisk AND handleInstallChoice) ──

      function waitForOllamaAndPull(isSilent = false) {
        let attempts = 0;
        const maxAttempts = 60; // 60 seconds

        const check = setInterval(() => {
          attempts++;
          if (!isSilent) {
            updateUI(`Starting AI Service (Attempt ${attempts}/${maxAttempts})...`, 100, true);
          }

          const checkReq = require('http').get({
            hostname: 'localhost',
            port: 11434,
            path: '/api/tags',
            timeout: 1500
          }, (res) => {
            if (res.statusCode === 200) {
              clearInterval(check);
              pullModel();
            }
          });

          checkReq.on('timeout', () => {
            checkReq.destroy();
          });

          checkReq.on('error', () => {
            // If it's been 15 seconds and still nothing, try to manually poke it
            if (attempts === 15) {
              logMain('Ollama daemon slow to start. Attempting manual start...');
              const ollamaExe = getOllamaPath();
              if (platform === 'win32') {
                exec(`start "" "${ollamaExe}"`);
              } else if (platform === 'linux') {
                exec('ollama serve &');
              }
            }

            if (attempts >= maxAttempts) {
              clearInterval(check);
              logMain('Ollama daemon start timed out.');
              updateUI('Service Time-out. Please restart Thia or start Ollama manually.', 100);
              setTimeout(resolve, 5000);
            }
          });
          checkReq.end();
        }, 1000);
      }

      function pullModel() {
        const ollamaPath = getOllamaPath();
        updateUI('Downloading AI Knowledge Model (qwen3.5:4b)...', 0, true);
        logMain(`Pulling qwen3.5:4b using: ${ollamaPath}`);

        setTimeout(() => {
          const pullProcess = spawn(ollamaPath, ['pull', 'qwen3.5:4b'], {
            env: { ...process.env }
          });

          let lastPercent = 0;
          pullProcess.stdout.on('data', (data) => {
            const out = data.toString();
            const match = out.match(/(\d{1,3})%/);
            if (match) {
              lastPercent = parseInt(match[1], 10);
              updateUI(`Downloading Model (${lastPercent}%)`, lastPercent);
            } else if (out.includes('pulling')) {
              updateUI('Initializing Model Pull...', lastPercent);
            }
          });

          pullProcess.on('close', (code) => {
            logMain(`Model pull exited with code ${code}`);
            updateUI('Setup Complete!', 100);
            setTimeout(() => {
              ipcMain.removeListener('install-choice', handleInstallChoice);
              if (installWindow && !installWindow.isDestroyed()) installWindow.close();
              done();
            }, 1500);
          });

          pullProcess.on('error', (err) => {
            logMain(`Pull spawn error: ${err.message}`);
            // Fallback to global command
            if (ollamaPath !== 'ollama') {
              logMain('Retrying with global ollama...');
              const retryProcess = spawn('ollama', ['pull', 'qwen3.5:4b']);
              retryProcess.on('close', done);
              retryProcess.on('error', done);
            } else {
              done();
            }
          });
        }, 2000);
      }

      // ── Install choice handler ──

      const handleInstallChoice = (_event, choice) => {
        if (choice === 'cloud') {
          logMain('User selected Cloud API. Skipping Ollama installation.');
          ipcMain.removeListener('install-choice', handleInstallChoice);
          if (installWindow && !installWindow.isDestroyed()) installWindow.close();
          done();
          return;
        }

        // Choice was 'local', proceed with install
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

        const downloadFile = (url, dest, onProgress, onDone, onError) => {
          const file = fs.createWriteStream(dest);
          let downloadedBytes = 0;
          let totalBytes = 0;

          const request = https.get(url, (response) => {
            // Handle Redirects (e.g. 307)
            if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
              file.close();
              fs.unlink(dest, () => {
                logMain(`Following redirect to: ${response.headers.location}`);
                downloadFile(response.headers.location, dest, onProgress, onDone, onError);
              });
              return;
            }

            if (response.statusCode !== 200) {
              onError(new Error(`Download failed: ${response.statusCode}`));
              return;
            }

            totalBytes = parseInt(response.headers['content-length'], 10);

            response.on('data', (chunk) => {
              downloadedBytes += chunk.length;
              if (totalBytes > 0) {
                const percent = Math.min(100, Math.round((downloadedBytes / totalBytes) * 100));
                onProgress(`Downloading (${Math.round(downloadedBytes / 1024 / 1024)}MB / ${Math.round(totalBytes / 1024 / 1024)}MB)`, percent);
              } else {
                onProgress(`Downloading... (${Math.round(downloadedBytes / 1024 / 1024)}MB)`, 0);
              }
            });

            response.pipe(file);

            file.on('finish', () => {
              file.close();
              onDone();
            });
          });

          request.on('error', (err) => {
            file.close();
            fs.unlink(dest, () => { });
            onError(err);
          });
        };

        logMain(`Starting Ollama auto-install. URL: ${downloadUrl}`);
        updateUI('Initializing Download...', 0, true);

        downloadFile(downloadUrl, installerPath, (status, percent) => {
          updateUI(status, percent);
        }, () => {
          logMain(`Download complete. Preparing to execute: ${installCmd}`);
          updateUI('Preparing Installation...', 100, true);

          const runInstallProcess = () => {
            updateUI('Installing AI Engine (Waiting for OS)...', 100, true);

            if (platform === 'darwin') {
              updateUI('Extracting AI Engine...', 100, true);
              decompress(installerPath, '/Applications').then(() => {
                logMain('Mac Zip Extracted to /Applications');
                exec('open -a Ollama', (err) => {
                  if (err) logMain(`Mac Open Error: ${err}`);
                  waitForOllamaAndPull();
                });
              }).catch(err => reject(err));
            } else {
              // On Windows/Linux, the installer might be a long-running process
              const installProcess = exec(installCmd);

              installProcess.on('exit', (code) => {
                logMain(`Installer exited with code ${code}`);
                waitForOllamaAndPull();
              });

              // Also listen for errors
              installProcess.on('error', (err) => {
                logMain(`Installer spawn error: ${err.message}`);
                // Proceed anyway, maybe it partially worked
                waitForOllamaAndPull();
              });
            }
          };

          runInstallProcess();
        }, (err) => {
          logMain(`Download error: ${err.message}`);
          updateUI(`Download Failed: ${err.message}`, 0);
          setTimeout(() => reject(err), 3000);
        });
      };

      ipcMain.on('install-choice', handleInstallChoice);
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

  const { ipcMain, shell } = require('electron');

  // Handle log opening
  ipcMain.on('open-logs', () => {
    const logPath = getMainLogPath();
    logMain(`User requested to open log at: ${logPath}`);
    if (fs.existsSync(logPath)) {
      shell.showItemInFolder(logPath);
    } else {
      shell.openPath(app.getPath('userData'));
    }
  });

  // Handle log content retrieval for UI dump
  ipcMain.handle('get-log-content', async () => {
    try {
      const logPath = getMainLogPath();
      if (fs.existsSync(logPath)) {
        return fs.readFileSync(logPath, 'utf8');
      }
      return 'No log file found.';
    } catch (err) {
      return `Error reading log: ${err.message}`;
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
