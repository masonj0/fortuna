// web_platform/frontend/src/components/LiveRaceDashboard.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { RaceFilters } from './RaceFilters';
import { RaceCard } from './RaceCard';
import { Race } from '../types/racing';

interface RaceFilterParams {
  maxFieldSize: number;
  minFavoriteOdds: number;
  minSecondFavoriteOdds: number;
}

export function LiveRaceDashboard() {
  const [races, setRaces] = useState<Race[]>([]);
  const [criteria, setCriteria] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [params, setParams] = useState<RaceFilterParams>({
    maxFieldSize: 10,
    minFavoriteOdds: 2.5,
    minSecondFavoriteOdds: 4.0,
  });

  const fetchQualifiedRaces = useCallback(async (isInitialLoad = true) => {
    if (isInitialLoad) setLoading(true);
    setError(null);

    try {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      if (!apiKey) {
        throw new Error('API key not configured');
      }

      // Build query string with filter parameters
      const queryParams = new URLSearchParams({
        max_field_size: params.maxFieldSize.toString(),
        min_favorite_odds: params.minFavoriteOdds.toString(),
        min_second_favorite_odds: params.minSecondFavoriteOdds.toString(),
      });

      const response = await fetch(
        `/api/races/qualified/trifecta?${queryParams.toString()}`,
        {
          headers: {
            'X-API-Key': apiKey,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();
      setRaces(data.races || []);
      setCriteria(data.criteria || {});
      setLastUpdate(new Date());
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Failed to fetch qualified races:', err);
    } finally {
      setLoading(false);
    }
  }, [params]);

  // Fetch on mount and set up interval
  useEffect(() => {
    fetchQualifiedRaces(true);
    const interval = setInterval(() => fetchQualifiedRaces(false), 30000);
    return () => clearInterval(interval);
  }, [fetchQualifiedRaces]);

  const handleParamsChange = useCallback((newParams: RaceFilterParams) => {
    setParams(newParams);
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center space-y-2">
        <h1 className="text-4xl font-bold text-white">🏇 Fortuna Faucet</h1>
        <p className="text-slate-400">
          Last updated: {lastUpdate.toLocaleTimeString()}
        </p>
      </div>

      {/* Filter Controls */}
      <RaceFilters onParamsChange={handleParamsChange} isLoading={loading} />

      {/* Status Messages */}
      {loading && (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-2 text-amber-500">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-amber-500 border-t-transparent" />
            <span>Loading qualified races...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded">
          <p className="font-semibold">Error</p>
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Results Summary */}
      {!loading && races.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded px-4 py-3">
          <p className="text-slate-300">
            <span className="font-semibold text-amber-500">{races.length}</span> qualified races found
          </p>
        </div>
      )}

      {/* Races Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {races.map((race) => (
          <RaceCard key={race.id} race={race} />
        ))}
      </div>

      {/* No Results */}
      {!loading && races.length === 0 && !error && (
        <div className="text-center py-12">
          <p className="text-slate-400">No races match your criteria</p>
          <p className="text-xs text-slate-500 mt-2">
            Try adjusting the filter parameters
          </p>
        </div>
      )}
    </div>
  );
}
