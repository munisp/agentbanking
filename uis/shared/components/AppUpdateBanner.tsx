import { AlertCircle, Download, RefreshCw, X } from "lucide-react";
import React, { useEffect, useState } from "react";

interface AppVersion {
  current_version: string;
  latest_version: string;
  update_available: boolean;
  update_url: string;
  release_notes: string;
  is_critical: boolean;
}

export const AppUpdateBanner: React.FC = () => {
  const [updateInfo, setUpdateInfo] = useState<AppVersion | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkForUpdates();
    // Check for updates every hour
    const interval = setInterval(checkForUpdates, 3600000);
    return () => clearInterval(interval);
  }, []);

  const checkForUpdates = async () => {
    try {
      // In a real implementation, this would call your version check API
      // For now, we'll use localStorage to simulate version checking
      const currentVersion = localStorage.getItem("app_version") || "1.0.0";
      const latestVersion = "1.2.0"; // This would come from your API

      const updateAvailable =
        compareVersions(latestVersion, currentVersion) > 0;

      if (updateAvailable) {
        setUpdateInfo({
          current_version: currentVersion,
          latest_version: latestVersion,
          update_available: true,
          update_url: "/download-update", // Your actual update URL
          release_notes:
            "Bug fixes, performance improvements, and new features",
          is_critical: false, // Set to true if update is mandatory
        });
      }
    } catch (error) {
      console.error("Failed to check for updates:", error);
    } finally {
      setLoading(false);
    }
  };

  const compareVersions = (v1: string, v2: string): number => {
    const parts1 = v1.split(".").map(Number);
    const parts2 = v2.split(".").map(Number);

    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
      const part1 = parts1[i] || 0;
      const part2 = parts2[i] || 0;

      if (part1 > part2) return 1;
      if (part1 < part2) return -1;
    }

    return 0;
  };

  const handleUpdate = () => {
    if (updateInfo?.update_url) {
      // In a web app, redirect to update page or trigger download
      window.location.href = updateInfo.update_url;

      // For mobile apps, this would open the app store
      // if (isMobile) {
      //   window.open(updateInfo.update_url, '_blank');
      // }
    }
  };

  const handleDismiss = () => {
    if (!updateInfo?.is_critical) {
      setDismissed(true);
      // Remember dismissal for 24 hours
      localStorage.setItem(
        "update_dismissed_until",
        String(Date.now() + 86400000),
      );
    }
  };

  // Don't show if loading, no update, or dismissed (and not critical)
  if (
    loading ||
    !updateInfo?.update_available ||
    (dismissed && !updateInfo.is_critical)
  ) {
    return null;
  }

  // Check if update was dismissed recently (only for non-critical updates)
  if (!updateInfo.is_critical) {
    const dismissedUntil = localStorage.getItem("update_dismissed_until");
    if (dismissedUntil && Date.now() < Number(dismissedUntil)) {
      return null;
    }
  }

  return (
    <div
      className={`fixed top-0 left-0 right-0 z-50 ${
        updateInfo.is_critical
          ? "bg-red-600"
          : "bg-gradient-to-r from-blue-600 to-blue-700"
      } text-white shadow-lg`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-3 flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center space-x-3 flex-1 min-w-0">
            {updateInfo.is_critical ? (
              <AlertCircle className="w-6 h-6 flex-shrink-0 animate-pulse" />
            ) : (
              <RefreshCw className="w-6 h-6 flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <p className="font-semibold">
                {updateInfo.is_critical
                  ? "🚨 Critical Update Required"
                  : "✨ New Version Available"}
              </p>
              <p className="text-sm opacity-90 truncate">
                Version {updateInfo.latest_version} is now available
                {updateInfo.release_notes && ` - ${updateInfo.release_notes}`}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleUpdate}
              className="bg-white text-blue-600 hover:bg-blue-50 px-4 py-2 rounded-lg font-medium flex items-center space-x-2 transition-colors"
            >
              <Download className="w-4 h-4" />
              <span>Update Now</span>
            </button>

            {!updateInfo.is_critical && (
              <button
                onClick={handleDismiss}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                aria-label="Dismiss"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Compact version for embedding in pages
export const AppUpdateBadge: React.FC = () => {
  const [updateAvailable, setUpdateAvailable] = useState(false);

  useEffect(() => {
    const checkUpdate = () => {
      const currentVersion = localStorage.getItem("app_version") || "1.0.0";
      const latestVersion = "1.2.0";
      setUpdateAvailable(latestVersion > currentVersion);
    };

    checkUpdate();
    const interval = setInterval(checkUpdate, 3600000);
    return () => clearInterval(interval);
  }, []);

  if (!updateAvailable) return null;

  return (
    <a
      href="/download-update"
      className="inline-flex items-center space-x-2 bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium hover:bg-blue-200 transition-colors"
    >
      <RefreshCw className="w-4 h-4" />
      <span>Update Available</span>
    </a>
  );
};

export default AppUpdateBanner;
