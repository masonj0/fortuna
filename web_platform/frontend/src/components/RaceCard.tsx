// web_platform/frontend/src/components/RaceCard.tsx
'use client';

import React, { useState, useEffect } from 'react';
import type { Race, Runner } from '../types/racing';

// Local types removed, now importing from '../types/racing'

interface RaceCardProps {
  race: Race;
}

const Countdown: React.FC<{ startTime: string }> = ({ startTime }) => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const getCountdown = (startTimeStr: string) => {
    const postTime = new Date(startTimeStr);
    const diff = postTime.getTime() - currentTime.getTime();

    if (diff <= 0) return { text: "RACE CLOSED", color: "text-gray-500" };

    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0');

    let color = "text-green-400";
    if (minutes < 2) color = "text-red-500 font-bold animate-pulse";
    else if (minutes < 10) color = "text-yellow-400";

    return { text: `${minutes}:${seconds} to post`, color };
  };

  const countdown = getCountdown(startTime);

  return (
    <span className={`font-mono text-sm ${countdown.color}`}>{countdown.text}</span>
  );
};

export const RaceCard: React.FC<RaceCardProps> = ({ race }) => {
  const activeRunners = race.runners.filter(r => !r.scratched);
  activeRunners.sort((a, b) => a.number - b.number);

  const getUniqueSourcesCount = (runners: Runner[]): number => {
    const sources = new Set();
    runners.forEach(runner => {
      if (runner.odds) {
        Object.keys(runner.odds).forEach(source => sources.add(source));
      }
    });
    return sources.size;
  };

  const getBestOdds = (runner: Runner): { odds: number, source: string } | null => {
    if (!runner.odds) return null;
  const validOdds = Object.values(runner.odds).filter(o => o.win !== null && o.win !== undefined && o.win < 999);
    if (validOdds.length === 0) return null;
  const best = validOdds.reduce((min, o) => (o.win ?? 999) < (min.win ?? 999) ? o : min);
    return { odds: best.win!, source: best.source };
  };

  return (
    <div className={`race-card-enhanced border rounded-lg p-4 bg-gray-800 shadow-lg hover:border-purple-500 transition-all ${race.qualification_score && race.qualification_score >= 80 ? 'card-premium' : 'border-gray-700'}`}>
      {/* Header with Smart Status Indicators */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-2xl font-bold text-white">{race.venue}</h2>
            <div className="flex gap-2 text-sm text-gray-400">
              <span>Race {race.race_number}</span>
              <span>•</span>
              <Countdown startTime={race.start_time} />
            </div>
            {race.favorite && (
              <div className="flex items-center gap-2 mt-2 text-sm text-yellow-400">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
                <span className="font-semibold">Favorite: {race.favorite.name}</span>
              </div>
            )}
          </div>
        </div>

        {race.qualification_score && (
          <div className={`px-4 py-2 rounded-full text-center ${
            race.qualification_score >= 80 ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
            race.qualification_score >= 60 ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
            'bg-green-500/20 text-green-400 border border-green-500/30'
          }`}>
            <div className="font-bold text-lg">{race.qualification_score.toFixed(0)}%</div>
            <div className="text-xs">Score</div>
          </div>
        )}
      </div>

      {/* Race Conditions Grid */}
      <div className="grid grid-cols-4 gap-2 mb-4 p-3 bg-gray-800/50 rounded-lg">
        <div className="text-center">
          <div className="text-xs text-gray-400">Distance</div>
          <div className="text-sm font-semibold text-white">{race.distance || 'N/A'}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-400">Surface</div>
          <div className="text-sm font-semibold text-white">{race.surface || 'Dirt'}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-400">Field</div>
          <div className="text-sm font-semibold text-white">{activeRunners.length}</div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-400">Sources</div>
          <div className="text-sm font-semibold text-white">{getUniqueSourcesCount(race.runners)}</div>
        </div>
      </div>

      {/* Interactive Runner Rows */}
      <div className="runners-table space-y-2">
        {activeRunners.map((runner, idx) => {
          const bestOddsInfo = getBestOdds(runner);
          return (
            <div key={runner.number} className="runner-row group hover:bg-purple-500/10 transition-all rounded-md p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all group-hover:scale-110 text-gray-900 shadow-lg ${idx === 0 ? 'bg-gradient-to-br from-yellow-400 to-yellow-600 shadow-yellow-500/50' : idx === 1 ? 'bg-gradient-to-br from-gray-300 to-gray-500 shadow-gray-400/50' : idx === 2 ? 'bg-gradient-to-br from-orange-400 to-orange-600 shadow-orange-500/50' : 'bg-gray-700 text-gray-300'}`}>
                    {runner.number}
                  </div>
                  <div className="flex flex-col">
                    <span className="font-bold text-white text-lg">{runner.name}</span>
                    <div className="flex gap-3 text-sm text-gray-400">
                      {runner.jockey && <span>J: {runner.jockey}</span>}
                      {runner.trainer && <span>T: {runner.trainer}</span>}
                    </div>
                  </div>
                </div>
                {bestOddsInfo && (
                  <div className="text-right">
                    <div className="text-2xl font-bold text-emerald-400">{bestOddsInfo.odds.toFixed(2)}</div>
                    <div className="text-xs text-gray-500">via {bestOddsInfo.source}</div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};