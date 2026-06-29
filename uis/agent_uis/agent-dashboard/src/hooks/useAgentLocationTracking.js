import { useCallback, useEffect, useState } from "react";

const DEFAULT_TENANT_ID = import.meta.env.VITE_TENANT_ID || "54agent";
const NOTIFICATION_WS_URL =
  import.meta.env.VITE_NOTIFICATION_WS_URL ||
  "wss://54agent.upi.dev/realtime/ws";

const GEOLOCATION_OPTIONS = {
  enableHighAccuracy: false,
  timeout: 10000,
  maximumAge: 10000,
};

export function useAgentLocationTracking() {
  const [trackingStatus, setTrackingStatus] = useState({
    isActive: false,
    permissionStatus: "unknown", // unknown, granted, denied
    error: null,
  });

  useEffect(() => {
    if (!("geolocation" in navigator)) {
      setTrackingStatus({
        isActive: false,
        permissionStatus: "denied",
        error: "Geolocation not supported",
      });
      return;
    }

    const keycloakId = localStorage.getItem("keycloakId");
    const token = localStorage.getItem("agent_dashboard_token");

    if (!keycloakId || !token) {
      setTrackingStatus({
        isActive: false,
        permissionStatus: "unknown",
        error: "Not authenticated",
      });
      return;
    }

    let ws = null;
    let watchId = null;
    let reconnectTimer = null;
    let shouldRun = true;
    let lastSentAt = 0;

    const connect = () => {
      if (!shouldRun) return;

      ws = new WebSocket(`${NOTIFICATION_WS_URL}/${keycloakId}`);

      ws.onerror = () => {
        ws?.close();
      };

      ws.onclose = () => {
        if (!shouldRun) return;
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    const sendLocationUpdate = (coords) => {
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }

      const now = Date.now();
      if (now - lastSentAt < 10000) {
        return;
      }

      lastSentAt = now;

      ws.send(
        JSON.stringify({
          type: "location_update",
          payload: {
            device_id: "agent-web-dashboard",
            agent_id: keycloakId,
            tenant_id: localStorage.getItem("tenantId") || DEFAULT_TENANT_ID,
            latitude: coords.latitude,
            longitude: coords.longitude,
            accuracy: coords.accuracy ?? null,
            speed: coords.speed ?? null,
            battery_level: null,
          },
        }),
      );
    };

    connect();
    setTrackingStatus((prev) => ({ ...prev, isActive: true }));

    watchId = navigator.geolocation.watchPosition(
      (position) => {
        setTrackingStatus((prev) => ({
          ...prev,
          permissionStatus: "granted",
          error: null,
        }));
        sendLocationUpdate(position.coords);
      },
      (error) => {
        setTrackingStatus((prev) => ({
          ...prev,
          permissionStatus: error.code === 1 ? "denied" : "unknown",
          error: error.message,
        }));
      },
      GEOLOCATION_OPTIONS,
    );

    return () => {
      shouldRun = false;

      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }

      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
      }

      if (ws) {
        ws.close();
      }

      setTrackingStatus({
        isActive: false,
        permissionStatus: "unknown",
        error: null,
      });
    };
  }, []);

  return trackingStatus;
}
