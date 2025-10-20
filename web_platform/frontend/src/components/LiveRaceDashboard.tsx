// web_platform/frontend/src/components/LiveRaceDashboard.tsx
'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RaceCard } from './RaceCard';
import { Race, AdapterStatus } from '../types/racing';

// --- Connection Status Component ---
const ConnectionStatus = ({ isError, isLoading }) => {
  const [status, setStatus] = useState({ color: 'gray', text: 'Connecting...' });

  useEffect(() => {
    if (isLoading) {
      setStatus({ color: 'yellow', text: 'Connecting...' });
    } else if (isError) {
      setStatus({ color: 'red', text: 'Connection Error' });
    } else {
      setStatus({ color: 'green', text: 'Connected to Fortuna Engine' });
    }
  }, [isError, isLoading]);

  const colorClasses = {
    gray: 'bg-gray-500',
    yellow: 'bg-yellow-500 animate-pulse',
    red: 'bg-red-500',
    green: 'bg-green-500',
  };

  return (
    <div className="fixed bottom-4 right-4 flex items-center bg-gray-800/80 backdrop-blur-sm text-white text-xs px-3 py-2 rounded-full shadow-lg border border-gray-700">
      <div className={`w-3 h-3 rounded-full mr-2 ${colorClasses[status.color]}`}></div>
      <span>{status.text}</span>
    </div>
  );
};

// --- Error Modal Component ---
const ErrorModal = ({ error, onClose }) => {
    if (!error) return null;
    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 border border-red-500/50 rounded-lg shadow-xl p-6 max-w-md w-full">
                <h3 className="text-xl font-bold text-red-400 mb-4">API Connection Error</h3>
                <p className="text-gray-300 mb-6">{error.message}</p>
                <button
                    onClick={onClose}
                    className="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded w-full"
                >
                    Close
                </button>
            </div>
        </div>
    );
};

// --- Main Component ---
export const LiveRaceDashboard: React.FC = () => {
  const [filterConfig, setFilterConfig] = useState({ minScore: 0, maxFieldSize: 999, sortBy: 'score' });
  const [showErrorModal, setShowErrorModal] = useState(false);

  const { data: qualifiedData, error: racesError, isLoading: racesLoading } = useQuery({
    queryKey: ['qualifiedRaces'],
    queryFn: async () => {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      if (!apiKey) throw new Error('API key not configured.');
      const res = await fetch(`/api/races/qualified/trifecta`, { headers: { 'X-API-Key': apiKey } });
      if (!res.ok) throw new Error(`Failed to fetch qualified races: ${res.statusText}`);
      return res.json();
    },
    refetchInterval: 30000,
  });

  const { data: statuses, error: statusError } = useQuery({
    queryKey: ['adapterStatuses'],
    queryFn: async () => {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      if (!apiKey) throw new Error('API key not configured.');
      const res = await fetch(`/api/adapters/status`, { headers: { 'X-API-Key': apiKey } });
      if (!res.ok) throw new Error(`Failed to fetch adapter statuses: ${res.statusText}`);
      return res.json();
    },
    refetchInterval: 60000,
  });

  const combinedError = racesError || statusError;

  useEffect(() => {
    if (combinedError) {
      setShowErrorModal(true);
    }
  }, [combinedError]);

  // --- Filtering and Sorting Logic (unchanged) ---
  const filteredAndSortedRaces = useMemo(() => {
    // ... (logic is the same)
    let processedRaces = [...(qualifiedData?.races || [])];
    processedRaces = processedRaces.filter(race => (race.qualification_score || 0) >= filterConfig.minScore && race.runners.filter(r => !r.scratched).length <= filterConfig.maxFieldSize);
    processedRaces.sort((a, b) => {
      switch (filterConfig.sortBy) {
        case 'time': return new Date(a.start_time).getTime() - new Date(b.start_time).getTime();
        case 'venue': return a.venue.localeCompare(b.venue);
        default: return (b.qualification_score || 0) - (a.qualification_score || 0);
      }
    });
    return processedRaces;
  }, [qualifiedData, filterConfig]);


  return (
    <>
      <main className="min-h-screen bg-gray-900 text-white p-8">
        {/* ... (Header and filter panels are the same) ... */}
        <h1 className="text-4xl font-bold text-center mb-8">Fortuna Faucet Command Deck</h1>
        <div className='mb-8 p-4 bg-gray-800/50 border border-gray-700 rounded-lg'>
          <h2 className='text-lg font-semibold text-gray-300 mb-3'>Adapter Status</h2>
          <div className='flex flex-wrap gap-2'>
            {statuses?.map(s => (
              <span key={s.adapter_name} className={`px-2 py-1 text-xs font-bold rounded-full ${s.status === 'SUCCESS' || s.status === 'OK' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}`}>{s.adapter_name}</span>
            )) ?? <span className='text-gray-500 text-sm'>Loading statuses...</span>}
          </div>
        </div>
        <div className="filter-panel bg-gray-800/90 backdrop-blur-sm p-4 rounded-xl border border-gray-700 mb-6">
            {/* ... */}
        </div>

        {racesLoading && <p className="text-center text-xl">Searching for qualified races...</p>}

        {!racesLoading && !combinedError && (
          <>
            <div className='text-center mb-4 text-gray-400'>Displaying <span className='font-bold text-white'>{filteredAndSortedRaces.length}</span> of <span className='font-bold text-white'>{qualifiedData?.races.length || 0}</span> total qualified races.</div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredAndSortedRaces.map(race => <RaceCard key={race.id} race={race} />)}
            </div>
          </>
        )}
      </main>

      <ConnectionStatus isError={!!combinedError} isLoading={racesLoading} />
      <ErrorModal error={combinedError} onClose={() => setShowErrorModal(false)} />
    </>
  );
};
