// web_platform/frontend/src/components/LiveRaceDashboard.tsx
'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { RaceFilters } from './RaceFilters';
import { RaceCard } from './RaceCard';
import { RaceCardSkeleton } from './RaceCardSkeleton';
import { EmptyState } from './EmptyState';
import { ErrorDisplay } from './ErrorDisplay';
import { Race, SourceInfo, AdapterError, AggregatedRacesResponse } from '../types/racing';
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
    throw new Error(JSON.stringify(errorData));
  }
  return response.json();
};

const fetchQualifiedRaces = async (apiKey: string | null, params: RaceFilterParams): Promise<AggregatedRacesResponse> => {
  if (!apiKey) {
    throw new Error('API key not available');
  }
  // NOTE: The endpoint is now the general /api/races, not the qualified one.
  const url = new URL('/api/races', window.location.origin);

  const response = await fetch(url.toString(), {
    headers: { 'X-API-Key': apiKey },
  });

  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(JSON.stringify(errorData));
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

const useBackendStatus = () => {
  const [backendStatus, setBackendStatus] = useState<BackendStatus>({ state: 'starting', logs: [] });

  useEffect(() => {
    let isMounted = true;

    const getInitialStatus = async () => {
      if (window.electronAPI?.getBackendStatus) {
        try {
          const initialStatus = await window.electronAPI.getBackendStatus();
          if (isMounted) setBackendStatus(initialStatus);
        } catch (error) {
          console.error("Failed to get initial backend status:", error);
          if (isMounted) setBackendStatus({ state: 'error', logs: ['Failed to query backend status from main process.'] });
        }
      } else {
          setBackendStatus({ state: 'running', logs: ['In a web-only environment, backend is assumed to be running.'] });
      }
    };

    if (window.electronAPI?.onBackendStatusUpdate) {
      const unsubscribe = window.electronAPI.onBackendStatusUpdate((status: BackendStatus) => {
        if (isMounted) setBackendStatus(status);
      });
      getInitialStatus();
      return () => {
        isMounted = false;
        if (typeof unsubscribe === 'function') {
          unsubscribe();
        }
      };
    } else {
        getInitialStatus();
    }
  }, []);

  return backendStatus;
};

export const LiveRaceDashboard = React.memo(() => {
  const [races, setRaces] = useState<Race[]>([]);
  const [adapterErrors, setAdapterErrors] = useState<AdapterError[]>([]);
  const backendStatus = useBackendStatus();
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

  const [params, setParams] = useState<RaceFilterParams>({
    maxFieldSize: 10,
    minFavoriteOdds: 2.5,
    minSecondFavoriteOdds: 4.0,
  });

  const {
    data,
    status: connectionStatus,
    error: errorDetails,
    refetch,
  } = useQuery({
    queryKey: ['aggregatedRaces', apiKey], // Simplified query key
    queryFn: () => fetchQualifiedRaces(apiKey, params),
    enabled: backendStatus.state === 'running' && !!apiKey,
    refetchOnWindowFocus: true,
  });

  // Update state when data is successfully fetched
  useEffect(() => {
    if (data) {
      setRaces(data.races || []);
      setAdapterErrors(data.errors || []);
      setLastUpdate(new Date());
    }
  }, [data]);

  const { data: liveData, isConnected: isLiveConnected } = useWebSocket<AggregatedRacesResponse>(
    apiKey ? '/ws/live-updates' : '',
    { apiKey }
  );

  // Effect to update state when new live data arrives
  useEffect(() => {
    if (liveData) {
      console.log('Received live data update:', liveData);
      // Update the query cache and local state with the new data
      queryClient.setQueryData(['aggregatedRaces', apiKey], liveData);
      setRaces(liveData.races || []);
      setAdapterErrors(liveData.errors || []);
      setLastUpdate(new Date());
    }
  }, [liveData, queryClient, apiKey]);

  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);


  const handleParamsChange = useCallback((newParams: RaceFilterParams) => {
    setParams(newParams);
  }, []);

  const handleParseSuccess = (adapterName: string, parsedRaces: Race[]) => {
    queryClient.setQueryData(['qualifiedRaces', apiKey, params], (oldData: { races: Race[], source_info: SourceInfo[] } | undefined) => {
      if (!oldData) return { races: parsedRaces, source_info: [] };

      // 1. Remove the placeholder error card for this adapter
      const otherRaces = oldData.races.filter(race => race.source !== adapterName);

      // 2. Merge the new races in
      const updatedRaces = [...otherRaces, ...parsedRaces].sort(
        (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      );

      // 3. Update source_info to remove the failed source
      const updatedSourceInfo = oldData.source_info.filter(s => s.name !== adapterName);

      return { races: updatedRaces, source_info: updatedSourceInfo };
    });
  };

  const renderContent = () => {
    // Priority 1: Backend process has failed.
    if (backendStatus.state === 'error') {
      return <BackendErrorPanel logs={backendStatus.logs} onRestart={() => window.electronAPI.restartBackend()} />;
    }

    if (backendStatus.state === 'stopped') {
        return <EmptyState
            title="Backend Service Stopped"
            message="The backend data service is not running. Please start it to see live race data."
            actionButton={<button onClick={() => window.electronAPI.restartBackend()} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Start Backend Service</button>}
        />;
    }

    // Priority 2: Backend is starting or initial fetch is happening.
    const isLoading = backendStatus.state === 'starting' || (connectionStatus === 'pending' && !data);
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {[...Array(8)].map((_, i) => <RaceCardSkeleton key={i} />)}
            </div>
        );
    }

    // Priority 3: API connection is offline.
    if (connectionStatus === 'error') {
      try {
        const errorInfo = JSON.parse((errorDetails as Error).message);
        return <ErrorDisplay error={errorInfo.error} />;
      } catch (e) {
        return <EmptyState
            title="API Connection Offline"
            message={(errorDetails as Error)?.message || "The backend is running, but the dashboard could not connect to its API."}
            actionButton={<button onClick={() => refetch()} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Retry Connection</button>}
        />;
      }
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
    if (backendStatus.state === 'stopped') {
        return { color: 'bg-gray-500', text: 'Stopped' };
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

        <RaceFilters onParamsChange={handleParamsChange} isLoading={connectionStatus === 'pending'} refetch={refetch} />

        {adapterErrors.map(error => (
          <ManualOverridePanel
            key={error.adapterName}
            adapterName={error.adapterName}
            attemptedUrl={error.attemptedUrl || 'URL not available'}
            apiKey={apiKey}
            onParseSuccess={handleParseSuccess}
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
