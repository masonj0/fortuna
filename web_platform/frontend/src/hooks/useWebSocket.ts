// web_platform/frontend/src/hooks/useWebSocket.ts
'use client';

import { useState, useEffect, useRef } from 'react';

interface WebSocketOptions {
  apiKey: string | null;
  port: number | null;
}

export const useWebSocket = <T>(path: string, options: WebSocketOptions) => {
  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const webSocketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!path || !options.apiKey || !options.port) {
      if (webSocketRef.current) {
        webSocketRef.current.close();
      }
      return;
    }

    const wsUrl = `ws://localhost:${options.port}${path}?api_key=${options.apiKey}`;

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
  }, [url, options.apiKey]);

  return { data, isConnected };
};
