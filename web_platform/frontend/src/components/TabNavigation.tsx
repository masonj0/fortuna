// web_platform/frontend/src/components/TabNavigation.tsx
'use client';

import { useState } from 'react';
import { LiveRaceDashboard } from './LiveRaceDashboard';
import { SettingsPage } from './SettingsPage';

type Tab = 'dashboard' | 'settings';

export function TabNavigation() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'settings':
        return <SettingsPage />;
      case 'dashboard':
      default:
        return <LiveRaceDashboard />;
    }
  };

  return (
    <div>
      <div className="flex border-b border-gray-700">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`px-4 py-2 ${activeTab === 'dashboard' ? 'border-b-2 border-blue-500 text-white' : 'text-gray-400'}`}
        >
          Dashboard
        </button>
        <button
          onClick={() => setActiveTab('settings')}
          className={`px-4 py-2 ${activeTab === 'settings' ? 'border-b-2 border-blue-500 text-white' : 'text-gray-400'}`}
        >
          Settings
        </button>
      </div>
      <div className="p-6">
        {renderTabContent()}
      </div>
    </div>
  );
}
