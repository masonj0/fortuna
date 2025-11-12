// src/components/SettingsPage.tsx
'use client';

import React, { useState, useEffect } from 'react';

export function SettingsPage() {
  const [apiKey, setApiKey] = useState('');
  const [betfairAppKey, setBetfairAppKey] = useState('');
  const [betfairUsername, setBetfairUsername] = useState('');
  const [betfairPassword, setBetfairPassword] = useState('');

  useEffect(() => {
    // Fetch the current API key when the component mounts
    const fetchApiKey = async () => {
      if (window.electronAPI?.getApiKey) {
        const key = await window.electronAPI.getApiKey();
        if (key) {
          setApiKey(key);
        }
      }
    };
    fetchApiKey();
  }, []);

  const handleGenerateApiKey = async () => {
    if (window.electronAPI?.generateApiKey) {
      const newKey = await window.electronAPI.generateApiKey();
      setApiKey(newKey);
    }
  };

  const handleSaveSettings = async () => {
    if (window.electronAPI?.saveApiKey && window.electronAPI?.saveBetfairCredentials) {
      await window.electronAPI.saveApiKey(apiKey);
      await window.electronAPI.saveBetfairCredentials({
        appKey: betfairAppKey,
        username: betfairUsername,
        password: betfairPassword,
      });
      alert('Settings saved successfully!');
    }
  };

  return (
    <div className="bg-slate-800 p-8 rounded-lg border border-slate-700 text-white max-w-2xl mx-auto">
      <h2 className="text-3xl font-bold text-white mb-6">Application Settings</h2>

      <div className="space-y-8">
        <div>
          <h3 className="text-xl font-semibold text-slate-300 mb-2">API Key</h3>
          <p className="text-sm text-slate-400 mb-3">This key is required for the dashboard to communicate with the backend service.</p>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              readOnly
              value={apiKey}
              className="w-full p-2 bg-slate-700 rounded border border-slate-600 font-mono text-sm"
            />
            <button
              onClick={handleGenerateApiKey}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded transition-colors font-semibold"
            >
              Generate New Key
            </button>
          </div>
        </div>

        <div>
          <h3 className="text-xl font-semibold text-slate-300 mb-2">Betfair Credentials (Optional)</h3>
           <p className="text-sm text-slate-400 mb-3">Required for adapters that use the Betfair Exchange API.</p>
          <div className="space-y-3">
            <input
              type="password"
              placeholder="App Key"
              value={betfairAppKey}
              onChange={(e) => setBetfairAppKey(e.target.value)}
              className="w-full p-2 bg-slate-700 rounded border border-slate-600 placeholder-slate-500"
            />
            <input
              type="text"
              placeholder="Username"
              value={betfairUsername}
              onChange={(e) => setBetfairUsername(e.target.value)}
              className="w-full p-2 bg-slate-700 rounded border border-slate-600 placeholder-slate-500"
            />
            <input
              type="password"
              placeholder="Password"
              value={betfairPassword}
              onChange={(e) => setBetfairPassword(e.target.value)}
              className="w-full p-2 bg-slate-700 rounded border border-slate-600 placeholder-slate-500"
            />
          </div>
        </div>

        <div className="flex justify-end pt-6 border-t border-slate-700">
          <button
            onClick={handleSaveSettings}
            className="px-8 py-3 bg-green-600 hover:bg-green-700 rounded font-bold text-lg transition-colors"
          >
            Save All Settings
          </button>
        </div>
      </div>
    </div>
  );
}
