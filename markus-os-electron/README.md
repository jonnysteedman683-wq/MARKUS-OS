# MARKUS OS - Electron Desktop Wrapper

## Overview
Standalone desktop application that bundles the MARKUS OS command deck UI (`markus-os.html`) with its local Python telemetry server (`markus_server.py`). The app auto-spawns the Python backend on launch and cleans it up on exit.

## Structure
```
markus-os-electron/
├── electron-main.js          # Main Electron bootstrap (spawns Python server)
├── electron-preload.js       # Context-safe IPC bridge
├── markus-os.html            # Holographic command deck UI
├── markus_server.py          # Python telemetry/streaming server (port 8128)
└── package.json              # Electron wrapper manifest
```

## Usage

### Development Mode
```bash
cd markus-os-electron
npm install
npm start
```

### Packaged Build (Windows/nsis)
```bash
cd markus-os-electron
npm install
npm run dist
```

### Prerequisites
Python path and `markus_server.py` must be present in the bundled directory.
