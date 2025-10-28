// web_platform/frontend/src/components/EmptyState.tsx
import React from 'react';

interface EmptyStateProps {
  title: string;
  message: string;
  actionButton?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, message, actionButton }) => {
  return (
    <div className="text-center p-8 bg-gray-800/50 border border-gray-700 rounded-lg mt-8">
      <svg
        className="mx-auto h-12 w-12 text-gray-500"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          vectorEffect="non-scaling-stroke"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <h3 className="mt-2 text-xl font-semibold text-white">{title}</h3>
      <p className="mt-1 text-md text-gray-400">
        {message}
      </p>
      {actionButton && <div className="mt-6">{actionButton}</div>}
    </div>
  );
};
