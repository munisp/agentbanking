/**
 * NotificationCenter — Floating notification panel with real-time feed,
 * filters, mark-read, clear, and sound alerts for critical events.
 *
 * Integrates with the existing NotificationContext (Socket.IO /notifications namespace)
 * and adds a rich UI panel accessible from the DashboardLayout header.
 */
import { useState, useCallback, useEffect, useRef } from "react";
import {
  useNotificationContext,
  type RealtimeNotification,
  type NotificationChannel,
} from "@/contexts/NotificationContext";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Bell,
  BellRing,
  Check,
  CheckCheck,
  ChevronDown,
  Filter,
  Settings,
  Trash2,
  Volume2,
  VolumeX,
  X,
  AlertTriangle,
  Shield,
  DollarSign,
  UserCheck,
  Activity,
  Globe,
  Zap,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ─── Channel Icons & Colors ──────────────────────────────────────────────────
const channelConfig: Record<
  NotificationChannel,
  { icon: any; color: string; label: string }
> = {
  transaction: {
    icon: DollarSign,
    color: "text-emerald-400",
    label: "Transactions",
  },
  fraud: { icon: Shield, color: "text-red-400", label: "Fraud Alerts" },
  rate_alert: { icon: Activity, color: "text-amber-400", label: "Rate Alerts" },
  kyc: { icon: UserCheck, color: "text-blue-400", label: "KYC" },
  settlement: {
    icon: DollarSign,
    color: "text-purple-400",
    label: "Settlement",
  },
  system: { icon: Zap, color: "text-cyan-400", label: "System" },
  commission: {
    icon: DollarSign,
    color: "text-green-400",
    label: "Commission",
  },
  compliance: { icon: Globe, color: "text-orange-400", label: "Compliance" },
};

const severityStyles = {
  critical: "border-l-4 border-l-red-500 bg-red-500/5",
  warning: "border-l-4 border-l-amber-500 bg-amber-500/5",
  info: "border-l-4 border-l-blue-500/30 bg-transparent",
};

