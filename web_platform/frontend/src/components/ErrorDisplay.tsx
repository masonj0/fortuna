// web_platform/frontend/src/components/ErrorDisplay.tsx
'use client';

import React from 'react';

interface ErrorInfo {
  message: string;
  suggestion: string;
  details?: string;
}

interface ErrorDisplayProps {
  error: ErrorInfo;
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error }) => {
  return (
    <div className="bg-red-900/20 border border-red-500/30 text-white rounded-lg p-6 max-w-2xl mx-auto my-8">
      <div className="flex items-center mb-4">
        <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-red-400 mr-4" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
        <h2 className="text-2xl font-bold text-red-400">An Error Occurred</h2>
      </div>
      <p className="text-lg text-slate-300 mb-2">{error.message}</p>
      <p className="text-slate-400 mb-6">{error.suggestion}</p>
      {error.details && (
        <details className="bg-slate-800/50 rounded-lg p-4">
          <summary className="cursor-pointer text-sm text-slate-500 hover:text-white">
            Technical Details
          </summary>
          <pre className="text-xs text-slate-400 mt-2 p-2 bg-black/30 rounded overflow-x-auto">
            <code>{error.details}</code>
          </pre>
        </details>
      )}
    </div>
  );
};
