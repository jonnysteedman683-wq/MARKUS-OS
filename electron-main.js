const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

let mainWindow = null;
let pyProc = null;

const SERVER_URL = 'http://127.0.0.1:8128';
const SERVER_SCRIPT = path.join(__dirname, 'markus_server.py');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    title: 'MARKUS OS — Autonomous Agent Command Deck',
    backgroundColor: '#030712',
    frame: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'electron-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  mainWindow.setMenuBarVisibility(false);

  // Poll server availability before loading
  let attempts = 0;
  const loadApp = () => {
    mainWindow.loadURL(SERVER_URL).catch(() => {
      attempts++;
      if (attempts < 10) {
        setTimeout(loadApp, 500);
      } else {
        console.warn('[Electron Main] Backend timeout. Fallback to local HTML.');
        mainWindow.loadFile(path.join(__dirname, 'markus-os.html'));
      }
    });
  };

  setTimeout(loadApp, 800);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startPythonServer() {
  console.log('[Electron Main] Spawning MARKUS OS Python Server:', SERVER_SCRIPT);
  pyProc = spawn('python', [SERVER_SCRIPT], {
    cwd: __dirname,
    stdio: 'inherit'
  });

  pyProc.on('error', (err) => {
    console.error('[Electron Main] Failed to spawn Python server:', err);
  });

  pyProc.on('exit', (code, signal) => {
    console.log(`[Electron Main] Python server process exited with code ${code}, signal ${signal}`);
  });
}

function stopPythonServer() {
  if (pyProc) {
    console.log('[Electron Main] Terminating Python Server process...');
    pyProc.kill('SIGTERM');
    pyProc = null;
  }
}

app.whenReady().then(() => {
  startPythonServer();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopPythonServer();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonServer();
});

// IPC handlers for window control
ipcMain.handle('system:minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.handle('system:maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('system:close', () => {
  if (mainWindow) mainWindow.close();
});
