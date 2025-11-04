// web_platform/frontend/src/hooks/useWebSocket.ts
'use client';

import { useState, useEffect, useRef } from 'react';

interface WebSocketOptions {
  apiKey: string | null;
}

export const useWebSocket = <T>(url: string, options: WebSocketOptions) => {
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const webSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!url || !options.apiKey) {
      if (webSocketRef.current) {
        webSocketRef.current.close();
      }
      return;
    }

    const wsUrl = new URL(url, window.location.href);
    wsUrl.protocol = wsUrl.protocol.replace('http', 'ws');
    wsUrl.searchParams.append('api_key', options.apiKey);

    const ws = new WebSocket(wsUrl.toString());
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
  }, [url, options.apiKey]);

  return { data, isConnected };
};
