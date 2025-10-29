// web_platform/frontend/src/components/LiveRaceDashboard.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { RaceFilters } from './RaceFilters';
import { RaceCard } from './RaceCard';
import { RaceCardSkeleton } from './RaceCardSkeleton';
import { EmptyState } from './EmptyState';
import { Race, SourceInfo } from '../types/racing';
import { StatusDetailModal } from './StatusDetailModal';
import ManualOverridePanel from './ManualOverridePanel';

type ConnectionStatus = 'connecting' | 'online' | 'offline';

interface RaceFilterParams {
  maxFieldSize: number;
  minFavoriteOdds: number;
  minSecondFavoriteOdds: number;
}

export function LiveRaceDashboard() {
  const [races, setRaces] = useState<Race[]>([]);
  const [failedSources, setFailedSources] = useState<SourceInfo[]>([]);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [errorDetails, setErrorDetails] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [params, setParams] = useState<RaceFilterParams>({
    maxFieldSize: 10,
    minFavoriteOdds: 2.5,
    minSecondFavoriteOdds: 4.0,
  });
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchQualifiedRaces = useCallback(async () => {
    if (connectionStatus !== 'connecting') {
      setConnectionStatus('connecting');
    }
    setErrorDetails(null);
    setFailedSources([]); // Clear previous failures on each fetch

    try {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      if (!apiKey) throw new Error('API key not configured');

      const queryParams = new URLSearchParams({
        max_field_size: params.maxFieldSize.toString(),
        min_favorite_odds: params.minFavoriteOdds.toString(),
        min_second_favorite_odds: params.minSecondFavoriteOdds.toString(),
      });

      const response = await fetch(`/api/races/qualified/trifecta?${queryParams.toString()}`, {
        headers: { 'X-API-Key': apiKey, 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`The backend service is currently unavailable (HTTP ${response.status}). Please try again shortly.`);
      }

      const data = await response.json();
      setRaces(data.races || []);

      // Filter out and store the sources that have failed
      const failed = data.source_info?.filter((source: SourceInfo) => source.status === 'FAILED' && source.attemptedUrl) || [];
      setFailedSources(failed);

      setLastUpdate(new Date());
      setConnectionStatus('online');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
      setErrorDetails(errorMessage);
      setConnectionStatus('offline');
      console.error('Failed to fetch qualified races:', err);
    } finally {
      setIsInitialLoad(false);
    }
  }, [params, connectionStatus]);

  useEffect(() => {
    // This effect runs once on mount to set up the backend status listener.
    if (window.electronAPI && typeof window.electronAPI.onBackendStatus === 'function') {
      window.electronAPI.onBackendStatus((statusUpdate) => {
        console.log('Received backend status update:', statusUpdate);
        setConnectionStatus(statusUpdate.status);
        if (statusUpdate.status === 'offline') {
          setErrorDetails(statusUpdate.error || 'The backend failed to start.');
        } else {
          // If the backend comes online, trigger an immediate fetch.
          fetchQualifiedRaces();
        }
      });
    }

    // Initial fetch is now triggered by the backend status becoming 'online'.
    // A periodic refresh interval is still useful for when the app is online.
    const interval = setInterval(() => {
        if(connectionStatus === 'online') {
            fetchQualifiedRaces();
        }
    }, 30000); // 30-second refresh
    return () => clearInterval(interval);
  }, [fetchQualifiedRaces, connectionStatus]); // Rerun if fetchQualifiedRaces changes

  const handleParamsChange = useCallback((newParams: RaceFilterParams) => {
    setParams(newParams);
  }, []);

  const renderContent = () => {
    // Priority 1: Handle offline state. This should be checked first.
    if (connectionStatus === 'offline') {
        return <EmptyState
            title="Backend Service Offline"
            message={errorDetails || "Could not connect to the backend data service. Please ensure it is running and try again."}
            actionButton={<button onClick={fetchQualifiedRaces} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Retry Connection</button>}
        />;
    }

    // Priority 2: Handle loading state (initial load OR subsequent refreshes)
    if (isInitialLoad || connectionStatus === 'connecting') {
      return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RaceCardSkeleton />
          <RaceCardSkeleton />
          <RaceCardSkeleton />
          <RaceCardSkeleton />
        </div>
      );
    }

    // Priority 3: Handle empty state when online but no races match criteria
    if (races.length === 0) {
      return <EmptyState
        title="No Races Found"
        message="No races matched the current filter criteria. Try adjusting the filters."
      />;
    }

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {races.map((race) => (
          <RaceCard key={race.id} race={race} />
        ))}
      </div>
    );
  };

  const getStatusIndicator = () => {
    switch (connectionStatus) {
      case 'online':
        return { color: 'bg-green-500', text: 'Online' };
      case 'offline':
        return { color: 'bg-red-500', text: 'Offline' };
      default:
        return { color: 'bg-yellow-500', text: 'Connecting...' };
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
                    onClick={() => connectionStatus === 'offline' && setIsModalOpen(true)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium text-white ${statusColor} ${connectionStatus === 'offline' ? 'cursor-pointer hover:opacity-80' : 'cursor-default'}`}
                >
                    <span className="w-2.5 h-2.5 rounded-full bg-white animate-pulse"></span>
                    {statusText}
                </button>
                <button onClick={fetchQualifiedRaces} disabled={connectionStatus === 'connecting'} className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-500">
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
        status={{ title: 'Backend Connection Error', details: errorDetails || 'No specific error message was provided.' }}
      />
    </>
  );
}
