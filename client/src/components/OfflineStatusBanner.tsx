/**
 * Offline Status Banner + Background Sync Indicator
 * Shows when user is offline, displays queued transaction count,
 * and animates sync progress when coming back online.
 */
import { useState, useEffect } from "react";
import { WifiOff, Wifi, RefreshCw, CheckCircle } from "lucide-react";
import {
  getQueueSize,
  syncQueuedTransactions,
  isOnline,
} from "@/lib/offlineQueue";
import { t } from "@/lib/i18n";

export function OfflineStatusBanner() {
  const [online, setOnline] = useState(true);
  const [queueSize, setQueueSize] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [justSynced, setJustSynced] = useState(false);

  useEffect(() => {
    setOnline(isOnline());

    const handleOnline = async () => {
      setOnline(true);
      setSyncing(true);
      try {
        await syncQueuedTransactions();
        setJustSynced(true);
        setTimeout(() => setJustSynced(false), 3000);
      } finally {
        setSyncing(false);
        const size = await getQueueSize().catch(() => 0);
        setQueueSize(size);
      }
    };

    const handleOffline = () => {
      setOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Check queue periodically
    const interval = setInterval(async () => {
      const size = await getQueueSize().catch(() => 0);
      setQueueSize(size);
    }, 5000);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearInterval(interval);
    };
  }, []);

  if (online && !syncing && !justSynced && queueSize === 0) return null;

  return (
    <div
      className={`px-4 py-2 text-sm flex items-center gap-2 transition-all ${
        !online
          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200"
          : syncing
            ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-200"
            : justSynced
              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-200"
              : "bg-gray-100 text-gray-800"
      }`}
    >
      {!online && (
        <>
          <WifiOff className="w-4 h-4" />
          <span>{t("offline.title")}</span>
          {queueSize > 0 && (
            <span className="ml-auto font-medium">
              {queueSize} {t("offline.queued")}
            </span>
          )}
        </>
      )}
      {syncing && (
        <>
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>{t("offline.syncing")}</span>
        </>
      )}
      {justSynced && (
        <>
          <CheckCircle className="w-4 h-4" />
          <span>{t("offline.synced")}</span>
        </>
      )}
    </div>
  );
}
