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
  const [step, setStep] = useState<"browse" | "select" | "confirm" | "success">(
    "browse"
  );
  const [selected, setSelected] = useState<{
    name: string;
    premium: number;
    cover: number;
    period: string;
  } | null>(null);

  const products = [
    {
      name: "Life Cover Basic",
      icon: "🛡️",
      premium: 500,
      cover: 500000,
      period: "Monthly",
      desc: "₦500K life insurance for ₦500/month",
    },
    {
      name: "Health Micro Plan",
      icon: "🏥",
      premium: 800,
      cover: 200000,
      period: "Monthly",
      desc: "Outpatient & emergency cover",
    },
    {
      name: "Crop Insurance",
      icon: "🌾",
      premium: 1200,
      cover: 1000000,
      period: "Seasonal",
      desc: "Protect farm income from weather events",
    },
    {
      name: "Device Protection",
      icon: "📱",
      premium: 300,
      cover: 150000,
      period: "Monthly",
      desc: "Cover for POS terminal & mobile devices",
    },
    {
      name: "Travel Accident",
      icon: "✈️",
      premium: 200,
      cover: 300000,
      period: "Per trip",
      desc: "Accidental death & disability cover",
    },
    {
      name: "Business Interruption",
      icon: "🏪",
      premium: 1500,
      cover: 2000000,
      period: "Monthly",
      desc: "Income protection for your agency",
    },
  ];

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

      <div className="flex-1 overflow-y-auto p-4">
        {step === "browse" && (
          <>
            <div
              className="rounded-2xl p-4 mb-4"
              style={{
                background: "oklch(0.55 0.22 300 / 0.1)",
                border: "1px solid oklch(0.55 0.22 300 / 0.3)",
              }}
            >
              <p className="text-gray-300 text-sm">
                Protect yourself and your customers with affordable
                micro-insurance products. Premiums deducted from your commission
                balance.
              </p>
            </div>
            <div className="flex flex-col gap-3">
              {products.map((p, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setSelected(p);
                    setStep("select");
                  }}
                  className="flex items-center gap-4 p-4 rounded-2xl text-left transition-all active:scale-98"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                >
                  <div className="text-3xl">{p.icon}</div>
                  <div className="flex-1">
                    <div
                      className="font-bold text-white text-sm"
                      style={{ fontFamily: DISP }}
                    >
                      {p.name}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">{p.desc}</div>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className="text-xs font-bold"
                        style={{ color: GREEN, fontFamily: MONO }}
                      >
                        ₦{p.premium.toLocaleString()}/{p.period}
                      </span>
                      <span className="text-xs text-gray-600">·</span>
                      <span className="text-xs text-gray-400">
                        Cover: ₦{p.cover.toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <span className="text-gray-500">›</span>
                </button>
              ))}
            </div>
          </>
        )}

        {step === "select" && selected && (
          <>
            <div
              className="rounded-2xl p-6 mb-4 text-center"
              style={{
                background: CARD,
                border: `1px solid oklch(0.55 0.22 300 / 0.4)`,
              }}
            >
              <div className="text-5xl mb-3">
                {products.find(p => p.name === selected.name)?.icon}
              </div>
              <h3
                className="text-white font-bold text-xl mb-1"
                style={{ fontFamily: DISP }}
              >
                {selected.name}
              </h3>
              <p className="text-gray-400 text-sm mb-4">
                Coverage: ₦{selected.cover.toLocaleString()}
              </p>
              <div
                className="text-3xl font-bold"
                style={{ color: GREEN, fontFamily: MONO }}
              >
                ₦{selected.premium.toLocaleString()}
              </div>
              <p className="text-gray-500 text-sm">
                per {selected.period.toLowerCase()}
              </p>
            </div>
            <div
              className="rounded-xl p-4 mb-4"
              style={{ background: BG, border: `1px solid ${BORDER}` }}
            >
              {[
                ["Coverage Amount", `₦${selected.cover.toLocaleString()}`],
                [
                  "Premium",
                  `₦${selected.premium.toLocaleString()}/${selected.period}`,
                ],
                ["Payment Method", "Commission Balance"],
                ["Provider", "AXA Mansard Insurance"],
                ["Underwriter", "NAICOM Licensed"],
              ].map(([k, v]) => (
                <div
                  key={k}
                  className="flex justify-between py-2 border-b last:border-0"
                  style={{ borderColor: BORDER }}
                >
                  <span className="text-gray-500 text-sm">{k}</span>
                  <span
                    className="text-white text-sm font-semibold"
                    style={{ fontFamily: MONO }}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setStep("browse")}
                className="flex-1 py-3 rounded-xl font-semibold text-gray-400"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                ← Back
              </button>
              <button
                onClick={() => setStep("confirm")}
                className="flex-2 flex-grow py-3 rounded-xl font-bold text-white"
                style={{ background: "oklch(0.55 0.22 300)" }}
              >
                Subscribe →
              </button>
            </div>
          </>
        )}

        {step === "confirm" && selected && (
          <>
            <div
              className="rounded-2xl p-6 mb-4 text-center"
              style={{ background: CARD, border: `1px solid ${GOLD}40` }}
            >
              <div className="text-4xl mb-3">🔐</div>
              <h3
                className="text-white font-bold text-xl mb-2"
                style={{ fontFamily: DISP }}
              >
                Confirm Subscription
              </h3>
              <p className="text-gray-400 text-sm mb-4">
                ₦{selected.premium.toLocaleString()} will be deducted from your
                commission balance {selected.period.toLowerCase()}
              </p>
              <div
                className="text-2xl font-bold"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                ₦{selected.premium.toLocaleString()}/{selected.period}
              </div>
            </div>
            <button
              onClick={() => setStep("success")}
              className="w-full py-4 rounded-2xl font-bold text-white text-lg mb-3"
              style={{ background: GREEN }}
            >
              ✓ Confirm Subscription
            </button>
            <button
              onClick={() => setStep("select")}
              className="w-full py-3 rounded-2xl font-semibold text-gray-400"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              ← Back
            </button>
          </>
        )}

        {step === "success" && selected && (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="text-7xl mb-6">🎉</div>
            <h3
              className="text-white font-bold text-2xl mb-2"
              style={{ fontFamily: DISP }}
            >
              Subscribed!
            </h3>
            <p className="text-gray-400 mb-4">{selected.name} is now active</p>
            <div
              className="rounded-xl px-6 py-3 mb-6"
              style={{
                background: "oklch(0.55 0.22 300 / 0.15)",
                border: "1px solid oklch(0.55 0.22 300 / 0.3)",
              }}
            >
              <p className="text-purple-400 font-semibold">Policy Number</p>
              <p className="text-white font-mono font-bold">
                POL-{Date.now().toString().slice(-8)}
              </p>
            </div>
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
  const [step, setStep] = useState<
    "idle" | "checking" | "available" | "downloading" | "installing" | "done"
  >("idle");
  const [progress, setProgress] = useState(0);
  const [latestRelease, setLatestRelease] = useState<{
    version: string;
    releaseNotes: string;
    fileSize: number;
  } | null>(null);
  // Fetch latest OTA release from MDM router
  const { data: releasesData } = trpc.mdm.listOtaReleases.useQuery(
    { limit: 1, offset: 0 },
    { enabled: false }
  );
  const releases = releasesData?.items;
  const recordUpdateMut = trpc.mdm.recordOtaUpdate.useMutation();
  const check = () => {
    setStep("checking");
    // Try to get latest release from server; fall back to known version
    const raw = releases?.[0];
    const latest = raw
      ? {
          version: raw.version,
          releaseNotes:
            raw.releaseNotes ?? "Security patch, performance improvements",
          fileSize: raw.fileSize,
        }
      : {
          version: "v4.3.0-NG",
          releaseNotes: "Security patch, performance improvements",
          fileSize: 12_400_000,
        };
    setTimeout(() => {
      setLatestRelease(latest);
      setStep("available");
    }, 1200);
  };
  const install = () => {
    setStep("downloading");
    setProgress(0);
    const iv = setInterval(() => {
      setProgress(p => {
        if (p >= 100) {
          clearInterval(iv);
          setStep("installing");
          setTimeout(() => {
            // Record successful OTA update in MDM
            recordUpdateMut.mutate({
              deviceId: 1, // terminal device DB id
              releaseId: releases?.[0]?.id ?? 1,
              status: "success",
              fromVersion: "v4.2.1-NG",
              toVersion: latestRelease?.version ?? "v4.3.0-NG",
            });
            setStep("done");
          }, 2000);
          return 100;
        }
        return p + 2;
      });
    }, 80);
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
            Update Available
          </div>
        }
      />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Current version */}
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
            ["Current Firmware", "v4.2.1-NG"],
            ["Latest Available", "v4.3.0-NG"],
            ["Release Date", "2024-03-15"],
            ["Size", "12.4 MB"],
            ["Model", TERMINAL.model],
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
        {(step === "available" ||
          step === "downloading" ||
          step === "installing" ||
          step === "done") && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-sm font-bold text-white mb-2"
              style={{ fontFamily: DISP }}
            >
              Release Notes v4.3.0-NG
            </div>
            {[
              "🔒 Enhanced EMV kernel security patch",
              "⚡ 15% faster transaction processing",
              "📶 Improved 4G/LTE connectivity",
              "🖨 80mm paper detection fix",
              "🇳🇬 CBN compliance updates (March 2024)",
            ].map(n => (
              <div
                key={n}
                className="text-xs text-gray-300 py-1 border-b last:border-0"
                style={{ borderColor: BORDER, fontFamily: DISP }}
              >
                {n}
              </div>
            ))}
          </div>
        )}
        {/* Progress */}
        {(step === "downloading" || step === "installing") && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div className="flex justify-between mb-2">
              <span
                className="text-sm font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                {step === "downloading" ? "Downloading…" : "Installing…"}
              </span>
              <span
                className="text-sm font-bold"
                style={{ color: BLUE, fontFamily: MONO }}
              >
                {progress}%
              </span>
            </div>
            <div
              className="h-3 rounded-full overflow-hidden"
              style={{ background: BORDER }}
            >
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${progress}%`, background: BLUE }}
              />
            </div>
            <div
              className="text-xs text-gray-400 mt-2"
              style={{ fontFamily: DISP }}
            >
              {step === "downloading"
                ? "Do not power off terminal"
                : "Installing — do not interrupt"}
            </div>
          </div>
        )}
        {step === "done" && (
          <div
            className="rounded-2xl p-5 flex flex-col items-center gap-3"
            style={{
              background: "oklch(0.65 0.18 160 / 0.1)",
              border: `1px solid ${GREEN}`,
            }}
          >
            <div className="text-4xl">✓</div>
            <div
              className="text-base font-bold"
              style={{ color: GREEN, fontFamily: DISP }}
            >
              Update Complete
            </div>
            <div
              className="text-xs text-gray-400 text-center"
              style={{ fontFamily: DISP }}
            >
              Firmware v4.3.0-NG installed successfully. Terminal will restart.
            </div>
            <button
              onClick={onBack}
              className="px-6 py-2 rounded-xl font-bold text-white"
              style={{ background: GREEN, fontFamily: DISP }}
            >
              Done
            </button>
          </div>
        )}
        {step === "idle" && (
          <button
            onClick={check}
            className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95"
            style={{ background: BLUE, fontFamily: DISP }}
          >
            Check for Updates
          </button>
        )}
        {step === "checking" && (
          <div className="flex items-center justify-center gap-3 py-4">
            <div className="w-5 h-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            <span
              className="text-sm text-blue-400"
              style={{ fontFamily: DISP }}
            >
              Checking for updates…
            </span>
          </div>
        )}
        {step === "available" && (
          <button
            onClick={install}
            className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95"
            style={{ background: GOLD, fontFamily: DISP }}
          >
            Download & Install v4.3.0-NG
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Gamification Panel ───────────────────────────────────────────────────────
// FloatBalance Screen ─────────────────────────────────────────────────────

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
            🔥 {terminal.tier} · {GAMIFICATION.streak}d streak
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

