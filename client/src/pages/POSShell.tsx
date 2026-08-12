// SECURITY: SQL template literals in this file are for display/mock purposes only. All actual DB queries use parameterized Drizzle ORM.
/**
 * 54Link POS — Bloomberg Terminal meets Modern Fintech (Dark Professional)
 * Features: Fraud Detection Dashboard, Live Chat Support, Loyalty Points System
 * Design: near-black (#0a0e1a), electric blue primary, emerald for positive values
 * Font: Space Grotesk (display) + Inter (body) + JetBrains Mono (financial data)
 * Layout: Full-bleed status bar → quick-access strip → configurable tile grid → live ticker
 * ALL 26 SCREENS FULLY IMPLEMENTED — Tier 1-4 improvements applied
 */


import FraudDashboard from "./FraudDashboard";
import LiveChatSupport from "./LiveChatSupport";
import LoyaltySystem from "./LoyaltySystem";
import { EODWidget } from "../components/EODWidget";
import { GdprConsentBanner } from "../components/GdprConsentBanner";
import { LAYOUT_PRESETS } from "../components/LayoutPresets";
import { NotificationBell } from "../components/NotificationBell";
import { PullToRefresh } from "../components/PullToRefresh";
import { TileContextMenu } from "../components/TileContextMenu";
import { haptic } from "../lib/haptics";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { DndContext, PointerSensor, TouchSensor, closestCenter, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, rectSortingStrategy } from "@dnd-kit/sortable";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Bar } from "recharts";
import { toast } from "sonner";
import { GamificationPanel, NotificationPanel, SortableTile, loadTileUsage } from "./POSShell.part10";
import { saveTileCustomizations, useGamification } from "./POSShell.part11";
import { loadTileCustomizations } from "./POSShell.part5";
import { ArchitecturePanel, fmt, saveTileUsage } from "./POSShell.part6";
import { USSDSimulator } from "./POSShell.part8";
import { TileEditorSheet } from "./POSShell.part9";
import { FloatLockOverlays, OfflineModeIndicator, OfflineUssdModal, QuickEntryModal, VelocityWarningBanner, createScreens } from "./POSShell.screens";
import { BG, BLUE, BORDER, CARD, DEFAULT_LAYOUT, DISP, GOLD, GREEN, GamificationData, MONO, QUICK_AMOUNTS, RED, TERMINAL_UNKNOWN, TILE_QUICK_ACTIONS, TILE_REGISTRY, TILE_THEME_COLORS, TerminalInfo, Tile, TileCategory, TileCustomization, TileSize, Transaction } from "./POSShell.shared";

