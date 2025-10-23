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
    };
  }
}
