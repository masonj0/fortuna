import React from 'react';

interface ManualOverridePanelProps {
  adapterName: string;
  attemptedUrl: string;
}

const ManualOverridePanel: React.FC<ManualOverridePanelProps> = ({ adapterName, attemptedUrl }) => {
  return (
    <div className="bg-red-900 border border-red-600 rounded-lg p-4 my-4">
      <h3 className="text-lg font-bold text-white">
        ⚠️ Fetch Failed: {adapterName}
      </h3>
      <p className="text-red-200 mt-2">
        The automated data fetch for this source failed, likely due to a temporary block (403 Forbidden). You can manually retrieve the data by following the steps below.
      </p>
      <ol className="list-decimal list-inside text-red-200 mt-2 space-y-1">
        <li>Copy the URL from the text area below.</li>
        <li>Paste it into a new browser tab to view the page content.</li>
        <li>Select all the content on the page (Ctrl+A) and copy it (Ctrl+C).</li>
        <li>Return here and paste the content into this text area to proceed.</li>
      </ol>
      <textarea
        className="w-full h-24 mt-3 p-2 font-mono text-sm bg-gray-900 text-white border border-gray-600 rounded"
        defaultValue={attemptedUrl}
      />
    </div>
  );
};

export default ManualOverridePanel;
