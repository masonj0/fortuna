// electron/main.js
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, ipcMain } = require('electron');
const { spawn, execFile } = require('child_process');
const path = require('path');
const fs = require('fs');
const notifier = require('node-notifier');
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
      this.mainWindow.loadFile(path.join(app.getAppPath(), '..', 'app.asar.unpacked', 'web_platform', 'frontend', 'out', 'index.html'));
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
    return new Promise((resolve, reject) => {
      const isDev = process.env.NODE_ENV === 'development';
      const rootPath = isDev ? path.join(__dirname, '..') : process.resourcesPath;

      let executablePath;
      let spawnOptions;

      if (isDev) {
        executablePath = path.join(rootPath, '.venv', 'Scripts', 'python.exe');
        spawnOptions = {
          cwd: path.join(rootPath, 'python_service'),
          stdio: ['ignore', 'pipe', 'pipe'],
          detached: false,
          args: ['run_server.py']
        };
      } else {
        // In production, the executable is the server runner itself.
        executablePath = path.join(rootPath, 'api.exe');
        spawnOptions = {
          stdio: ['ignore', 'pipe', 'pipe'],
          detached: false,
          args: []
        };
      }

      if (!fs.existsSync(executablePath)) {
        const errorMsg = `Backend executable not found at: ${executablePath}`;
        console.error(`[ERROR] ${errorMsg}`);
        // Immediately reject if the file doesn't exist. No need for detailed logs.
        return reject(new Error(errorMsg));
      }

      this.backendProcess = spawn(executablePath, spawnOptions.args, spawnOptions);

      let stdoutBuffer = '';
      let stderrBuffer = '';
      let startupResolved = false;

      const rejectWithDetails = (baseError) => {
        if (!startupResolved) {
          startupResolved = true;
          const detailMessage = `
--- Backend Process Failed ---
Error: ${baseError.message}

--- STDOUT ---
${stdoutBuffer.trim() || '(No standard output)'}

--- STDERR ---
${stderrBuffer.trim() || '(No standard error output)'}
          `;
          reject(new Error(detailMessage));
        }
      };

      this.backendProcess.stdout.on('data', (data) => {
        const logMsg = data.toString();
        stdoutBuffer += logMsg;
        console.log(`[Backend] ${logMsg}`);
        if (!startupResolved) {
          if (stdoutBuffer.includes('Backend ready')) {
            console.log('[✓] Backend startup signal received.');
            startupResolved = true;
            // Add a small delay for safety, as recommended
            setTimeout(resolve, 1000);
          }
        }
      });

      this.backendProcess.stderr.on('data', (data) => {
        const errorMsg = data.toString();
        stderrBuffer += errorMsg;
        console.error(`[Backend STDERR] ${errorMsg}`);
        notifier.notify({
          title: 'Fortuna Faucet - Backend Error',
          message: `Error: ${errorMsg.trim()}`,
          icon: path.join(__dirname, 'assets', 'icon.ico')
        });
      });

      this.backendProcess.on('error', (error) => {
        console.error(`[Backend ERROR] Spawning process failed: ${error}`);
        notifier.notify({
          title: 'Fortuna Faucet - Backend Error',
          message: `Backend spawn failed: ${error.message}`,
          icon: path.join(__dirname, 'assets', 'icon.ico')
        });
        rejectWithDetails(error);
      });

      this.backendProcess.on('close', (code) => {
        console.log(`[Backend] Process exited with code ${code}`);
        if (!startupResolved) {
          notifier.notify({
            title: 'Fortuna Faucet - Backend Error',
            message: `Backend process exited prematurely with code ${code}.`,
            icon: path.join(__dirname, 'assets', 'icon.ico')
          });
          rejectWithDetails(new Error(`Process exited prematurely with code ${code}.`));
        }
      });

      // Safety timeout
      setTimeout(() => {
        if (!startupResolved) {
          rejectWithDetails(new Error('Startup timed out after 15 seconds.'));
        }
      }, 15000);
    });
  }


  initialize() {
    // --- Create and Show UI Immediately ---
    this.createMainWindow();
    this.createSystemTray();
    this.mainWindow.once('ready-to-show', () => {
      this.mainWindow.show();
      this.mainWindow.focus();
    });

    // --- Start Backend Asynchronously (Non-Blocking) ---
    // Do NOT await or block on this. Let it run in the background.
    this.startBackend()
      .then(() => {
        console.log('[SUCCESS] Backend started successfully.');
        // Notify frontend of online status
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
          this.mainWindow.webContents.send('backend-status', { status: 'online' });
        }
      })
      .catch(error => {
        console.error(`[BACKEND FAILURE] Backend failed to start: ${error.message}`);
        // Do NOT show blocking error dialog. Log it and notify frontend of offline status.
        if (this.mainWindow && !this.mainWindow.isDestroyed()) {
          this.mainWindow.webContents.send('backend-status', { status: 'offline', error: error.message });
        }
      });
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
