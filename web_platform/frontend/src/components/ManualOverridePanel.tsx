// web_platform/frontend/src/components/ManualOverridePanel.tsx
'use client';

import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { saveAs } from 'file-saver';
import * as XLSX from 'xlsx';

// --- API Fetcher Functions ---
const getFailedRequests = async () => {
    const res = await fetch('/api/manual-override/failed-requests');
    if (!res.ok) throw new Error('Network response was not ok');
    return res.json();
};

const getRequestPayload = async (adapterName: string) => {
    const res = await fetch(`/api/manual-override/payload/${adapterName}`);
    if (!res.ok) throw new Error('Network response was not ok');
    return res.json();
};

const postOverrideData = async ({ adapterName, htmlContent }: { adapterName: string; htmlContent: string }) => {
    const res = await fetch(`/api/manual-override/execute/${adapterName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html_content: htmlContent }),
    });
    if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to execute override');
    }
    return res.json();
};

const clearFailedRequest = async (adapterName: string) => {
    const res = await fetch(`/api/manual-override/clear/${adapterName}`, {
        method: 'POST',
    });
    if (!res.ok) throw new Error('Network response was not ok');
    return res.json();
};

// --- Main Component ---
const ManualOverridePanel: React.FC = () => {
    const queryClient = useQueryClient();
    const [selectedAdapter, setSelectedAdapter] = useState<string | null>(null);
    const [htmlContent, setHtmlContent] = useState('');
    const [isPanelVisible, setIsPanelVisible] = useState(false);

    const { data: failedRequests, isLoading, error } = useQuery({
        queryKey: ['failedRequests'],
        queryFn: getFailedRequests,
        refetchInterval: 5000, // Poll every 5 seconds
    });

    const { data: payloadData, isLoading: isPayloadLoading, refetch: refetchPayload } = useQuery({
        queryKey: ['requestPayload', selectedAdapter],
        queryFn: () => {
            if (!selectedAdapter) return Promise.resolve(null);
            return getRequestPayload(selectedAdapter);
        },
        enabled: !!selectedAdapter,
        refetchOnWindowFocus: false,
    });

    const executeMutation = useMutation({
        mutationFn: postOverrideData,
        onSuccess: () => {
            alert('Override executed successfully!');
            queryClient.invalidateQueries({ queryKey: ['failedRequests'] });
            queryClient.invalidateQueries({ queryKey: ['races'] }); // To refresh the main dashboard
            setSelectedAdapter(null);
            setHtmlContent('');
        },
        onError: (error: Error) => {
            alert(`Error executing override: ${error.message}`);
        },
    });

    const clearMutation = useMutation({
        mutationFn: clearFailedRequest,
        onSuccess: () => {
            alert('Failed request cleared.');
            queryClient.invalidateQueries({ queryKey: ['failedRequests'] });
            setSelectedAdapter(null);
        },
    });

    useEffect(() => {
        if (failedRequests && failedRequests.failed_requests.length > 0) {
            setIsPanelVisible(true);
        } else {
            setIsPanelVisible(false);
            setSelectedAdapter(null); // Clear selection when panel hides
        }
    }, [failedRequests]);

    const handleAdapterSelect = (adapterName: string) => {
        setSelectedAdapter(adapterName);
        setHtmlContent(''); // Clear previous content
    };

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                setHtmlContent(e.target?.result as string);
            };
            reader.readAsText(file);
        }
    };

    const handleExportPayload = () => {
        if (!payloadData || !selectedAdapter) return;
        const data = JSON.stringify(payloadData.payload, null, 2);
        const blob = new Blob([data], { type: "application/json;charset=utf-8" });
        saveAs(blob, `${selectedAdapter}_payload.json`);
    };

    if (!isPanelVisible || isLoading) {
        return null;
    }

    if (error) {
        return (
            <div className="bg-red-900 border border-red-700 text-red-100 px-4 py-3 rounded-lg mb-6">
                <strong>Error:</strong> Could not load failed requests. Manual override panel is unavailable.
            </div>
        );
    }

    return (
        <div className="bg-yellow-900/50 border border-yellow-700 rounded-lg p-4 mb-6 text-yellow-100">
            <h3 className="text-lg font-bold mb-2">Manual Override Required</h3>
            <p className="text-sm mb-4">The following data adapters have failed. You can manually provide the required data to proceed.</p>

            <div className="flex gap-2 mb-4">
                {failedRequests.failed_requests.map((name: string) => (
                    <button
                        key={name}
                        onClick={() => handleAdapterSelect(name)}
                        className={`px-3 py-1 rounded-md text-sm transition ${selectedAdapter === name ? 'bg-yellow-600 text-white font-bold' : 'bg-yellow-800 hover:bg-yellow-700'}`}
                    >
                        {name}
                    </button>
                ))}
            </div>

            {selectedAdapter && (
                <div className="bg-slate-800/50 p-4 rounded-md">
                    <h4 className="font-semibold text-white">Override for: {selectedAdapter}</h4>

                    {isPayloadLoading && <p>Loading payload info...</p>}

                    {payloadData && (
                        <div className="my-2 text-xs text-slate-400">
                            <p>Target URL: <a href={payloadData.url} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">{payloadData.url}</a></p>
                            <button onClick={handleExportPayload} className="text-cyan-400 hover:underline mt-1">Export Request Payload</button>
                        </div>
                    )}

                    <div className="mt-4">
                        <label className="block text-sm font-medium mb-1">Upload HTML file or paste content:</label>
                        <input
                            type="file"
                            accept=".html,.txt"
                            onChange={handleFileChange}
                            className="text-sm mb-2 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-yellow-100 file:text-yellow-800 hover:file:bg-yellow-200"
                        />
                        <textarea
                            value={htmlContent}
                            onChange={(e) => setHtmlContent(e.target.value)}
                            placeholder="Paste HTML source here"
                            className="w-full h-32 p-2 bg-slate-900 border border-slate-600 rounded-md text-sm text-slate-200 focus:ring-yellow-500 focus:border-yellow-500"
                        />
                    </div>

                    <div className="flex gap-4 mt-4">
                        <button
                            onClick={() => executeMutation.mutate({ adapterName: selectedAdapter, htmlContent })}
                            disabled={!htmlContent || executeMutation.isPending}
                            className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {executeMutation.isPending ? 'Executing...' : 'Execute Override'}
                        </button>
                        <button
                            onClick={() => clearMutation.mutate(selectedAdapter)}
                            disabled={clearMutation.isPending}
                            className="px-4 py-2 bg-red-700 hover:bg-red-600 rounded-md disabled:opacity-50"
                        >
                            {clearMutation.isPending ? 'Clearing...' : 'Clear Failed Request'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ManualOverridePanel;