export default function POSShell() {
  const [activeScreen, setActiveScreen] = useState<string | null>(null);
  const [layout, setLayout] = useState<string[]>(DEFAULT_LAYOUT);
  const [editMode, setEditMode] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [showGamification, setShowGamification] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUSSD, setShowUSSD] = useState(false);
  const [showArch, setShowArch] = useState(false);
  const [showFraudDash, setShowFraudDash] = useState(false);
  const [showLiveChat, setShowLiveChat] = useState(false);
  const [showLoyalty, setShowLoyalty] = useState(false);
  const [showOfflineUssd, setShowOfflineUssd] = useState(false);
  const [homeUssdCodes, setHomeUssdCodes] = useState<
    Array<{
      id: string;
      ussd_string: string;
      instructions: string;
      carrier_hint: string | null;
      tx_type: string;
      amount: number;
    }>
  >([]);
  const [generatingHomeUssd, setGeneratingHomeUssd] = useState(false);
  const [catFilter, setCatFilter] = useState<TileCategory | "all">("all");
  const [tickerPos, setTickerPos] = useState(0);
  const [time, setTime] = useState(new Date());
  const tickerRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  // ── UX Enhancement State (P0→P3) ─────────────────────────────────────────
  const [tileCustom, setTileCustom] = useState<TileCustomization>(
    loadTileCustomizations
  );
  const [tileUsage, setTileUsage] =
    useState<Record<string, number>>(loadTileUsage);
  const [showQuickEntry, setShowQuickEntry] = useState(false);
  const [quickEntryAmount, setQuickEntryAmount] = useState<number | null>(null);
  const [quickEntryDirection, setQuickEntryDirection] = useState<
    "CashIn" | "CashOut" | null
  >(null);
  const [showPresets, setShowPresets] = useState(false);
  const [showTileThemer, setShowTileThemer] = useState<string | null>(null);
  const [showSizeChooser, setShowSizeChooser] = useState<string | null>(null);
  const [showLanguageSelector, setShowLanguageSelector] = useState(false);

  // DnD Kit sensors (P1: drag-and-drop)
  const pointerSensor = useSensor(PointerSensor, {
    activationConstraint: { distance: 8 },
  });
  const touchSensor = useSensor(TouchSensor, {
    activationConstraint: { delay: 300, tolerance: 8 },
  });
  const dndSensors = useSensors(pointerSensor, touchSensor);

  // Handle tile drag end (P1)
  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      haptic("micro");
      setLayout(prev => {
        const oldIndex = prev.indexOf(active.id as string);
        const newIndex = prev.indexOf(over.id as string);
        const newLayout = arrayMove(prev, oldIndex, newIndex);
        setTileCustom(c => {
          const updated = { ...c, order: newLayout };
          saveTileCustomizations(updated);
          return updated;
        });
        return newLayout;
      });
    }
  }, []);

  // Track tile usage (P2: smart ordering)
  const trackTileUsage = useCallback((tileId: string) => {
    setTileUsage(prev => {
      const updated = { ...prev, [tileId]: (prev[tileId] || 0) + 1 };
      saveTileUsage(updated);
      return updated;
    });
  }, []);

  // Apply layout preset (P2)
  const applyPreset = useCallback((preset: LayoutPreset) => {
    if (preset.id === "custom") return;
    setLayout(preset.tileIds);
    setTileCustom(c => {
      const updated = { ...c, preset: preset.id, order: preset.tileIds };
      saveTileCustomizations(updated);
      return updated;
    });
    setShowPresets(false);
    haptic("success");
    toast.success(`Layout: ${preset.name}`);
  }, []);

  // Change tile size (P2: tile size customization)
  const changeTileSize = useCallback((tileId: string, newSize: TileSize) => {
    setTileCustom(c => {
      const updated = { ...c, sizes: { ...c.sizes, [tileId]: newSize } };
      saveTileCustomizations(updated);
      return updated;
    });
    setShowSizeChooser(null);
    haptic("micro");
  }, []);

  // Change tile color (P3: tile theming)
  const changeTileColor = useCallback((tileId: string, hue: number) => {
    setTileCustom(c => {
      const updated = { ...c, colors: { ...c.colors, [tileId]: hue } };
      saveTileCustomizations(updated);
      return updated;
    });
    setShowTileThemer(null);
    haptic("micro");
  }, []);

  // Restore persisted layout on mount
  useEffect(() => {
    const custom = loadTileCustomizations();
    if (custom.order.length > 0) {
      setLayout(custom.order);
    }
  }, []);

  // Live clock
  useEffect(() => {
    const iv = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  // ── Resilience: connection quality probe (Go service) ────────────────────
  const { data: probeData } = trpc.resilience.probe.useQuery(undefined, {
    refetchInterval: 5_000,
    retry: false,
  }) as any;
  const connQuality: string =
    (probeData as any)?.quality ?? (navigator.onLine ? "Good" : "Offline");
  const connLatency: number | null = (probeData as any)?.latency_ms ?? null;
  const connColor =
    connQuality === "Excellent"
      ? GREEN
      : connQuality === "Good"
        ? BLUE
        : connQuality === "Poor"
          ? GOLD
          : RED;

  // ── Resilience: offline queue count (Rust service) ───────────────────────
  const { data: queueData } = trpc.resilience.queueCount.useQuery(undefined, {
    refetchInterval: 10_000,
    retry: false,
  }) as any;
  const pendingQueueCount: number = (queueData as any)?.pending ?? 0;

  // ── Resilience: 7-day success rate (Python service) ──────────────────────
  const { data: successRateData } = trpc.resilience.successRate.useQuery(
    { days: 7 },
    {
      refetchInterval: 60_000,
      retry: false,
    }
  ) as any;
  const successRatePct: number | null =
    (successRateData as any)?.success_rate_pct ?? null;
  const successTier: string | null = (successRateData as any)?.tier ?? null;

  // Ticker animation
  useEffect(() => {
    const iv = setInterval(() => {
      setTickerPos(p => p - 1);
    }, 30);
    return () => clearInterval(iv);
  }, []);

  // ── Live data from Zustand store (populated by Socket.IO + tRPC) ─────────────────
  const storeAgent = usePosStore(s => s.agent);
  const isOnline = usePosStore(s => s.isOnline);
  const storeRecentTxs = usePosStore(s => s.recentTxs);
  const unreadFraudCount = usePosStore(s => s.unreadFraudCount);
  const unreadChatCount = usePosStore(s => s.unreadChatCount);
  const storeLogout = usePosStore(s => s.logout);
  const storeOfflineQueue = usePosStore(s => s.offlineQueue);
  const encodeUssdHome = trpc.resilience.encodeUssd.useMutation() as any;
  const printUssdHome = trpc.resilience.printUssdReceipt.useMutation() as any;
  const generateHomeUssdCodes = async () => {
    const items = storeOfflineQueue.slice(0, 10);
    if (items.length === 0) {
      toast.info("No pending transactions");
      return;
    }
    setGeneratingHomeUssd(true);
    const codes: typeof homeUssdCodes = [];
    for (const tx of items) {
      try {
        const result = await encodeUssdHome.mutateAsync({
          txType: tx.type,
          amount: tx.amount,
          destinationAccount: tx.destinationAccount,
          destinationBank: tx.destinationBank,
          customerPhone: tx.customerPhone,
        });
        codes.push({
          id: tx.id,
          ussd_string: (result as any).ussd_string,
          instructions: (result as any).instructions,
          carrier_hint: (result as any).carrier_hint ?? null,
          tx_type: tx.type,
          amount: tx.amount,
        });
      } catch {
        codes.push({
          id: tx.id,
          ussd_string: `*966*${Math.round(tx.amount)}#`,
          instructions: `Dial *966*${Math.round(tx.amount)}# to pay via USSD.`,
          carrier_hint: null,
          tx_type: tx.type,
          amount: tx.amount,
        });
      }
    }
    setHomeUssdCodes(codes);
    setGeneratingHomeUssd(false);
    setShowOfflineUssd(true);
  };

  // Merge store agent data into terminal display (unknown until the agent
  // profile loads — no fabricated identity/float fallbacks).
  const terminal: TerminalInfo = storeAgent
    ? {
        ...TERMINAL_UNKNOWN,
        model: storeAgent.terminalModel ?? null,
        serialNo: storeAgent.terminalSerial ?? null,
        agentName: storeAgent.name,
        agentCode: storeAgent.agentCode,
        floatBalance: storeAgent.floatBalance,
        commissionBalance: storeAgent.commissionBalance,
        tier: storeAgent.tier,
        location: storeAgent.location ?? null,
        online: isOnline,
        network: isOnline ? null : ("Offline" as const),
      }
    : { ...TERMINAL_UNKNOWN, online: isOnline, network: isOnline ? null : ("Offline" as const) };

  // ── Float-lock status polling (every 30s) ──────────────────────────────────
  const setAgent = usePosStore(s => s.setAgent);
  const { data: agentMeData } = trpc.agent.me.useQuery(undefined, {
    refetchInterval: 30_000,
    retry: false,
    enabled: !!storeAgent,
  }) as any;
  // Derive float-lock state from server (falls back to store, then false)
  const floatLocked =
    agentMeData?.floatLocked ?? storeAgent?.floatLocked ?? false;
  // Track elapsed time since float lock was first detected
  const lockStartRef = useRef<number | null>(null);
  const [lockElapsed, setLockElapsed] = useState(0);
  useEffect(() => {
    if (floatLocked) {
      if (lockStartRef.current === null) lockStartRef.current = Date.now();
      const interval = setInterval(() => {
        setLockElapsed(
          Math.floor((Date.now() - (lockStartRef.current ?? Date.now())) / 1000)
        );
      }, 1000);
      return () => clearInterval(interval);
    } else {
      lockStartRef.current = null;
      setLockElapsed(0);
    }
  }, [floatLocked]);
  const fmtElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  // ── Remote kill-switch state ──────────────────────────────────────────────
  const [terminalKilled, setTerminalKilled] = useState<{
    reason: string;
    disabledBy: string;
    disabledAt: string;
  } | null>(() => {
    try {
      const stored = localStorage.getItem("pos_terminal_disabled");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  useEffect(() => {
    const onKill = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setTerminalKilled(detail);
    };
    const onLift = () => setTerminalKilled(null);
    window.addEventListener("terminal:kill-switch", onKill);
    window.addEventListener("terminal:kill-switch-lift", onLift);
    return () => {
      window.removeEventListener("terminal:kill-switch", onKill);
      window.removeEventListener("terminal:kill-switch-lift", onLift);
    };
  }, []);
  // ── Velocity warning banner state ──────────────────────────────────────────
  const [velocityWarning, setVelocityWarning] = useState<{
    type: "hourly_count" | "daily_volume";
    used: number;
    limit: number;
    pct: number;
    tier: string;
  } | null>(null);
  useEffect(() => {
    const onWarning = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setVelocityWarning(detail);
      // Auto-dismiss after 30 seconds
      setTimeout(() => setVelocityWarning(null), 30000);
    };
    window.addEventListener("terminal:velocity_warning", onWarning);
    return () =>
      window.removeEventListener("terminal:velocity_warning", onWarning);
  }, []);

  // Live transactions from tRPC
  const { data: liveTxs } = trpc.transactions.list.useQuery(
    {},
    { refetchInterval: 30000 }
  ) as any;
  const recentTxs = (liveTxs ?? storeRecentTxs).slice(0, 10).map((t: any) => ({
    id: String(t.id ?? t.ref),
    type: t.type,
    amount:
      typeof t.amount === "number" ? t.amount : parseFloat(t.amount ?? "0"),
    customer: t.customerName ?? "Customer",
    phone: t.customerPhone ?? "",
    status: (t.status ?? "success") as "success" | "pending" | "failed",
    time: t.createdAt
      ? new Date(t.createdAt).toLocaleTimeString("en-NG", {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "",
    ref: t.ref ?? String(t.id),
    channel: t.channel ?? "Cash",
  }));

  // Live loyalty/gamification from tRPC (null-safe, never fabricated)
  const gamification: GamificationData = useGamification();

  // ── Live analytics: day stats for ticker, hourly chart, commission chart ──
  const { data: dayStats } = trpc.transactions.agentDayStats.useQuery(
    undefined,
    {
      refetchInterval: 30_000,
      retry: false,
    }
  ) as any;
  const { data: liveHourlyStats } = trpc.transactions.hourlyStats.useQuery(
    undefined,
    {
      refetchInterval: 60_000,
      retry: false,
    }
  ) as any;
  const { data: liveCommissionStats } =
    trpc.transactions.commissionStats.useQuery(undefined, {
      refetchInterval: 60_000,
      retry: false,
    }) as any;

  // Build live ticker items from dayStats (empty until the server responds — no mock ticker)
  const liveTickerItems = dayStats
    ? [
        {
          label: "CASH-IN",
          value: `₦${dayStats.cashIn.toLocaleString("en-NG")}`,
          change: "+today",
          up: true,
        },
        {
          label: "CASH-OUT",
          value: `₦${dayStats.cashOut.toLocaleString("en-NG")}`,
          change: "+today",
          up: true,
        },
        {
          label: "TRANSFERS",
          value: `₦${dayStats.transfers.toLocaleString("en-NG")}`,
          change: "+today",
          up: true,
        },
        {
          label: "FLOAT",
          value: `₦${dayStats.float.toLocaleString("en-NG")}`,
          change: "live",
          up: dayStats.float > 0,
        },
        {
          label: "COMMISSION",
          value: `₦${dayStats.commission.toLocaleString("en-NG")}`,
          change: "+today",
          up: true,
        },
        {
          label: "TX COUNT",
          value: String(dayStats.count),
          change: "+today",
          up: true,
        },
        {
          label: "SUCCESS",
          value: `${dayStats.successRate}%`,
          change: "live",
          up: dayStats.successRate >= 95,
        },
      ]
    : [];

  // Build chart data from live queries (empty until loaded — no static mock data)
  const liveChartData =
    liveHourlyStats && liveHourlyStats.length > 0
      ? liveHourlyStats.map((b: any) => ({
          h: b.h,
          in: b.cashIn,
          out: b.cashOut,
        }))
      : [];
  const liveCommissionData =
    liveCommissionStats && liveCommissionStats.length > 0
      ? liveCommissionStats
      : [];

  // WebSocket connection status from store
  const wsStatus = isOnline ? ("connected" as const) : ("offline" as const);

  // Live notification badge count
  const notifCount = unreadFraudCount + unreadChatCount;

  const navigate = useCallback(
    (screen: string, tileId?: string) => {
      if (tileId) trackTileUsage(tileId);
      haptic("tap");
      if (screen === "__ussd__") {
        setShowUSSD(true);
        return;
      }
      if (screen === "__arch__") {
        setShowArch(true);
        return;
      }
      if (screen === "__fraud_dash__") {
        setShowFraudDash(true);
        return;
      }
      if (screen === "__live_chat__") {
        setShowLiveChat(true);
        return;
      }
      if (screen === "__loyalty__") {
        setShowLoyalty(true);
        return;
      }
      setActiveScreen(screen);
      setEditMode(false);
    },
    [
      setShowUSSD,
      setShowArch,
      setShowFraudDash,
      setShowLiveChat,
      setShowLoyalty,
      trackTileUsage,
    ]
  );

  const goHome = useCallback(() => setActiveScreen(null), []);

  // ── Dynamic badge: offline-resilience tile shows total pending count ────────
  const offlineQueueStore = usePosStore(s => s.offlineQueue);
  const totalOfflinePending = offlineQueueStore.length + pendingQueueCount;

  // Compute visible tiles with smart ordering (P2)
  const visibleTiles = useMemo(() => {
    const tileMap = new Map(TILE_REGISTRY.map(t => [t.id, t]));
    const base = layout
      .map(id => tileMap.get(id))
      .filter((t): t is Tile => !!t);

    const filtered =
      catFilter === "all" ? base : base.filter(t => t.category === catFilter);

    return filtered.map(t =>
      t.id === "offline-resilience" && totalOfflinePending > 0
        ? { ...t, badge: totalOfflinePending }
        : t
    );
  }, [layout, catFilter, totalOfflinePending]);

  // Quick access tiles (sorted by actual usage)
  const quickAccess = useMemo(() => {
    return [...TILE_REGISTRY]
      .sort(
        (a, b) =>
          (tileUsage[b.id] || b.usageCount || 0) -
          (tileUsage[a.id] || a.usageCount || 0)
      )
      .slice(0, 4);
  }, [tileUsage]);

  // Live data for tiles (P1)
  const tileLiveData = useMemo(() => {
    const data: Record<string, React.ReactNode> = {};
    data["float-bal"] = fmt(terminal.floatBalance);
    data["commission"] = fmt(terminal.commissionBalance);
    data["daily-report"] = `${terminal.txToday}/${terminal.txTarget} today`;
    if (unreadFraudCount > 0)
      data["fraud-alerts"] = `${unreadFraudCount} active`;
    if (pendingQueueCount > 0)
      data["offline-resilience"] = `${pendingQueueCount} queued`;
    return data;
  }, [
    terminal.floatBalance,
    terminal.commissionBalance,
    terminal.txToday,
    terminal.txTarget,
    unreadFraudCount,
    pendingQueueCount,
  ]);

  // Screen router
  if (activeScreen) {
    const screenMap = createScreens({
      goHome,
      liveCommissionData,
      liveChartData,
      setActiveScreen,
    });
    const screen = screenMap[activeScreen];
    if (!screen) {
      // All screens are implemented — this branch only fires if a tile ID is misconfigured
      console.warn(`[POSShell] No screen mapped for: ${activeScreen}`);
      setActiveScreen(null);
      return null;
    }
    return (
      <div
        className="flex flex-col h-screen overflow-hidden"
        style={{ background: BG, maxWidth: 430, margin: "0 auto" }}
      >
        {screen}
      </div>
    );
  }

  // ── Home screen ──
  const cats: (TileCategory | "all")[] = [
    "all",
    "transactions",
    "customers",
    "finance",
    "compliance",
    "reports",
    "settings",
  ];
  const tickerText = liveTickerItems
    .map((t: any) => `${t.label}: ${t.value}  ${t.change}`)
    .join("   ·   ");

  return (
    <div
      className="relative flex flex-col h-screen overflow-hidden select-none"
      style={{ background: BG, maxWidth: 430, margin: "0 auto" }}
    >
      {/* ── GDPR/NDPR Consent Banner ── */}
      <GdprConsentBanner agentId={storeAgent?.agentCode} />
      {/* ── Velocity Warning Amber Banner ── */}
      <VelocityWarningBanner
        velocityWarning={velocityWarning}
        setVelocityWarning={setVelocityWarning}
      />

      {/* ── Float-Lock Overlay ── */}
      <FloatLockOverlays
        terminalKilled={terminalKilled}
        floatLocked={floatLocked}
        lockElapsed={lockElapsed}
        fmtElapsed={fmtElapsed}
      />
      {/* ── Status Bar (P0: safe-top for notched devices) ── */}
      <div
        className="flex items-center justify-between px-4 py-2 flex-shrink-0 safe-top"
        style={{
          background: "oklch(0.07 0.01 240)",
          borderBottom: `1px solid ${BORDER}`,
        }}
        role="status"
        aria-label="Terminal status bar"
      >
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full animate-pulse"
            style={{
              background:
                wsStatus === "connected"
                  ? GREEN
                  : wsStatus === "offline"
                    ? RED
                    : GOLD,
            }}
          />
          <span
            className="text-xs font-bold"
            style={{ color: BLUE, fontFamily: DISP }}
          >
            54Link
          </span>
          <span className="text-xs text-gray-500" style={{ fontFamily: MONO }}>
            ·
          </span>
          <span className="text-xs text-gray-400" style={{ fontFamily: DISP }}>
            {terminal.agentCode ?? "—"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span
            className="text-xs font-semibold"
            style={{ color: connColor, fontFamily: MONO }}
          >
            {connQuality}
            {connLatency !== null ? ` ${connLatency}ms` : ""}
          </span>
          <div className="flex items-end gap-0.5 h-3">
            {[40, 60, 80, 100].map((h, i) => (
              <div
                key={i}
                className="w-1 rounded-sm"
                style={{
                  height: `${h}%`,
                  background:
                    connQuality === "Offline"
                      ? RED
                      : connQuality === "Poor"
                        ? GOLD
                        : BLUE,
                }}
              />
            ))}
          </div>
          <div className="flex items-center gap-1">
            <div
              className="w-6 h-3 rounded-sm border flex items-center px-0.5"
              style={{ borderColor: (terminal.batteryLevel ?? 100) > 20 ? GREEN : RED }}
            >
              <div
                className="h-1.5 rounded-sm"
                style={{
                  width: `${terminal.batteryLevel ?? 0}%`,
                  background: (terminal.batteryLevel ?? 100) > 20 ? GREEN : RED,
                }}
              />
            </div>
            <span
              className="text-xs"
              style={{
                color: (terminal.batteryLevel ?? 100) > 20 ? GREEN : RED,
                fontFamily: MONO,
              }}
            >
              {terminal.batteryLevel != null ? `${terminal.batteryLevel}%` : "—"}
            </span>
          </div>
          <span
            className="text-xs font-bold text-white"
            style={{ fontFamily: MONO }}
          >
            {time.toLocaleTimeString("en-NG", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </div>

      {/* ── Offline Mode Indicator (Sprint 74: F10-F16) ── */}
      <OfflineModeIndicator
        connQuality={connQuality}
        pendingQueueCount={pendingQueueCount}
        storeOfflineQueue={storeOfflineQueue}
      />

      {/* ── Agent Header ── */}
      <div
        className="px-4 py-3 flex-shrink-0"
        style={{
          background: "oklch(0.10 0.012 240)",
          borderBottom: `1px solid ${BORDER}`,
        }}
      >
        <div className="flex items-center justify-between mb-2">
          <div>
            <div
              className="text-sm font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              {terminal.agentName ?? "—"}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <div
                className="px-1.5 py-0.5 rounded text-xs font-bold"
                style={{ background: "oklch(0.78 0.18 80 / 0.2)", color: GOLD }}
              >
                {terminal.tier ?? "—"}
              </div>
              <span
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                {terminal.location ?? "—"}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Notification Bell with Push support */}
            <NotificationBell
              unreadCount={notifCount}
              onClick={() => setShowNotifications(true)}
              cardStyle={CARD}
              borderStyle={BORDER}
              redColor={RED}
            />
            {/* Platform Hub Button */}
            <a
              href="/hub"
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-all active:scale-90"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
              title="Platform Hub"
            >
              <span
                className="text-xs font-bold"
                style={{ color: "#06b6d4", fontFamily: MONO }}
              >
                ⊞
              </span>
            </a>
            {/* Admin Panel Button */}
            <a
              href="/admin"
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-all active:scale-90"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
              title="Admin Panel"
            >
              <span
                className="text-xs font-bold"
                style={{ color: "#8b5cf6", fontFamily: MONO }}
              >
                ⬡
              </span>
            </a>
            {/* USSD Button */}
            <button
              onClick={() => setShowUSSD(true)}
              className="w-9 h-9 rounded-xl flex items-center justify-center transition-all active:scale-90"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <span
                className="text-xs font-bold"
                style={{ color: BLUE, fontFamily: MONO }}
              >
                #
              </span>
            </button>
            <button
              onClick={() => setShowGamification(true)}
              className="flex flex-col items-end gap-0.5"
            >
              <div
                className="text-xs font-bold"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                🏆 #{gamification.rank}
              </div>
              <div
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                🔥 {gamification.streak}d streak
              </div>
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div
            className="rounded-xl p-2.5"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-xs text-gray-500 mb-0.5"
              style={{ fontFamily: DISP }}
            >
              Float Balance
            </div>
            <div
              className="text-base font-bold"
              style={{ color: GOLD, fontFamily: MONO }}
            >
              {fmt(terminal.floatBalance)}
            </div>
          </div>
          <div
            className="rounded-xl p-2.5"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-xs text-gray-500 mb-0.5"
              style={{ fontFamily: DISP }}
            >
              Commission
            </div>
            <div
              className="text-base font-bold"
              style={{ color: GREEN, fontFamily: MONO }}
            >
              {fmt(terminal.commissionBalance)}
            </div>
          </div>
        </div>
      </div>

      {/* ── Quick Access Strip (P0: touch targets 48px) ── */}
      <div
        className="flex gap-2 px-4 py-2 flex-shrink-0 overflow-x-auto"
        style={{ borderBottom: `1px solid ${BORDER}` }}
      >
        {quickAccess.map((t: any) => (
          <TileContextMenu
            key={t.id}
            disabled={editMode}
            actions={(TILE_QUICK_ACTIONS[t.id] || []).map(a => ({
              label: a.label,
              icon: a.icon,
              action: () => navigate(a.screenOverride || t.screen, t.id),
            }))}
          >
            <button
              onClick={() => navigate(t.screen, t.id)}
              className="flex flex-col items-center gap-1 flex-shrink-0 transition-all active:scale-90 touch-target"
              aria-label={`Quick access: ${t.label}`}
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center text-lg"
                style={{
                  background: t.bgColor,
                  border: `1px solid ${t.color}40`,
                }}
              >
                {t.icon}
              </div>
              <span
                className="text-xs text-gray-400 whitespace-nowrap"
                style={{ fontFamily: DISP, fontSize: 10 }}
              >
                {t.label}
              </span>
            </button>
          </TileContextMenu>
        ))}
        <div
          className="w-px flex-shrink-0 mx-1"
          style={{ background: BORDER }}
        />
        <button
          onClick={() => setShowEditor(true)}
          className="flex flex-col items-center gap-1 flex-shrink-0 touch-target"
          aria-label="Add more tiles"
        >
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-lg"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            +
          </div>
          <span
            className="text-xs text-gray-500 whitespace-nowrap"
            style={{ fontFamily: DISP, fontSize: 10 }}
          >
            More
          </span>
        </button>
      </div>

      {/* ── Transaction Quick-Entry Strip (P1) ── */}
      <div
        className="flex gap-1.5 px-4 py-1.5 overflow-x-auto flex-shrink-0"
        style={{
          borderBottom: `1px solid ${BORDER}`,
          background: "oklch(0.08 0.01 240)",
        }}
      >
        {QUICK_AMOUNTS.map(amt => (
          <button
            key={amt}
            onClick={() => {
              haptic("micro");
              setQuickEntryAmount(amt);
              setShowQuickEntry(true);
            }}
            className="amount-chip"
            style={{
              background: CARD,
              color: GREEN,
              border: `1px solid ${BORDER}`,
            }}
          >
            ₦{amt >= 1000 ? `${amt / 1000}K` : amt}
          </button>
        ))}
      </div>

      {/* ── Category Filter (P0: touch targets 44px) ── */}
      <div
        className="flex gap-2 px-4 py-2 overflow-x-auto flex-shrink-0"
        style={{ borderBottom: `1px solid ${BORDER}` }}
      >
        {cats.map((c: any) => (
          <button
            key={c}
            onClick={() => {
              haptic("micro");
              setCatFilter(c);
            }}
            className="px-4 py-2.5 rounded-lg text-xs font-semibold whitespace-nowrap capitalize transition-all touch-target"
            style={{
              background: catFilter === c ? BLUE : CARD,
              color: catFilter === c ? "white" : "#9ca3af",
              border: `1px solid ${catFilter === c ? BLUE : BORDER}`,
            }}
            aria-pressed={catFilter === c}
          >
            {c}
          </button>
        ))}
      </div>

      {/* ── Daily Progress Bar (P2: status enhancement) ── */}
      <div
        className="px-4 py-1 flex-shrink-0"
        style={{ background: "oklch(0.08 0.01 240)" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-xs"
            style={{ color: "#6b7280", fontFamily: MONO }}
          >
            {terminal.txToday}/{terminal.txTarget} today
          </span>
          <div
            className="flex-1 h-1.5 rounded-full"
            style={{ background: BORDER }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min((terminal.txToday / terminal.txTarget) * 100, 100)}%`,
                background: BLUE,
              }}
            />
          </div>
          <span
            className="text-xs font-bold"
            style={{
              color: successTier === "Excellent" ? GREEN : GOLD,
              fontFamily: MONO,
            }}
          >
            {successRatePct != null ? `${successRatePct}%` : "—"}
          </span>
        </div>
      </div>

      {/* ── Tile Grid (P1: DndContext wrapper) ── */}
      <PullToRefresh
        onRefresh={async () => {
          window.location.reload();
        }}
        disabled={editMode || showQuickEntry}
        className="flex-1 overflow-y-auto"
        style={{ background: BG }}
      >
        <DndContext
          sensors={dndSensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext items={layout} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-4 gap-2 p-4 grid-tile-enter">
              {visibleTiles.map((tile: any) => (
                <SortableTile
                  key={tile.id}
                  tile={tile}
                  editMode={editMode}
                  isOnline={isOnline}
                  onPress={t => navigate(t.screen, t.id)}
                  customSize={tileCustom.sizes[tile.id]}
                  customColor={tileCustom.colors[tile.id]}
                  liveData={tileLiveData[tile.id]}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      </PullToRefresh>

      {/* ── Live Ticker ── */}
      <div
        className="flex-shrink-0 overflow-hidden"
        style={{
          background: "oklch(0.07 0.01 240)",
          borderTop: `1px solid ${BORDER}`,
        }}
      >
        <div
          ref={tickerRef}
          className="whitespace-nowrap py-1.5 px-4"
          style={{
            transform: `translateX(${tickerPos}px)`,
            fontFamily: MONO,
            fontSize: 11,
          }}
        >
          {tickerText ? (
            <span style={{ color: "#6b7280" }}>{tickerText}&nbsp;&nbsp;&nbsp;·&nbsp;&nbsp;&nbsp;{tickerText}</span>
          ) : (
            <span style={{ color: "#4b5563" }}>Live stats appear here once today's data loads…</span>
          )}
        </div>
      </div>

      {/* ── Bottom Bar ── */}
      <div
        className="flex items-center justify-between px-4 py-3 flex-shrink-0"
        style={{
          background: "oklch(0.07 0.01 240)",
          borderTop: `1px solid ${BORDER}`,
        }}
      >
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => {
              haptic("micro");
              setEditMode(!editMode);
            }}
            className="px-3 py-2 rounded-xl text-xs font-semibold transition-all touch-target"
            style={{
              background: editMode ? BLUE : CARD,
              color: editMode ? "white" : "#9ca3af",
              border: `1px solid ${editMode ? BLUE : BORDER}`,
            }}
            aria-pressed={editMode}
          >
            {editMode ? "Done" : "Edit"}
          </button>
          <button
            onClick={() => setShowPresets(true)}
            className="px-3 py-2 rounded-xl text-xs font-semibold transition-all touch-target"
            style={{
              background: CARD,
              color: "#9ca3af",
              border: `1px solid ${BORDER}`,
            }}
          >
            Layouts
          </button>
          <button
            onClick={() => setShowLanguageSelector(true)}
            className="px-3 py-2 rounded-xl text-xs font-semibold transition-all touch-target"
            style={{
              background: CARD,
              color: "#9ca3af",
              border: `1px solid ${BORDER}`,
            }}
          >
            🌐
          </button>
        </div>
        <div className="flex items-center gap-1.5">
          {/* EOD Widget — Sprint 74 */}
          <EODWidget onOpen={() => navigate("EODReconcile", "eod-reconcile")} />
          {/* Logout — Sprint 74: F9 */}
          <button
            onClick={() => {
              storeLogout();
              toast.success("Signed out");
              window.location.href = "/pos-login";
            }}
            className="p-2 rounded-xl transition-all active:scale-95"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
            title="Sign out"
          >
            <span className="text-sm">⏻</span>
          </button>
        </div>
      </div>

      {/* ── Modals ── */}
      {showEditor && (
        <TileEditorSheet
          layout={layout}
          onClose={() => setShowEditor(false)}
          onSave={ids => {
            setLayout(ids);
            setTileCustom(c => {
              const updated = { ...c, order: ids };
              saveTileCustomizations(updated);
              return updated;
            });
          }}
        />
      )}
      {showGamification && (
        <GamificationPanel onClose={() => setShowGamification(false)} />
      )}
      {showNotifications && (
        <NotificationPanel onClose={() => setShowNotifications(false)} />
      )}
      {showUSSD && <USSDSimulator onClose={() => setShowUSSD(false)} />}
      {showArch && <ArchitecturePanel onClose={() => setShowArch(false)} />}
      {showFraudDash && (
        <div className="fixed inset-0 z-50" style={{ background: BG }}>
          <FraudDashboard onClose={() => setShowFraudDash(false)} />
        </div>
      )}
      {showLiveChat && (
        <div className="fixed inset-0 z-50" style={{ background: BG }}>
          <LiveChatSupport onClose={() => setShowLiveChat(false)} />
        </div>
      )}
      {showLoyalty && (
        <div className="fixed inset-0 z-50" style={{ background: BG }}>
          <LoyaltySystem onClose={() => setShowLoyalty(false)} />
        </div>
      )}
      {showPresets && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end"
          style={{
            maxWidth: 430,
            margin: "0 auto",
            background: "oklch(0.04 0.01 240 / 0.85)",
          }}
          onClick={e => {
            if (e.target === e.currentTarget) setShowPresets(false);
          }}
        >
          <div
            className="rounded-t-3xl p-5 flex flex-col gap-3"
            style={{ background: BG, border: `1px solid ${BORDER}` }}
          >
            <div className="flex items-center justify-between">
              <div
                className="text-base font-black text-white"
                style={{ fontFamily: DISP }}
              >
                Layout Presets
              </div>
              <button
                onClick={() => setShowPresets(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: CARD, color: "#9ca3af" }}
              >
                ✕
              </button>
            </div>
            {LAYOUT_PRESETS.map((preset: any) => (
              <button
                key={preset.id}
                onClick={() => applyPreset(preset)}
                disabled={preset.id === "custom"}
                className="flex items-center gap-3 p-4 rounded-2xl text-left transition-all active:scale-95 disabled:opacity-50"
                style={{
                  background:
                    tileCustom.preset === preset.id
                      ? "oklch(0.60 0.22 260 / 0.2)"
                      : CARD,
                  border: `1px solid ${tileCustom.preset === preset.id ? BLUE : BORDER}`,
                }}
              >
                <div className="flex-1">
                  <div
                    className="text-sm font-bold text-white"
                    style={{ fontFamily: DISP }}
                  >
                    {preset.name}
                  </div>
                  <div
                    className="text-xs text-gray-400"
                    style={{ fontFamily: DISP }}
                  >
                    {preset.description}
                  </div>
                </div>
                {tileCustom.preset === preset.id && (
                  <span className="text-xs font-bold" style={{ color: BLUE }}>
                    Active
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
      {showLanguageSelector && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end"
          style={{
            maxWidth: 430,
            margin: "0 auto",
            background: "oklch(0.04 0.01 240 / 0.85)",
          }}
          onClick={e => {
            if (e.target === e.currentTarget) setShowLanguageSelector(false);
          }}
        >
          <div
            className="rounded-t-3xl p-5 flex flex-col gap-3"
            style={{ background: BG, border: `1px solid ${BORDER}` }}
          >
            <div className="flex items-center justify-between">
              <div
                className="text-base font-black text-white"
                style={{ fontFamily: DISP }}
              >
                {t("language.select", "Select Language")}
              </div>
              <button
                onClick={() => setShowLanguageSelector(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: CARD, color: "#9ca3af" }}
              >
                ✕
              </button>
            </div>
            {[
              { code: "en", label: "English" },
              { code: "ha", label: "Hausa" },
              { code: "yo", label: "Yorùbá" },
              { code: "ig", label: "Igbo" },
              { code: "pcm", label: "Nigerian Pidgin" },
            ].map(lang => (
              <button
                key={lang.code}
                onClick={() => {
                  setShowLanguageSelector(false);
                  toast.success(`Language: ${lang.label}`);
                }}
                className="w-full py-3.5 rounded-2xl text-sm font-bold text-white text-left px-4 transition-all active:scale-95"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </div>
      )}
      {/* ── Tile Size Chooser (P2) ── */}
      {showSizeChooser && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end"
          style={{
            maxWidth: 430,
            margin: "0 auto",
            background: "oklch(0.04 0.01 240 / 0.85)",
          }}
          onClick={e => {
            if (e.target === e.currentTarget) setShowSizeChooser(null);
          }}
        >
          <div
            className="rounded-t-3xl p-5 flex flex-col gap-3"
            style={{ background: BG, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-base font-black text-white"
              style={{ fontFamily: DISP }}
            >
              Tile Size
            </div>
            <div className="grid grid-cols-4 gap-2">
              {(["sm", "md", "lg", "wide"] as TileSize[]).map(size => (
                <button
                  key={size}
                  onClick={() => changeTileSize(showSizeChooser, size)}
                  className="py-3 rounded-xl text-xs font-bold uppercase transition-all active:scale-95"
                  style={{
                    background:
                      tileCustom.sizes[showSizeChooser] === size
                        ? BLUE
                        : CARD,
                    color: "white",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  {size}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      {/* ── Tile Color Themer (P3) ── */}
      {showTileThemer && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end"
          style={{
            maxWidth: 430,
            margin: "0 auto",
            background: "oklch(0.04 0.01 240 / 0.85)",
          }}
          onClick={e => {
            if (e.target === e.currentTarget) setShowTileThemer(null);
          }}
        >
          <div
            className="rounded-t-3xl p-5 flex flex-col gap-3"
            style={{ background: BG, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-base font-black text-white"
              style={{ fontFamily: DISP }}
            >
              Tile Color
            </div>
            <div className="grid grid-cols-4 gap-2">
              {TILE_THEME_COLORS.map(theme => (
                <button
                  key={theme.name}
                  onClick={() => changeTileColor(showTileThemer, theme.hue)}
                  className="py-3 rounded-xl text-xs font-bold transition-all active:scale-95"
                  style={{
                    background:
                      theme.hue >= 0
                        ? `oklch(0.35 0.15 ${theme.hue})`
                        : CARD,
                    color: "white",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  {theme.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      {/* ── Offline USSD Bottom-Sheet Modal ── */}
      <OfflineUssdModal
        showOfflineUssd={showOfflineUssd}
        setShowOfflineUssd={setShowOfflineUssd}
        homeUssdCodes={homeUssdCodes}
        terminal={terminal}
        printUssdHome={printUssdHome}
      />
      {/* ── Quick Entry Modal (P1) ── */}
      <QuickEntryModal
        showQuickEntry={showQuickEntry}
        setShowQuickEntry={setShowQuickEntry}
        quickEntryAmount={quickEntryAmount}
        setQuickEntryDirection={setQuickEntryDirection}
        navigate={navigate}
      />
      {/* ── USSD FAB (visible when offline with pending queue) ── */}
      {storeOfflineQueue.length > 0 && (
        <button
          onClick={generateHomeUssdCodes}
          disabled={generatingHomeUssd}
          className="absolute z-40 w-14 h-14 rounded-full flex items-center justify-center transition-all active:scale-90"
          style={{
            bottom: 96,
            right: 16,
            background: GOLD,
            color: "#000",
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
          }}
          title="Generate USSD codes for offline transactions"
        >
          <span style={{ fontSize: 20 }}>
            {generatingHomeUssd ? "⏳" : "📞"}
          </span>
          <span
            className="absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ background: RED, color: "#fff" }}
          >
            {storeOfflineQueue.length}
          </span>
        </button>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// SCREEN COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

// 1. Cash In ────────────────────────────────────────────────────────────────────

export { FraudDashboardPanel } from "./POSShell.part1";
export { FraudDashboardPanel as FraudPanel } from "./POSShell.part1";
export { GamificationPanel as GamificationWidget } from "./POSShell.part10";
export { DisputesPanel } from "./POSShell.part2";
export { KYCVerifyScreen, UssdTransactionScreen } from "./POSShell.part4";
export { FloatBalanceScreen, ReconciliationWizard, SuccessScreen, CarrierSwitchScreen } from "./POSShell.part5";
export { ArchitecturePanel, NanoLoanScreen, MyLimitsScreen, NetworkTestScreen, ReceiptModal } from "./POSShell.part6";
export { FraudAlertsScreen, ReversalScreen, CashOutScreen, PrinterTestScreen, TransferScreen, TxHistoryScreen, BiometricScreen } from "./POSShell.part7";
export { ReconcileScreen, TerminalConfigScreen, AIFraudExplanationModal, SupervisorApprovalModal, CashInScreen, ScorecardScreen, USSDSimulator, CustomerLookupScreen } from "./POSShell.part8";
export { AnalyticsScreen, FirmwareOTAScreen, TileEditorSheet, AMLCheckScreen, OpenAccountScreen, CommissionScreen, AirtimeScreen, ReceiptPrinterModal, DailyReportScreen } from "./POSShell.part9";
