'use client';
import dynamic from 'next/dynamic';
import React from 'react';

// Dynamically import components to ensure they are client-side rendered
const ManualOverridePanel = dynamic(
  () => import('../src/components/ManualOverridePanel'),
  { ssr: false }
);

const LiveRaceDashboard = dynamic(
  () => import('../src/components/LiveRaceDashboard').then((mod) => mod.LiveRaceDashboard),
  {
    ssr: false,
    loading: () => <p className="text-center text-xl mt-8">Loading Dashboard...</p>
  }
);

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Manual Override Panel - Shows only when needed */}
        <ManualOverridePanel />

        {/* Main Dashboard */}
        <LiveRaceDashboard />
      </div>
    </main>
  );
}
