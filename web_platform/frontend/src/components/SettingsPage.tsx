// web_platform/frontend/src/components/SettingsPage.tsx
'use client';

import { useState } from 'react';

export function SettingsPage() {
  const [apiKey, setApiKey] = useState('');
  const [message, setMessage] = useState('');

  const handleGenerateApiKey = async () => {
    try {
      if (window.electronAPI) {
        const newApiKey = await window.electronAPI.generateApiKey();
        setApiKey(newApiKey);
        setMessage('Successfully generated and saved a new API key.');
      } else {
        setMessage('Error: Not running in Electron context.');
      }
    } catch (error: any) {
      setMessage(`Error: ${error.message}`);
    }
  };

  return (
    <div className="p-6 bg-gray-900 text-white min-h-screen">
      <h1 className="text-2xl font-bold mb-4">Settings</h1>
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">API Key</h2>
          <p className="text-gray-400">
            A secure API key is required to communicate with the backend service.
          </p>
          <div className="mt-2 flex items-center space-x-2">
            <input
              type="text"
              readOnly
              value={apiKey}
              className="w-full p-2 bg-gray-800 border border-gray-700 rounded"
              placeholder="API Key will be displayed here..."
            />
            <button
              onClick={handleGenerateApiKey}
              className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700"
            >
              Generate Key
            </button>
          </div>
          {message && <p className="mt-2 text-sm text-gray-400">{message}</p>}
        </div>
      </div>
    </div>
  );
}
