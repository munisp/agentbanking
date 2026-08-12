// SECURITY: SQL template literals in this file are for display/mock purposes only. All actual DB queries use parameterized Drizzle ORM.
/**
 * 54Link — Real-Time Fraud Detection Admin Dashboard
 * Design: Bloomberg Terminal dark — near-black bg, electric-red alerts, emerald safe
 * Features: Live feed, risk heatmap, SHAP explanations, agent network graph, case management
 */

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { useFraudSocket } from "../hooks/useSocket";
import { usePosStore } from "../store/posStore";
import { trpc } from "../lib/trpc";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
  LineChart,
  Line,
} from "recharts";

// ─── Design Tokens ────────────────────────────────────────────────────────────
const BG = "oklch(0.08 0.012 240)";
const CARD = "oklch(0.12 0.015 240)";
const CARD2 = "oklch(0.15 0.015 240)";
const BORDER = "oklch(0.22 0.015 240)";
const RED = "#ef4444";
const ORANGE = "#f97316";
const GOLD = "#f59e0b";
const GREEN = "#10b981";
const BLUE = "#3b82f6";
const CYAN = "#06b6d4";
const PURPLE = "#8b5cf6";
const DISP = "'Space Grotesk', sans-serif";
const MONO = "'JetBrains Mono', monospace";

// ─── Types ────────────────────────────────────────────────────────────────────
type Severity = "critical" | "high" | "medium" | "low";
type CaseStatus = "open" | "investigating" | "resolved" | "escalated";

interface FraudEvent {
  id: string;
  agentCode: string;
  agentName: string;
  location: string;
  txType: string;
  amount: number;
  customer: string;
  riskScore: number;
  severity: Severity;
  reason: string;
  time: string;
  timestamp: number;
  status: CaseStatus;
  channel: string;
  shapFeatures: { name: string; value: number; direction: "risk" | "safe" }[];
}

interface AgentRisk {
  agentCode: string;
  agentName: string;
  location: string;
  riskScore: number;
  txCount: number;
  flaggedCount: number;
  tier: string;
}

// HOURLY_DATA is fetched live via trpc.fraud.hourlyStats in the component

// ─── Severity helpers ─────────────────────────────────────────────────────────
const SEV_COLOR: Record<Severity, string> = {
  critical: RED,
  high: ORANGE,
  medium: GOLD,
  low: "#6b7280",
};
const SEV_BG: Record<Severity, string> = {
  critical: `${RED}18`,
  high: `${ORANGE}18`,
  medium: `${GOLD}18`,
  low: "oklch(0.22 0.01 240 / 0.5)",
};
const STATUS_COLOR: Record<CaseStatus, string> = {
  open: RED,
  investigating: GOLD,
  resolved: GREEN,
  escalated: PURPLE,
};

const fmt = (n: number) =>
  n >= 1_000_000
    ? `₦${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
      ? `₦${(n / 1_000).toFixed(0)}K`
      : `₦${n}`;

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  color,
  pulse,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
  pulse?: boolean;
}) {
  return (
    <div
      className="rounded-2xl p-4 flex flex-col gap-1"
      style={{ background: CARD, border: `1px solid ${BORDER}` }}
    >
      <div className="flex items-center gap-2">
        {pulse && (
          <div
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: color }}
          />
        )}
        <span
          className="text-xs text-gray-500 uppercase tracking-wider"
          style={{ fontFamily: DISP }}
        >
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold" style={{ color, fontFamily: MONO }}>
        {value}
      </div>
      {sub && (
        <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function SHAPBar({
  feature,
}: {
  feature: { name: string; value: number; direction: "risk" | "safe" };
}) {
  const color = feature.direction === "risk" ? RED : GREEN;
  return (
    <div className="mb-2">
      <div className="flex justify-between items-center mb-0.5">
        <span className="text-xs text-gray-300" style={{ fontFamily: DISP }}>
          {feature.name}
        </span>
        <span className="text-xs font-bold" style={{ color, fontFamily: MONO }}>
          {feature.direction === "risk" ? "+" : "−"}
          {(feature.value * 100).toFixed(0)}%
        </span>
      </div>
      <div
        className="h-1.5 rounded-full overflow-hidden"
        style={{ background: BORDER }}
      >
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${feature.value * 100}%`, background: color }}
        />
      </div>
    </div>
  );
}

