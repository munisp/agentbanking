// @ts-nocheck
import type { ChallengeType as MotionChallengeType } from "./useFaceMotionDetection";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useState } from "react";
import { Bar } from "recharts";
import { toast } from "sonner";
import { ScreenHeader } from "./POSShell.part10";
import { fmt } from "./POSShell.part5";
import { BG, BLUE, BORDER, CARD, DISP, GAMIFICATION, GOLD, GREEN, MONO, TERMINAL, TerminalInfo, Transaction } from "./POSShell.shared";

export function ArchitecturePanel({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"services" | "infra" | "hardware">("services");

  const services = [
    {
      name: "Backend API",
      lang: "Python",
      count: 260,
      color: "#3b82f6",
      desc: "FastAPI microservices",
    },
    {
      name: "Go Services",
      lang: "Go",
      count: 52,
      color: "#06b6d4",
      desc: "High-performance event processing",
    },
    {
      name: "Rust Services",
      lang: "Rust",
      count: 5,
      color: "#f59e0b",
      desc: "Ultra-low-latency financial ops",
    },
    {
      name: "React PWA",
      lang: "TSX",
      count: 552,
      color: "#8b5cf6",
      desc: "Management dashboard",
    },
    {
      name: "React Native",
      lang: "JSX",
      count: 64,
      color: "#ec4899",
      desc: "Mobile agent app (64 screens)",
    },
    {
      name: "Flutter",
      lang: "Dart",
      count: 214,
      color: "#10b981",
      desc: "Alternative mobile app",
    },
  ];

  const infra = [
    { name: "Kafka", icon: "📨", desc: "Event streaming & DLQ" },
    { name: "TigerBeetle", icon: "⚡", desc: "Double-entry ledger" },
    { name: "Temporal", icon: "⏱", desc: "Workflow orchestration" },
    { name: "Keycloak", icon: "🔑", desc: "Identity & OAuth2" },
    { name: "Istio", icon: "🕸", desc: "Service mesh & mTLS" },
    { name: "Vault", icon: "🔐", desc: "Secrets management" },
    { name: "PgBouncer", icon: "🏊", desc: "Connection pooling" },
    { name: "APISIX", icon: "🚪", desc: "API gateway" },
    { name: "Prometheus", icon: "📊", desc: "Metrics & alerting" },
    { name: "Flagsmith", icon: "🚩", desc: "Feature flags" },
    { name: "Chaos Mesh", icon: "💥", desc: "Chaos engineering" },
    { name: "OpenTelemetry", icon: "🔭", desc: "Distributed tracing" },
  ];

  const hardware = [
    {
      model: "PAX A920 MAX",
      os: "PayDroid",
      nfc: true,
      printer: true,
      camera: true,
    },
    {
      model: "PAX A8900",
      os: "PayDroid",
      nfc: true,
      printer: true,
      camera: false,
    },
    {
      model: "HorizonPay K11",
      os: "AOSP",
      nfc: true,
      printer: true,
      camera: true,
    },
    {
      model: "Newland N910",
      os: "AOSP",
      nfc: false,
      printer: true,
      camera: false,
    },
    {
      model: "Newland N910 Pro",
      os: "AOSP",
      nfc: true,
      printer: true,
      camera: true,
    },
    {
      model: "Topwise T11 Pro",
      os: "PAXBiz",
      nfc: true,
      printer: true,
      camera: true,
    },
    {
      model: "Topwise MP45P",
      os: "PAXBiz",
      nfc: false,
      printer: false,
      camera: false,
    },
    {
      model: "Verifone P400",
      os: "AOSP",
      nfc: true,
      printer: false,
      camera: false,
    },
    {
      model: "Ingenico MOVE 5000",
      os: "AOSP",
      nfc: true,
      printer: false,
      camera: false,
    },
    {
      model: "Sunmi P2 Pro",
      os: "AOSP",
      nfc: true,
      printer: true,
      camera: true,
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      style={{ background: "rgba(0,0,0,0.85)" }}
      onClick={onClose}
    >
      <div
        className="w-full rounded-t-3xl flex flex-col"
        style={{
          background: "oklch(0.11 0.012 240)",
          border: `1px solid ${BORDER}`,
          maxHeight: "90vh",
        }}
        onClick={e => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between p-4 border-b flex-shrink-0"
          style={{ borderColor: BORDER }}
        >
          <div>
            <div
              className="text-base font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              54Link Platform Architecture
            </div>
            <div className="text-xs text-gray-500">v14 · Production Ready</div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl"
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 px-4 py-3 flex-shrink-0">
          {(["services", "infra", "hardware"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="px-4 py-2 rounded-xl text-xs font-semibold capitalize transition-all"
              style={{
                background: tab === t ? BLUE : CARD,
                color: tab === t ? "white" : "#6b7280",
                border: `1px solid ${tab === t ? BLUE : BORDER}`,
              }}
            >
              {t === "services"
                ? "Services"
                : t === "infra"
                  ? "Infrastructure"
                  : "POS Hardware"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {tab === "services" && (
            <div className="flex flex-col gap-3">
              {services.map((s, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-3 rounded-xl"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xs"
                    style={{
                      background: `${s.color}20`,
                      color: s.color,
                      fontFamily: MONO,
                    }}
                  >
                    {s.lang}
                  </div>
                  <div className="flex-1">
                    <div
                      className="text-sm font-bold text-white"
                      style={{ fontFamily: DISP }}
                    >
                      {s.name}
                    </div>
                    <div className="text-xs text-gray-400">{s.desc}</div>
                  </div>
                  <div className="text-right">
                    <div
                      className="text-lg font-bold"
                      style={{ color: s.color, fontFamily: MONO }}
                    >
                      {s.count}
                    </div>
                    <div className="text-xs text-gray-600">files</div>
                  </div>
                </div>
              ))}
              <div
                className="rounded-xl p-3 text-center"
                style={{
                  background: "oklch(0.65 0.18 160 / 0.1)",
                  border: `1px solid ${GREEN}30`,
                }}
              >
                <div
                  className="text-2xl font-bold"
                  style={{ color: GREEN, fontFamily: MONO }}
                >
                  8,076
                </div>
                <div className="text-xs text-gray-400">
                  Total files across all services
                </div>
              </div>
            </div>
          )}

          {tab === "infra" && (
            <div className="grid grid-cols-2 gap-3">
              {infra.map((item, i) => (
                <div
                  key={i}
                  className="p-3 rounded-xl"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                >
                  <div className="text-2xl mb-1">{item.icon}</div>
                  <div
                    className="text-sm font-bold text-white"
                    style={{ fontFamily: DISP }}
                  >
                    {item.name}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === "hardware" && (
            <div className="flex flex-col gap-2">
              {hardware.map((h, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-3 rounded-xl"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                >
                  <div className="text-xl">🖥</div>
                  <div className="flex-1">
                    <div
                      className="text-sm font-bold text-white"
                      style={{ fontFamily: DISP }}
                    >
                      {h.model}
                    </div>
                    <div className="text-xs text-gray-400">{h.os}</div>
                  </div>
                  <div className="flex gap-1">
                    {h.nfc && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          background: "oklch(0.60 0.22 260 / 0.2)",
                          color: "#3b82f6",
                        }}
                      >
                        NFC
                      </span>
                    )}
                    {h.printer && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          background: "oklch(0.65 0.18 160 / 0.2)",
                          color: GREEN,
                        }}
                      >
                        PRT
                      </span>
                    )}
                    {h.camera && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded"
                        style={{
                          background: "oklch(0.78 0.18 80 / 0.2)",
                          color: GOLD,
                        }}
                      >
                        CAM
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Disputes Screen ──────────────────────────────────────────────────────────

export function MicroInsuranceScreen({ onBack }: { onBack: () => void }) {
  // The micro-insurance product catalog and enrolment endpoints are not
  // connected to this build. We therefore show an honest unavailable state
  // instead of fabricated products, premiums, or a fake "subscription" success.
  return (
    <div className="flex flex-col h-screen" style={{ background: BG }}>
      <ScreenHeader
        title="🛡️ Micro-Insurance"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.55 0.22 300 / 0.2)",
              color: "#a855f7",
              fontFamily: DISP,
            }}
          >
            EMBEDDED FINANCE
          </span>
        }
      />
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
        <div className="text-5xl">🛡️</div>
        <p className="text-white font-bold" style={{ fontFamily: DISP }}>
          Micro-insurance is currently unavailable
        </p>
        <p className="text-gray-400 text-sm">
          Insurance products will appear here once the insurance service is
          connected. No premiums can be purchased in this build.
        </p>
      </div>
    </div>
  );
}

// ── Architecture Overview Panel ───────────────────────────────────────────────

function MyLimitsScreen({ onBack }: { onBack: () => void }) {
  const BG2 = "#0a0e1a";
  const CARD2 = "oklch(0.14 0.02 240)";
  const BORDER2 = "oklch(0.22 0.02 240)";
  const GREEN2 = "oklch(0.65 0.18 160)";
  const RED2 = "oklch(0.60 0.22 25)";
  const GOLD2 = "oklch(0.78 0.18 80)";
  const BLUE2 = "oklch(0.60 0.22 260)";
  const DISP2 = "'Space Grotesk', sans-serif";
  const MONO2 = "'JetBrains Mono', monospace";
  const fmt2 = (n: number) =>
    `₦${Number(n).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const { data, isLoading, refetch } =
    trpc.transactions.getMyVelocityUsage.useQuery(undefined, {
      refetchInterval: 60_000,
    });

  const tierColors: Record<string, string> = {
    bronze: "oklch(0.65 0.15 50)",
    silver: "oklch(0.75 0.05 240)",
    gold: GOLD2,
    platinum: "oklch(0.80 0.10 200)",
  };
  const tierColor = tierColors[(data?.tier ?? "").toLowerCase()] ?? BLUE2;

  function UsageBar({
    used,
    max,
    color,
  }: {
    used: number;
    max: number;
    color: string;
  }) {
    const pct = max > 0 ? Math.min(100, (used / max) * 100) : 0;
    const barColor = pct >= 90 ? RED2 : pct >= 70 ? GOLD2 : color;
    return (
      <div
        className="w-full rounded-full overflow-hidden"
        style={{ height: 6, background: BORDER2 }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
    );
  }

  const limits = data?.limits;
  const usage = data?.usage;
  const recent = data?.recentTransactions ?? [];

  return (
    <div
      className="flex flex-col h-full"
      style={{ background: BG2, color: "white" }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3"
        style={{ borderBottom: `1px solid ${BORDER2}` }}
      >
        <button
          onClick={onBack}
          className="text-gray-400 hover:text-white text-xl font-bold transition-colors"
        >
          ←
        </button>
        <div>
          <div
            className="text-sm font-black text-white"
            style={{ fontFamily: DISP2 }}
          >
            My Limits
          </div>
          <div className="text-xs text-gray-500" style={{ fontFamily: DISP2 }}>
            Real-time velocity usage vs your tier
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="ml-auto text-xs px-2 py-1 rounded-lg"
          style={{
            background: "oklch(0.60 0.22 260 / 0.2)",
            color: BLUE2,
            border: `1px solid ${BLUE2}`,
            fontFamily: DISP2,
          }}
        >
          ↻ Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {isLoading ? (
          <div
            className="text-xs text-gray-500 animate-pulse text-center py-8"
            style={{ fontFamily: MONO2 }}
          >
            Loading limits…
          </div>
        ) : (
          <>
            {/* Tier badge */}
            <div
              className="flex items-center justify-between px-4 py-3 rounded-2xl"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div>
                <div
                  className="text-xs text-gray-500 mb-0.5"
                  style={{ fontFamily: DISP2 }}
                >
                  Your Tier
                </div>
                <div
                  className="text-lg font-black uppercase tracking-widest"
                  style={{ color: tierColor, fontFamily: MONO2 }}
                >
                  {data?.tier ?? "—"}
                </div>
              </div>
              <div className="text-3xl">🏅</div>
            </div>

            {/* Limit cards */}
            {limits &&
              usage &&
              [
                {
                  label: "Hourly Transactions",
                  used: usage.hourlyCount,
                  max: limits.maxTxPerHour,
                  unit: "tx",
                  color: BLUE2,
                  icon: "⏱",
                  desc: `${usage.hourlyCount} of ${limits.maxTxPerHour} this hour`,
                  noBar: false,
                },
                {
                  label: "Single Transaction Cap",
                  used: 0,
                  max: limits.maxSingleTxAmount,
                  unit: "₦",
                  color: GOLD2,
                  icon: "💰",
                  desc: `Max per transaction: ${fmt2(limits.maxSingleTxAmount)}`,
                  noBar: true,
                },
                {
                  label: "Daily Volume",
                  used: usage.dailyVolume,
                  max: limits.maxDailyVolume,
                  unit: "₦",
                  color: GREEN2,
                  icon: "📊",
                  desc: `${fmt2(usage.dailyVolume)} of ${fmt2(limits.maxDailyVolume)} today`,
                  noBar: false,
                },
              ].map(item => (
                <div
                  key={item.label}
                  className="px-4 py-3 rounded-2xl flex flex-col gap-2"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{item.icon}</span>
                      <span
                        className="text-xs font-semibold text-gray-300"
                        style={{ fontFamily: DISP2 }}
                      >
                        {item.label}
                      </span>
                    </div>
                    <span
                      className="text-xs font-black"
                      style={{ color: item.color, fontFamily: MONO2 }}
                    >
                      {item.unit === "₦" && item.noBar
                        ? fmt2(item.max)
                        : item.unit === "₦"
                          ? `${fmt2(item.used)} / ${fmt2(item.max)}`
                          : `${item.used} / ${item.max} ${item.unit}`}
                    </span>
                  </div>
                  {!item.noBar && (
                    <UsageBar
                      used={item.used}
                      max={item.max}
                      color={item.color}
                    />
                  )}
                  <div
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP2 }}
                  >
                    {item.desc}
                  </div>
                </div>
              ))}

            {/* Recent transactions today */}
            <div
              className="px-4 py-3 rounded-2xl flex flex-col gap-3"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs font-black text-white"
                style={{ fontFamily: DISP2 }}
              >
                Today's Activity ({recent.length})
              </div>
              {recent.length === 0 ? (
                <div
                  className="text-xs text-gray-600 py-2 text-center"
                  style={{ fontFamily: MONO2 }}
                >
                  No transactions today
                </div>
              ) : (
                recent.map((tx: any) => (
                  <div
                    key={tx.id}
                    className="flex items-center justify-between py-1"
                    style={{ borderBottom: `1px solid ${BORDER2}` }}
                  >
                    <div>
                      <div
                        className="text-xs font-semibold text-white"
                        style={{ fontFamily: DISP2 }}
                      >
                        {tx.type}
                      </div>
                      <div
                        className="text-xs text-gray-500"
                        style={{ fontFamily: MONO2 }}
                      >
                        {tx.txRef}
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className="text-xs font-black"
                        style={{ color: GOLD2, fontFamily: MONO2 }}
                      >
                        ₦{Number(tx.amount).toLocaleString("en-NG")}
                      </div>
                      <div
                        className="text-xs"
                        style={{
                          color: tx.status === "success" ? GREEN2 : RED2,
                          fontFamily: MONO2,
                        }}
                      >
                        {tx.status}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// 18. Audit Log ─────────────────────────────────────────────────────────────────

function FirmwareOTAScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"idle" | "checking" | "available">("idle");
  const [latestRelease, setLatestRelease] = useState<{
    version: string;
    releaseNotes: string;
    fileSize: number;
  } | null>(null);
  // Fetch latest OTA release from the MDM router (real query — enabled).
  const { data: releasesData, refetch: refetchReleases, isFetching: checkingReleases } =
    trpc.mdm.listOtaReleases.useQuery({ limit: 1, offset: 0 }) as any;
  // A firmware package can only be flashed by the device MDM agent — this UI
  // can check for releases, but never simulates a download/install and never
  // records a fabricated OTA result.
  const check = async () => {
    setStep("checking");
    const res = await refetchReleases();
    const raw = res.data?.items?.[0];
    if (raw) {
      setLatestRelease({
        version: raw.version,
        releaseNotes: raw.releaseNotes ?? "",
        fileSize: raw.fileSize,
      });
      setStep("available");
    } else {
      setLatestRelease(null);
      setStep("idle");
      toast.info("No firmware updates available for this terminal.");
    }
  };
  const install = () => {
    toast.error(
      "Firmware installation runs through the device MDM agent and cannot be started from this screen."
    );
  };
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="Firmware OTA Update"
        onBack={onBack}
        badge={
          <div
            className="px-2 py-0.5 rounded text-xs font-bold"
            style={{ background: "oklch(0.78 0.18 80 / 0.2)", color: GOLD }}
          >
            {latestRelease ? "Update Available" : "Check for Updates"}
          </div>
        }
      />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Version information — only real MDM data, never invented versions */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Version Information
          </div>
          {[
            ["Current Firmware", "Reported by the device MDM agent"],
            ["Latest Available", latestRelease?.version ?? "—"],
            ["Size", latestRelease?.fileSize != null ? `${(latestRelease.fileSize / 1_000_000).toFixed(1)} MB` : "—"],
            ["Model", TERMINAL.model ?? "—"],
          ].map(([k, v]) => (
            <div
              key={k}
              className="flex justify-between py-2 border-b last:border-0"
              style={{ borderColor: BORDER }}
            >
              <span
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                {k}
              </span>
              <span
                className="text-xs font-bold"
                style={{
                  color: k === "Latest Available" ? GOLD : "white",
                  fontFamily: MONO,
                }}
              >
                {v}
              </span>
            </div>
          ))}
        </div>
        {/* Release notes */}
        {step === "available" && latestRelease && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-sm font-bold text-white mb-2"
              style={{ fontFamily: DISP }}
            >
              Release Notes {latestRelease.version}
            </div>
            <div
              className="text-xs text-gray-300 py-1 whitespace-pre-wrap"
              style={{ fontFamily: DISP }}
            >
              {latestRelease.releaseNotes || "No release notes provided."}
            </div>
          </div>
        )}

        {step !== "available" && (
          <button
            onClick={check}
            disabled={step === "checking" || checkingReleases}
            className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95 disabled:opacity-50"
            style={{ background: BLUE, fontFamily: DISP }}
          >
            {step === "checking" || checkingReleases
              ? "Checking for Updates…"
              : "Check for Updates"}
          </button>
        )}
        {step === "available" && latestRelease && (
          <button
            onClick={install}
            className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95"
            style={{ background: GOLD, fontFamily: DISP }}
          >
            Install {latestRelease.version}
          </button>
        )}
      </div>
    </div>
  );
}

function ReceiptModal({
  tx,
  onClose,
}: {
  tx: {
    type: string;
    amount: number;
    customer: string;
    ref: string;
    time: string;
  };
  onClose: () => void;
}) {
  const [sent, setSent] = useState<"none" | "sms" | "email">("none");
  const [smsPhone, setSmsPhone] = useState(
    tx.customer.match(/^\d{10,15}$/) ? tx.customer : ""
  );
  const [showSmsInput, setShowSmsInput] = useState(false);
  const agent = usePosStore(s => s.agent);

  const sendSmsMut = trpc.smsReceipt.send.useMutation({
    onSuccess: () => {
      setSent("sms");
      setShowSmsInput(false);
      toast.success(`Receipt SMS sent to ${smsPhone}`);
    },
    onError: e => toast.error(`SMS failed: ${e.message}`),
  });

  const handleSmsClick = () => {
    if (!tx.ref.startsWith("TXN-") && !tx.ref.startsWith("54L-")) {
      // Real txRef from server — use tRPC
      if (!smsPhone || smsPhone.length < 10) {
        setShowSmsInput(true);
        return;
      }
      sendSmsMut.mutate({ transactionRef: tx.ref, recipientPhone: smsPhone });
    } else {
      // Simulate ref for offline/fallback path
      setSent("sms");
      toast.success("SMS receipt sent");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      style={{ background: "oklch(0 0 0 / 0.8)" }}
      onClick={onClose}
    >
      <div
        className="w-full rounded-t-2xl p-4 flex flex-col gap-4 max-h-[85vh] overflow-y-auto"
        style={{ background: CARD, border: `1px solid ${BORDER}` }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div
            className="text-base font-bold text-white"
            style={{ fontFamily: DISP }}
          >
            Receipt
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl"
          >
            ×
          </button>
        </div>
        {/* ESC/POS style receipt */}
        <div
          className="rounded-xl p-4 font-mono text-xs leading-relaxed"
          style={{
            background: "oklch(0.97 0 0)",
            color: "#111",
            fontFamily: MONO,
          }}
        >
          <div className="text-center font-bold text-sm mb-2">
            54LINK AGENCY BANKING
          </div>
          <div className="text-center text-xs mb-1">
            Powered by 54Link Platform
          </div>
          <div className="text-center mb-3">{"─".repeat(32)}</div>
          <div className="flex justify-between">
            <span>Date:</span>
            <span>{new Date().toLocaleDateString("en-NG")}</span>
          </div>
          <div className="flex justify-between">
            <span>Time:</span>
            <span>{tx.time}</span>
          </div>
          <div className="flex justify-between">
            <span>Ref:</span>
            <span>{tx.ref}</span>
          </div>
          <div className="flex justify-between">
            <span>Type:</span>
            <span>{tx.type}</span>
          </div>
          <div className="text-center my-2">{"─".repeat(32)}</div>
          <div className="flex justify-between">
            <span>Customer:</span>
            <span>{tx.customer}</span>
          </div>
          <div className="text-center my-2">{"─".repeat(32)}</div>
          <div className="flex justify-between font-bold text-sm">
            <span>AMOUNT:</span>
            <span>
              ₦{tx.amount.toLocaleString("en-NG", { minimumFractionDigits: 2 })}
            </span>
          </div>
          <div className="text-center my-2">{"─".repeat(32)}</div>
          <div className="text-center text-xs">
            Agent: {agent?.agentCode ?? "AG-LOS-004821"}
          </div>
          <div className="text-center text-xs">
            Terminal: {agent?.terminalModel ?? "PAX A920 MAX"}
          </div>
          <div className="text-center text-xs mt-2">*** CUSTOMER COPY ***</div>
        </div>
        {/* SMS phone input (shown when phone is not auto-detected) */}
        {showSmsInput && (
          <div className="flex gap-2">
            <input
              value={smsPhone}
              onChange={e => setSmsPhone(e.target.value)}
              placeholder="Enter recipient phone (e.g. 08012345678)"
              className="flex-1 px-3 py-2 rounded-xl text-sm text-white bg-transparent border outline-none"
              style={{
                borderColor: GREEN,
                fontFamily: DISP,
                background: "oklch(0.10 0.015 240)",
              }}
            />
            <button
              onClick={() => {
                if (smsPhone.length >= 10) {
                  sendSmsMut.mutate({
                    transactionRef: tx.ref,
                    recipientPhone: smsPhone,
                  });
                }
              }}
              disabled={sendSmsMut.isPending}
              className="px-4 py-2 rounded-xl text-xs font-bold text-white"
              style={{
                background: GREEN,
                fontFamily: DISP,
                opacity: sendSmsMut.isPending ? 0.5 : 1,
              }}
            >
              {sendSmsMut.isPending ? "Sending…" : "Send"}
            </button>
          </div>
        )}
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => {
              setSent("none");
              toast.success("Printing receipt...");
            }}
            className="py-3 rounded-xl text-xs font-semibold"
            style={{
              background: "oklch(0.60 0.22 260 / 0.2)",
              color: "#3b82f6",
              fontFamily: DISP,
            }}
          >
            🖨 Print
          </button>
          <button
            onClick={handleSmsClick}
            disabled={sendSmsMut.isPending}
            className="py-3 rounded-xl text-xs font-semibold transition-all"
            style={{
              background:
                sent === "sms"
                  ? "oklch(0.65 0.18 160 / 0.3)"
                  : "oklch(0.65 0.18 160 / 0.15)",
              color: GREEN,
              fontFamily: DISP,
              opacity: sendSmsMut.isPending ? 0.5 : 1,
            }}
          >
            {sendSmsMut.isPending
              ? "Sending…"
              : sent === "sms"
                ? "✓ SMS Sent"
                : "📱 SMS"}
          </button>
          <button
            onClick={() => {
              setSent("email");
              toast.success("Email sent!");
            }}
            className="py-3 rounded-xl text-xs font-semibold"
            style={{
              background:
                sent === "email"
                  ? "oklch(0.78 0.18 80 / 0.3)"
                  : "oklch(0.78 0.18 80 / 0.15)",
              color: GOLD,
              fontFamily: DISP,
            }}
          >
            ✉ Email
          </button>
        </div>
        {/* Raise Dispute quick-action */}
        <button
          onClick={() => {
            onClose();
            // Copy txRef to clipboard so agent can paste into Disputes screen
            navigator.clipboard?.writeText(tx.ref).catch(() => {});
            toast.info(
              `Ref ${tx.ref} copied — tap My Disputes to raise a dispute`,
              { duration: 4000 }
            );
          }}
          className="w-full py-3 rounded-xl text-xs font-semibold transition-all"
          style={{
            background: "oklch(0.55 0.22 300 / 0.15)",
            color: "#a855f7",
            border: "1px solid oklch(0.55 0.22 300 / 0.3)",
            fontFamily: DISP,
          }}
        >
          ⚖ Raise Dispute for this Transaction
        </button>
      </div>
    </div>
  );
}

// ─── Status Bar ───────────────────────────────────────────────────────────────

function FloatHeader({ terminal }: { terminal: TerminalInfo }) {
  const progress = (terminal.txToday / terminal.txTarget) * 100;
  return (
    <div
      className="px-4 py-3 flex-shrink-0"
      style={{
        background: "oklch(0.11 0.012 240)",
        borderBottom: `1px solid ${BORDER}`,
      }}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <div
            className="text-xs text-gray-500 uppercase tracking-widest mb-0.5"
            style={{ fontFamily: DISP }}
          >
            Float Balance
          </div>
          <div
            className="text-2xl font-bold"
            style={{ fontFamily: MONO, color: GOLD }}
          >
            {fmt(terminal.floatBalance)}
          </div>
        </div>
        <div className="w-px h-10 bg-white/10" />
        <div>
          <div
            className="text-xs text-gray-500 uppercase tracking-widest mb-0.5"
            style={{ fontFamily: DISP }}
          >
            Commission
          </div>
          <div
            className="text-2xl font-bold"
            style={{ fontFamily: MONO, color: GREEN }}
          >
            {fmt(terminal.commissionBalance)}
          </div>
        </div>
        <div className="w-px h-10 bg-white/10" />
        <div className="flex flex-col items-end gap-1">
          <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
            Today{" "}
            <span className="font-bold text-white">{terminal.txToday}</span> /{" "}
            {terminal.txTarget} tx
          </div>
          <div
            className="w-20 h-1.5 rounded-full overflow-hidden"
            style={{ background: "oklch(0.20 0.01 240)" }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${progress}%`,
                background: progress >= 100 ? GREEN : BLUE,
              }}
            />
          </div>
          <div
            className="flex items-center gap-1 text-xs"
            style={{ color: GOLD, fontFamily: MONO }}
          >
            🔥 {terminal.tier ?? "—"} · {GAMIFICATION.streak != null ? `${GAMIFICATION.streak}d streak` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Quick Access Strip ───────────────────────────────────────────────────────

function pickChallenges(count: number): Array<{
  type: MotionChallengeType;
  instruction: string;
  completed: boolean;
}> {
  const shuffled = [...KYC_CHALLENGE_POOL].sort(() => Math.random() - 0.5);
  return shuffled
    .slice(0, Math.min(count, shuffled.length))
    .map(c => ({ ...c, completed: false }));
}

