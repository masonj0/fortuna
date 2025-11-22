// web_platform/frontend/src/components/LiveModeToggle.tsx
'use client';

import React from 'react';

interface LiveModeToggleProps {
  isLive: boolean;
  onToggle: (isLive: boolean) => void;
  isDisabled: boolean;
}

export const LiveModeToggle: React.FC<LiveModeToggleProps> = ({ isLive, onToggle, isDisabled }) => {
  const handleToggle = () => {
    if (!isDisabled) {
      onToggle(!isLive);
    }
  };

  return (
    <button
      onClick={handleToggle}
      disabled={isDisabled}
      className={`relative inline-flex items-center h-8 rounded-full w-32 transition-colors duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-800 focus:ring-blue-500 ${
        isDisabled ? 'cursor-not-allowed bg-slate-700' : 'cursor-pointer'
      } ${isLive ? 'bg-green-600' : 'bg-slate-600'}`}
    >
      <span className="sr-only">Toggle Live Mode</span>
      <span
        className={`absolute left-1 top-1 inline-block w-6 h-6 rounded-full bg-white transform transition-transform duration-300 ease-in-out ${
          isLive ? 'translate-x-[104px]' : 'translate-x-0'
        }`}
      />
      <span
        className={`absolute left-8 transition-opacity duration-200 ease-in-out ${
          !isLive && !isDisabled ? 'opacity-100' : 'opacity-50'
        }`}
      >
        Poll
      </span>
      <span
        className={`absolute right-4 transition-opacity duration-200 ease-in-out ${
          isLive && !isDisabled ? 'opacity-100' : 'opacity-50'
        }`}
      >
        ⚡ Live
      </span>
    </button>
  );
};
