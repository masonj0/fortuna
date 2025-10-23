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
    const [detailsVisible, setDetailsVisible] = useState(false);
    if (!error) return null;

    const userMessage = error?.user_message || 'An unexpected error occurred.';
    const technicalDetails = error?.technical_details || error?.message || 'No technical details available.';

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 border border-red-500/50 rounded-lg shadow-xl p-6 max-w-md w-full">
                <h3 className="text-xl font-bold text-red-400 mb-4">Application Alert</h3>
                <p className="text-gray-300 mb-6">{userMessage}</p>

                <div className="mb-4">
                    <button onClick={() => setDetailsVisible(!detailsVisible)} className="text-sm text-gray-400 hover:underline">
                        {detailsVisible ? 'Hide' : 'Show'} Technical Details
                    </button>
                    {detailsVisible && (
                        <div className="mt-2 p-3 bg-gray-900/50 rounded-md border border-gray-700 text-xs text-gray-400">
                            <code>{technicalDetails}</code>
                        </div>
                    )}
                </div>

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

  const fetchWithStructuredError = async (url: string, headers: HeadersInit) => {
    console.log("Fetching URL:", url); // DEBUGGING
    const res = await fetch(url, { headers });
    console.log("Response Status:", res.status); // DEBUGGING
    if (!res.ok) {
        try {
            // Try to parse the structured error from the backend
            const errorBody = await res.json();
            throw errorBody;
        } catch (e) {
            // If parsing fails, fall back to a generic error
            throw new Error(`Request failed with status: ${res.statusText}`);
        }
    }
    return res.json();
  };

  // A new helper function to abstract the logic of getting the API key.
  // It first tries the secure Electron API and falls back to the .env variable for standalone development.
  const getApiKey = async (): Promise<string> => {
    // The preload script exposes the electronAPI on the window object.
    if (window.electronAPI && typeof window.electronAPI.getApiKey === 'function') {
      console.log("Using electronAPI.getApiKey() to fetch key.");
      const key = await window.electronAPI.getApiKey();
      if (key) return key;
      console.warn("electronAPI.getApiKey() returned a null or empty value.");
    }

    console.log("Falling back to process.env.NEXT_PUBLIC_API_KEY.");
    const fallbackKey = process.env.NEXT_PUBLIC_API_KEY;
    if (fallbackKey) return fallbackKey;

    // If both methods fail, we throw an error.
    throw new Error('API key could not be retrieved from secure storage or .env fallback.');
  };

  const { data: qualifiedData, error: racesError, isLoading: racesLoading } = useQuery({
    queryKey: ['qualifiedRaces'],
    queryFn: async () => {
      const apiKey = await getApiKey();
      return fetchWithStructuredError(`/api/races/qualified/trifecta`, { 'X-API-Key': apiKey });
    },
    refetchInterval: 30000,
  });

  const { data: statuses, error: statusError } = useQuery({
    queryKey: ['adapterStatuses'],
    queryFn: async () => {
      const apiKey = await getApiKey();
      return fetchWithStructuredError(`/api/adapters/status`, { 'X-API-Key': apiKey });
    },
    refetchInterval: 60000,
  });

  const { isError: backendFailed } = useQuery({
    queryKey: ['healthCheck'],
    queryFn: async () => {
      // We don't need the API key for the health check
      const res = await fetch(`/health`);
      if (!res.ok) throw new Error('Backend health check failed');
      return res.json();
    },
    refetchInterval: 15000, // Check every 15 seconds
    retry: 1, // Don't retry aggressively
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
        {backendFailed && (
          <div className="bg-red-800 border border-red-600 text-white text-center p-4 rounded-lg mb-8">
            <h3 className="font-bold text-lg">Backend Service Unavailable</h3>
            <p>The core data service is not responding. Some features of the application will be unavailable. Please ensure the Fortuna Faucet Backend service is running via the System Console.</p>
          </div>
        )}
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
