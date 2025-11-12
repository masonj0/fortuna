// electron/preload.js
// This script runs in a privileged environment with access to Node.js APIs.
// It's used to securely expose specific functionality to the renderer process (the web UI).

const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe, limited API to the frontend.
contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Asynchronously fetches the secure API key from the main process.
   * @returns {Promise<string|null>} A promise that resolves with the API key or null if not found.
   */
  getApiKey: () => ipcRenderer.invoke('get-api-key'),

  /**
   * Registers a callback to be invoked when the backend status changes.
   * @param {Function} callback - The function to call with the status object.
   *                              It receives an object like { status: 'online' | 'offline', error?: string }.
   */
  onBackendStatusUpdate: (callback) => {
    const handler = (_event, value) => callback(value);
    ipcRenderer.on('backend-status-update', handler);
    // Return a cleanup function to remove the listener
    return () => ipcRenderer.removeListener('backend-status-update', handler);
  },
  restartBackend: () => ipcRenderer.send('restart-backend'),
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  generateApiKey: () => ipcRenderer.invoke('generate-api-key'),
  saveApiKey: (apiKey) => ipcRenderer.invoke('save-api-key', apiKey),
  saveBetfairCredentials: (credentials) => ipcRenderer.invoke('save-betfair-credentials', credentials),
});

console.log('Preload script loaded and electronAPI is exposed.');
