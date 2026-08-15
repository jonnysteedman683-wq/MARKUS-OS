const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let pyProc = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: '#030712',
    webPreferences: {
      preload: path.join(__dirname, 'electron-preload.js'),
      contextIsolation: false,
      nodeIntegration: false
    }
  });

  win.loadFile('markus-os.html');
}

function startPythonServer() {
  const pyPath = path.join(__dirname, 'markus_server.py');
  pyProc = spawn('python', [pyPath], {
    cwd: __dirname
  });

  pyProc.stdout?.on('data', (data) => {
    console.log(`[MARKUS-SERVER] ${data}`);
  });

  pyProc.stderr?.on('data', (data) => {
    console.error(`[MARKUS-SERVER-ERR] ${data}`);
  });

  pyProc.on('close', (code) => {
    console.log(`[MARKUS-SERVER] Exited with code ${code}`);
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

app.on('before-quit', () => {
  if (pyProc) {
    pyProc.kill();
  }
});
