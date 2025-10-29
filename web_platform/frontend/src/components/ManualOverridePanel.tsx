// web_platform/frontend/src/components/ManualOverridePanel.tsx
import React, { useState } from 'react';

const ADAPTERS = [
  "AtTheRaces", "Betfair", "BetfairGreyhound", "Brisnet", "DRF", "Equibase",
  "FanDuel", "GbgbApi", "Greyhound", "Harness", "HorseRacingNation", "NYRABets",
  "Oddschecker", "Punters", "RacingAndSports", "RacingAndSportsGreyhound",
  "RacingPost", "RacingTV", "SportingLife", "Tab", "TheRacingApi",
  "Timeform", "TwinSpires", "TVG", "Xpressbet", "PointsBetGreyhound"
];

const ManualOverridePanel: React.FC = () => {
  const [selectedAdapter, setSelectedAdapter] = useState<string>(ADAPTERS[0]);
  const [content, setContent] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(true);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFeedbackMessage(null);

    const apiKey = process.env.NEXT_PUBLIC_API_KEY;
    if (!apiKey) {
      setFeedbackMessage('Error: API key is not configured.');
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await fetch('/api/manual-override', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: JSON.stringify({
          adapter_name: selectedAdapter,
          content: content,
        }),
      });

      if (response.ok) {
        setFeedbackMessage(`Success! Override for ${selectedAdapter} submitted.`);
        setContent('');
      } else {
        const errorData = await response.json();
        setFeedbackMessage(`Error: ${errorData.detail || 'An unknown error occurred.'}`);
      }
    } catch (error) {
      setFeedbackMessage('Error: Failed to connect to the backend.');
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setFeedbackMessage(null), 5000);
    }
  };

  return (
    <div className="bg-gray-800 text-white p-4 rounded-lg shadow-lg mt-4">
      <h2
        className="text-lg font-bold mb-2 cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        Manual Override Panel {isCollapsed ? '▼' : '▲'}
      </h2>
      {!isCollapsed && (
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label htmlFor="adapter-select" className="block text-sm font-medium mb-1">
              Select Adapter
            </label>
            <select
              id="adapter-select"
              value={selectedAdapter}
              onChange={(e) => setSelectedAdapter(e.target.value)}
              className="w-full p-2 bg-gray-700 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {ADAPTERS.map((adapter) => (
                <option key={adapter} value={adapter}>
                  {adapter}
                </option>
              ))}
            </select>
          </div>
          <div className="mb-4">
            <label htmlFor="content-textarea" className="block text-sm font-medium mb-1">
              Paste Page Content (HTML/JSON)
            </label>
            <textarea
              id="content-textarea"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={`Paste the full page source for ${selectedAdapter} here...`}
              rows={10}
              className="w-full p-2 bg-gray-700 rounded border border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting || !content}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:bg-gray-500"
          >
            {isSubmitting ? 'Submitting...' : 'Submit Override'}
          </button>
          {feedbackMessage && (
            <p className={`mt-2 text-sm ${feedbackMessage.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
              {feedbackMessage}
            </p>
          )}
        </form>
      )}
    </div>
  );
};

export default ManualOverridePanel;
