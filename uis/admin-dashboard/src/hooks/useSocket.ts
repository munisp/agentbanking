/**
 * WebSocket hooks for the real-time admin feeds.
 *
 * The dashboard is served behind the same gateway that proxies the platform's
 * realtime namespaces (`/fraud`, `/chat/<sessionRef>`) as WebSocket endpoints.
 * These hooks open a socket when the page mounts (or when a chat session is
 * established), push inbound events into the shared POS store, and expose
 * send helpers. If the endpoint is unreachable the hook simply leaves the
 * store untouched — pages already render their polled/REST data.
 */

import { useCallback, useEffect, useRef } from "react";
import { usePosStore, type FraudEvent } from "../store/posStore";

function openSocket(path: string): WebSocket | null {
  if (typeof window === "undefined") return null;
  try {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return new WebSocket(`${proto}://${window.location.host}${path}`);
  } catch {
    return null;
  }
}

/** Connects to the /fraud namespace and pushes events into the store. */
export function useFraudSocket() {
  const addFraudEvent = usePosStore(s => s.addFraudEvent);
  const setConnected = usePosStore(s => s.setConnected);

  useEffect(() => {
    const ws = openSocket("/fraud");
    if (!ws) return;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = ev => {
      try {
        const data = JSON.parse(ev.data) as FraudEvent;
        addFraudEvent(data);
      } catch {
        // ignore malformed frames
      }
    };
    return () => {
      ws.close();
      setConnected(false);
    };
  }, [addFraudEvent, setConnected]);
}

export interface ChatSocketApi {
  sendMessage: (content: string) => void;
  sendTyping: () => void;
  sendStopTyping: () => void;
}

/** Connects to the support-chat namespace for the given session ref. */
export function useChatSocket(sessionRef: string | null): ChatSocketApi {
  const addChatMessage = usePosStore(s => s.addChatMessage);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!sessionRef) return;
    const ws = openSocket(`/chat/${encodeURIComponent(sessionRef)}`);
    if (!ws) return;
    wsRef.current = ws;
    ws.onmessage = ev => {
      try {
        addChatMessage(JSON.parse(ev.data));
      } catch {
        // ignore malformed frames
      }
    };
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionRef, addChatMessage]);

  const send = useCallback((payload: Record<string, unknown>) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }, []);

  const sendMessage = useCallback(
    (content: string) => send({ type: "message", sessionRef, content }),
    [send, sessionRef]
  );
  const sendTyping = useCallback(
    () => send({ type: "typing", sessionRef }),
    [send, sessionRef]
  );
  const sendStopTyping = useCallback(
    () => send({ type: "stop_typing", sessionRef }),
    [send, sessionRef]
  );

  return { sendMessage, sendTyping, sendStopTyping };
}

export interface BatchProgressEvent {
  type: "batch.started" | "batch.progress" | "batch.completed" | "batch.failed";
  batchId: string;
  total: number;
  processed: number;
  errors: number;
  percentage: number;
  rate?: number;
  estimatedSecondsRemaining?: number;
  startedAt?: number;
  updatedAt?: number;
}

/**
 * Subscribes to settlement-batch progress events from the /settlement
 * namespace and forwards each parsed event to `onEvent`.
 */
export function useSettlementProgressSocket(
  onEvent: (event: BatchProgressEvent) => void
) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    const ws = openSocket("/settlement");
    if (!ws) return;
    ws.onmessage = ev => {
      try {
        handlerRef.current(JSON.parse(ev.data) as BatchProgressEvent);
      } catch {
        // ignore malformed frames
      }
    };
    return () => ws.close();
  }, []);
}
