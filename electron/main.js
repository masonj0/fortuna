// electron/main.js
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, ipcMain } = require('electron');
const { spawn, execFile } = require('child_process');
const path = require('path');
const fs = require('fs');
const { validateInstallation } = require('./install-validator');

/**
 * Executes a Python script to securely retrieve the API key from the Windows Credential Manager.
 * @returns {Promise<string>} A promise that resolves with the API key.
 * @throws {Error} If the Python script fails or the key cannot be retrieved.
 */
async function getApiKeyFromCredentials() {
  return new Promise((resolve, reject) => {
    const isDev = process.env.NODE_ENV === 'development';

    // Determine the correct paths for the Python executable and the script
    const pythonExecutable = isDev
      ? path.join(process.cwd(), '.venv', 'Scripts', 'python.exe')
      : path.join(process.resourcesPath, 'app', 'python', 'python.exe');

    const scriptPath = isDev
      ? path.join(process.cwd(), 'scripts', 'get_api_key.py')
      : path.join(process.resourcesPath, 'app', 'scripts', 'get_api_key.py');

    if (!fs.existsSync(pythonExecutable)) {
      return reject(new Error(`Python executable not found at: ${pythonExecutable}`));
    }
    if (!fs.existsSync(scriptPath)) {
      return reject(new Error(`API key script not found at: ${scriptPath}`));
    }

    execFile(pythonExecutable, [scriptPath], (error, stdout, stderr) => {
      if (error) {
        console.error('Error executing get_api_key.py:', stderr);
        return reject(new Error(`Failed to retrieve API key. Details: ${stderr}`));
      }
      // The key is printed to stdout by the script.
      resolve(stdout.trim());
    });
  });
}


class FortunaDesktopApp {
  constructor() {
    this.mainWindow = null;
    this.tray = null;
    this.backendProcess = null;

    if (!app.requestSingleInstanceLock()) {
      app.quit();
    } else {
      app.on('second-instance', () => {
        if (this.mainWindow) {
          if (this.mainWindow.isMinimized()) this.mainWindow.restore();
          this.mainWindow.focus();
        }
      });
    }
  }

