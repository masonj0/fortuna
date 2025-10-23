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
});

console.log('Preload script loaded and electronAPI is exposed.');
