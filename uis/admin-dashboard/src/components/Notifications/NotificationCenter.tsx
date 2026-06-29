import {
    AlertTriangle,
    Bell,
    CheckCircle,
    Eye,
    Info,
    MapPin,
    RefreshCw,
    Trash2,
    Wifi,
    WifiOff,
    XCircle,
} from "lucide-react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../utils/api";

type NotificationType = "success" | "error" | "warning" | "info" | "geofence";

interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  time: string;
  read: boolean;
  raw?: Record<string, unknown>;
}

const REALTIME_BASE = (
  import.meta.env.VITE_AGENT_API_URL ?? "https://54agent.upi.dev"
)
  .replace(/^https?/, "wss")
  .replace(/\/+$/, "");

const getIcon = (type: NotificationType) => {
  switch (type) {
    case "success":
      return <CheckCircle className="w-6 h-6 text-green-500" />;
    case "error":
      return <XCircle className="w-6 h-6 text-red-500" />;
    case "warning":
      return <AlertTriangle className="w-6 h-6 text-yellow-500" />;
    case "geofence":
      return <MapPin className="w-6 h-6 text-orange-500" />;
    default:
      return <Info className="w-6 h-6 text-[var(--tenant-primary-color,#002082)]" />;
  }
};

const getBg = (type: NotificationType) => {
  switch (type) {
    case "success":
      return "bg-green-50 border-green-200";
    case "error":
      return "bg-red-50 border-red-200";
    case "warning":
      return "bg-yellow-50 border-yellow-200";
    case "geofence":
      return "bg-orange-50 border-orange-200";
    default:
      return "bg-[rgba(0,79,113,0.05)] border-[rgba(0,79,113,0.2)]";
  }
};

const relativeTime = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} minute${mins > 1 ? "s" : ""} ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} hour${hrs > 1 ? "s" : ""} ago`;
  return `${Math.floor(hrs / 24)} day(s) ago`;
};

const NotificationCenter: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [wsStatus, setWsStatus] = useState<
    "connecting" | "connected" | "disconnected"
  >("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const addNotification = useCallback((n: Notification) => {
    setNotifications((prev) => {
      if (prev.some((p) => p.id === n.id)) return prev;
      return [n, ...prev].slice(0, 200);
    });
  }, []);

  // Load recent geofence violations from REST on mount
  const loadViolations = useCallback(async () => {
    try {
      const tenantId = localStorage.getItem("tenantId") || "";
      const data = await api.getActiveViolations({ tenantId, hours: 24 });
      (data?.violations ?? []).forEach((v) => {
        addNotification({
          id: v.id,
          type: "geofence",
          title: "Geofence Violation",
          message: `Device ${v.device_id} is ${Number(v.distance_from_center_km).toFixed(2)} km outside geofence`,
          time: relativeTime(v.violation_time),
          read: false,
          raw: v as unknown as Record<string, unknown>,
        });
      });
    } catch (err) {
      console.warn("Could not load violations:", err);
    }
  }, [addNotification]);

  // WebSocket connection to realtime service
  const connect = useCallback(() => {
    const adminId = localStorage.getItem("keycloakId");
    if (!adminId) return;

    setWsStatus("connecting");
    const ws = new WebSocket(`${REALTIME_BASE}/realtime/ws/${adminId}`);
    wsRef.current = ws;

    ws.onopen = () => setWsStatus("connected");

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "admin_geofence_violation") {
          const p = msg.payload ?? {};
          addNotification({
            id: p.violation_id ?? String(Date.now()),
            type: "geofence",
            title: "Geofence Violation",
            message: `Device ${p.device_id} moved ${Number(p.distance_km ?? 0).toFixed(2)} km outside allowed zone`,
            time: relativeTime(p.timestamp ?? new Date().toISOString()),
            read: false,
            raw: p,
          });
        }

        if (msg.type === "transaction_ping") {
          const p = msg.payload ?? {};
          addNotification({
            id: msg.message_id ?? String(Date.now()),
            type: "success",
            title: "Transaction Received",
            message: `₦${Number(p.amount ?? 0).toLocaleString()} from ${p.sender_name ?? "unknown"}`,
            time: relativeTime(p.timestamp ?? new Date().toISOString()),
            read: false,
            raw: p,
          });
        }
      } catch {}
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      retryRef.current = setTimeout(connect, 5000);
    };

    ws.onerror = () => ws.close();
  }, [addNotification]);

  useEffect(() => {
    loadViolations();
    connect();

    // Send keep-alive ping every 30s
    const pingTimer = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);

    return () => {
      clearInterval(pingTimer);
      if (retryRef.current) clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect, loadViolations]);

  const markAsRead = (id: string) =>
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n)),
    );

  const markAllAsRead = () =>
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));

  const deleteNotification = (id: string) =>
    setNotifications((prev) => prev.filter((n) => n.id !== id));

  const unreadCount = notifications.filter((n) => !n.read).length;
  const displayed =
    filter === "all" ? notifications : notifications.filter((n) => !n.read);

  return (
    <div className="space-y-6 p-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Notification Center
          </h1>
          <div className="flex items-center gap-2 mt-1">
            {wsStatus === "connected" ? (
              <span className="flex items-center gap-1 text-green-600 text-sm">
                <Wifi className="w-3.5 h-3.5" /> Live
              </span>
            ) : wsStatus === "connecting" ? (
              <span className="flex items-center gap-1 text-yellow-600 text-sm">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Connecting…
              </span>
            ) : (
              <span className="flex items-center gap-1 text-gray-400 text-sm">
                <WifiOff className="w-3.5 h-3.5" /> Reconnecting…
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadViolations}
            className="px-3 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-1 text-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
          <button
            onClick={markAllAsRead}
            className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] text-sm"
          >
            Mark All as Read
          </button>
        </div>
      </div>

      <div className="flex gap-4 items-center">
        <button
          onClick={() => setFilter("all")}
          className={`px-4 py-2 rounded-lg text-sm ${filter === "all" ? "bg-[var(--tenant-primary-color,#002082)] text-white" : "bg-white text-gray-700 border border-gray-300"}`}
        >
          All ({notifications.length})
        </button>
        <button
          onClick={() => setFilter("unread")}
          className={`px-4 py-2 rounded-lg text-sm ${filter === "unread" ? "bg-[var(--tenant-primary-color,#002082)] text-white" : "bg-white text-gray-700 border border-gray-300"}`}
        >
          Unread ({unreadCount})
        </button>
      </div>

      <div className="space-y-3">
        {displayed.map((n) => (
          <div
            key={n.id}
            className={`p-6 rounded-lg border ${n.read ? "bg-white border-gray-200" : getBg(n.type)}`}
          >
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">{getIcon(n.type)}</div>
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-base font-semibold text-gray-900">
                      {n.title}
                    </h3>
                    <p className="text-sm text-gray-700 mt-1">{n.message}</p>
                    <p className="text-xs text-gray-500 mt-2">{n.time}</p>
                  </div>
                  {!n.read && (
                    <span className="ml-4 w-2 h-2 bg-[var(--tenant-primary-color,#002082)] rounded-full flex-shrink-0 mt-1" />
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                {!n.read && (
                  <button
                    onClick={() => markAsRead(n.id)}
                    className="p-2 text-[var(--tenant-primary-color,#002082)] hover:bg-[rgba(0,79,113,0.05)] rounded-lg"
                    title="Mark as read"
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => deleteNotification(n.id)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                  title="Delete"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {displayed.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <Bell className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            No notifications
          </h3>
          <p className="text-gray-500">You're all caught up!</p>
        </div>
      )}
    </div>
  );
};

export default NotificationCenter;