  createMainWindow() {
    this.mainWindow = new BrowserWindow({
      width: 1600,
      height: 1000,
      title: 'Fortuna Faucet - Racing Analysis',
      icon: path.join(__dirname, 'assets', 'icon.ico'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      },
      autoHideMenuBar: true,
      backgroundColor: '#1a1a2e',
      show: false
    });

    this.mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault();
        this.mainWindow.hide();
      }
    });

    const isDev = process.env.NODE_ENV === 'development';
    if (isDev) {
      this.mainWindow.loadURL('http://localhost:3000');
    } else {
      this.mainWindow.loadFile(path.join(__dirname, '..', 'web_platform', 'frontend', 'out', 'index.html'));
    }

    this.mainWindow.once('ready-to-show', () => {
      this.mainWindow.show();
    });
  }

  createSystemTray() {
    const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
    const icon = nativeImage.createFromPath(iconPath);
    this.tray = new Tray(icon.resize({ width: 16, height: 16 }));

    const contextMenu = Menu.buildFromTemplate([
      { label: 'Show Dashboard', click: () => this.showWindow() },
      { type: 'separator' },
      { label: 'Quit Fortuna Faucet', click: () => this.quitApp() }
    ]);

    this.tray.setToolTip('Fortuna Faucet - Monitoring Races');
    this.tray.setContextMenu(contextMenu);
    this.tray.on('double-click', () => this.showWindow());
  }

  showWindow() {
    if (this.mainWindow) {
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  quitApp() {
    app.isQuitting = true;
    app.quit();
  }

  async startBackend() {
    const isDev = process.env.NODE_ENV !== 'production';
    const rootPath = isDev ? path.join(__dirname, '..') : process.resourcesPath;

    // CRITICAL: These paths MUST exist
    const pythonPath = isDev
      ? path.join(rootPath, '.venv', 'Scripts', 'python.exe')
      : path.join(rootPath, 'python', 'python.exe');

    const apiPath = path.join(rootPath, 'python_service', 'api.py');
    const diagnosticsPath = path.join(app.getPath('userData'), 'backend_diagnostics.log');

    console.log('🔍 BACKEND STARTUP DIAGNOSTICS');
    console.log(`Root path: ${rootPath}`);
    console.log(`Python path: ${pythonPath}`);
    console.log(`Python exists: ${fs.existsSync(pythonPath)}`);
    console.log(`API path: ${apiPath}`);
    console.log(`API exists: ${fs.existsSync(apiPath)}`);

    // VALIDATION: Fail LOUDLY if prerequisites are missing
    if (!fs.existsSync(pythonPath)) {
        const msg = `❌ FATAL: Python not found at ${pythonPath}`;
        console.error(msg);
        fs.writeFileSync(diagnosticsPath, `${new Date().toISOString()}: ${msg}\n`);
        throw new Error(msg);
    }

    if (!fs.existsSync(apiPath)) {
        const msg = `❌ FATAL: API module not found at ${apiPath}`;
        console.error(msg);
        fs.writeFileSync(diagnosticsPath, `${new Date().toISOString()}: ${msg}\n`);
        throw new Error(msg);
    }

    // Spawn with detailed error capture
    return new Promise((resolve, reject) => {
        const pythonProcess = spawn(pythonPath, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'], {
            cwd: path.join(rootPath, 'python_service'),
            stdio: 'pipe'
        });

        this.backendProcess = pythonProcess;

        let stdoutData = '';
        let stderrData = '';

        const logStream = fs.createWriteStream(diagnosticsPath, { flags: 'a' });
        logStream.write(`\n--- New Session: ${new Date().toISOString()} ---\n`);

        pythonProcess.stdout.on('data', (data) => {
            const msg = data.toString();
            stdoutData += msg;
            console.log(`[Python STDOUT] ${msg.trim()}`);
            logStream.write(`${new Date().toISOString()}: STDOUT: ${msg}`);

            if (msg.includes('Uvicorn running')) {
                clearTimeout(timeout);
                console.log('✅ Backend started successfully');
                resolve();
            }
        });

        pythonProcess.stderr.on('data', (data) => {
            const msg = data.toString();
            stderrData += msg;
            console.error(`[Python STDERR] ${msg.trim()}`);
            logStream.write(`${new Date().toISOString()}: STDERR: ${msg}`);
        });

        pythonProcess.on('error', (error) => {
            clearTimeout(timeout);
            const msg = `❌ Process error: ${error.message}`;
            console.error(msg);
            logStream.write(`${new Date().toISOString()}: ${msg}\n`);
            reject(error);
        });

        pythonProcess.on('exit', (code, signal) => {
            clearTimeout(timeout);
            if (code !== 0 && !app.isQuitting) {
                const msg = `❌ Python exited with code ${code}, signal ${signal}\n${stderrData}`;
                console.error(msg);
                logStream.write(`${new Date().toISOString()}: ${msg}\n`);
                reject(new Error(msg));
            }
        });

        const timeout = setTimeout(() => {
            pythonProcess.kill();
            const msg = `❌ Backend startup timeout (10s)`;
            console.error(msg);
            logStream.write(`${new Date().toISOString()}: ${msg}\n`);
            reject(new Error(msg));
        }, 10000);
    });
  }

  async initialize() {
    try {
        await validateInstallation();
        await this.startBackend();
        this.createMainWindow();
        this.createSystemTray();
    } catch (error) {
        dialog.showErrorBox(
            'Installation Error',
            `Fortuna Faucet failed to start: ${error.message}\n\nPlease see backend_diagnostics.log for details.`
        );
        app.quit();
    }
  }

  cleanup() {
    console.log('Cleaning up backend process...');
    if (this.backendProcess) {
      this.backendProcess.kill();
    }
  }
}

let fortunaApp;

app.whenReady().then(() => {
  // Register the IPC handler to retrieve the API key when requested by the frontend.
  ipcMain.handle('get-api-key', async () => {
    try {
      console.log('IPC handler "get-api-key" invoked.');
      const apiKey = await getApiKeyFromCredentials();
      console.log('Successfully retrieved API key.');
      return apiKey;
    } catch (error) {
      console.error('Failed to get API key via IPC handler:', error);
      // Return null or an empty string to the renderer process in case of an error.
      // The frontend should handle this gracefully.
      return null;
    }
  });

  fortunaApp = new FortunaDesktopApp();
  fortunaApp.initialize();
});

app.on('window-all-closed', (event) => {
  // Prevent app from quitting when all windows are closed.
  // The app will continue to run in the system tray.
  event.preventDefault();
});

app.on('before-quit', () => {
  if (fortunaApp) {
    fortunaApp.cleanup();
  }
});
