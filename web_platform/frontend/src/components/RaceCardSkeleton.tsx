// web_platform/frontend/src/components/RaceCardSkeleton.tsx
import React from 'react';

export const RaceCardSkeleton: React.FC = () => {
  return (
    <div className="race-card-skeleton border border-gray-700 rounded-lg p-4 bg-gray-800 shadow-lg animate-pulse">
      {/* Skeleton Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div>
            <div className="h-7 w-28 bg-gray-700 rounded-md"></div>
            <div className="h-4 w-40 bg-gray-700 rounded-md mt-2"></div>
          </div>
        </div>
        <div className="h-16 w-16 bg-gray-700 rounded-full"></div>
      </div>

      {/* Skeleton Info Grid */}
      <div className="grid grid-cols-4 gap-2 mb-4 p-3 bg-gray-800/50 rounded-lg">
        <div className="text-center">
          <div className="h-3 w-12 mx-auto bg-gray-700 rounded-md"></div>
          <div className="h-4 w-8 mx-auto bg-gray-700 rounded-md mt-2"></div>
        </div>
        <div className="text-center">
          <div className="h-3 w-12 mx-auto bg-gray-700 rounded-md"></div>
          <div className="h-4 w-8 mx-auto bg-gray-700 rounded-md mt-2"></div>
        </div>
        <div className="text-center">
          <div className="h-3 w-10 mx-auto bg-gray-700 rounded-md"></div>
          <div className="h-4 w-6 mx-auto bg-gray-700 rounded-md mt-2"></div>
        </div>
        <div className="text-center">
          <div className="h-3 w-10 mx-auto bg-gray-700 rounded-md"></div>
          <div className="h-4 w-6 mx-auto bg-gray-700 rounded-md mt-2"></div>
        </div>
      </div>

      {/* Skeleton Runner Rows */}
      <div className="space-y-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="runner-row rounded-md p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4 flex-1">
                <div className="w-10 h-10 rounded-full bg-gray-700"></div>
                <div className="flex flex-col space-y-2">
                  <div className="h-5 w-32 bg-gray-700 rounded-md"></div>
                  <div className="h-4 w-40 bg-gray-700 rounded-md"></div>
                </div>
              </div>
              <div className="text-right">
                <div className="h-6 w-16 bg-gray-700 rounded-md"></div>
                <div className="h-3 w-12 bg-gray-700 rounded-md mt-2"></div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
