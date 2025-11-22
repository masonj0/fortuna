// web_platform/frontend/src/hooks/useWebSocket.ts
'use client';

import { useState, useEffect, useRef } from 'react';

interface WebSocketOptions {
  apiKey: string | null;
  port?: number | null; // Port is now optional
}

export const useWebSocket = <T>(path: string, options: WebSocketOptions) => {
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const webSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!path || !options.apiKey) {
      console.log('[useWebSocket] Missing path or API key. Aborting connection.');
      if (webSocketRef.current) {
        webSocketRef.current.close();
      }
      return;
    }

    // Use relative URL for same-origin, or build full URL if port is provided
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = options.port ? `localhost:${options.port}` : window.location.host;
    const wsUrl = `${protocol}//${host}${path}?api_key=${options.apiKey}`;

    console.log(`[useWebSocket] Attempting to connect to: ${wsUrl}`);

    const ws = new WebSocket(wsUrl);
    webSocketRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connection established.');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const messageData = JSON.parse(event.data);
        setData(messageData);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = (event) => {
      console.log(`WebSocket connection closed: ${event.code} ${event.reason}`);
      setIsConnected(false);
      webSocketRef.current = null;
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [path, options.apiKey, options.port]);

  return { data, isConnected };
};