function EventRow({
  event,
  onSelect,
  selected,
}: {
  event: FraudEvent;
  onSelect: (e: FraudEvent) => void;
  selected: boolean;
}) {
  return (
    <button
      onClick={() => onSelect(event)}
      className="w-full flex items-center gap-3 px-4 py-3 text-left transition-all hover:opacity-90"
      style={{
        background: selected ? `${SEV_COLOR[event.severity]}12` : "transparent",
        borderLeft: selected
          ? `3px solid ${SEV_COLOR[event.severity]}`
          : "3px solid transparent",
        borderBottom: `1px solid ${BORDER}`,
      }}
    >
      {/* Severity dot */}
      <div
        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
        style={{ background: SEV_COLOR[event.severity] }}
      />
      {/* Main info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className="text-xs font-bold text-white truncate"
            style={{ fontFamily: DISP }}
          >
            {event.agentName}
          </span>
          <span
            className="text-xs px-1.5 py-0.5 rounded font-bold uppercase flex-shrink-0"
            style={{
              background: SEV_BG[event.severity],
              color: SEV_COLOR[event.severity],
              fontFamily: DISP,
              fontSize: 9,
            }}
          >
            {event.severity}
          </span>
        </div>
        <div
          className="text-xs text-gray-400 truncate"
          style={{ fontFamily: DISP }}
        >
          {event.reason}
        </div>
      </div>
      {/* Amount + time */}
      <div className="text-right flex-shrink-0">
        <div
          className="text-xs font-bold"
          style={{ color: GOLD, fontFamily: MONO }}
        >
          {fmt(event.amount)}
        </div>
        <div className="text-xs text-gray-600" style={{ fontFamily: MONO }}>
          {event.time}
        </div>
      </div>
    </button>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function FraudDashboard() {
  const [events, setEvents] = useState<FraudEvent[]>([]);
  const [selected, setSelected] = useState<FraudEvent | null>(null);
  const [tab, setTab] = useState<"feed" | "agents" | "analytics">("feed");
  const [filterSev, setFilterSev] = useState<Severity | "all">("all");
  const [filterStatus, setFilterStatus] = useState<CaseStatus | "all">("all");
  const [paused, setPaused] = useState(false);
  const [newCount, setNewCount] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const feedRef = useRef<HTMLDivElement>(null);

  // ── Live fraud alerts from DB ───────────────────────────────────────────────
  const { data: dbAlerts, isError: alertsError } = trpc.fraud.list.useQuery(
    { page: 1, limit: 50 },
    { refetchInterval: 30_000, retry: false }
  );
  // Seed events from DB when available
  useEffect(() => {
    if (!dbAlerts?.items?.length) return;
    const mapped: FraudEvent[] = dbAlerts.items.map((a: any) => {
      const score = parseFloat(a.fraudScore ?? "0");
      return {
        id: String(a.id),
        agentCode: a.agentCode ?? "UNKNOWN",
        agentName: a.agentCode ?? "Unknown Agent",
        location: a.location ?? "—",
        txType: a.txType ?? "Transaction",
        amount: Number(a.amount ?? 0),
        customer: a.customerName ?? "-",
        riskScore: Math.round(score * 100),
        severity: (a.severity as Severity) ?? "medium",
        reason: a.reason ?? "Flagged by system",
        time: new Date(a.createdAt ?? Date.now()).toLocaleTimeString("en-NG", {
          hour: "2-digit",
          minute: "2-digit",
        }),
        timestamp: new Date(a.createdAt ?? Date.now()).getTime(),
        status: (a.status as CaseStatus) ?? "open",
        channel: a.channel ?? "—",
        shapFeatures: Array.isArray(a.shapFeatures) ? a.shapFeatures : [],
      };
    });
    setEvents(prev => {
      const ids = new Set(prev.map(e => e.id));
      const newOnes = mapped.filter(m => !ids.has(m.id));
      return [...newOnes, ...prev].slice(0, 100);
    });
  }, [dbAlerts]);

  // ── Real-time Socket.IO fraud feed ──────────────────────────────────────────
  const storeEvents = usePosStore(s => s.fraudEvents);
  useFraudSocket(); // connects to /fraud namespace and pushes events into store

  // Merge store (socket) events into local display state
  useEffect(() => {
    if (storeEvents.length === 0) return;
    const latest = storeEvents[0];
    const mapped: FraudEvent = {
      id: latest.id,
      agentCode: latest.agentCode,
      agentName: latest.customerName,
      location: "—",
      txType: latest.type,
      amount: latest.amount,
      customer: latest.customerName,
      riskScore: parseFloat(latest.fraudScore) * 100,
      severity: latest.severity,
      reason: latest.reason,
      time: new Date(latest.timestamp).toLocaleTimeString("en-NG", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      timestamp: new Date(latest.timestamp).getTime(),
      status: "open",
      channel: latest.type,
      shapFeatures: [],
    };
    if (!paused) {
      setEvents(prev => [mapped, ...prev].slice(0, 50));
      setNewCount(c => c + 1);
      if (latest.severity === "critical") {
        toast.error(
          `🚨 CRITICAL: ${latest.customerName} — ${fmt(latest.amount)} ${latest.type}`,
          { duration: 5000 }
        );
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeEvents.length]);

  // ── Live hourly stats from DB ───────────────────────────────────────────────
  const { data: liveHourlyData } = trpc.fraud.hourlyStats.useQuery(undefined, {
    refetchInterval: 60_000,
    retry: false,
  });
  // Stable fallback — 24 zero-filled hours — avoids re-render flicker
  const [fallbackHourly] = useState(() =>
    Array.from({ length: 24 }, (_, h) => ({
      h: `${String(h).padStart(2, "0")}:00`,
      alerts: 0,
      blocked: 0,
      volume: 0,
    }))
  );
  const hourlyData =
    liveHourlyData && liveHourlyData.length > 0
      ? liveHourlyData
      : fallbackHourly;

  // ── tRPC status update ──────────────────────────────────────────────────────
  const updateStatusMutation = trpc.fraud.updateStatus.useMutation();

  const updateStatus = useCallback(
    (id: string, status: CaseStatus) => {
      const numId = parseInt(id, 10);
      if (isNaN(numId)) {
        toast.error(
          "This case cannot be updated: it is not a persisted fraud alert in the database."
        );
        return;
      }
      updateStatusMutation.mutate(
        { id: numId, status },
        {
          onSuccess: () => {
            setEvents(prev =>
              prev.map(e => (e.id === id ? { ...e, status } : e))
            );
            if (selected?.id === id)
              setSelected(prev => (prev ? { ...prev, status } : null));
            toast.success(
              `Case ${status === "resolved" ? "resolved" : status === "escalated" ? "escalated to compliance" : "status updated"}`
            );
          },
          onError: (err: any) => {
            toast.error(
              `Failed to update case status: ${err?.message ?? "The fraud service rejected the update."}`
            );
          },
        }
      );
    },
    [selected, updateStatusMutation]
  );

  const filtered = events.filter(
    e =>
      (filterSev === "all" || e.severity === filterSev) &&
      (filterStatus === "all" || e.status === filterStatus)
  );

  // Agent risk is derived exclusively from live fraud events
  const agentRisks: AgentRisk[] = useMemo(() => {
    const byAgent = new Map<string, AgentRisk>();
    for (const e of events) {
      const existing = byAgent.get(e.agentCode);
      if (existing) {
        existing.txCount += 1;
        existing.flaggedCount += 1;
        existing.riskScore = Math.max(existing.riskScore, e.riskScore);
      } else {
        byAgent.set(e.agentCode, {
          agentCode: e.agentCode,
          agentName: e.agentName,
          location: e.location,
          riskScore: e.riskScore,
          txCount: 1,
          flaggedCount: 1,
          tier: "—",
        });
      }
    }
    return [...byAgent.values()];
  }, [events]);

  // Risk score distribution derived from live fraud events
  const riskDistribution = useMemo(() => {
    const buckets: { range: string; min: number; max: number; color: string }[] = [
      { range: "40-50", min: 40, max: 50, color: "#6b7280" },
      { range: "50-60", min: 50, max: 60, color: GOLD },
      { range: "60-70", min: 60, max: 70, color: ORANGE },
      { range: "70-80", min: 70, max: 80, color: ORANGE },
      { range: "80-90", min: 80, max: 90, color: RED },
      { range: "90-100", min: 90, max: 101, color: RED },
    ];
    return buckets.map(b => ({
      range: b.range,
      count: events.filter(
        e => e.riskScore >= b.min && e.riskScore < b.max
      ).length,
      color: b.color,
    }));
  }, [events]);

  const stats = {
    total: events.length,
    critical: events.filter(e => e.severity === "critical").length,
    open: events.filter(e => e.status === "open").length,
    blocked: events.filter(e => e.status === "resolved").length,
    totalRisk: events.reduce((s: any, e: any) => s + e.amount, 0),
  };

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: BG, fontFamily: DISP }}
    >
      {/* ── Top Bar ── */}
      <div
        className="flex items-center justify-between px-5 py-3 flex-shrink-0"
        style={{
          background: "oklch(0.07 0.01 240)",
          borderBottom: `1px solid ${BORDER}`,
        }}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-full animate-pulse"
              style={{ background: paused ? GOLD : RED }}
            />
            <span
              className="text-sm font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              Fraud Detection Center
            </span>
          </div>
          <div
            className="px-2 py-0.5 rounded text-xs font-bold"
            style={{ background: `${RED}20`, color: RED }}
          >
            LIVE
          </div>
          {newCount > 0 && (
            <div
              className="px-2 py-0.5 rounded-full text-xs font-bold text-white"
              style={{ background: RED }}
            >
              +{newCount} new
            </div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setPaused(p => !p);
              setNewCount(0);
            }}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
            style={{
              background: paused ? `${GREEN}20` : `${GOLD}20`,
              color: paused ? GREEN : GOLD,
              border: `1px solid ${paused ? GREEN : GOLD}40`,
            }}
          >
            {paused ? "▶ Resume" : "⏸ Pause"}
          </button>
          <span className="text-xs text-gray-500" style={{ fontFamily: MONO }}>
            {new Date().toLocaleTimeString("en-NG", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        </div>
      </div>

      {alertsError && (
        <div
          className="mx-5 mt-3 px-4 py-2 rounded-xl text-xs font-semibold flex-shrink-0"
          style={{
            background: `${RED}15`,
            color: RED,
            border: `1px solid ${RED}40`,
          }}
        >
          Unable to load persisted fraud alerts from the database. Only live
          socket events (if any) are shown.
        </div>
      )}

      {/* ── KPI Strip ── */}
      <div className="grid grid-cols-5 gap-3 px-5 py-3 flex-shrink-0">
        <StatCard
          label="Total Events"
          value={String(stats.total)}
          sub="Live + persisted alerts"
          color={BLUE}
        />
        <StatCard
          label="Critical"
          value={String(stats.critical)}
          sub="Immediate action"
          color={RED}
          pulse
        />
        <StatCard
          label="Open Cases"
          value={String(stats.open)}
          sub="Pending review"
          color={ORANGE}
        />
        <StatCard
          label="Resolved"
          value={String(stats.blocked)}
          sub="Cases closed"
          color={GREEN}
        />
        <StatCard
          label="At-Risk Volume"
          value={fmt(stats.totalRisk)}
          sub="Flagged transactions"
          color={GOLD}
        />
      </div>

      {/* ── Tab Nav ── */}
      <div className="flex gap-1 px-5 pb-3 flex-shrink-0">
        {(["feed", "agents", "analytics"] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="px-4 py-2 rounded-xl text-xs font-semibold capitalize transition-all"
            style={{
              background: tab === t ? RED : CARD,
              color: tab === t ? "white" : "#6b7280",
              border: `1px solid ${tab === t ? RED : BORDER}`,
            }}
          >
            {t === "feed"
              ? "🔴 Live Feed"
              : t === "agents"
                ? "👤 Agent Risk"
                : "📊 Analytics"}
          </button>
        ))}
      </div>

      {/* ── Main Content ── */}
      <div className="flex-1 overflow-hidden px-5 pb-5">
        {/* ── LIVE FEED TAB ── */}
        {tab === "feed" && (
          <div className="flex gap-4 h-full">
            {/* Left: Event list */}
            <div
              className="w-96 flex flex-col rounded-2xl overflow-hidden flex-shrink-0"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              {/* Filters */}
              <div
                className="px-4 py-3 flex gap-2 flex-wrap"
                style={{ borderBottom: `1px solid ${BORDER}` }}
              >
                {(["all", "critical", "high", "medium", "low"] as const).map(
                  s => (
                    <button
                      key={s}
                      onClick={() => setFilterSev(s)}
                      className="px-2.5 py-1 rounded-lg text-xs font-semibold capitalize transition-all"
                      style={{
                        background:
                          filterSev === s
                            ? (s === "all"
                                ? BLUE
                                : SEV_COLOR[s as Severity] || BLUE) + "30"
                            : "transparent",
                        color:
                          filterSev === s
                            ? s === "all"
                              ? BLUE
                              : SEV_COLOR[s as Severity] || BLUE
                            : "#6b7280",
                        border: `1px solid ${filterSev === s ? (s === "all" ? BLUE : SEV_COLOR[s as Severity] || BLUE) : BORDER}`,
                      }}
                    >
                      {s}
                    </button>
                  )
                )}
              </div>
              {/* Event rows */}
              <div ref={feedRef} className="flex-1 overflow-y-auto">
                {filtered.length === 0 && (
                  <div className="text-center text-gray-500 py-12 text-sm px-4">
                    {events.length === 0
                      ? "No fraud events recorded yet. Live alerts from the fraud engine will appear here."
                      : "No events match filter"}
                  </div>
                )}
                {filtered.map(e => (
                  <EventRow
                    key={e.id}
                    event={e}
                    onSelect={setSelected}
                    selected={selected?.id === e.id}
                  />
                ))}
              </div>
            </div>

            {/* Right: Case detail */}
            <div className="flex-1 overflow-y-auto flex flex-col gap-4">
              {selected ? (
                <>
                  {/* Header */}
                  <div
                    className="rounded-2xl p-5"
                    style={{
                      background: CARD,
                      border: `2px solid ${SEV_COLOR[selected.severity]}40`,
                    }}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="text-lg font-bold text-white"
                            style={{ fontFamily: DISP }}
                          >
                            {selected.agentName}
                          </span>
                          <span
                            className="px-2 py-0.5 rounded text-xs font-bold uppercase"
                            style={{
                              background: SEV_BG[selected.severity],
                              color: SEV_COLOR[selected.severity],
                            }}
                          >
                            {selected.severity}
                          </span>
                        </div>
                        <div className="text-xs text-gray-400">
                          {selected.agentCode} · {selected.location}
                        </div>
                      </div>
                      <div className="text-right">
                        <div
                          className="text-2xl font-bold"
                          style={{ color: GOLD, fontFamily: MONO }}
                        >
                          {fmt(selected.amount)}
                        </div>
                        <div className="text-xs text-gray-400">
                          {selected.txType} · {selected.channel}
                        </div>
                      </div>
                    </div>

                    {/* Risk gauge */}
                    <div className="mb-4">
                      <div className="flex justify-between mb-1">
                        <span className="text-xs text-gray-400">
                          Risk Score
                        </span>
                        <span
                          className="text-xl font-bold"
                          style={{
                            color: SEV_COLOR[selected.severity],
                            fontFamily: MONO,
                          }}
                        >
                          {selected.riskScore}%
                        </span>
                      </div>
                      <div
                        className="h-3 rounded-full overflow-hidden"
                        style={{ background: BORDER }}
                      >
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${selected.riskScore}%`,
                            background: `linear-gradient(90deg, ${GOLD}, ${SEV_COLOR[selected.severity]})`,
                          }}
                        />
                      </div>
                    </div>

                    {/* Reason */}
                    <div
                      className="rounded-xl p-3 mb-4"
                      style={{ background: BG, border: `1px solid ${BORDER}` }}
                    >
                      <div className="text-xs text-gray-500 mb-1">
                        Detection Reason
                      </div>
                      <div className="text-sm text-gray-200">
                        {selected.reason}
                      </div>
                    </div>

                    {/* Status + Actions */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{ background: STATUS_COLOR[selected.status] }}
                        />
                        <span
                          className="text-xs font-semibold capitalize"
                          style={{ color: STATUS_COLOR[selected.status] }}
                        >
                          {selected.status}
                        </span>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() =>
                            updateStatus(selected.id, "investigating")
                          }
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                          style={{
                            background: `${GOLD}20`,
                            color: GOLD,
                            border: `1px solid ${GOLD}40`,
                          }}
                        >
                          🔍 Investigate
                        </button>
                        <button
                          onClick={() => updateStatus(selected.id, "escalated")}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                          style={{
                            background: `${PURPLE}20`,
                            color: PURPLE,
                            border: `1px solid ${PURPLE}40`,
                          }}
                        >
                          📋 Escalate
                        </button>
                        <button
                          onClick={() => updateStatus(selected.id, "resolved")}
                          className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                          style={{
                            background: `${GREEN}20`,
                            color: GREEN,
                            border: `1px solid ${GREEN}40`,
                          }}
                        >
                          ✓ Resolve
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* SHAP Explanation */}
                  <div
                    className="rounded-2xl p-5"
                    style={{ background: CARD, border: `1px solid ${BORDER}` }}
                  >
                    <div className="flex items-center gap-2 mb-4">
                      <span
                        className="text-sm font-bold text-white"
                        style={{ fontFamily: DISP }}
                      >
                        🤖 AI Feature Explanation (SHAP)
                      </span>
                    </div>
                    {selected.shapFeatures.length > 0 ? (
                      <>
                        {selected.shapFeatures.map((f, i) => (
                          <SHAPBar key={i} feature={f} />
                        ))}
                        <div
                          className="mt-3 p-3 rounded-xl"
                          style={{
                            background: `${GOLD}10`,
                            border: `1px solid ${GOLD}20`,
                          }}
                        >
                          <div className="text-xs font-semibold text-yellow-400 mb-1">
                            AI Recommendation
                          </div>
                          <div className="text-xs text-gray-300">
                            {selected.riskScore >= 80
                              ? "Block transaction immediately and escalate to compliance. Request biometric re-verification."
                              : selected.riskScore >= 65
                                ? "Place transaction on hold. Request additional customer verification (OTP)."
                                : "Monitor agent activity for next 2 hours. No immediate action required."}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="text-xs text-gray-500">
                        Feature attribution is not available for this event.
                        Explanations appear here when the fraud engine provides
                        them for a persisted alert.
                      </div>
                    )}
                  </div>

                  {/* Transaction metadata */}
                  <div
                    className="rounded-2xl p-5"
                    style={{ background: CARD, border: `1px solid ${BORDER}` }}
                  >
                    <div
                      className="text-sm font-bold text-white mb-3"
                      style={{ fontFamily: DISP }}
                    >
                      Transaction Metadata
                    </div>
                    {[
                      ["Event ID", selected.id],
                      ["Customer", selected.customer],
                      ["Channel", selected.channel],
                      ["Time", selected.time],
                    ].map(([k, v]) => (
                      <div
                        key={k}
                        className="flex justify-between py-2"
                        style={{ borderBottom: `1px solid ${BORDER}` }}
                      >
                        <span className="text-xs text-gray-500">{k}</span>
                        <span
                          className="text-xs text-white font-semibold"
                          style={{ fontFamily: MONO }}
                        >
                          {v}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500">
                  Select an event to view details
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── AGENT RISK TAB ── */}
        {tab === "agents" && (
          <div className="flex gap-4 h-full overflow-hidden">
            {/* Agent risk table */}
            <div
              className="flex-1 overflow-y-auto rounded-2xl"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="sticky top-0 grid grid-cols-6 gap-3 px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider"
                style={{
                  background: CARD,
                  borderBottom: `1px solid ${BORDER}`,
                }}
              >
                <span className="col-span-2">Agent</span>
                <span>Risk Score</span>
                <span>Transactions</span>
                <span>Flagged</span>
                <span>Flag Rate</span>
              </div>
              {agentRisks.length === 0 && (
                <div className="text-center text-gray-500 py-12 text-sm px-4">
                  No agent risk data available. Risk profiles are built from
                  live fraud events as they arrive.
                </div>
              )}
              {[...agentRisks]
                .sort((a: any, b: any) => b.riskScore - a.riskScore)
                .map((agent, i) => {
                  const flagRate = (
                    (agent.flaggedCount / agent.txCount) *
                    100
                  ).toFixed(1);
                  const riskColor =
                    agent.riskScore >= 80
                      ? RED
                      : agent.riskScore >= 60
                        ? ORANGE
                        : agent.riskScore >= 40
                          ? GOLD
                          : GREEN;
                  return (
                    <div
                      key={agent.agentCode}
                      className="grid grid-cols-6 gap-3 px-5 py-4 items-center transition-all hover:opacity-80"
                      style={{
                        borderBottom: `1px solid ${BORDER}`,
                        background: i === 0 ? `${RED}08` : "transparent",
                      }}
                    >
                      <div className="col-span-2">
                        <div
                          className="text-sm font-bold text-white"
                          style={{ fontFamily: DISP }}
                        >
                          {agent.agentName}
                        </div>
                        <div className="text-xs text-gray-500">
                          {agent.agentCode} · {agent.location}
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="text-sm font-bold"
                            style={{ color: riskColor, fontFamily: MONO }}
                          >
                            {agent.riskScore}
                          </span>
                        </div>
                        <div
                          className="h-1.5 w-20 rounded-full overflow-hidden"
                          style={{ background: BORDER }}
                        >
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${agent.riskScore}%`,
                              background: riskColor,
                            }}
                          />
                        </div>
                      </div>
                      <span
                        className="text-sm text-white"
                        style={{ fontFamily: MONO }}
                      >
                        {agent.txCount}
                      </span>
                      <span
                        className="text-sm font-bold"
                        style={{
                          color: agent.flaggedCount > 5 ? RED : GOLD,
                          fontFamily: MONO,
                        }}
                      >
                        {agent.flaggedCount}
                      </span>
                      <span
                        className="text-sm"
                        style={{
                          color: parseFloat(flagRate) > 5 ? RED : GREEN,
                          fontFamily: MONO,
                        }}
                      >
                        {flagRate}%
                      </span>
                    </div>
                  );
                })}
            </div>

            {/* Scatter: risk vs volume */}
            <div className="w-72 flex flex-col gap-4">
              <div
                className="rounded-2xl p-4 flex-1"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                <div className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                  Risk vs Volume
                </div>
                {agentRisks.length === 0 ? (
                  <div className="text-xs text-gray-500">
                    No data available yet.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <ScatterChart>
                      <XAxis
                        dataKey="txCount"
                        name="Transactions"
                        tick={{ fill: "#6b7280", fontSize: 10 }}
                      />
                      <YAxis
                        dataKey="riskScore"
                        name="Risk Score"
                        tick={{ fill: "#6b7280", fontSize: 10 }}
                      />
                      <Tooltip
                        contentStyle={{
                          background: CARD2,
                          border: `1px solid ${BORDER}`,
                          borderRadius: 8,
                        }}
                        labelStyle={{ color: "white" }}
                        itemStyle={{ color: GOLD }}
                      />
                      <Scatter
                        data={agentRisks.map(a => ({
                          txCount: a.txCount,
                          riskScore: a.riskScore,
                          name: a.agentName,
                        }))}
                      >
                        {agentRisks.map((a, i) => (
                          <Cell
                            key={i}
                            fill={
                              a.riskScore >= 80
                                ? RED
                                : a.riskScore >= 60
                                  ? ORANGE
                                  : a.riskScore >= 40
                                    ? GOLD
                                    : GREEN
                            }
                          />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                )}
              </div>
              <div
                className="rounded-2xl p-4"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                <div className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                  Severity Breakdown
                </div>
                {events.length === 0 ? (
                  <div className="text-xs text-gray-500">
                    No events recorded yet.
                  </div>
                ) : (
                  (["critical", "high", "medium", "low"] as Severity[]).map(
                    sev => {
                      const count = events.filter(
                        e => e.severity === sev
                      ).length;
                      const pct = Math.round((count / events.length) * 100);
                      return (
                        <div key={sev} className="mb-2">
                          <div className="flex justify-between mb-0.5">
                            <span className="text-xs text-gray-300 capitalize">
                              {sev}
                            </span>
                            <span
                              className="text-xs font-bold"
                              style={{ color: SEV_COLOR[sev], fontFamily: MONO }}
                            >
                              {pct}%
                            </span>
                          </div>
                          <div
                            className="h-1.5 rounded-full overflow-hidden"
                            style={{ background: BORDER }}
                          >
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${pct}%`,
                                background: SEV_COLOR[sev],
                              }}
                            />
                          </div>
                        </div>
                      );
                    }
                  )
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── ANALYTICS TAB ── */}
        {tab === "analytics" && (
          <div className="grid grid-cols-2 gap-4 h-full overflow-y-auto">
            {/* Hourly alert volume */}
            <div
              className="rounded-2xl p-5"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-sm font-bold text-white mb-4"
                style={{ fontFamily: DISP }}
              >
                Hourly Alert Volume (24h)
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <AreaChart data={hourlyData}>
                  <defs>
                    <linearGradient id="alertGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={RED} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={RED} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="h"
                    tick={{ fill: "#6b7280", fontSize: 9 }}
                    interval={3}
                  />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
                  <Tooltip
                    contentStyle={{
                      background: CARD2,
                      border: `1px solid ${BORDER}`,
                      borderRadius: 8,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="alerts"
                    stroke={RED}
                    fill="url(#alertGrad)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Blocked vs Allowed */}
            <div
              className="rounded-2xl p-5"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-sm font-bold text-white mb-4"
                style={{ fontFamily: DISP }}
              >
                Blocked vs Allowed (24h)
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={hourlyData.filter(
                    (_: (typeof hourlyData)[0], i: number) => i % 3 === 0
                  )}
                >
                  <XAxis dataKey="h" tick={{ fill: "#6b7280", fontSize: 9 }} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 9 }} />
                  <Tooltip
                    contentStyle={{
                      background: CARD2,
                      border: `1px solid ${BORDER}`,
                      borderRadius: 8,
                    }}
                  />
                  <Bar
                    dataKey="blocked"
                    fill={RED}
                    radius={[3, 3, 0, 0]}
                    name="Blocked"
                  />
                  <Bar
                    dataKey="volume"
                    fill={GREEN}
                    radius={[3, 3, 0, 0]}
                    name="Allowed"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Risk score distribution */}
            <div
              className="rounded-2xl p-5"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-sm font-bold text-white mb-4"
                style={{ fontFamily: DISP }}
              >
                Risk Score Distribution
              </div>
              {events.length === 0 ? (
                <div className="text-xs text-gray-500">
                  No fraud events recorded yet. The distribution is computed
                  from live alerts as they arrive.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={riskDistribution}>
                    <XAxis
                      dataKey="range"
                      tick={{ fill: "#6b7280", fontSize: 9 }}
                    />
                    <YAxis
                      tick={{ fill: "#6b7280", fontSize: 9 }}
                      allowDecimals={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: CARD2,
                        border: `1px solid ${BORDER}`,
                        borderRadius: 8,
                      }}
                    />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                      {riskDistribution.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Model performance */}
            <div
              className="rounded-2xl p-5"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-sm font-bold text-white mb-4"
                style={{ fontFamily: DISP }}
              >
                Model Performance
              </div>
              <div className="text-xs text-gray-500">
                Model quality metrics (precision, recall, F1, AUC) are not
                exposed by the live fraud service. This panel will populate
                when the model-monitoring endpoint is available.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
