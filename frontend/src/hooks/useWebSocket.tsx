import { useEffect, useRef, useState, useCallback } from "react";

// Read API url and construct corresponding WebSocket URL
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws";

export interface WsMessage<T = any> {
  event: string;
  data: T;
}

export function useWebSocket(onMessage?: (msg: WsMessage) => void) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const listenersRef = useRef<Set<(msg: WsMessage) => void>>(new Set());

  // Register dynamic message listeners
  const addListener = useCallback((cb: (msg: WsMessage) => void) => {
    listenersRef.current.add(cb);
    return () => {
      listenersRef.current.delete(cb);
    };
  }, []);

  // Send messages over the active connection
  const send = useCallback((msg: WsMessage) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      console.warn("WebSocket is not connected. Message not sent.");
    }
  }, []);

  // Keep onMessage updated in listeners set
  useEffect(() => {
    if (onMessage) {
      listenersRef.current.add(onMessage);
    }
    return () => {
      if (onMessage) {
        listenersRef.current.delete(onMessage);
      }
    };
  }, [onMessage]);

  // Establish connection and assign event triggers
  const connect = useCallback(() => {
    if (wsRef.current) return;

    try {
      console.log(`[WebSocket] Connecting to ${WS_URL}...`);
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log("[WebSocket] Connection established.");
      };

      ws.onmessage = (event) => {
        try {
          const parsed: WsMessage = JSON.parse(event.data);
          listenersRef.current.forEach((listener) => listener(parsed));
        } catch (err) {
          console.error("[WebSocket] Failed to parse message data", err);
        }
      };

      ws.onclose = (e) => {
        setIsConnected(false);
        wsRef.current = null;
        console.log(`[WebSocket] Connection closed: ${e.reason || "No reason specified"}. Reconnecting in 5s...`);
        
        // Prevent duplicate timelines
        if (reconnectTimeoutRef.current) window.clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 5000);
      };

      ws.onerror = () => {
        // Avoid duplicate console error logs as the browser already native-logs connection failures
        ws.close();
      };
    } catch (e) {
      console.error("[WebSocket] Failed to initialize connection:", e);
    }
  }, []);

  // Self-start connection on hook mount and disconnect on unmount
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        const socket = wsRef.current;
        // Detach all handlers before closing to prevent Strict Mode callbacks in unmounted states
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        
        if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
          socket.close();
        }
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { isConnected, send, addListener };
}
