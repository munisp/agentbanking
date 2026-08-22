/**
 * useRealtimeNotifications — subscribes to the platform's realtime
 * notification WebSocket (/notifications) for the given channels and
 * maintains the local notification list plus read/unread state.
 */

import React from "react";
import { toast } from "sonner";

export interface RealtimeNotification {
  id: string;
  channel?: string;
  type?: string;
  title?: string;
  message?: string;
  read?: boolean;
  createdAt?: string;
  [key: string]: unknown;
}

export type ConnectionState = "connecting" | "connected" | "disconnected";

export interface UseRealtimeNotificationsOptions {
  channels?: string[];
  /** Cap on retained notifications (most recent first). */
  maxNotifications?: number;
  /** Show a toast for each incoming notification. */
  showToasts?: boolean;
  /** Connect immediately on mount (default true). */
  autoConnect?: boolean;
}

export function useRealtimeNotifications(
  options?: UseRealtimeNotificationsOptions
) {
  const [notifications, setNotifications] = React.useState<
    RealtimeNotification[]
  >([]);
  const [connectionState, setConnectionState] =
    React.useState<ConnectionState>("disconnected");

  const channelsKey = (options?.channels ?? []).join(",");
  const maxNotifications = options?.maxNotifications ?? 200;
  const showToasts = options?.showToasts ?? false;
  const autoConnect = options?.autoConnect ?? true;

  React.useEffect(() => {
    if (!autoConnect) return;
    if (typeof window === "undefined") return;
    let ws: WebSocket | null = null;
    try {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${window.location.host}/notifications`);
    } catch {
      return;
    }
    setConnectionState("connecting");
    ws.onopen = () => {
      setConnectionState("connected");
      const channels = channelsKey ? channelsKey.split(",") : [];
      if (channels.length > 0) {
        ws?.send(JSON.stringify({ type: "subscribe", channels }));
      }
    };
    ws.onclose = () => setConnectionState("disconnected");
    ws.onerror = () => setConnectionState("disconnected");
    ws.onmessage = ev => {
      try {
        const n = JSON.parse(ev.data) as RealtimeNotification;
        setNotifications(prev =>
          [{ read: false, ...n }, ...prev].slice(0, maxNotifications)
        );
        if (showToasts) {
          toast(n.title ?? n.type ?? "Notification", {
            description: typeof n.message === "string" ? n.message : undefined,
          });
        }
      } catch {
        // ignore malformed frames
      }
    };
    return () => ws?.close();
  }, [channelsKey, maxNotifications, showToasts, autoConnect]);

  const markAsRead = React.useCallback(
    (id: string) =>
      setNotifications(prev =>
        prev.map(n => (String(n.id) === String(id) ? { ...n, read: true } : n))
      ),
    []
  );
  const markAllAsRead = React.useCallback(
    () => setNotifications(prev => prev.map(n => ({ ...n, read: true }))),
    []
  );
  const clearAll = React.useCallback(() => setNotifications([]), []);

  const unreadCount = notifications.filter(n => !n.read).length;

  return {
    notifications,
    unreadCount,
    connectionState,
    isConnected: connectionState === "connected",
    markAsRead,
    markRead: markAsRead,
    markAllAsRead,
    clearAll,
  };
}

export function ConnectionStatusBadge({ state }: { state: string }) {
  const color =
    state === "connected"
      ? "bg-emerald-500"
      : state === "connecting"
        ? "bg-amber-500"
        : "bg-gray-400";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={`inline-block h-2 w-2 rounded-full ${color}`} />
      {state === "connected"
        ? "Live"
        : state === "connecting"
          ? "Connecting…"
          : "Offline"}
    </span>
  );
}
