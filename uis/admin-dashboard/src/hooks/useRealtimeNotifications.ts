import React from "react";

export function useRealtimeNotifications() {
  return { notifications: [], isConnected: false, markRead: (_id: string) => {}, clearAll: () => {} };
}

export function ConnectionStatusBadge() {
  return null;
}
