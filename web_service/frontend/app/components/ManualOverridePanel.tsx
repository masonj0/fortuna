// web_platform/frontend/src/components/ManualOverridePanel.tsx
import React, { useState } from 'react';
import { Race } from '../types/racing';

interface ManualOverridePanelProps {
  adapterName: string;
  attemptedUrl: string;
  apiKey: string | null;
  onParseSuccess: (adapterName: string, parsedRaces: Race[]) => void;
}

const ManualOverridePanel: React.FC<ManualOverridePanelProps> = ({
  adapterName,
  attemptedUrl,
  apiKey,
  onParseSuccess,
}) => {
  const [showPanel, setShowPanel] = useState(true);
  const [htmlContent, setHtmlContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!htmlContent.trim()) {
      setError('HTML content cannot be empty.');
      return;
    }
    if (!apiKey) {
      setError('API key is not available. Cannot submit.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch('/api/races/parse-manual', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: JSON.stringify({
          adapter_name: adapterName,
          html_content: htmlContent,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to parse HTML.');
      }

      const parsedRaces: Race[] = await response.json();
      onParseSuccess(adapterName, parsedRaces);
      setShowPanel(false); // Hide panel on success

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred.';
      setError(errorMessage);
      console.error('Manual parse submission failed:', err);
    } finally {
      setIsSubmitting(false);
    }
  };


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
          value={htmlContent}
          onChange={(e) => setHtmlContent(e.target.value)}
          disabled={isSubmitting}
        />
        {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        <div className="mt-2 flex gap-2">
          <button
            onClick={handleSubmit}
            className="px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm disabled:bg-blue-800 disabled:cursor-not-allowed"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : 'Submit Manual Data'}
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
