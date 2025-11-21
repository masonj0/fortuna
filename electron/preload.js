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
 * Asynchronously generates and saves a new secure API key.
 * @returns {Promise<string>} A promise that resolves with the newly generated API key.
 */
 generateApiKey: () => ipcRenderer.invoke('generate-api-key'),

 /**
 * Asynchronously saves a provided API key.
 * @param {string} apiKey - The API key to save.
 * @returns {Promise<{success: boolean}>} A promise that resolves with the result of the save operation.
 */
 saveApiKey: (apiKey) => ipcRenderer.invoke('save-api-key', apiKey),

 /**
 * Asynchronously saves Betfair credentials.
 * @param {{username: string, apiKey: string}} credentials - The credentials to save.
 * @returns {Promise<{success: boolean}>} A promise that resolves with the result of the save operation.
 */
 saveBetfairCredentials: (credentials) => ipcRenderer.invoke('save-betfair-credentials', credentials),

 /**
  * Restarts the backend service.
  */
 restartBackend: () => ipcRenderer.send('restart-backend'),

 /**
  * Stops the backend service.
  */
 stopBackend: () => ipcRenderer.send('stop-backend'),

 /**
  * Fetches the current status of the backend service.
  * @returns {Promise<{state: string, logs: string[]}>} A promise that resolves with the backend status.
  */
 getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),

 /**
  * Subscribes to backend status updates.
  * @param {function(event, {state: string, logs: string[]})} callback - The function to call with status updates.
  */
 onBackendStatusUpdate: (callback) => {
    // Deliberately strip event sender from callback to avoid security risks
    const subscription = (event, ...args) => callback(...args);
    ipcRenderer.on('backend-status-update', subscription);

    // Return a function to unsubscribe
    return () => {
      ipcRenderer.removeListener('backend-status-update', subscription);
    };
  },

  /**
   * Gets the port the backend API is running on.
   * @returns {Promise<number>} A promise that resolves with the port number.
   */
  getApiPort: () => ipcRenderer.invoke('get-api-port'),
});
