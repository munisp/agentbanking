/**
 * FluvioStreamTab — Live Fluvio Event Stream Dashboard
 *
 * Connects to the server-sent events (SSE) endpoint at /api/v1/fluvio/sse/:topic
 * and renders a real-time scrolling feed of events from:
 *   - pos.transactions.created
 *   - pos.fraud-alerts.created
 *   - pos.float-events.created
 *   - pos.kyc-events.created
 *
 * Also shows Fluvio connection status, stream stats, and a produce test panel.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import { MQTTBridgeTab } from "./MQTTBridgeTab";

// ── Design tokens (match AdminPanel) ─────────────────────────────────────────
const BG = "#0a0e1a";
const CARD = "oklch(0.14 0.02 240)";
const CARD2 = "oklch(0.17 0.02 240)";
const BORDER = "oklch(0.22 0.02 240)";
const GREEN = "oklch(0.65 0.18 160)";
const RED = "oklch(0.60 0.22 25)";
const GOLD = "oklch(0.78 0.18 80)";
const BLUE = "oklch(0.60 0.22 260)";
const PURPLE = "oklch(0.65 0.20 300)";
const DISP = "'Space Grotesk', sans-serif";
const MONO = "'JetBrains Mono', monospace";

// ── Topic config ──────────────────────────────────────────────────────────────
const TOPICS = [
  {
    id: "pos.transactions.created",
    label: "Transactions",
    color: GREEN,
    icon: "💳",
  },
  {
    id: "pos.fraud-alerts.created",
    label: "Fraud Alerts",
    color: RED,
    icon: "⚠️",
  },
  {
    id: "pos.float-events.created",
    label: "Float Events",
    color: GOLD,
    icon: "🏦",
  },
  {
    id: "pos.kyc-events.created",
    label: "KYC Events",
    color: PURPLE,
    icon: "🪪",
  },
] as const;

type TopicId = (typeof TOPICS)[number]["id"];

interface StreamEvent {
  id: string;
  topic: TopicId;
  timestamp: string;
  payload: Record<string, unknown>;
}

interface FluvioStats {
  messagesPerSecond: number;
  totalMessages: number;
  activeTopics: string[];
  bufferSize: number;
  connected: boolean;
  endpoint: string | null;
  mode: "live" | "buffer" | "offline";
}

// ── Status dot ────────────────────────────────────────────────────────────────
function StatusDot({ ok, pulse = false }: { ok: boolean; pulse?: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${pulse ? "animate-pulse" : ""}`}
      style={{ background: ok ? GREEN : RED }}
    />
  );
}

// ── Event row ─────────────────────────────────────────────────────────────────
function EventRow({
  event,
  topicColor,
}: {
  event: StreamEvent;
  topicColor: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const topic = TOPICS.find(t => t.id === event.topic);

  return (
    <div
      className="rounded-xl p-3 cursor-pointer transition-all"
      style={{ background: CARD2, border: `1px solid ${BORDER}` }}
      onClick={() => setExpanded(e => !e)}
    >
      <div className="flex items-center gap-3">
        <span className="text-base">{topic?.icon ?? "📨"}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="text-xs font-bold uppercase tracking-wider"
              style={{ color: topicColor, fontFamily: DISP }}
            >
              {topic?.label ?? event.topic}
            </span>
            <span
              className="text-xs text-gray-500"
              style={{ fontFamily: MONO }}
            >
              {new Date(event.timestamp).toLocaleTimeString("en-NG", {
                hour12: false,
              })}
            </span>
            {event.payload.ref != null && (
              <span
                className="text-xs text-gray-400"
                style={{ fontFamily: MONO }}
              >
                ref: {String(event.payload.ref)}
              </span>
            )}
            {event.payload.amount != null && (
              <span
                className="text-xs font-bold"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                ₦{Number(event.payload.amount).toLocaleString("en-NG")}
              </span>
            )}
            {event.payload.severity != null && (
              <span
                className="text-xs px-1.5 py-0.5 rounded-full font-bold uppercase"
                style={{
                  background:
                    String(event.payload.severity) === "critical"
                      ? `${RED}33`
                      : `${GOLD}33`,
                  color:
                    String(event.payload.severity) === "critical" ? RED : GOLD,
                  fontFamily: DISP,
                }}
              >
                {String(event.payload.severity)}
              </span>
            )}
          </div>
          {expanded && (
            <pre
              className="mt-2 text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap break-all"
              style={{ fontFamily: MONO, maxHeight: "200px" }}
            >
              {JSON.stringify(event.payload, null, 2)}
            </pre>
          )}
        </div>
        <span className="text-gray-600 text-xs" style={{ fontFamily: MONO }}>
          {expanded ? "▲" : "▼"}
        </span>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export function FluvioStreamTab() {
  const [activeTopic, setActiveTopic] = useState<TopicId | "all">("all");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [stats, setStats] = useState<FluvioStats | null>(null);
  const [sseStatus, setSseStatus] = useState<
    "connecting" | "connected" | "error" | "closed"
  >("connecting");
  const [paused, setPaused] = useState(false);
  const [maxEvents] = useState(200);
  const eventSourceRef = useRef<EventSource | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  // ── Fetch Fluvio stats ────────────────────────────────────────────────────
  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/fluvio/stats", {
        credentials: "include",
      });
      if (res.ok) setStats(await res.json());
    } catch {
      // stats fetch is non-critical
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10_000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  // ── SSE connection ────────────────────────────────────────────────────────
  useEffect(() => {
    const topic =
      activeTopic === "all" ? "all" : encodeURIComponent(activeTopic);
    const url = `/api/v1/fluvio/sse/${topic}`;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setSseStatus("connecting");
    setEvents([]);

    const es = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = es;

    es.onopen = () => setSseStatus("connected");

    es.onmessage = e => {
      if (pausedRef.current) return;
      try {
        const data = JSON.parse(e.data) as StreamEvent;
        setEvents(prev => {
          const next = [data, ...prev];
          return next.length > maxEvents ? next.slice(0, maxEvents) : next;
        });
      } catch {
        // ignore malformed events
      }
    };

    es.addEventListener("ping", () => {
      // keepalive — no action needed
    });

    es.onerror = () => {
      setSseStatus("error");
      // EventSource auto-reconnects; we just update the status indicator
    };

    return () => {
      es.close();
      setSseStatus("closed");
    };
  }, [activeTopic, maxEvents]);

  // ── Auto-scroll to top when new events arrive ─────────────────────────────
  useEffect(() => {
    if (!paused && feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [events, paused]);

  // ── Produce test event ────────────────────────────────────────────────────
  const produceTestEvent = async (topicId: string) => {
    try {
      const res = await fetch("/api/v1/fluvio/produce", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topicId,
          key: `test-${Date.now()}`,
          value: JSON.stringify({
            ref: `TEST-${Math.random().toString(36).slice(2, 8).toUpperCase()}`,
            amount: Math.floor(Math.random() * 50000) + 1000,
            type: "Test",
            timestamp: new Date().toISOString(),
            source: "admin-dashboard",
          }),
        }),
      });
      if (res.ok) {
        toast.success(`Test event produced to ${topicId}`);
      } else {
        const err = await res.json();
        toast.error(`Produce failed: ${err.error ?? "unknown error"}`);
      }
    } catch (e) {
      toast.error("Network error producing test event");
    }
  };

  const filteredEvents =
    activeTopic === "all"
      ? events
      : events.filter(e => e.topic === activeTopic);

  const modeColor =
    stats?.mode === "live" ? GREEN : stats?.mode === "buffer" ? GOLD : RED;
  const modeLabel =
    stats?.mode === "live"
      ? "Live (Fluvio)"
      : stats?.mode === "buffer"
        ? "Buffered (fallback)"
        : "Offline";

  return (
    <div className="flex flex-col gap-5">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div
            className="text-lg font-black text-white"
            style={{ fontFamily: DISP }}
          >
            Fluvio Stream Dashboard
          </div>
          <div
            className="text-xs text-gray-500 mt-0.5"
            style={{ fontFamily: MONO }}
          >
            Real-time event bus — InfinyOn Fluvio
          </div>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* SSE status */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
            style={{ background: CARD2, border: `1px solid ${BORDER}` }}
          >
            <StatusDot
              ok={sseStatus === "connected"}
              pulse={sseStatus === "connecting"}
            />
            <span
              className="text-xs font-semibold"
              style={{
                color:
                  sseStatus === "connected"
                    ? GREEN
                    : sseStatus === "connecting"
                      ? GOLD
                      : RED,
                fontFamily: DISP,
              }}
            >
              SSE {sseStatus}
            </span>
          </div>
          {/* Fluvio mode */}
          {stats && (
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
              style={{ background: CARD2, border: `1px solid ${BORDER}` }}
            >
              <StatusDot
                ok={stats.mode === "live"}
                pulse={stats.mode === "live"}
              />
              <span
                className="text-xs font-semibold"
                style={{ color: modeColor, fontFamily: DISP }}
              >
                {modeLabel}
              </span>
            </div>
          )}
          {/* Pause / resume */}
          <button
            onClick={() => setPaused(p => !p)}
            className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
            style={{
              background: paused ? `${GOLD}22` : `${BLUE}22`,
              color: paused ? GOLD : BLUE,
              border: `1px solid ${paused ? GOLD : BLUE}44`,
              fontFamily: DISP,
            }}
          >
            {paused ? "▶ Resume" : "⏸ Pause"}
          </button>
          {/* Clear */}
          <button
            onClick={() => setEvents([])}
            className="px-3 py-1.5 rounded-lg text-xs font-bold"
            style={{
              background: `${RED}22`,
              color: RED,
              border: `1px solid ${RED}44`,
              fontFamily: DISP,
            }}
          >
            🗑 Clear
          </button>
        </div>
      </div>

      {/* ── Stats cards ─────────────────────────────────────────────────────── */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            {
              label: "Msg/sec",
              value: stats.messagesPerSecond.toFixed(1),
              color: GREEN,
            },
            {
              label: "Total Messages",
              value: stats.totalMessages.toLocaleString(),
              color: BLUE,
            },
            {
              label: "Active Topics",
              value: String(stats.activeTopics.length),
              color: GOLD,
            },
            {
              label: "Buffer Size",
              value: String(stats.bufferSize),
              color: PURPLE,
            },
          ].map(s => (
            <div
              key={s.label}
              className="rounded-xl p-3 flex flex-col gap-1"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-xs text-gray-500 uppercase tracking-widest"
                style={{ fontFamily: DISP }}
              >
                {s.label}
              </div>
              <div
                className="text-xl font-black"
                style={{ color: s.color, fontFamily: MONO }}
              >
                {s.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Topic filter + produce ───────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setActiveTopic("all")}
          className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
          style={{
            background: activeTopic === "all" ? `${BLUE}33` : "transparent",
            color: activeTopic === "all" ? BLUE : "oklch(0.55 0.015 230)",
            border: `1px solid ${activeTopic === "all" ? BLUE : BORDER}`,
            fontFamily: DISP,
          }}
        >
          All Topics
        </button>
        {TOPICS.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTopic(t.id)}
            className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all"
            style={{
              background: activeTopic === t.id ? `${t.color}22` : "transparent",
              color: activeTopic === t.id ? t.color : "oklch(0.55 0.015 230)",
              border: `1px solid ${activeTopic === t.id ? t.color : BORDER}44`,
              fontFamily: DISP,
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
            Produce test:
          </span>
          {TOPICS.map(t => (
            <button
              key={t.id}
              onClick={() => produceTestEvent(t.id)}
              title={`Produce test event to ${t.id}`}
              className="px-2 py-1 rounded-lg text-xs font-bold transition-all"
              style={{
                background: `${t.color}15`,
                color: t.color,
                border: `1px solid ${t.color}33`,
                fontFamily: MONO,
              }}
            >
              {t.icon}
            </button>
          ))}
        </div>
      </div>

      {/* ── Event feed ──────────────────────────────────────────────────────── */}
      <div
        ref={feedRef}
        className="flex flex-col gap-2 overflow-y-auto"
        style={{ maxHeight: "500px" }}
      >
        {filteredEvents.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-16 text-center"
            style={{
              background: CARD,
              borderRadius: "16px",
              border: `1px solid ${BORDER}`,
            }}
          >
            <div className="text-4xl mb-3">📡</div>
            <div
              className="text-sm font-semibold text-gray-400"
              style={{ fontFamily: DISP }}
            >
              {sseStatus === "connecting"
                ? "Connecting to Fluvio stream…"
                : "Waiting for events…"}
            </div>
            <div
              className="text-xs text-gray-600 mt-1"
              style={{ fontFamily: MONO }}
            >
              {activeTopic === "all"
                ? "Subscribed to all topics"
                : `Subscribed to ${activeTopic}`}
            </div>
            <div
              className="text-xs text-gray-600 mt-3"
              style={{ fontFamily: DISP }}
            >
              Use the produce buttons above to inject a test event.
            </div>
          </div>
        ) : (
          filteredEvents.map(event => {
            const topic = TOPICS.find(t => t.id === event.topic);
            return (
              <EventRow
                key={event.id}
                event={event}
                topicColor={topic?.color ?? BLUE}
              />
            );
          })
        )}
      </div>

      {/* ── Endpoint info ───────────────────────────────────────────────────── */}
      {stats?.endpoint && (
        <div
          className="rounded-xl p-3 flex items-center gap-3"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <span className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
            Fluvio endpoint:
          </span>
          <span
            className="text-xs font-mono"
            style={{ color: BLUE, fontFamily: MONO }}
          >
            {stats.endpoint}
          </span>
        </div>
      )}
      {/* ── MQTT Bridge Configuration ──────────────────────────────────────── */}
      <div
        className="rounded-xl p-5"
        style={{ background: CARD, border: `1px solid ${BORDER}` }}
      >
        <MQTTBridgeTab />
      </div>
    </div>
  );
}
