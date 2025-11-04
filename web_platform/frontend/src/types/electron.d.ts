// web_platform/frontend/src/types/electron.d.ts

/**
 * This declaration file extends the global Window interface to include the
 * 'electronAPI' object exposed by the preload script. This provides
 * TypeScript with type information for the functions we're using for IPC.
 */
export {};

declare global {
  interface Window {
    electronAPI?: {
      /**
       * Asynchronously fetches the secure API key from the main process.
       * @returns {Promise<string|null>} A promise that resolves with the API key or null if not found.
       */
      getApiKey: () => Promise<string | null>;
      /**
       * Registers a callback for backend status updates from the main process.
       * @param callback The function to execute. Receives an object with state and logs.
       * @returns A function to unsubscribe the listener.
       */
      onBackendStatusUpdate: (callback: (status: { state: 'starting' | 'running' | 'error' | 'stopped'; logs: string[] }) => void) => () => void;

      /**
       * Sends a command to the main process to restart the backend executable.
       */
      restartBackend: () => void;

      /**
       * Asynchronously fetches the current backend status from the main process.
       * @returns {Promise<{ state: 'starting' | 'running' | 'error' | 'stopped'; logs: string[] }>}
       */
      getBackendStatus: () => Promise<{ state: 'starting' | 'running' | 'error' | 'stopped'; logs: string[] }>;
      generateApiKey: () => Promise<string>;
    };
  }
}
