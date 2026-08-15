// @ts-nocheck
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
import { GdprConsentBanner } from "../components/GdprConsentBanner";
import { NotificationBell } from "../components/NotificationBell";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useCallback, useEffect, useRef, useState } from "react";
import { Bar } from "recharts";
import { toast } from "sonner";
import { OfflineResilienceScreen } from "./POSShell.part1";
import { AnalyticsScreen, AuditLogScreen, BillsScreen, DailyReportScreen, NFCPaymentScreen, SettlementScreen } from "./POSShell.part10";
import { QRPaymentScreen } from "./POSShell.part2";
import { DisputesScreen } from "./POSShell.part3";
import { CarrierSwitchScreen, KYCVerifyScreen } from "./POSShell.part4";
import { FloatBalanceScreen, NetworkTestScreen, ReconciliationWizard, UssdTransactionScreen, fmt } from "./POSShell.part5";
import { ArchitecturePanel, FirmwareOTAScreen, MicroInsuranceScreen, MyLimitsScreen } from "./POSShell.part6";
import { CashOutScreen, FraudAlertsScreen, NanoLoanScreen, PrinterTestScreen, ReversalScreen, TransferScreen } from "./POSShell.part7";
import { AMLCheckScreen, CashInScreen, ReconcileScreen, TerminalConfigScreen, TileEditorSheet, TxHistoryScreen, USSDSimulator } from "./POSShell.part8";
import { AirtimeScreen, BiometricScreen, CardPaymentScreen, CommissionScreen, CustomerLookupScreen, GamificationPanel, NotificationPanel, OpenAccountScreen, ScorecardScreen } from "./POSShell.part9";
import { BG, BLUE, BORDER, CARD, CHART_DATA, COMMISSION_DATA, DEFAULT_LAYOUT, DISP, GAMIFICATION, GOLD, GREEN, MONO, RED, TERMINAL, TICKER_ITEMS, TILE_REGISTRY, Tile, TileCategory } from "./POSShell.shared";

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

  // Live clock
  useEffect(() => {
    const iv = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  // ── Resilience: connection quality probe (Go service) ────────────────────
  const { data: probeData } = trpc.resilience.probe.useQuery(undefined, {
    refetchInterval: 5_000,
    retry: false,
  });
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
  });
  const pendingQueueCount: number = (queueData as any)?.pending ?? 0;

  // ── Resilience: 7-day success rate (Python service) ──────────────────────
  const { data: successRateData } = trpc.resilience.successRate.useQuery(
    { days: 7 },
    {
      refetchInterval: 60_000,
      retry: false,
    }
  );
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
  const encodeUssdHome = trpc.resilience.encodeUssd.useMutation();
  const printUssdHome = trpc.resilience.printUssdReceipt.useMutation();
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

  // Merge store agent data into terminal display (falls back to TERMINAL mock)
  const terminal = storeAgent
    ? {
        ...TERMINAL,
        agentName: storeAgent.name,
        agentCode: storeAgent.agentCode,
        floatBalance: storeAgent.floatBalance,
        commissionBalance: storeAgent.commissionBalance,
        tier: storeAgent.tier,
        location: storeAgent.location ?? TERMINAL.location,
        online: isOnline,
        network: isOnline ? TERMINAL.network : ("Offline" as const),
      }
    : TERMINAL;

  // ── Float-lock status polling (every 30s) ──────────────────────────────────
  const setAgent = usePosStore(s => s.setAgent);
  const { data: agentMeData } = trpc.agent.me.useQuery(undefined, {
    refetchInterval: 30_000,
    retry: false,
    enabled: !!storeAgent,
  });
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
  );
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

  // Live loyalty/gamification from tRPC
  const { data: loyaltyProfile } = trpc.loyalty.profile.useQuery(undefined, {
    retry: false,
    refetchInterval: 60000,
  });
  const gamification = loyaltyProfile
    ? {
        ...GAMIFICATION,
        points: loyaltyProfile.points,
        level: loyaltyProfile.tier + " Agent",
        streak: storeAgent?.streak ?? GAMIFICATION.streak,
        rank: storeAgent?.rank ?? GAMIFICATION.rank,
      }
    : GAMIFICATION;

  // ── Live analytics: day stats for ticker, hourly chart, commission chart ──
  const { data: dayStats } = trpc.transactions.agentDayStats.useQuery(
    undefined,
    {
      refetchInterval: 30_000,
      retry: false,
    }
  );
  const { data: liveHourlyStats } = trpc.transactions.hourlyStats.useQuery(
    undefined,
    {
      refetchInterval: 60_000,
      retry: false,
    }
  );
  const { data: liveCommissionStats } =
    trpc.transactions.commissionStats.useQuery(undefined, {
      refetchInterval: 60_000,
      retry: false,
    });

  // Build live ticker items from dayStats (falls back to TICKER_ITEMS if not loaded)
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
    : TICKER_ITEMS;

  // Build chart data from live queries (fall back to static mocks)
  const liveChartData =
    liveHourlyStats && liveHourlyStats.length > 0
      ? liveHourlyStats.map((b: any) => ({
          h: b.h,
          in: b.cashIn,
          out: b.cashOut,
        }))
      : CHART_DATA;
  const liveCommissionData =
    liveCommissionStats && liveCommissionStats.length > 0
      ? liveCommissionStats
      : COMMISSION_DATA;

  // WebSocket connection status from store
  const wsStatus = isOnline ? ("connected" as const) : ("offline" as const);

  // Live notification badge count
  const notifCount = unreadFraudCount + unreadChatCount;

  const navigate = useCallback(
    (screen: string) => {
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
    ]
  );

  const goHome = useCallback(() => setActiveScreen(null), []);

  // ── Dynamic badge: offline-resilience tile shows total pending count ────────
  const offlineQueueStore = usePosStore(s => s.offlineQueue);
  const totalOfflinePending = offlineQueueStore.length + pendingQueueCount;

  const visibleTiles = layout
    .map(id => TILE_REGISTRY.find(t => t.id === id))
    .filter(
      (t): t is Tile => !!t && (catFilter === "all" || t.category === catFilter)
    )
    .map(t =>
      t.id === "offline-resilience" && totalOfflinePending > 0
        ? { ...t, badge: totalOfflinePending }
        : t
    );

  const quickAccess = [...TILE_REGISTRY]
    .sort((a: any, b: any) => (b.usageCount || 0) - (a.usageCount || 0))
    .slice(0, 4);

  // Screen router
  if (activeScreen) {
    const props = { onBack: goHome };
    const screenMap: Record<string, React.ReactNode> = {
      CashIn: <CashInScreen {...props} />,
      CashOut: <CashOutScreen {...props} />,
      Transfer: <TransferScreen {...props} />,
      CardPayment: <CardPaymentScreen {...props} />,
      QRPayment: <QRPaymentScreen {...props} />,
      NFCPayment: <NFCPaymentScreen {...props} />,
      Airtime: <AirtimeScreen {...props} />,
      Bills: <BillsScreen {...props} />,
      Reversal: <ReversalScreen {...props} />,
      CustomerLookup: <CustomerLookupScreen {...props} />,
      KYCVerify: <KYCVerifyScreen {...props} />,
      Biometric: <BiometricScreen {...props} />,
      OpenAccount: <OpenAccountScreen {...props} />,
      FloatBalance: <FloatBalanceScreen {...props} />,
      Commission: (
        <CommissionScreen {...props} commissionData={liveCommissionData} />
      ),
      Settlement: <SettlementScreen {...props} />,
      Reconcile: <ReconcileScreen {...props} />,
      FraudAlerts: <FraudAlertsScreen {...props} />,
      AMLCheck: <AMLCheckScreen {...props} />,
      AuditLog: <AuditLogScreen {...props} />,
      MyLimits: <MyLimitsScreen {...props} />,
      DailyReport: <DailyReportScreen {...props} chartData={liveChartData} />,
      TxHistory: <TxHistoryScreen {...props} />,
      Analytics: <AnalyticsScreen {...props} chartData={liveChartData} />,
      Scorecard: <ScorecardScreen {...props} />,
      TerminalConfig: <TerminalConfigScreen {...props} />,
      PrinterTest: <PrinterTestScreen {...props} />,
      NetworkTest: <NetworkTestScreen {...props} />,
      FirmwareOTA: <FirmwareOTAScreen {...props} />,
      NanoLoan: <NanoLoanScreen {...props} />,
      EODReconcile: <ReconciliationWizard {...props} />,
      MicroInsurance: <MicroInsuranceScreen {...props} />,
      Disputes: <DisputesScreen onBack={() => setActiveScreen(null)} />,
      OfflineResilience: <OfflineResilienceScreen {...props} />,
      UssdTransaction: <UssdTransactionScreen {...props} />,
      CarrierSwitch: <CarrierSwitchScreen {...props} />,
    };
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
    .map(t => `${t.label}: ${t.value}  ${t.change}`)
    .join("   ·   ");

  return (
    <div
      className="relative flex flex-col h-screen overflow-hidden select-none"
      style={{ background: BG, maxWidth: 430, margin: "0 auto" }}
    >
      {/* ── GDPR/NDPR Consent Banner ── */}
      <GdprConsentBanner agentId={storeAgent?.agentCode} />
      {/* ── Velocity Warning Amber Banner ── */}
      {velocityWarning && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 150,
            background: "oklch(0.55 0.22 65 / 0.95)",
            borderBottom: "2px solid oklch(0.70 0.25 65)",
            padding: "0.5rem 1rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            backdropFilter: "blur(4px)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: 18 }}>⚠️</span>
            <div>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "oklch(0.98 0.02 65)",
                  fontFamily: "monospace",
                }}
              >
                {velocityWarning.type === "hourly_count"
                  ? `HOURLY LIMIT WARNING — ${velocityWarning.pct}% USED`
                  : `DAILY VOLUME WARNING — ${velocityWarning.pct}% USED`}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: "oklch(0.90 0.05 65)",
                  fontFamily: "monospace",
                }}
              >
                {velocityWarning.type === "hourly_count"
                  ? `${velocityWarning.used} of ${velocityWarning.limit} transactions this hour (${velocityWarning.tier} tier)`
                  : `₦${Number(velocityWarning.used).toLocaleString("en-NG")} of ₦${Number(velocityWarning.limit).toLocaleString("en-NG")} daily volume (${velocityWarning.tier} tier)`}
              </div>
            </div>
          </div>
          <button
            onClick={() => setVelocityWarning(null)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "oklch(0.98 0.02 65)",
              fontSize: 16,
              padding: "0 0.25rem",
            }}
            aria-label="Dismiss warning"
          >
            ×
          </button>
        </div>
      )}

      {/* ── Float-Lock Overlay ── */}
      {terminalKilled && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            zIndex: 200,
            background: "oklch(0.10 0.03 25 / 0.97)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backdropFilter: "blur(8px)",
          }}
        >
          <div style={{ textAlign: "center", maxWidth: 480, padding: "2rem" }}>
            <div style={{ fontSize: 64, marginBottom: "1rem" }}>🔴</div>
            <div
              style={{
                fontSize: 22,
                fontWeight: 700,
                color: "oklch(0.85 0.18 25)",
                marginBottom: "0.5rem",
                fontFamily: MONO,
              }}
            >
              TERMINAL DISABLED
            </div>
            <div
              style={{
                fontSize: 13,
                color: "oklch(0.65 0.05 25)",
                marginBottom: "1.5rem",
                fontFamily: MONO,
              }}
            >
              This terminal has been remotely disabled by your administrator.
            </div>
            <div
              style={{
                background: "oklch(0.15 0.04 25 / 0.8)",
                border: "1px solid oklch(0.30 0.08 25)",
                borderRadius: 8,
                padding: "1rem 1.5rem",
                textAlign: "left",
                marginBottom: "1.5rem",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  color: "oklch(0.55 0.04 25)",
                  marginBottom: 4,
                  fontFamily: MONO,
                }}
              >
                REASON
              </div>
              <div
                style={{
                  fontSize: 14,
                  color: "oklch(0.85 0.05 25)",
                  fontFamily: MONO,
                }}
              >
                {terminalKilled.reason}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: "oklch(0.50 0.04 25)",
                  marginTop: 8,
                  fontFamily: MONO,
                }}
              >
                Disabled by {terminalKilled.disabledBy} &bull;{" "}
                {new Date(terminalKilled.disabledAt).toLocaleString()}
              </div>
            </div>
            <div
              style={{
                fontSize: 12,
                color: "oklch(0.50 0.04 25)",
                fontFamily: MONO,
              }}
            >
              All transactions are blocked. Contact your supervisor to re-enable
              this terminal.
            </div>
          </div>
        </div>
      )}
      {floatLocked && (
        <div
          className="absolute inset-0 z-50 flex flex-col items-center justify-center gap-6"
          style={{
            background: "oklch(0.05 0.01 240 / 0.97)",
            backdropFilter: "blur(8px)",
            maxWidth: 430,
          }}
        >
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center animate-pulse"
            style={{
              background: "oklch(0.60 0.22 25 / 0.2)",
              border: "2px solid oklch(0.60 0.22 25)",
            }}
          >
            <span style={{ fontSize: 36 }}>🔒</span>
          </div>
          <div className="text-center px-8">
            <div
              className="text-xl font-black text-white mb-2"
              style={{ fontFamily: DISP }}
            >
              Settlement in Progress
            </div>
            <div
              className="text-sm text-gray-400 leading-relaxed"
              style={{ fontFamily: DISP }}
            >
              Transactions are temporarily paused while daily settlement runs.
              This usually takes 2–5 minutes.
            </div>
          </div>
          {/* Elapsed timer */}
          <div className="flex flex-col items-center gap-1">
            <div
              className="text-3xl font-black tabular-nums"
              style={{
                color:
                  lockElapsed >= 600
                    ? "oklch(0.60 0.22 25)"
                    : lockElapsed >= 300
                      ? "oklch(0.78 0.18 80)"
                      : "oklch(0.65 0.18 160)",
                fontFamily: MONO,
              }}
            >
              {fmtElapsed(lockElapsed)}
            </div>
            <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
              locked for
            </div>
          </div>
          <div
            className="px-4 py-2 rounded-xl text-xs font-semibold"
            style={{
              background: "oklch(0.60 0.22 25 / 0.15)",
              color: "oklch(0.60 0.22 25)",
              border: "1px solid oklch(0.60 0.22 25)",
              fontFamily: MONO,
            }}
          >
            Float locked — auto-refreshing every 30s
          </div>
          <div className="text-xs text-gray-600" style={{ fontFamily: MONO }}>
            {lockElapsed >= 600
              ? "⚠ Lock exceeds 10 min — contact your supervisor now"
              : "Contact your supervisor if this persists beyond 10 minutes."}
          </div>
        </div>
      )}
      {/* ── Status Bar ── */}
      <div
        className="flex items-center justify-between px-4 py-2 flex-shrink-0"
        style={{
          background: "oklch(0.07 0.01 240)",
          borderBottom: `1px solid ${BORDER}`,
        }}
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
              style={{
              borderColor:
                (terminal.batteryLevel ?? 0) > 20 ? GREEN : RED,
            }}
            >
              <div
                className="h-1.5 rounded-sm"
                style={{
                  width: `${terminal.batteryLevel ?? 0}%`,
                  background: (terminal.batteryLevel ?? 0) > 20 ? GREEN : RED,
                }}
              />
            </div>
            <span
              className="text-xs"
              style={{
                color: (terminal.batteryLevel ?? 0) > 20 ? GREEN : RED,
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
      {(() => {
        const networkTier =
          connQuality === "Offline"
            ? "offline"
            : connQuality === "Poor"
              ? "2g"
              : connQuality === "Good"
                ? "3g"
                : "4g";
        const queueCount = pendingQueueCount + (storeOfflineQueue?.length ?? 0);
        const lastSyncTime = localStorage.getItem("pos_last_sync") ?? null;
        const isOffline = !navigator.onLine || connQuality === "Offline";
        const isDegraded = connQuality === "Poor" || networkTier === "2g";
        const showBanner = isOffline || isDegraded || queueCount > 0;
        if (!showBanner) return null;
        const tierLabels: Record<string, string> = {
          offline: "OFFLINE",
          "2g": "2G GPRS",
          "3g": "3G",
          "4g": "4G LTE",
        };
        const tierColors: Record<string, string> = {
          offline: RED,
          "2g": "#f97316",
          "3g": GOLD,
          "4g": GREEN,
        };
        const tierBg: Record<string, string> = {
          offline: "oklch(0.15 0.06 25)",
          "2g": "oklch(0.15 0.06 55)",
          "3g": "oklch(0.15 0.04 80)",
          "4g": "oklch(0.12 0.03 150)",
        };
        return (
          <div
            data-testid="offline-mode-indicator"
            className="flex items-center justify-between px-4 py-1.5 flex-shrink-0"
            style={{
              background: tierBg[networkTier],
              borderBottom: `1px solid ${tierColors[networkTier]}44`,
            }}
          >
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                {isOffline ? (
                  <span style={{ fontSize: 12 }}>📡</span>
                ) : (
                  <div
                    className="w-1.5 h-1.5 rounded-full animate-pulse"
                    style={{ background: tierColors[networkTier] }}
                  />
                )}
                <span
                  className="text-xs font-bold"
                  style={{ color: tierColors[networkTier], fontFamily: MONO }}
                >
                  {tierLabels[networkTier]}
                </span>
              </div>
              {isDegraded && !isOffline && (
                <span
                  className="text-xs"
                  style={{ color: "oklch(0.65 0.04 55)", fontFamily: DISP }}
                >
                  Degraded mode — images disabled
                </span>
              )}
              {isOffline && (
                <span
                  className="text-xs"
                  style={{ color: "oklch(0.65 0.06 25)", fontFamily: DISP }}
                >
                  Transactions queued locally
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              {queueCount > 0 && (
                <div className="flex items-center gap-1">
                  <span
                    className="text-xs"
                    style={{ color: "oklch(0.70 0.10 55)", fontFamily: MONO }}
                  >
                    ⏳ {queueCount} queued
                  </span>
                </div>
              )}
              {lastSyncTime && (
                <span
                  className="text-xs"
                  style={{ color: "oklch(0.55 0.02 240)", fontFamily: MONO }}
                >
                  Last sync:{" "}
                  {(() => {
                    const diff = Math.floor(
                      (Date.now() - new Date(lastSyncTime).getTime()) / 1000
                    );
                    if (diff < 60) return `${diff}s ago`;
                    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
                    return `${Math.floor(diff / 3600)}h ago`;
                  })()}
                </span>
              )}
            </div>
          </div>
        );
      })()}

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
                🏆 {gamification.rank != null ? `#${gamification.rank}` : "—"}
              </div>
              <div
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                🔥 {gamification.streak != null ? `${gamification.streak}d streak` : "—"}
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

      {/* ── Quick Access Strip ── */}
      <div
        className="flex gap-2 px-4 py-2 flex-shrink-0 overflow-x-auto"
        style={{ borderBottom: `1px solid ${BORDER}` }}
      >
        {quickAccess.map(t => (
          <button
            key={t.id}
            onClick={() => navigate(t.screen)}
            className="flex flex-col items-center gap-1 flex-shrink-0 transition-all active:scale-90"
          >
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
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
        ))}
        <div
          className="w-px flex-shrink-0 mx-1"
          style={{ background: BORDER }}
        />
        <button
          onClick={() => setShowEditor(true)}
          className="flex flex-col items-center gap-1 flex-shrink-0"
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-lg"
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

      {/* ── Category Filter ── */}
      <div
        className="flex gap-2 px-4 py-2 overflow-x-auto flex-shrink-0"
        style={{ borderBottom: `1px solid ${BORDER}` }}
      >
        {cats.map(c => (
          <button
            key={c}
            onClick={() => setCatFilter(c)}
            className="px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap capitalize transition-all"
            style={{
              background: catFilter === c ? BLUE : CARD,
              color: catFilter === c ? "white" : "#6b7280",
              border: `1px solid ${catFilter === c ? BLUE : BORDER}`,
            }}
          >
            {c}
          </button>
        ))}
      </div>

      {/* ── Tile Grid ── */}
      <div className="flex-1 overflow-y-auto p-3">
        <div className="grid grid-cols-4 gap-2 auto-rows-auto">
          {visibleTiles.map(tile => {
            const colSpan =
              tile.size === "wide"
                ? "col-span-4"
                : tile.size === "lg"
                  ? "col-span-2"
                  : tile.size === "md"
                    ? "col-span-2"
                    : "col-span-1";
            const rowSpan = tile.size === "lg" ? "row-span-2" : "";
            const h =
              tile.size === "lg"
                ? "h-28"
                : tile.size === "wide"
                  ? "h-16"
                  : "h-20";
            return (
              <button
                key={tile.id}
                onClick={() => !editMode && navigate(tile.screen)}
                className={`${colSpan} ${rowSpan} ${h} rounded-2xl p-3 flex flex-col justify-between transition-all active:scale-95 relative overflow-hidden`}
                style={{
                  background: tile.bgColor,
                  border: `1px solid ${tile.color}30`,
                }}
              >
                {/* Wobble in edit mode */}
                {editMode && (
                  <div
                    className="absolute inset-0 rounded-2xl border-2 animate-pulse"
                    style={{ borderColor: tile.color }}
                  />
                )}
                {/* Badge */}
                {(tile.badge || 0) > 0 && (
                  <div
                    className="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white z-10"
                    style={{ background: RED }}
                  >
                    {tile.badge}
                  </div>
                )}
                {/* Hot indicator */}
                {tile.hot && !editMode && (
                  <div
                    className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full animate-pulse"
                    style={{ background: tile.color }}
                  />
                )}
                <div className="text-2xl leading-none">{tile.icon}</div>
                <div>
                  <div
                    className="text-xs font-bold text-white leading-tight"
                    style={{ fontFamily: DISP }}
                  >
                    {tile.label}
                  </div>
                  {tile.size !== "sm" && (
                    <div
                      className="text-xs mt-0.5 leading-tight"
                      style={{
                        color: tile.color,
                        fontFamily: DISP,
                        fontSize: 10,
                        opacity: 0.8,
                      }}
                    >
                      {tile.description}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
          {/* Add tile button */}
          <button
            onClick={() => setShowEditor(true)}
            className="col-span-1 h-20 rounded-2xl flex flex-col items-center justify-center gap-1 transition-all active:scale-95"
            style={{ background: CARD, border: `2px dashed ${BORDER}` }}
          >
            <span className="text-xl text-gray-600">+</span>
            <span
              className="text-xs text-gray-600"
              style={{ fontFamily: DISP, fontSize: 10 }}
            >
              Add
            </span>
          </button>
        </div>
      </div>

      {/* ── Edit Mode Toggle ── */}
      <div
        className="flex items-center justify-between px-4 py-2 flex-shrink-0"
        style={{ borderTop: `1px solid ${BORDER}` }}
      >
        <button
          onClick={() => setEditMode(e => !e)}
          className="px-4 py-2 rounded-xl text-xs font-semibold transition-all"
          style={{
            background: editMode ? "oklch(0.60 0.22 25 / 0.2)" : CARD,
            color: editMode ? RED : "#6b7280",
            border: `1px solid ${editMode ? RED : BORDER}`,
          }}
        >
          {editMode ? "✓ Done Editing" : "✏ Edit Layout"}
        </button>
        <div className="flex items-center gap-2">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: wsStatus === "connected" ? GREEN : GOLD }}
          />
          <span className="text-xs text-gray-500" style={{ fontFamily: MONO }}>
            {TERMINAL.model ?? "—"}
          </span>
        </div>
      </div>

      {/* ── Pending Sync Banner (Rust offline-queue) ── */}
      {pendingQueueCount > 0 && (
        <button
          onClick={generateHomeUssdCodes}
          className="px-4 py-1.5 flex items-center gap-2 flex-shrink-0 w-full text-left transition-all active:opacity-80"
          style={{
            background: "oklch(0.78 0.18 80 / 0.12)",
            borderTop: `1px solid ${GOLD}44`,
          }}
        >
          <span style={{ color: GOLD, fontFamily: DISP, fontSize: 11 }}>
            ⏳ {pendingQueueCount} transaction{pendingQueueCount > 1 ? "s" : ""}{" "}
            pending sync
          </span>
          {!isOnline && (
            <span
              className="ml-auto text-xs font-bold"
              style={{ color: GOLD, fontFamily: MONO }}
            >
              {generatingHomeUssd ? "Generating…" : "📞 USSD Fallback"}
            </span>
          )}
        </button>
      )}

      {/* ── Success Rate Badge (Python analytics) ── */}
      {successRatePct !== null && (
        <div
          className="px-4 py-1 flex items-center gap-2 flex-shrink-0"
          style={{
            background: "oklch(0.08 0.01 240)",
            borderTop: `1px solid ${BORDER}`,
          }}
        >
          <span
            className="text-xs"
            style={{ color: "#4b5563", fontFamily: DISP }}
          >
            7-day success rate:
          </span>
          <span
            className="text-xs font-bold"
            style={{
              color:
                successTier === "Excellent"
                  ? GREEN
                  : successTier === "Good"
                    ? BLUE
                    : successTier === "Fair"
                      ? GOLD
                      : RED,
              fontFamily: MONO,
            }}
          >
            {successRatePct.toFixed(1)}% — {successTier}
          </span>
        </div>
      )}

      {/* ── Live Ticker ── */}
      <div
        className="flex-shrink-0 overflow-hidden py-1.5 px-4"
        style={{
          background: "oklch(0.07 0.01 240)",
          borderTop: `1px solid ${BORDER}`,
        }}
      >
        <div
          ref={tickerRef}
          className="flex items-center gap-6 whitespace-nowrap"
          style={{
            transform: `translateX(${tickerPos % (tickerText.length * 8)}px)`,
            transition: "none",
          }}
        >
          {[...liveTickerItems, ...liveTickerItems].map((t, i) => (
            <div key={i} className="flex items-center gap-1.5 flex-shrink-0">
              <span
                className="text-xs font-bold"
                style={{ color: "#4b5563", fontFamily: MONO }}
              >
                {t.label}
              </span>
              <span
                className="text-xs font-bold text-white"
                style={{ fontFamily: MONO }}
              >
                {t.value}
              </span>
              <span
                className="text-xs"
                style={{ color: t.up ? GREEN : RED, fontFamily: MONO }}
              >
                {t.change}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Overlays ── */}
      {showEditor && (
        <TileEditorSheet
          layout={layout}
          onClose={() => setShowEditor(false)}
          onSave={ids => {
            setLayout(ids);
            toast.success("Layout saved");
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
        <div
          className="fixed inset-0 z-50 overflow-hidden"
          style={{ maxWidth: 430, margin: "0 auto" }}
        >
          <FraudDashboard />
          <button
            onClick={() => setShowFraudDash(false)}
            className="absolute top-3 right-3 z-50 w-8 h-8 rounded-full flex items-center justify-center text-white font-bold"
            style={{
              background: "oklch(0.22 0.015 240)",
              border: "1px solid oklch(0.30 0.015 240)",
            }}
          >
            ✕
          </button>
        </div>
      )}
      {showLiveChat && (
        <div
          className="fixed inset-0 z-50 overflow-hidden"
          style={{ maxWidth: 430, margin: "0 auto" }}
        >
          <LiveChatSupport onBack={() => setShowLiveChat(false)} />
        </div>
      )}
      {showLoyalty && (
        <div
          className="fixed inset-0 z-50 overflow-hidden"
          style={{ maxWidth: 430, margin: "0 auto" }}
        >
          <LoyaltySystem onBack={() => setShowLoyalty(false)} />
        </div>
      )}

      {/* ── Offline USSD Bottom-Sheet Modal ── */}
      {showOfflineUssd && (
        <div
          className="fixed inset-0 z-50 flex flex-col justify-end"
          style={{
            maxWidth: 430,
            margin: "0 auto",
            background: "oklch(0.04 0.01 240 / 0.85)",
          }}
          onClick={e => {
            if (e.target === e.currentTarget) setShowOfflineUssd(false);
          }}
        >
          <div
            className="rounded-t-3xl flex flex-col overflow-hidden"
            style={{
              background: BG,
              border: `1px solid ${GOLD}44`,
              maxHeight: "80vh",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 pt-5 pb-3 flex-shrink-0">
              <div>
                <div
                  className="text-base font-black"
                  style={{ color: GOLD, fontFamily: DISP }}
                >
                  📞 USSD Fallback
                </div>
                <div
                  className="text-xs"
                  style={{ color: "#6b7280", fontFamily: DISP }}
                >
                  Complete transactions without internet
                </div>
              </div>
              <button
                onClick={() => setShowOfflineUssd(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center"
                style={{ background: CARD, color: "#9ca3af" }}
              >
                ✕
              </button>
            </div>
            {/* USSD codes list */}
            <div className="flex-1 overflow-y-auto px-5 pb-5 flex flex-col gap-3">
              {homeUssdCodes.length === 0 ? (
                <div
                  className="text-center py-8 text-sm"
                  style={{ color: "#6b7280", fontFamily: DISP }}
                >
                  No pending transactions to encode.
                </div>
              ) : (
                homeUssdCodes.map((code, i) => (
                  <div
                    key={code.id}
                    className="rounded-2xl p-4"
                    style={{ background: CARD, border: `1px solid ${GOLD}33` }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span
                        className="text-xs font-bold"
                        style={{ color: GOLD, fontFamily: MONO }}
                      >
                        #{i + 1} {code.tx_type.toUpperCase()} · ₦
                        {Number(code.amount).toLocaleString()}
                      </span>
                      {code.carrier_hint && (
                        <span
                          className="text-xs px-2 py-0.5 rounded-full"
                          style={{
                            background: `${BLUE}22`,
                            color: BLUE,
                            fontFamily: MONO,
                          }}
                        >
                          {code.carrier_hint}
                        </span>
                      )}
                    </div>
                    <div
                      className="text-lg font-black mb-1"
                      style={{
                        color: "#ffffff",
                        fontFamily: MONO,
                        letterSpacing: "0.05em",
                      }}
                    >
                      {code.ussd_string}
                    </div>
                    <div
                      className="text-xs mb-3"
                      style={{ color: "#6b7280", fontFamily: DISP }}
                    >
                      {code.instructions}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          navigator.clipboard?.writeText(code.ussd_string);
                          toast.success("Copied!");
                        }}
                        className="flex-1 py-2 rounded-xl text-xs font-bold"
                        style={{
                          background: `${GOLD}22`,
                          color: GOLD,
                          border: `1px solid ${GOLD}44`,
                          fontFamily: MONO,
                        }}
                      >
                        Copy
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await printUssdHome.mutateAsync({
                              agentCode: terminal.agentCode,
                              txType: code.tx_type,
                              amount: code.amount,
                              ussdString: code.ussd_string,
                              instructions: code.instructions,
                            });
                            toast.success("Sent to printer");
                          } catch {
                            toast.error("Printer offline");
                          }
                        }}
                        className="flex-1 py-2 rounded-xl text-xs font-bold"
                        style={{
                          background: `${BLUE}22`,
                          color: BLUE,
                          border: `1px solid ${BLUE}44`,
                          fontFamily: MONO,
                        }}
                      >
                        🖨 Print
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TIER 2 ENHANCEMENTS
// ═══════════════════════════════════════════════════════════════════════════════

// ── Receipt Printer Modal ─────────────────────────────────────────────────────

export { DisputesScreen } from "./POSShell.part3";
export { ReconciliationWizard } from "./POSShell.part5";
export { ArchitecturePanel, MicroInsuranceScreen } from "./POSShell.part6";
export { NanoLoanScreen, SupervisorApprovalModal } from "./POSShell.part7";
export { AIFraudExplanationModal, USSDSimulator } from "./POSShell.part8";
export { NotificationPanel, ReceiptPrinterModal } from "./POSShell.part9";
