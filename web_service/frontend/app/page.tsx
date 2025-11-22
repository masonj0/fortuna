'use client';
import dynamic from 'next/dynamic';
import React from 'react';
import { Tabs } from '../src/components/Tabs';
import { SettingsPage } from '../src/components/SettingsPage';

const LiveRaceDashboard = dynamic(
  () => import('../src/components/LiveRaceDashboard').then((mod) => mod.LiveRaceDashboard),
  {
    ssr: false,
    loading: () => <p className="text-center text-xl mt-8">Loading Dashboard...</p>
  }
);

export default function Home() {
  const tabs = [
    {
      label: 'Dashboard',
      content: <LiveRaceDashboard />,
    },
    {
      label: 'Settings',
      content: <SettingsPage />,
    },
  ];

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <h1 className="text-4xl font-bold text-white">Fortuna Faucet</h1>
        <Tabs tabs={tabs} />
      </div>
    </main>
  );
}
