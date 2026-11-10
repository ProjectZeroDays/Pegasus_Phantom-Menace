/**
 * Pegasus Phantom Menace - Electron main process.
 *
 * Boots the Flask backend as a child process, opens the renderer window
 * pointed at it, and installs Windows auto-start via the Run registry key
 * (or a scheduled task when elevation is unavailable).
 */
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const DEV = process.argv.includes('--dev');
const BACKEND_PORT = process.env.PEGASUS_PORT || '5001';
const BACKEND_HOST = process.env.PEGASUS_HOST || '127.0.0.1';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

let mainWindow = null;
let backendProc = null;
let startupRegistered = false;

// ---------------------------------------------------------------------------
// Backend management
// ---------------------------------------------------------------------------
function findPython() {
  const candidates = [
    process.env.PEGASUS_PYTHON,
    'python',
    'python3',
    path.join(app.getAppPath(), 'pegasus', 'venv', 'Scripts', 'python.exe'),
    path.join(app.getAppPath(), 'pegasus', 'venv', 'bin', 'python'),
  ].filter(Boolean);
  for (const c of candidates) {
    try {
      const r = spawnSync(c, ['--version']);
      if (r.status === 0) return c;
    } catch (_) { /* keep looking */ }
  }
  return 'python';
}

function spawnSync(cmd, args) {
  const { spawnSync: ss } = require('child_process');
  return ss(cmd, args, { stdio: 'ignore' });
}

function backendEntry() {
  // Prefer start_server.py (honours PEGASUS_PORT/HOST), fall back to run_server.py
  const root = path.join(app.getAppPath(), '..');
  const startServer = path.join(root, 'start_server.py');
  const runServer = path.join(root, 'run_server.py');
  if (fs.existsSync(startServer)) return startServer;
  if (fs.existsSync(runServer)) return runServer;
  return null;
}

function startBackend() {
  if (backendProc) return;
  const entry = backendEntry();
  if (!entry) {
    dialog.showErrorBox('Backend not found',
      'Could not locate start_server.py or run_server.py next to the Electron app.');
    return;
  }
  const python = findPython();
  const env = Object.assign({}, process.env, {
    PEGASUS_HOST: BACKEND_HOST,
    PEGASUS_PORT: BACKEND_PORT,
    PYTHONUNBUFFERED: '1',
  });
  backendProc = spawn(python, [entry], {
    cwd: path.dirname(entry),
    env,
    detached: false,
    windowsHide: true,
  });
  backendProc.stdout.on('data', (d) => process.stdout.write(`[backend] ${d}`));
  backendProc.stderr.on('data', (d) => process.stderr.write(`[backend:err] ${d}`));
  backendProc.on('exit', (code) => {
    backendProc = null;
    if (code !== 0 && code !== null) {
      dialog.showErrorBox('Backend stopped', `The Pegasus backend exited with code ${code}.`);
    }
  });
}

function stopBackend() {
  if (backendProc) {
    try { backendProc.kill(); } catch (_) {}
    backendProc = null;
  }
}

// ---------------------------------------------------------------------------
// Window management
// ---------------------------------------------------------------------------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'Pegasus Phantom Menace',
    icon: path.join(__dirname, 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (DEV) mainWindow.webContents.openDevTools();
  });

  mainWindow.loadURL(BACKEND_URL);

  // Retry the backend URL if it is not up yet.
  let retries = 0;
  const retry = setInterval(() => {
    if (retries++ > 30 || !mainWindow) { clearInterval(retry); return; }
    mainWindow.loadURL(BACKEND_URL);
  }, 1000);
  mainWindow.webContents.on('did-finish-load', () => clearInterval(retry));

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ---------------------------------------------------------------------------
// Windows auto-start (Run registry key, fallback scheduled task)
// ---------------------------------------------------------------------------
function registerAutoStart() {
  if (process.platform !== 'win32' || startupRegistered) return;
  try {
    const reg = require('winreg');
    const key = new reg({
      hive: reg.HKCU,
      key: '\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',
    });
    const exe = app.getPath('exe');
    key.set('PegasusPhantomMenace', reg.REG_SZ, `"${exe}"`, (err) => {
      if (!err) startupRegistered = true;
      else scheduleTaskFallback(exe);
    });
  } catch (_) {
    scheduleTaskFallback(app.getPath('exe'));
  }
}

function scheduleTaskFallback(exe) {
  const { exec } = require('child_process');
  const name = 'PegasusPhantomMenace';
  const cmd = `schtasks /create /tn "${name}" /tr "\\"${exe}\\"" /sc onlogon /f`;
  exec(cmd, (err) => { if (!err) startupRegistered = true; });
}

function unregisterAutoStart() {
  if (process.platform !== 'win32') return;
  try {
    const reg = require('winreg');
    const key = new reg({
      hive: reg.HKCU,
      key: '\\Software\\Microsoft\\Windows\\CurrentVersion\\Run',
    });
    key.remove('PegasusPhantomMenace', () => {});
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// IPC handlers
// ---------------------------------------------------------------------------
function registerIpc() {
  ipcMain.handle('backend:url', () => BACKEND_URL);
  ipcMain.handle('backend:start', () => { startBackend(); return true; });
  ipcMain.handle('backend:stop', () => { stopBackend(); return true; });
  ipcMain.handle('autostart:get', () => startupRegistered);
  ipcMain.handle('autostart:set', (_evt, enable) => {
    if (enable) { registerAutoStart(); }
    else { unregisterAutoStart(); startupRegistered = false; }
    return startupRegistered;
  });
  ipcMain.handle('app:version', () => app.getVersion());
  ipcMain.handle('shell:open-external', (_evt, url) => shell.openExternal(url));
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(() => {
  registerIpc();
  startBackend();
  createWindow();
  registerAutoStart();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  stopBackend();
});
