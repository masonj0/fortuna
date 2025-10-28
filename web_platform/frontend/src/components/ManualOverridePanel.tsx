'use client';

import { useState, useEffect } from 'react';

interface PendingRequest {
  request_id: string;
  adapter_name: string;
  url: string;
  date: string;
  timestamp: string;
  error_message: string;
  status: string;
}

export default function ManualOverridePanel() {
  const [pendingRequests, setPendingRequests] = useState<PendingRequest[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<PendingRequest | null>(null);
  const [manualContent, setManualContent] = useState('');
  const [contentType, setContentType] = useState('html');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);

  useEffect(() => {
    fetchPendingRequests();
    // Poll every 30 seconds
    const interval = setInterval(fetchPendingRequests, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchPendingRequests = async () => {
    try {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      const response = await fetch('/api/manual-overrides/pending', {
        headers: { 'X-API-Key': apiKey || '' }
      });

      if (response.ok) {
        const data = await response.json();
        setPendingRequests(data.pending_requests);
      }
    } catch (error) {
      console.error('Failed to fetch pending requests:', error);
    }
  };

  const handleSubmit = async () => {
    if (!selectedRequest || !manualContent.trim()) return;

    setIsSubmitting(true);
    setMessage(null);

    try {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      const response = await fetch('/api/manual-overrides/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey || ''
        },
        body: JSON.stringify({
          request_id: selectedRequest.request_id,
          content: manualContent,
          content_type: contentType
        })
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Data submitted successfully!' });
        setManualContent('');
        setSelectedRequest(null);
        await fetchPendingRequests();
      } else {
        setMessage({ type: 'error', text: 'Failed to submit data' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error occurred' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = async (requestId: string) => {
    try {
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      await fetch(`/api/manual-overrides/skip/${requestId}`, {
        method: 'POST',
        headers: { 'X-API-Key': apiKey || '' }
      });
      await fetchPendingRequests();
    } catch (error) {
      console.error('Failed to skip request:', error);
    }
  };

  if (pendingRequests.length === 0) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <p className="text-green-800">✓ No manual overrides needed - all fetches successful!</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg p-6 space-y-6">
      <div className="border-b pb-4">
        <h2 className="text-2xl font-bold text-gray-900">Manual Data Override</h2>
        <p className="text-gray-600 mt-1">
          Some data sources are blocking automated access. Please provide the data manually.
        </p>
      </div>

      {message && (
        <div className={`p-4 rounded ${message.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pending Requests List */}
        <div className="lg:col-span-1 space-y-2">
          <h3 className="font-semibold text-gray-900">Pending Requests ({pendingRequests.length})</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {pendingRequests.map((request) => (
              <div
                key={request.request_id}
                className={`p-3 border rounded cursor-pointer hover:bg-gray-50 transition ${
                  selectedRequest?.request_id === request.request_id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                }`}
                onClick={() => setSelectedRequest(request)}
              >
                <div className="font-medium text-sm">{request.adapter_name}</div>
                <div className="text-xs text-gray-600 truncate">{request.url}</div>
                <div className="text-xs text-gray-500 mt-1">{request.date}</div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSkip(request.request_id);
                  }}
                  className="text-xs text-red-600 hover:text-red-800 mt-2"
                >
                  Skip
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Data Entry Panel */}
        <div className="lg:col-span-2 space-y-4">
          {selectedRequest ? (
            <>
              <div className="bg-gray-50 p-4 rounded border border-gray-200">
                <h4 className="font-semibold mb-2">Request Details</h4>
                <div className="text-sm space-y-1">
                  <p><strong>Adapter:</strong> {selectedRequest.adapter_name}</p>
                  <p><strong>URL:</strong> <a href={selectedRequest.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{selectedRequest.url}</a></p>
                  <p><strong>Date:</strong> {selectedRequest.date}</p>
                  <p><strong>Error:</strong> {selectedRequest.error_message}</p>
                </div>
              </div>

              <div className="space-y-2">
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">Content Type</span>
                  <select
                    value={contentType}
                    onChange={(e) => setContentType(e.target.value)}
                    className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  >
                    <option value="html">HTML</option>
                    <option value="json">JSON</option>
                    <option value="text">Plain Text</option>
                  </select>
                </label>

                <label className="block">
                  <span className="text-sm font-medium text-gray-700">Page Content</span>
                  <textarea
                    value={manualContent}
                    onChange={(e) => setManualContent(e.target.value)}
                    placeholder="Paste the page source code here (View Page Source in your browser)"
                    rows={15}
                    className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 font-mono text-sm"
                  />
                </label>

                <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-800">
                  <strong>How to get the content:</strong>
                  <ol className="list-decimal ml-4 mt-2 space-y-1">
                    <li>Click the URL link above to open the page in your browser</li>
                    <li>Right-click anywhere on the page and select "View Page Source" (or press Ctrl+U / Cmd+Option+U)</li>
                    <li>Select all the source code (Ctrl+A / Cmd+A) and copy it</li>
                    <li>Paste it into the text box above</li>
                    <li>Click Submit below</li>
                  </ol>
                </div>

                <button
                  onClick={handleSubmit}
                  disabled={isSubmitting || !manualContent.trim()}
                  className="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
                >
                  {isSubmitting ? 'Submitting...' : 'Submit Data'}
                </button>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              Select a pending request from the list to provide data
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
