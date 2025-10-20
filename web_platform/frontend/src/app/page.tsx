'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LiveRaceDashboard } from '../components/LiveRaceDashboard';

const queryClient = new QueryClient();

export default function Home() {
  return (
    <QueryClientProvider client={queryClient}>
      <main className="flex min-h-screen flex-col items-center justify-between p-4 md:p-12 bg-gray-900">
        <LiveRaceDashboard />
      </main>
    </QueryClientProvider>
  );
}
