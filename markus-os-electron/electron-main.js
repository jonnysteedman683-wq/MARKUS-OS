const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonServerProcess = null;

const SERVER_URL = 'http://127.0.0.1:8128';
const SERVER_SCRIPT = path.join(__dirname, '..', 'markus_server.py');

function startPythonServer() {
  console.log('[Electron Main] Spawning MARKUS OS Python Server:', SERVER_SCRIPT);
  pythonServerProcess = spawn('python', [SERVER_SCRIPT], {
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit'
  });

  pythonServerProcess.on('error', (err) => {
    console.error('[Electron Main] Failed to spawn Python server:', err);
  });

  pythonServerProcess.on('exit', (code, signal) => {
    console.log(`[Electron Main] Python server process exited with code ${code}, signal ${signal}`);
  });
}

function stopPythonServer() {
  if (pythonServerProcess) {
    console.log('[Electron Main] Terminating Python Server process...');
    pythonServerProcess.kill('SIGTERM');
    pythonServerProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    title: 'MARKUS OS — Autonomous Command Deck & UI OS',
    backgroundColor: '#030712',
    frame: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'electron-preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
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
        mainWindow.loadFile(path.join(__dirname, '..', 'markus_ui_os.html'));
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
