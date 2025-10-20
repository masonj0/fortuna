'use client';

import dynamic from 'next/dynamic';
import React from 'react';

const LiveRaceDashboard = dynamic(
  () => import('../src/components/LiveRaceDashboard').then((mod) => mod.LiveRaceDashboard),
  {
    ssr: false,
    loading: () => <p className="text-center text-xl mt-8">Loading Dashboard...</p>
  }
);

export default function Home() {
  return (
    <LiveRaceDashboard />
  );
}