// ─── Sound Alert ─────────────────────────────────────────────────────────────
function playAlertSound(severity: "critical" | "warning" | "info") {
  try {
    const ctx = new (window.AudioContext ||
      (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    gain.gain.value = severity === "critical" ? 0.3 : 0.15;
    osc.frequency.value =
      severity === "critical" ? 880 : severity === "warning" ? 660 : 440;
    osc.type = severity === "critical" ? "square" : "sine";
    osc.start();
    osc.stop(ctx.currentTime + (severity === "critical" ? 0.3 : 0.15));
  } catch {
    // Audio not available
  }
}

// ─── Time Ago Helper ─────────────────────────────────────────────────────────
function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ═══════════════════════════════════════════════════════════════════════════════
// NotificationCenter Component
// ═══════════════════════════════════════════════════════════════════════════════
export function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [activeFilter, setActiveFilter] = useState<NotificationChannel | "all">(
    "all"
  );
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const panelRef = useRef<HTMLDivElement>(null);
  const prevCountRef = useRef(0);

  const {
    notifications,
    unreadCount,
    connectionState,
    markAsRead,
    markAllAsRead,
    clearAll,
  } = useNotificationContext();

  // Play sound on new critical/warning notifications
  useEffect(() => {
    if (notifications.length > prevCountRef.current && soundEnabled) {
      const newest = notifications[0];
      if (
        newest &&
        (newest.severity === "critical" || newest.severity === "warning")
      ) {
        playAlertSound(newest.severity);
        // Vibrate on mobile
        if (navigator.vibrate) {
          navigator.vibrate(
            newest.severity === "critical" ? [200, 100, 200] : [100]
          );
        }
      }
    }
    prevCountRef.current = notifications.length;
  }, [notifications, soundEnabled]);

  // Close panel on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () =>
        document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  const handleMarkRead = useCallback(
    (id: string) => {
      setReadIds(prev => new Set(prev).add(id));
      markAsRead([id]);
    },
    [markAsRead]
  );

  const handleMarkAllRead = useCallback(() => {
    const allIds = notifications.map(n => n.id);
    setReadIds(prev => {
      const next = new Set(prev);
      allIds.forEach(id => next.add(id));
      return next;
    });
    markAllAsRead();
  }, [notifications, markAllAsRead]);

  const handleClearAll = useCallback(() => {
    clearAll();
    setReadIds(new Set());
  }, [clearAll]);

  // Filter notifications
  const filtered =
    activeFilter === "all"
      ? notifications
      : notifications.filter(n => n.channel === activeFilter);

  const effectiveUnread = notifications.filter(n => !readIds.has(n.id)).length;

  return (
    <div className="relative" ref={panelRef}>
      {/* ── Bell Trigger ───────────────────────────────────────────────── */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "relative inline-flex items-center justify-center h-9 w-9 rounded-lg transition-colors",
          isOpen ? "bg-accent" : "hover:bg-accent"
        )}
        title="Notification Center"
      >
        {effectiveUnread > 0 ? (
          <BellRing className="h-5 w-5 text-amber-400 animate-pulse" />
        ) : (
          <Bell className="h-5 w-5 text-muted-foreground" />
        )}
        {effectiveUnread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {effectiveUnread > 99 ? "99+" : effectiveUnread}
          </span>
        )}
        {/* Connection indicator */}
        <span
          className={cn(
            "absolute bottom-0 right-0 h-2 w-2 rounded-full border border-background",
            connectionState.connected ? "bg-emerald-500" : "bg-red-500"
          )}
        />
      </button>

      {/* ── Floating Panel ─────────────────────────────────────────────── */}
      {isOpen && (
        <div className="absolute right-0 top-12 z-50 w-[400px] max-h-[600px] rounded-xl border border-border bg-background shadow-2xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-muted-foreground" />
              <span className="font-semibold text-sm">Notifications</span>
              {effectiveUnread > 0 && (
                <Badge variant="destructive" className="h-5 text-[10px]">
                  {effectiveUnread} new
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setSoundEnabled(!soundEnabled)}
                className="h-7 w-7 rounded-md hover:bg-accent flex items-center justify-center"
                title={soundEnabled ? "Mute sounds" : "Enable sounds"}
              >
                {soundEnabled ? (
                  <Volume2 className="h-3.5 w-3.5 text-muted-foreground" />
                ) : (
                  <VolumeX className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </button>
              <button
                onClick={handleMarkAllRead}
                className="h-7 w-7 rounded-md hover:bg-accent flex items-center justify-center"
                title="Mark all as read"
              >
                <CheckCheck className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
              <button
                onClick={handleClearAll}
                className="h-7 w-7 rounded-md hover:bg-accent flex items-center justify-center"
                title="Clear all"
              >
                <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="h-7 w-7 rounded-md hover:bg-accent flex items-center justify-center"
              >
                <X className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </div>
          </div>

          {/* Channel Filters */}
          <div className="flex items-center gap-1 px-3 py-2 border-b border-border overflow-x-auto scrollbar-none">
            <button
              onClick={() => setActiveFilter("all")}
              className={cn(
                "px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors",
                activeFilter === "all"
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent text-muted-foreground"
              )}
            >
              All
            </button>
            {(Object.keys(channelConfig) as NotificationChannel[]).map(ch => {
              const cfg = channelConfig[ch];
              const count = notifications.filter(
                n => n.channel === ch && !readIds.has(n.id)
              ).length;
              return (
                <button
                  key={ch}
                  onClick={() => setActiveFilter(ch)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors flex items-center gap-1",
                    activeFilter === ch
                      ? "bg-primary text-primary-foreground"
                      : "hover:bg-accent text-muted-foreground"
                  )}
                >
                  {cfg.label}
                  {count > 0 && (
                    <span className="bg-red-500/20 text-red-400 px-1 rounded text-[10px]">
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Notification Feed */}
          <ScrollArea className="flex-1 max-h-[420px]">
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Bell className="h-10 w-10 mb-3 opacity-30" />
                <p className="text-sm font-medium">No notifications</p>
                <p className="text-xs mt-1">You're all caught up!</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {filtered.map(notif => {
                  const cfg =
                    channelConfig[notif.channel] || channelConfig.system;
                  const Icon = cfg.icon;
                  const isRead = readIds.has(notif.id);

                  return (
                    <div
                      key={notif.id}
                      className={cn(
                        "px-4 py-3 cursor-pointer transition-colors hover:bg-accent/50",
                        severityStyles[notif.severity],
                        isRead && "opacity-60"
                      )}
                      onClick={() => {
                        handleMarkRead(notif.id);
                        if (notif.actionUrl) {
                          window.location.href = notif.actionUrl;
                          setIsOpen(false);
                        }
                      }}
                    >
                      <div className="flex items-start gap-3">
                        <div className={cn("mt-0.5 flex-shrink-0", cfg.color)}>
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2">
                            <p
                              className={cn(
                                "text-sm font-medium truncate",
                                isRead
                                  ? "text-muted-foreground"
                                  : "text-foreground"
                              )}
                            >
                              {notif.title}
                            </p>
                            {!isRead && (
                              <span className="h-2 w-2 rounded-full bg-blue-500 flex-shrink-0" />
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                            {notif.body}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5">
                            <Badge
                              variant="outline"
                              className="text-[10px] h-4 px-1.5"
                            >
                              {cfg.label}
                            </Badge>
                            <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                              <Clock className="h-2.5 w-2.5" />
                              {timeAgo(notif.timestamp)}
                            </span>
                            {notif.severity === "critical" && (
                              <Badge
                                variant="destructive"
                                className="text-[10px] h-4 px-1.5"
                              >
                                Critical
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-muted/30">
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  connectionState.connected ? "bg-emerald-500" : "bg-red-500"
                )}
              />
              <span className="text-[10px] text-muted-foreground">
                {connectionState.connected ? "Live" : "Disconnected"}
                {connectionState.activeUsers > 0 &&
                  ` · ${connectionState.activeUsers} online`}
              </span>
            </div>
            <a
              href="/notification-inbox"
              className="text-xs text-primary hover:underline"
              onClick={() => setIsOpen(false)}
            >
              View all notifications →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationCenter;
