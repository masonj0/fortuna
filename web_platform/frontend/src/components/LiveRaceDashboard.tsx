// web_platform/frontend/src/components/LiveRaceDashboard.tsx
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { RaceFilters } from './RaceFilters';
import { RaceCard } from './RaceCard';
import { RaceCardSkeleton } from './RaceCardSkeleton';
import { EmptyState } from './EmptyState';
import { Race, SourceInfo } from '../types/racing';
import { useWebSocket } from '../hooks/useWebSocket';
import { StatusDetailModal } from './StatusDetailModal';
import ManualOverridePanel from './ManualOverridePanel';
import { LiveModeToggle } from './LiveModeToggle';
import { AdapterStatusPanel } from './AdapterStatusPanel';

// Type for the backend process status received from Electron main
type BackendState = 'starting' | 'running' | 'error' | 'stopped';
interface BackendStatus {
  state: BackendState;
  logs: string[];
}

interface RaceFilterParams {
  maxFieldSize: number;
  minFavoriteOdds: number;
  minSecondFavoriteOdds: number;
}

const fetchAdapterStatuses = async (apiKey: string | null): Promise<SourceInfo[]> => {
  if (!apiKey) {
    throw new Error('API key not configured or retrieved.');
  }
  const response = await fetch('/api/adapters/status', {
    headers: { 'X-API-Key': apiKey, 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error || `API request failed with status ${response.status}`);
  }
  return response.json();
};


const BackendErrorPanel = ({ logs, onRestart }: { logs: string[]; onRestart: () => void }) => (
  <div className="bg-slate-800 p-6 rounded-lg border border-red-500/50 text-white">
    <h2 className="text-2xl font-bold text-red-400 mb-4">Backend Service Error</h2>
    <p className="text-slate-400 mb-4">The backend data service failed to start or has crashed. Below are the most recent diagnostic messages.</p>
    <div className="bg-black p-4 rounded-md font-mono text-sm text-slate-300 h-64 overflow-y-auto mb-4">
      {logs.map((log, index) => (
        <p key={index} className="whitespace-pre-wrap">{`> ${log}`}</p>
      ))}
    </div>
    <button
      onClick={onRestart}
      className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
    >
      Restart Backend Service
    </button>
  </div>
);

// New Sub-Component to display an error from a specific adapter
const ErrorCard = ({ source, message }: { source: string; message: string }) => (
  <div className="bg-slate-800 rounded-lg p-4 border border-red-500/50 flex flex-col justify-between">
    <div>
      <h3 className="font-bold text-red-400 text-lg">{source} Failed</h3>
      <p className="text-slate-400 text-sm mt-2">{message}</p>
    </div>
    <div className="mt-4 text-xs text-slate-500">
      <p>This adapter failed to fetch data. This is not a critical error; other adapters may provide the necessary data.</p>
    </div>
  </div>
);

// New Sub-Component to render the grid of races or error cards
const RaceGrid = ({ races }: { races: Race[] }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
    {races.map(race =>
      race.isErrorPlaceholder ? (
        <ErrorCard key={race.id} source={race.venue} message={race.errorMessage || 'An unknown error occurred.'} />
      ) : (
        <RaceCard key={race.id} race={race} />
      )
    )}
  </div>
);

export const LiveRaceDashboard = React.memo(() => {
  const [races, setRaces] = useState<Race[]>([]);
  const [failedSources, setFailedSources] = useState<SourceInfo[]>([]);

  // Separate status for backend process and API connection
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ state: 'starting', logs: [] });
  const [apiKey, setApiKey] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Get API key on component mount
  useEffect(() => {
    const fetchApiKey = async () => {
      try {
        const key = window.electronAPI ? await window.electronAPI.getApiKey() : process.env.NEXT_PUBLIC_API_KEY;
        if (key) {
          setApiKey(key);
        } else {
          console.error('API key could not be retrieved.');
        }
      } catch (error) {
        console.error('Error fetching API key:', error);
      }
    };
    fetchApiKey();
  }, []);

  const {
    data: adapterStatuses,
    status: connectionStatus,
    error: errorDetails,
    refetch,
  } = useQuery({
    queryKey: ['adapterStatuses', apiKey],
    queryFn: () => fetchAdapterStatuses(apiKey),
    enabled: backendStatus.state === 'running' && !!apiKey,
    refetchOnWindowFocus: false,
  });

  const { data: liveData, isConnected: isLiveConnected } = useWebSocket<{ races: Race[], source_info: SourceInfo[] }>(
    apiKey ? '/ws/live-updates' : '',
    { apiKey }
  );

  // Effect to update state when new live data arrives
  useEffect(() => {
    if (liveData) {
      console.log('Received live data update:', liveData);
      queryClient.setQueryData(['adapterStatuses', apiKey], liveData.source_info);
      setRaces(liveData.races || []);
      setFailedSources(liveData.source_info?.filter((s: SourceInfo) => s.status === 'FAILED' && s.attemptedUrl) || []);
      setLastUpdate(new Date());
    }
  }, [liveData, queryClient, apiKey]);

  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [params, setParams] = useState<RaceFilterParams>({
    maxFieldSize: 10,
    minFavoriteOdds: 2.5,
    minSecondFavoriteOdds: 4.0,
  });
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Effect for setting up Electron IPC listener and fetching initial status
  useEffect(() => {
    console.log('[LiveRaceDashboard] Component did mount.');
    // Flag to prevent updates after unmount
    let isMounted = true;

    // Function to get the initial status
    const getInitialStatus = async () => {
      if (window.electronAPI?.getBackendStatus) {
        console.log('[LiveRaceDashboard] electronAPI is available. Requesting initial status.');
        try {
          const initialStatus = await window.electronAPI.getBackendStatus();
          console.log('[LiveRaceDashboard] Received initial status:', initialStatus);
          if (isMounted) {
            setBackendStatus(initialStatus);
          }
        } catch (error) {
          console.error("[LiveRaceDashboard] Failed to get initial backend status:", error);
          if (isMounted) {
            setBackendStatus({ state: 'error', logs: ['Failed to query backend status from main process.'] });
          }
        }
      } else {
        console.warn('[LiveRaceDashboard] electronAPI is not available. Forcing error state for verification.');
        if (isMounted) {
            setBackendStatus({ state: 'error', logs: ['In a web-only environment, backend is unavailable. This is a simulated error for component verification.'] });
        }
      }
    };

    // Set up the listener for ongoing status updates
    if (window.electronAPI?.onBackendStatusUpdate) {
      const unsubscribe = window.electronAPI.onBackendStatusUpdate((status: BackendStatus) => {
        if (isMounted) {
          setBackendStatus(status);
        }
      });

      // Get the initial state right after setting up the listener
      getInitialStatus();

      // Cleanup: remove the listener when the component unmounts
      return () => {
        isMounted = false;
        if (typeof unsubscribe === 'function') {
          unsubscribe();
        }
      };
    }
  }, []);


  const handleParamsChange = useCallback((newParams: RaceFilterParams) => {
    setParams(newParams);
  }, []);

  const renderContent = () => {
    // Priority 1: Backend process has failed.
    if (backendStatus.state === 'error') {
      return <BackendErrorPanel logs={backendStatus.logs} onRestart={() => window.electronAPI.restartBackend()} />;
    }

    // Priority 2: Backend is starting or initial fetch is happening.
    const isLoading = backendStatus.state === 'starting' || (connectionStatus === 'pending' && !adapterStatuses);
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {[...Array(8)].map((_, i) => <RaceCardSkeleton key={i} />)}
            </div>
        );
    }

    // Priority 3: API connection is offline.
    if (connectionStatus === 'error') {
      return <EmptyState
          title="API Connection Offline"
          message={(errorDetails as Error)?.message || "The backend is running, but the dashboard could not connect to its API."}
          actionButton={<button onClick={() => refetch()} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Retry Connection</button>}
      />;
    }

    // Priority 4: No races found after a successful fetch.
    if (!races || races.length === 0) {
      return <EmptyState
          title="No Races Found"
          message="No races matched the specified criteria for the selected date. Please try different filters."
      />;
    }

    // Priority 5: Display the races (and any error placeholders).
    return <RaceGrid races={races} />;
  };

  const getStatusIndicator = () => {
    if (backendStatus.state === 'error') {
      return { color: 'bg-red-500', text: 'Backend Error' };
    }
    if (backendStatus.state === 'starting') {
      return { color: 'bg-yellow-500', text: 'Backend Starting...' };
    }
    if (isLiveConnected) {
      return { color: 'bg-cyan-500', text: 'Live' };
    }
    return { color: 'bg-yellow-500', text: 'Connecting...' };
  };

  const { color: statusColor, text: statusText } = getStatusIndicator();

  return (
    <>
      <div className="space-y-6">
        <div className="flex justify-between items-start">
            <div className="text-left space-y-2">
                <h1 className="text-4xl font-bold text-white">🏇 Fortuna Faucet</h1>
                <p className="text-slate-400">
                Last updated: {lastUpdate ? lastUpdate.toLocaleTimeString() : 'N/A'}
                </p>
            </div>
            <div className="flex items-center gap-4">
                <button
                    onClick={() => (connectionStatus === 'error' || backendStatus.state === 'error') && setIsModalOpen(true)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium text-white ${statusColor} ${(connectionStatus === 'error' || backendStatus.state === 'error') ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}`}
                    data-testid="status-indicator"
                >
                    <span className={`w-2.5 h-2.5 rounded-full bg-white ${isLiveConnected ? 'animate-pulse' : ''}`}></span>
                    {statusText}
                </button>
            </div>
        </div>

        <RaceFilters onParamsChange={handleParamsChange} isLoading={connectionStatus === 'pending'} />

        {failedSources.map(source => (
          <ManualOverridePanel
            key={source.name}
            adapterName={source.name}
            attemptedUrl={source.attemptedUrl || 'URL not available'}
          />
        ))}

        {renderContent()}
      </div>

      <StatusDetailModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        status={{ title: 'Connection Error', details: (errorDetails as Error)?.message || 'No specific error message was provided.' }}
      />
    </>
  );
});
