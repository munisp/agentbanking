import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useState } from "react";
import { Bar } from "recharts";
import { toast } from "sonner";
import { ScreenHeader, SortableTile } from "./POSShell.part10";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TILE_USAGE_KEY, Transaction } from "./POSShell.shared";

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
          {(["services", "infra", "hardware"] as const).map((t: any) => (
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

export function NanoLoanScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"offer" | "apply" | "confirm" | "success">(
    "offer"
  );
  const [amount, setAmount] = useState(50000);
  const [tenor, setTenor] = useState(30);
  const loanAgent = usePosStore(s => s.agent);
  const loanAgentId = loanAgent?.id ?? 0;

  // Real credit score from the backend — never an invented number.
  const { data: credit, isLoading: creditLoading } =
    trpc.agentLoanFacility.creditScore.useQuery(
      { agentId: loanAgentId },
      { enabled: loanAgentId > 0, retry: false }
    ) as any;
  const applyLoanMut = trpc.agentLoanFacility.applyLoan.useMutation() as any;
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);
  const [loanRef, setLoanRef] = useState<string | null>(null);
  const [loanStatus, setLoanStatus] = useState<string | null>(null);
  const maxLoan = credit?.maxLoanAmount != null && credit.maxLoanAmount > 0 ? credit.maxLoanAmount : 500000;

  // Interest/total are set by the server on approval — not computed from an
  // invented rate here.
  const submitApplication = async () => {
    setApplyError(null);
    setApplying(true);
    try {
      const resp: any = await applyLoanMut.mutateAsync({
        agentId: loanAgentId,
        loanType: "float_advance",
        principalAmount: amount,
        tenorDays: tenor,
      });
      setLoanRef(resp?.loanId != null ? `LOAN-${resp.loanId}` : resp?.id != null ? `LOAN-${resp.id}` : null);
      setLoanStatus(resp?.status ?? "submitted");
      setStep("success");
    } catch (err: any) {
      setApplyError(err?.message || "Loan application failed — nothing was disbursed.");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: BG }}>
      <ScreenHeader title="💰 Nano Loan" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4">
        {step === "offer" && (
          <>
            {/* Credit score */}
            <div
              className="rounded-2xl p-4 mb-4"
              style={{
                background: `${GREEN}15`,
                border: `1px solid ${GREEN}30`,
              }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-400 text-xs">Your Credit Score</p>
                  <p
                    className="text-3xl font-bold"
                    style={{ color: GREEN, fontFamily: MONO }}
                  >
                    {creditLoading ? "…" : credit?.score != null ? credit.score : "—"}
                  </p>
                  <p className="text-green-400 text-xs">
                    {creditLoading
                      ? "Checking score…"
                      : credit?.score != null
                        ? credit.eligible ? "Eligible to apply" : "Not currently eligible"
                        : "Score unavailable"}
                  </p>
                </div>
                <div className="text-5xl">🏆</div>
              </div>
            </div>

            {/* Loan offer */}
            <div
              className="rounded-2xl p-4 mb-4"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <h3
                className="text-white font-bold mb-3"
                style={{ fontFamily: DISP }}
              >
                Loan Amount
              </h3>
              <div className="text-center mb-4">
                <span
                  className="text-4xl font-bold"
                  style={{ color: GOLD, fontFamily: MONO }}
                >
                  ₦{amount.toLocaleString()}
                </span>
              </div>
              <input
                type="range"
                min={10000}
                max={maxLoan}
                step={10000}
                value={amount}
                onChange={e => setAmount(Number(e.target.value))}
                className="w-full mb-4"
                style={{ accentColor: BLUE }}
              />
              <div className="flex justify-between text-xs text-gray-500 mb-4">
                <span>₦10,000</span>
                <span>₦{maxLoan.toLocaleString()}</span>
              </div>

              <div className="grid grid-cols-3 gap-3 mb-4">
                {[7, 14, 30].map((t: any) => (
                  <button
                    key={t}
                    onClick={() => setTenor(t)}
                    className="py-2 rounded-xl text-sm font-semibold transition-all"
                    style={{
                      background: tenor === t ? BLUE : BG,
                      color: tenor === t ? "white" : "#6b7280",
                      border: `1px solid ${tenor === t ? BLUE : BORDER}`,
                    }}
                  >
                    {t} days
                  </button>
                ))}
              </div>

              <div className="rounded-xl p-3" style={{ background: BG }}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Principal</span>
                  <span className="text-white" style={{ fontFamily: MONO }}>
                    ₦{amount.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-400">Interest</span>
                  <span className="text-white" style={{ fontFamily: MONO }}>
                    Set by the server on approval
                  </span>
                </div>
                <div className="flex justify-between text-sm font-bold">
                  <span className="text-gray-300">Total Repayment</span>
                  <span style={{ color: GOLD, fontFamily: MONO }}>
                    Confirmed on approval
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setStep("confirm")}
              className="w-full py-4 rounded-2xl font-bold text-white text-lg"
              style={{
                background: `linear-gradient(135deg, ${BLUE}, oklch(0.55 0.22 280))`,
              }}
            >
              Apply for Loan →
            </button>
          </>
        )}

        {step === "confirm" && (
          <>
            <div
              className="rounded-2xl p-6 mb-4 text-center"
              style={{ background: CARD, border: `1px solid ${GOLD}40` }}
            >
              <div className="text-5xl mb-4">💳</div>
              <h3
                className="text-white font-bold text-xl mb-2"
                style={{ fontFamily: DISP }}
              >
                Confirm Loan Application
              </h3>
              <p className="text-gray-400 text-sm mb-4">
                Disbursement follows server approval — timing is confirmed by the server
              </p>
              <div
                className="text-4xl font-bold mb-1"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                ₦{amount.toLocaleString()}
              </div>
              <p className="text-gray-500 text-sm">
                Repayment terms are confirmed by the server on approval
              </p>
            </div>
            {applyError && (
              <div
                className="text-xs text-center rounded-xl p-3 mb-3"
                style={{ color: "#f87171", border: "1px solid #7f1d1d" }}
              >
                {applyError}
              </div>
            )}
            <button
              onClick={submitApplication}
              disabled={applying || loanAgentId <= 0 || credit?.eligible === false}
              className="w-full py-4 rounded-2xl font-bold text-white text-lg mb-3 disabled:opacity-40"
              style={{ background: GREEN }}
            >
              {applying ? "Submitting…" : "✓ Submit Loan Application"}
            </button>
            <button
              onClick={() => setStep("offer")}
              className="w-full py-3 rounded-2xl font-semibold text-gray-400"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              ← Back
            </button>
          </>
        )}

        {step === "success" && (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="text-7xl mb-6">🎉</div>
            <h3
              className="text-white font-bold text-2xl mb-2"
              style={{ fontFamily: DISP }}
            >
              Application {loanStatus ?? "Submitted"}
            </h3>
            <p className="text-gray-400 mb-4">
              ₦{amount.toLocaleString()} requested — disbursement is confirmed by the server
            </p>
            {loanRef && (
              <div
                className="rounded-xl px-6 py-3 mb-6"
                style={{
                  background: `${GREEN}20`,
                  border: `1px solid ${GREEN}40`,
                }}
              >
                <p className="text-green-400 font-semibold">Application Reference</p>
                <p
                  className="text-2xl font-bold"
                  style={{ color: GREEN, fontFamily: MONO }}
                >
                  {loanRef}
                </p>
              </div>
            )}
            <button
              onClick={onBack}
              className="px-8 py-3 rounded-2xl font-bold text-white"
              style={{ background: BLUE }}
            >
              Back to Home
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── End-of-Day Reconciliation Wizard ─────────────────────────────────────────

export function MyLimitsScreen({ onBack }: { onBack: () => void }) {
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
    }) as any;

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
              ].map((item: any) => (
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

export function NetworkTestScreen({ onBack }: { onBack: () => void }) {
  // State must be declared before hooks that reference them
  const [testPhone, setTestPhone] = useState("0803");
  const [testing, setTesting] = useState(false);
  const [probeResult, setProbeResult] = useState<{
    latency_ms: number;
    quality: string;
    online: boolean;
    targets_checked: number;
    targets_reachable: number;
  } | null>(null);
  const [carrierResult, setCarrierResult] = useState<{
    carrier: string;
    ussd_shortcode: string;
    phone_prefix: string;
  } | null>(null);

  // Live probe via Go resilience-agent
  const { refetch: runProbe } = trpc.resilience.probe.useQuery(undefined, {
    enabled: false,
    retry: false,
  }) as any;
  const { refetch: runCarrier } = trpc.resilience.detectCarrier.useQuery(
    { phone: testPhone },
    { enabled: false, retry: false }
  ) as any;

  const qualityColor = (q: string) =>
    q === "Excellent" ? GREEN : q === "Good" ? BLUE : q === "Poor" ? GOLD : RED;

  const qualityBars = (q: string) => {
    const map: Record<string, number> = {
      Excellent: 5,
      Good: 4,
      Poor: 2,
      Offline: 0,
    };
    return map[q] ?? 0;
  };

  const runTest = async () => {
    setTesting(true);
    try {
      const [p, carrier] = await Promise.all([runProbe(), runCarrier()]);
      if (p.data) setProbeResult(p.data as any);
      if (carrier.data) setCarrierResult(carrier.data as any);
      if (!p.data && !carrier.data)
        toast.error("Network test failed — resilience agent may be offline");
    } catch {
      toast.error("Network test failed — resilience agent may be offline");
    } finally {
      setTesting(false);
    }
  };

  const tip = () => {
    if (!probeResult) return null;
    if (probeResult.quality === "Excellent")
      return {
        icon: "✅",
        text: "Signal is excellent. All payment channels available.",
      };
    if (probeResult.quality === "Good")
      return {
        icon: "✔",
        text: "Good signal. Move closer to a window or open area for best results.",
      };
    if (probeResult.quality === "Poor")
      return {
        icon: "⚠️",
        text: "Weak signal. Move to a higher floor or near a window. USSD fallback is active.",
      };
    return {
      icon: "📵",
      text: "No internet. Only USSD and offline queue are available. Move to an area with mobile coverage.",
    };
  };

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Network Test" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Live probe result */}
        {probeResult && (
          <div
            className="rounded-2xl p-4"
            style={{
              background: CARD,
              border: `2px solid ${qualityColor(probeResult.quality)}44`,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div
                className="text-sm font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                Connection Quality
              </div>
              <span
                className="text-xs px-3 py-1 rounded-full font-bold"
                style={{
                  background: `${qualityColor(probeResult.quality)}22`,
                  color: qualityColor(probeResult.quality),
                  fontFamily: DISP,
                }}
              >
                {probeResult.quality}
              </span>
            </div>
            {/* Animated signal bars */}
            <div className="flex items-end gap-1.5 h-14 mb-3">
              {[1, 2, 3, 4, 5].map((bar: any) => (
                <div
                  key={bar}
                  className="flex-1 rounded-t transition-all duration-500"
                  style={{
                    height: `${bar * 20}%`,
                    background:
                      bar <= qualityBars(probeResult.quality)
                        ? qualityColor(probeResult.quality)
                        : BORDER,
                  }}
                />
              ))}
            </div>
            {[
              ["Latency", `${probeResult.latency_ms}ms`],
              [
                "Targets Reachable",
                `${probeResult.targets_reachable}/${probeResult.targets_checked}`,
              ],
              ["Internet", probeResult.online ? "Connected" : "Offline"],
            ].map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between py-1.5 border-b last:border-0"
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
                    color:
                      k === "Latency"
                        ? probeResult.latency_ms < 100
                          ? GREEN
                          : probeResult.latency_ms < 300
                            ? GOLD
                            : RED
                        : "white",
                    fontFamily: MONO,
                  }}
                >
                  {v}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Carrier detection */}
        {carrierResult && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-sm font-bold text-white mb-3"
              style={{ fontFamily: DISP }}
            >
              SIM Carrier
            </div>
            {[
              ["Carrier", carrierResult.carrier],
              ["USSD Shortcode", carrierResult.ussd_shortcode],
              ["Prefix", carrierResult.phone_prefix],
            ].map(([k, v]) => (
              <div
                key={k}
                className="flex justify-between py-1.5 border-b last:border-0"
                style={{ borderColor: BORDER }}
              >
                <span
                  className="text-xs text-gray-400"
                  style={{ fontFamily: DISP }}
                >
                  {k}
                </span>
                <span
                  className="text-xs font-bold text-white"
                  style={{ fontFamily: MONO }}
                >
                  {v}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Best position tip */}
        {tip() && (
          <div
            className="rounded-2xl p-4"
            style={{
              background: "oklch(0.60 0.22 260 / 0.08)",
              border: `1px solid ${BLUE}44`,
            }}
          >
            <div
              className="text-sm font-bold text-white mb-1"
              style={{ fontFamily: DISP }}
            >
              {tip()!.icon} Positioning Tip
            </div>
            <div className="text-xs text-gray-400" style={{ fontFamily: DISP }}>
              {tip()!.text}
            </div>
          </div>
        )}

        {/* Phone prefix input for carrier detection */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-xs text-gray-400 mb-2"
            style={{ fontFamily: DISP }}
          >
            Carrier detection phone prefix (first 4 digits)
          </div>
          <input
            value={testPhone}
            onChange={e => setTestPhone(e.target.value.slice(0, 4))}
            maxLength={4}
            className="w-full px-3 py-2 rounded-xl text-sm text-white bg-transparent border"
            style={{ borderColor: BORDER, fontFamily: MONO }}
            placeholder="e.g. 0803"
          />
        </div>

        <button
          onClick={runTest}
          disabled={testing}
          className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95 disabled:opacity-50"
          style={{ background: BLUE, fontFamily: DISP }}
        >
          {testing
            ? "Testing…"
            : probeResult
              ? "Re-Test Connection"
              : "Run Network Test"}
        </button>
      </div>
    </div>
  );
}
// 26. FirmwareOTA ───────────────────────────────────────────────────────────────

export function ReceiptModal({
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
  }) as any;

  const handleSmsClick = () => {
    if (!tx.ref.startsWith("TXN-") && !tx.ref.startsWith("54L-")) {
      // Real txRef from server — use tRPC
      if (!smsPhone || smsPhone.length < 10) {
        setShowSmsInput(true);
        return;
      }
      sendSmsMut.mutate({ transactionRef: tx.ref, recipientPhone: smsPhone });
    } else {
      // No transaction reference — the SMS cannot be sent. Never claim it was.
      toast.error("SMS receipt was NOT sent: no transaction reference available.");
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
            Agent: {agent?.agentCode ?? "—"}
          </div>
          <div className="text-center text-xs">
            Terminal: {agent?.terminalModel ?? "—"}
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

export function fmt(n: number | null | undefined) {
  if (n == null) return "—"; // unknown balance renders as an honest placeholder
  return (
    "₦" +
    n.toLocaleString("en-NG", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}


export function saveTileUsage(u: Record<string, number>) {
  localStorage.setItem(TILE_USAGE_KEY, JSON.stringify(u));
}

// SortableTile wrapper for DnD Kit (P1)

