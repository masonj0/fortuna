// web_platform/frontend/src/components/RaceFilters.tsx
'use client';

import { useState, useCallback } from 'react';
import { Settings, RotateCcw } from 'lucide-react';

interface FilterParams {
  maxFieldSize: number;
  minFavoriteOdds: number;
  minSecondFavoriteOdds: number;
}

export interface RaceFiltersProps {
  onParamsChange: (params: FilterParams) => void;
  isLoading: boolean;
}

const DEFAULT_PARAMS: FilterParams = {
  maxFieldSize: 10,
  minFavoriteOdds: 2.5,
  minSecondFavoriteOdds: 4.0,
};

export function RaceFilters({ onParamsChange, isLoading }: RaceFiltersProps) {
  const [params, setParams] = useState<FilterParams>(DEFAULT_PARAMS);
  const [isExpanded, setIsExpanded] = useState(false);

  // Handle individual parameter changes
  const handleChange = useCallback((key: keyof FilterParams, value: number) => {
    setParams(prev => {
      const updated = { ...prev, [key]: value };
      onParamsChange(updated);
      return updated;
    });
  }, [onParamsChange]);

  // Reset to defaults
  const handleReset = useCallback(() => {
    setParams(DEFAULT_PARAMS);
    onParamsChange(DEFAULT_PARAMS);
  }, [onParamsChange]);

  return (
    <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-lg p-4 mb-6 border border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-amber-500" />
          <h3 className="text-lg font-semibold text-white">Race Filters</h3>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-sm text-slate-400 hover:text-slate-200 transition"
        >
          {isExpanded ? 'Hide' : 'Show'}
        </button>
      </div>

      {isExpanded && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 border-t border-slate-700">
          {/* Max Field Size */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">
              Max Field Size
              <span className="text-amber-500 ml-2">{params.maxFieldSize}</span>
            </label>
            <input
              type="range"
              min="2"
              max="20"
              value={params.maxFieldSize}
              onChange={(e) => handleChange('maxFieldSize', parseInt(e.target.value))}
              disabled={isLoading}
              className="w-full accent-amber-500 cursor-pointer disabled:opacity-50"
            />
            <p className="text-xs text-slate-500">Filters races with larger fields</p>
          </div>

          {/* Min Favorite Odds */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">
              Min Favorite Odds
              <span className="text-amber-500 ml-2">{params.minFavoriteOdds.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="1.5"
              max="5"
              step="0.1"
              value={params.minFavoriteOdds}
              onChange={(e) => handleChange('minFavoriteOdds', parseFloat(e.target.value))}
              disabled={isLoading}
              className="w-full accent-amber-500 cursor-pointer disabled:opacity-50"
            />
            <p className="text-xs text-slate-500">Higher = pickier favorites</p>
          </div>

          {/* Min Second Favorite Odds */}
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">
              Min 2nd Favorite Odds
              <span className="text-amber-500 ml-2">{params.minSecondFavoriteOdds.toFixed(2)}</span>
            </label>
            <input
              type="range"
              min="2.0"
              max="8"
              step="0.1"
              value={params.minSecondFavoriteOdds}
              onChange={(e) => handleChange('minSecondFavoriteOdds', parseFloat(e.target.value))}
              disabled={isLoading}
              className="w-full accent-amber-500 cursor-pointer disabled:opacity-50"
            />
            <p className="text-xs text-slate-500">Higher = better odds separation</p>
          </div>

          {/* Reset Button */}
          <div className="md:col-span-3 flex justify-end pt-4 border-t border-slate-700">
            <button
              onClick={handleReset}
              disabled={isLoading}
              className="inline-flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-sm font-medium transition disabled:opacity-50"
            >
              <RotateCcw className="w-4 h-4" />
              Reset to Defaults
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
