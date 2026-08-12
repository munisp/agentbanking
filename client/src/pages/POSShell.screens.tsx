// Screens registry and overlay panels extracted from the POSShell entry module
// (POSShell.tsx) to keep the entry under the push size limit. Pure factory plus
// props-only components — every value from the shell is passed in explicitly.
import { haptic } from "../lib/haptics";
import { toast } from "sonner";
import { QRPaymentScreen } from "./POSShell.part1";
import { AuditLogScreen, BillsScreen, CardPaymentScreen, MicroInsuranceScreen, NFCPaymentScreen, SettlementScreen } from "./POSShell.part10";
import { OfflineResilienceScreen } from "./POSShell.part2";
import { DisputesScreen } from "./POSShell.part3";
import { KYCVerifyScreen, UssdTransactionScreen } from "./POSShell.part4";
import { CarrierSwitchScreen, FloatBalanceScreen, ReconciliationWizard } from "./POSShell.part5";
import { MyLimitsScreen, NanoLoanScreen, NetworkTestScreen, fmt } from "./POSShell.part6";
import { BiometricScreen, CashOutScreen, FraudAlertsScreen, PrinterTestScreen, ReversalScreen, TransferScreen, TxHistoryScreen } from "./POSShell.part7";
import { CashInScreen, CustomerLookupScreen, ReconcileScreen, ScorecardScreen, TerminalConfigScreen } from "./POSShell.part8";
import { AMLCheckScreen, AirtimeScreen, AnalyticsScreen, CommissionScreen, DailyReportScreen, FirmwareOTAScreen, OpenAccountScreen } from "./POSShell.part9";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TerminalInfo } from "./POSShell.shared";

type VelocityWarning = {
  type: "hourly_count" | "daily_volume";
  used: number;
  limit: number;
  pct: number;
  tier: string;
} | null;

type TerminalKilled = {
  reason: string;
  disabledBy: string;
  disabledAt: string;
} | null;

type HomeUssdCode = {
  id: string;
  ussd_string: string;
  instructions: string;
  carrier_hint: string | null;
  tx_type: string;
  amount: number;
};

interface ScreensDeps {
  goHome: () => void;
  liveCommissionData: any[];
  liveChartData: any[];
  setActiveScreen: (screen: string | null) => void;
}

interface VelocityWarningBannerProps {
  velocityWarning: VelocityWarning;
  setVelocityWarning: (v: VelocityWarning) => void;
}

interface FloatLockOverlaysProps {
  terminalKilled: TerminalKilled;
  floatLocked: boolean;
  lockElapsed: number;
  fmtElapsed: (s: number) => string;
}

interface OfflineModeIndicatorProps {
  connQuality: string;
  pendingQueueCount: number;
  storeOfflineQueue: unknown[] | null | undefined;
}

interface OfflineUssdModalProps {
  showOfflineUssd: boolean;
  setShowOfflineUssd: (v: boolean) => void;
  homeUssdCodes: HomeUssdCode[];
  terminal: TerminalInfo;
  printUssdHome: any;
}

interface QuickEntryModalProps {
  showQuickEntry: boolean;
  setShowQuickEntry: (v: boolean) => void;
  quickEntryAmount: number | null;
  setQuickEntryDirection: (d: "CashIn" | "CashOut" | null) => void;
  navigate: (screen: string, tileId?: string) => void;
}
// ── Screen registry (was inline in POSShell router) ───────────────────────
export function createScreens({
  goHome,
  liveCommissionData,
  liveChartData,
  setActiveScreen,
}: ScreensDeps): Record<string, React.ReactNode> {
  const props = { onBack: goHome };
  return {
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
}
// ── Velocity Warning Amber Banner ──────────────────────────────────────────
export function VelocityWarningBanner({
  velocityWarning,
  setVelocityWarning,
}: VelocityWarningBannerProps) {
  if (!velocityWarning) return null;
  return (
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
  );
}
// ── Float-Lock / Kill-Switch Overlays ──────────────────────────────────────
export function FloatLockOverlays({
  terminalKilled,
  floatLocked,
  lockElapsed,
  fmtElapsed,
}: FloatLockOverlaysProps) {
  return (
    <>
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
    </>
  );
}
// ── Offline Mode Indicator (Sprint 74: F10-F16) ────────────────────────────
export function OfflineModeIndicator({
  connQuality,
  pendingQueueCount,
  storeOfflineQueue,
}: OfflineModeIndicatorProps) {
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
}
// ── Offline USSD Bottom-Sheet Modal ────────────────────────────────────────
export function OfflineUssdModal({
  showOfflineUssd,
  setShowOfflineUssd,
  homeUssdCodes,
  terminal,
  printUssdHome,
}: OfflineUssdModalProps) {
  if (!showOfflineUssd) return null;
  return (
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
                      if (!terminal.agentCode) {
                        toast.error("Agent profile not loaded yet — cannot print.");
                        return;
                      }
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
  );
}
// ── Quick Entry Modal (P1: transaction quick-entry) ────────────────────────
export function QuickEntryModal({
  showQuickEntry,
  setShowQuickEntry,
  quickEntryAmount,
  setQuickEntryDirection,
  navigate,
}: QuickEntryModalProps) {
  if (!showQuickEntry || !quickEntryAmount) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end"
      style={{
        maxWidth: 430,
        margin: "0 auto",
        background: "oklch(0.04 0.01 240 / 0.85)",
      }}
      onClick={e => {
        if (e.target === e.currentTarget) setShowQuickEntry(false);
      }}
    >
      <div
        className="rounded-t-3xl p-5 flex flex-col gap-4"
        style={{ background: BG, border: `1px solid ${BORDER}` }}
      >
        <div className="flex items-center justify-between">
          <div
            className="text-base font-black text-white"
            style={{ fontFamily: DISP }}
          >
            Quick Transaction · {fmt(quickEntryAmount)}
          </div>
          <button
            onClick={() => setShowQuickEntry(false)}
            className="w-8 h-8 rounded-full flex items-center justify-center"
            style={{ background: CARD, color: "#9ca3af" }}
          >
            ✕
          </button>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setQuickEntryDirection("CashIn");
              navigate("CashIn");
              setShowQuickEntry(false);
              haptic("success");
            }}
            className="flex-1 py-4 rounded-2xl text-sm font-bold text-white transition-all active:scale-95 touch-target"
            style={{
              background: "oklch(0.45 0.18 160)",
              border: `1px solid ${GREEN}44`,
            }}
          >
            ⬇ Cash In
          </button>
          <button
            onClick={() => {
              setQuickEntryDirection("CashOut");
              navigate("CashOut");
              setShowQuickEntry(false);
              haptic("success");
            }}
            className="flex-1 py-4 rounded-2xl text-sm font-bold text-white transition-all active:scale-95 touch-target"
            style={{
              background: "oklch(0.45 0.18 260)",
              border: `1px solid ${BLUE}44`,
            }}
          >
            ⬆ Cash Out
          </button>
        </div>
        <button
          onClick={() => {
            navigate("Transfer");
            setShowQuickEntry(false);
            haptic("success");
          }}
          className="w-full py-3 rounded-2xl text-sm font-bold text-white transition-all active:scale-95 touch-target"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          ⇄ Transfer
        </button>
      </div>
    </div>
  );
}
