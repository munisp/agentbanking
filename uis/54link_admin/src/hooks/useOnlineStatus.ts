/**
 * Online/Offline Status Hook (#23)
 * Tracks connection state and pending offline queue count.
 */

import { useCallback, useEffect, useState } from "react";

interface OnlineStatus {
  isOnline: boolean;
  pendingQueueCount: number;
  lastOnline: Date | null;
  connectionType: string | null;
  effectiveBandwidthMbps: number | null;
}

export function useOnlineStatus(): OnlineStatus {
  const [isOnline, setIsOnline] = useState(typeof navigator !== "undefined" ? navigator.onLine : true);
  const [pendingQueueCount, setPendingQueueCount] = useState(0);
  const [lastOnline, setLastOnline] = useState<Date | null>(isOnline ? new Date() : null);
  const [connectionType, setConnectionType] = useState<string | null>(null);
  const [effectiveBandwidthMbps, setEffectiveBandwidthMbps] = useState<number | null>(null);

  const updateConnectionInfo = useCallback(() => {
    const nav = navigator as Navigator & { connection?: { effectiveType?: string; downlink?: number } };
    if (nav.connection) {
      setConnectionType(nav.connection.effectiveType ?? null);
      setEffectiveBandwidthMbps(nav.connection.downlink ?? null);
    }
  }, []);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setLastOnline(new Date());
      updateConnectionInfo();
    };
    const handleOffline = () => {
      setIsOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    updateConnectionInfo();

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [updateConnectionInfo]);

  // Poll IndexedDB for pending queue count
  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;

    const checkQueue = async () => {
      try {
        const dbs = await indexedDB.databases();
        const offlineDb = dbs.find((db) => db.name === "54link-dev-offline-queue");
        if (!offlineDb) {
          setPendingQueueCount(0);
          return;
        }
        const req = indexedDB.open("54link-dev-offline-queue");
        req.onsuccess = () => {
          const db = req.result;
          if (!db.objectStoreNames.contains("mutations")) {
            setPendingQueueCount(0);
            db.close();
            return;
          }
          const tx = db.transaction("mutations", "readonly");
          const store = tx.objectStore("mutations");
          const countReq = store.count();
          countReq.onsuccess = () => setPendingQueueCount(countReq.result);
          tx.oncomplete = () => db.close();
        };
      } catch {
        setPendingQueueCount(0);
      }
    };

    void checkQueue();
    timer = setInterval(() => void checkQueue(), 5000);
    return () => clearInterval(timer);
  }, []);

  return { isOnline, pendingQueueCount, lastOnline, connectionType, effectiveBandwidthMbps };
}
