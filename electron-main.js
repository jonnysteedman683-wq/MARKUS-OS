const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

let pyProc = null;

// Narrow IPC: surface MARKUS server health to the renderer through the
// secure preload bridge (never raw ipcRenderer — contextIsolation: true).
ipcMain.handle('markus:health', () => new Promise((resolve) => {
  const req = http.get({ host: '127.0.0.1', port: 8128, path: '/api/health', timeout: 2500 }, (res) => {
    let body = '';
    res.on('data', (c) => { body += c; });
    res.on('end', () => {
      let json = null;
      try { json = JSON.parse(body); } catch (_) { /* keep null */ }
      resolve({ status: res.statusCode, ok: res.statusCode === 200, body: body.slice(0, 512), json });
    });
  });
  req.on('error', (err) => resolve({ status: 0, ok: false, error: err.message, body: '' }));
  req.on('timeout', () => { req.destroy(); resolve({ status: 0, ok: false, error: 'timeout' }); });
}));

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    backgroundColor: '#030712',
    webPreferences: {
      preload: path.join(__dirname, 'electron-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
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
