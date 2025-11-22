// web_platform/frontend/src/components/StatusDetailModal.tsx
import React from 'react';

interface StatusDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  status: {
      title: string;
      details: string | Record<string, any>;
  };
}

export const StatusDetailModal: React.FC<StatusDetailModalProps> = ({ isOpen, onClose, status }) => {
  if (!isOpen) {
    return null;
  }

  const { title, details } = status;
  const isDetailsString = typeof details === 'string';

  // Determine status color only if details is an object with a status property
  const statusColor = !isDetailsString && (details.status === 'SUCCESS' || details.status === 'OK')
    ? 'text-green-400'
    : 'text-gray-300'; // Default color

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-6 max-w-lg w-full" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-xl font-bold text-white">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">&times;</button>
        </div>
        <div className="space-y-2 text-sm max-h-96 overflow-y-auto pr-2">
            {isDetailsString ? (
                <div className="text-gray-300 whitespace-pre-wrap bg-gray-900/50 p-4 rounded-md">{details}</div>
            ) : (
                Object.entries(details).map(([key, value]) => (
                    <div key={key} className="grid grid-cols-3 gap-4 border-b border-gray-700/50 py-2">
                    <span className="font-semibold text-gray-400 capitalize">{key.replace(/_/g, ' ')}</span>
                    <span className={`col-span-2 break-words ${key === 'status' ? statusColor : 'text-gray-300'}`}>
                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                    </span>
                    </div>
                ))
            )}
        </div>
        <button
          onClick={onClose}
          className="bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded w-full mt-6"
        >
          Close
        </button>
      </div>
    </div>
  );
};
