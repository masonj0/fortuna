// web_platform/frontend/src/components/AdapterStatusPanel.tsx
'use client';

import React from 'react';
import { SourceInfo } from '../types/racing';

interface AdapterStatusPanelProps {
  adapter: SourceInfo;
  onFetchRaces: (sourceName: string) => void;
}

export const AdapterStatusPanel: React.FC<AdapterStatusPanelProps> = ({ adapter, onFetchRaces }) => {
  const isConfigured = adapter.status !== 'CONFIG_ERROR';

  return (
    <div className={`p-4 rounded-lg border ${isConfigured ? 'bg-slate-800 border-slate-700' : 'bg-yellow-900/20 border-yellow-700/50'}`}>
      <div className="flex justify-between items-center">
        <h3 className="font-bold text-lg text-white">{adapter.name}</h3>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${isConfigured ? 'bg-green-500/20 text-green-300' : 'bg-yellow-500/20 text-yellow-300'}`}>
          {isConfigured ? 'Ready' : 'Not Configured'}
        </span>
      </div>
      <div className="mt-4 flex gap-2">
        <button
          onClick={() => onFetchRaces(adapter.name)}
          disabled={!isConfigured}
          className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-slate-700 disabled:text-slate-400 disabled:cursor-not-allowed"
        >
          Automatic Load
        </button>
        <button
          disabled
          className="flex-1 px-4 py-2 bg-slate-700 text-slate-400 rounded cursor-not-allowed"
        >
          Manual Entry (Coming Soon)
        </button>
      </div>
    </div>
  );
};
