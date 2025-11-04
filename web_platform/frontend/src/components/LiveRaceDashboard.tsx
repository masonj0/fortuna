// web_platform/frontend/src/components/LiveRaceDashboard.tsx
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { RaceFilters } from './RaceFilters';
import { RaceCard } from './RaceCard';
import { RaceCardSkeleton } from './RaceCardSkeleton';
import { EmptyState } from './EmptyState';
import { Race, SourceInfo } from '../types/racing';
import { useWebSocket } from '../hooks/useWebSocket';
import { StatusDetailModal } from './StatusDetailModal';
import ManualOverridePanel from './ManualOverridePanel';
import { LiveModeToggle } from './LiveModeToggle';

// Type for the API connection status
type ConnectionStatus = 'connecting' | 'online' | 'offline';

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


export const LiveRaceDashboard = React.memo(() => {
  const [races, setRaces] = useState<Race[]>([]);
  const [failedSources, setFailedSources] = useState<SourceInfo[]>([]);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  // Separate status for backend process and API connection
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ state: 'starting', logs: [] });
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [apiKey, setApiKey] = useState<string | null>(null);

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

  const { data: liveData, isConnected: isLiveConnected } = useWebSocket<{ races: Race[], source_info: SourceInfo[] }>(
    isLiveMode && apiKey ? '/ws/live-updates' : '',
    { apiKey }
  );

  // Effect to update state when new live data arrives
  useEffect(() => {
    if (isLiveMode && liveData) {
      console.log('Received live data update:', liveData);
      setRaces(liveData.races || []);
      setFailedSources(liveData.source_info?.filter((s: SourceInfo) => s.status === 'FAILED' && s.attemptedUrl) || []);
      setLastUpdate(new Date());
      setConnectionStatus('online');
      setIsInitialLoad(false);
    }
  }, [liveData, isLiveMode]);

  const [errorDetails, setErrorDetails] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [params, setParams] = useState<RaceFilterParams>({
    maxFieldSize: 10,
    minFavoriteOdds: 2.5,
    minSecondFavoriteOdds: 4.0,
  });
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchQualifiedRaces = useCallback(async () => {
    // Only fetch if the backend is actually running
    if (backendStatus.state !== 'running') return;

    setConnectionStatus('connecting');
    setErrorDetails(null);
    setFailedSources([]);

    try {
      const apiKey = window.electronAPI ? await window.electronAPI.getApiKey() : process.env.NEXT_PUBLIC_API_KEY;
      if (!apiKey) throw new Error('API key not configured or retrieved.');

      const queryParams = new URLSearchParams({
        max_field_size: params.maxFieldSize.toString(),
        min_favorite_odds: params.minFavoriteOdds.toString(),
        min_second_favorite_odds: params.minSecondFavoriteOdds.toString(),
      });

      const response = await fetch(`/api/races/qualified/trifecta?${queryParams.toString()}`, {
        headers: { 'X-API-Key': apiKey, 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `API request failed with status ${response.status}`);
      }

      const data = await response.json();
      setRaces(data.races || []);
      setFailedSources(data.source_info?.filter((s: SourceInfo) => s.status === 'FAILED' && s.attemptedUrl) || []);
      setLastUpdate(new Date());
      setConnectionStatus('online');
    } catch (err: any) {
      setErrorDetails(err.message || 'An unknown API error occurred.');
      setConnectionStatus('offline');
      console.error('Failed to fetch qualified races:', err);
    } finally {
      setIsInitialLoad(false);
    }
  }, [params, backendStatus.state]);

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
            // If the backend is already running, fetch races immediately.
            if (initialStatus.state === 'running') {
              console.log('[LiveRaceDashboard] Initial state is "running", fetching races.');
              fetchQualifiedRaces();
            }
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
    } else {
        // If there's no electron API, maybe we are in a web-only environment.
        // Let's assume the backend is running and try to fetch.
        fetchQualifiedRaces();
    }
  }, [fetchQualifiedRaces]); // Removed isInitialLoad, as this effect should manage its own logic.

  // Effect for periodic data refresh
  useEffect(() => {
    if (isLiveMode) {
      return; // Don't poll when in live mode
    }
    const interval = setInterval(() => {
      if (backendStatus.state === 'running' && connectionStatus === 'online') {
        fetchQualifiedRaces();
      }
    }, 30000); // 30-second refresh
    return () => clearInterval(interval);
  }, [backendStatus.state, connectionStatus, fetchQualifiedRaces, isLiveMode]);


  const handleParamsChange = useCallback((newParams: RaceFilterParams) => {
    setParams(newParams);
  }, []);

  const renderContent = () => {
    // Priority 1: Backend process has failed.
    if (backendStatus.state === 'error') {
      return <BackendErrorPanel logs={backendStatus.logs} onRestart={() => window.electronAPI.restartBackend()} />;
    }

    // Priority 2: Handle loading states (initial load, backend starting, or API connecting)
    if (isInitialLoad || backendStatus.state === 'starting' || connectionStatus === 'connecting') {
      return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RaceCardSkeleton /><RaceCardSkeleton /><RaceCardSkeleton /><RaceCardSkeleton />
        </div>
      );
    }

    // Priority 3: API connection is offline, but backend is running.
    if (connectionStatus === 'offline') {
      return <EmptyState
          title="API Connection Offline"
          message={errorDetails || "The backend service is running, but the dashboard could not connect to its API."}
          actionButton={<button onClick={fetchQualifiedRaces} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Retry Connection</button>}
      />;
    }

    // Priority 4: Online but no races match criteria.
    if (races.length === 0) {
      return failedSources.length > 0
        ? <EmptyState title="Incomplete Results" message="Some data sources failed. No races matched your filters from the sources that responded." />
        : <EmptyState title="No Races Found" message="All data sources responded, but no races matched your current filters." />;
    }

    // Default: Show the race cards.
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {races.map((race) => <RaceCard key={race.id} race={race} />)}
      </div>
    );
  };

  const getStatusIndicator = () => {
    if (backendStatus.state === 'error') {
      return { color: 'bg-red-500', text: 'Backend Error' };
    }
    if (backendStatus.state === 'starting') {
      return { color: 'bg-yellow-500', text: 'Backend Starting...' };
    }
    if (isLiveMode) {
      return isLiveConnected
        ? { color: 'bg-cyan-500', text: 'Live' }
        : { color: 'bg-yellow-500', text: 'Live Connecting...' };
    }
    switch (connectionStatus) {
      case 'online': return { color: 'bg-green-500', text: 'Online' };
      case 'offline': return { color: 'bg-orange-500', text: 'API Offline' };
      default: return { color: 'bg-yellow-500', text: 'Connecting...' };
    }
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
                    onClick={() => (connectionStatus === 'offline' || backendStatus.state === 'error') && setIsModalOpen(true)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium text-white ${statusColor} ${(connectionStatus === 'offline' || backendStatus.state === 'error') ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}`}
                >
                    <span className={`w-2.5 h-2.5 rounded-full bg-white ${connectionStatus === 'online' ? 'animate-pulse' : ''}`}></span>
                    {statusText}
                </button>
                <LiveModeToggle
                  isLive={isLiveMode}
                  onToggle={setIsLiveMode}
                  isDisabled={backendStatus.state !== 'running' || connectionStatus === 'offline'}
                />
                <button
                    onClick={fetchQualifiedRaces}
                    disabled={isLiveMode || connectionStatus === 'connecting' || backendStatus.state !== 'running'}
                    className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500"
                >
                    Refresh
                </button>
            </div>
        </div>

        <RaceFilters onParamsChange={handleParamsChange} isLoading={connectionStatus === 'connecting'} />

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
        status={{ title: 'Connection Error', details: errorDetails || 'No specific error message was provided.' }}
      />
    </>
  );
});
