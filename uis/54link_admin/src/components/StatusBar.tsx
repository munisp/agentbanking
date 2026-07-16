/**
 * StatusBar — Persistent bottom bar showing online/offline status, pending queue,
 * dark mode toggle, and language selector.
 * Features: #23 (Offline Indicator), #24 (Dark Mode), #26 (i18n)
 */

import { Globe, Moon, Sun, Wifi, WifiOff } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { useI18n, type Locale } from "@/hooks/useI18n";
import { useOnlineStatus } from "@/hooks/useOnlineStatus";

export default function StatusBar() {
  const { effectiveTheme, setTheme } = useTheme();
  const { locale, setLocale, locales, localeNames } = useI18n();
  const { isOnline, pendingQueueCount, connectionType, effectiveBandwidthMbps } = useOnlineStatus();

  return (
    <div
      className="fixed bottom-0 left-0 right-0 h-8 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 flex items-center justify-between px-4 text-xs z-50"
      role="status"
      aria-label="Platform status bar"
    >
      {/* Left: Connection status */}
      <div className="flex items-center gap-3">
        <div className={`flex items-center gap-1 ${isOnline ? "text-emerald-600" : "text-red-500"}`}>
          {isOnline ? (
            <Wifi className="h-3.5 w-3.5" aria-hidden="true" />
          ) : (
            <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          <span>{isOnline ? "Online" : "Offline"}</span>
        </div>
        {connectionType && (
          <span className="text-gray-400">
            {connectionType.toUpperCase()}
            {effectiveBandwidthMbps !== null && ` ${effectiveBandwidthMbps} Mbps`}
          </span>
        )}
        {pendingQueueCount > 0 && (
          <span className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 px-1.5 py-0.5 rounded-full font-medium">
            {pendingQueueCount} pending sync
          </span>
        )}
      </div>

      {/* Right: Theme + Language */}
      <div className="flex items-center gap-3">
        {/* Dark mode toggle */}
        <button
          onClick={() => setTheme(effectiveTheme === "dark" ? "light" : "dark")}
          className="flex items-center gap-1 text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
          aria-label={`Switch to ${effectiveTheme === "dark" ? "light" : "dark"} mode`}
        >
          {effectiveTheme === "dark" ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
        </button>

        {/* Language selector */}
        <div className="flex items-center gap-1">
          <Globe className="h-3.5 w-3.5 text-gray-400" aria-hidden="true" />
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value as Locale)}
            className="bg-transparent text-xs text-gray-500 dark:text-gray-400 border-none outline-none cursor-pointer"
            aria-label="Select language"
          >
            {locales.map((l) => (
              <option key={l} value={l}>{localeNames[l]}</option>
            ))}
          </select>
        </div>

        <span className="text-gray-300 dark:text-gray-600">54link-dev v1.0.0</span>
      </div>
    </div>
  );
}
