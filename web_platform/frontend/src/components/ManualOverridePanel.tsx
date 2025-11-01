// web_platform/frontend/src/components/ManualOverridePanel.tsx
import React, { useState } from 'react';

interface ManualOverridePanelProps {
  adapterName: string;
  attemptedUrl: string;
}

const ManualOverridePanel: React.FC<ManualOverridePanelProps> = ({ adapterName, attemptedUrl }) => {
  const [showPanel, setShowPanel] = useState(true);

  if (!showPanel) {
    return null;
  }

  return (
    <div className="bg-red-900 bg-opacity-50 border border-red-700 p-4 rounded-lg shadow-lg mb-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="font-bold text-red-300">Data Fetch Failed: {adapterName}</h3>
          <p className="text-sm text-red-400">
            The application failed to automatically retrieve data from:{' '}
            <a href={attemptedUrl} target="_blank" rel="noopener noreferrer" className="underline hover:text-red-200">
              {attemptedUrl}
            </a>
          </p>
        </div>
        <button onClick={() => setShowPanel(false)} className="text-red-400 hover:text-red-200 text-2xl">&times;</button>
      </div>
      <div className="mt-4">
        <p className="text-sm text-red-300 mb-2">
          <strong>To resolve this:</strong>
          <ol className="list-decimal list-inside pl-4">
            <li>Click the link above to open the page in a new tab.</li>
            <li>Right-click on the page and select "View Page Source".</li>
            <li>Copy the entire HTML source code.</li>
            <li>Paste the code into the text area below and click "Submit Manual Data".</li>
          </ol>
        </p>
        <textarea
          className="w-full h-24 p-2 bg-gray-900 border border-gray-700 rounded text-gray-300 font-mono text-xs"
          placeholder={`Paste HTML source for ${adapterName} here...`}
        />
        <div className="mt-2 flex gap-2">
          <button
            className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
          >
            Submit Manual Data
          </button>
          <button
            onClick={() => setShowPanel(false)}
            className="px-3 py-1.5 bg-gray-700 text-white rounded hover:bg-gray-600 text-sm"
          >
            Skip for Now
          </button>
        </div>
      </div>
    </div>
  );
};

export default ManualOverridePanel;
