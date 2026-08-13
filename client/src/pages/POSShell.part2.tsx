import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useEffect, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { ScreenHeader } from "./POSShell.part10";
import { BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED } from "./POSShell.shared";

export function OfflineResilienceScreen({ onBack }: { onBack: () => void }) {
  const { offlineQueue, dequeueOfflineTx, isOnline, agent } = usePosStore();
  const [syncing, setSyncing] = useState(false);
  const [syncProgress, setSyncProgress] = useState(0);
  const [syncTotal, setSyncTotal] = useState(0);

  const {
    data: sysStatus,
    refetch: refetchStatus,
    isLoading: statusLoading,
  } = trpc.resilience.systemStatus.useQuery(undefined, {
    refetchInterval: 15_000,
    retry: false,
  }) as any;
  const { data: rustItems, refetch: refetchRust } =
    trpc.resilience.listPendingOffline.useQuery(undefined, {
      refetchInterval: 10_000,
      retry: false,
    }) as any;
  const { data: probe } = trpc.resilience.probe.useQuery(undefined, {
    refetchInterval: 5_000,
    retry: false,
  }) as any;

  const createTx = trpc.transactions.create.useMutation() as any;
  const dequeue = trpc.resilience.dequeueOffline.useMutation() as any;
  const requeue = trpc.resilience.enqueueOffline.useMutation() as any;
  const discard = trpc.resilience.discardOfflineItem.useMutation() as any;
  const encodeUssd = trpc.resilience.encodeUssd.useMutation() as any;
  const printUssd = trpc.resilience.printUssdReceipt.useMutation() as any;
  const retryDeadLetterMut =
    trpc.resilience.retryDeadLetter.useMutation() as any;
  const logConnectivityMut =
    trpc.resilience.logConnectivity.useMutation() as any;
  const alertOnPoorConnMut =
    trpc.resilience.alertOnPoorConnectivity.useMutation() as any;
  const { data: pushSubs } = trpc.resilience.getPushSubscriptions.useQuery(
    { agentCode: agent?.agentCode ?? "DEMO" },
    { refetchInterval: 30_000, retry: false }
  ) as any;
  const { data: connHistory } = trpc.resilience.getConnectivityHistory.useQuery(
    { agentCode: agent?.agentCode ?? "DEMO", hours: 24 },
    { refetchInterval: 60_000, retry: false }
  ) as any;
  const utils = trpc.useUtils();

  // USSD fallback state
  const [ussdCodes, setUssdCodes] = useState<
    Array<{
      id: string;
      ussd_string: string;
      instructions: string;
      carrier_hint: string | null;
      tx_type: string;
      amount: number;
    }>
  >([]);
  const [generatingUssd, setGeneratingUssd] = useState(false);
  const [showUssdPanel, setShowUssdPanel] = useState(false);
  const [printingUssdId, setPrintingUssdId] = useState<string | null>(null);
  // Thermal receipt preview modal state
  const [thermalPreviewCode, setThermalPreviewCode] = useState<{
    ussd_string: string;
    instructions: string;
    tx_type: string;
    amount: number;
    carrier_hint: string | null;
  } | null>(null);
  const [smsUssdPhone, setSmsUssdPhone] = useState("");
  const sendUssdSms = trpc.smsReceipt.sendUssd.useMutation({
    onSuccess: () => {
      toast.success("USSD code sent via SMS");
      setSmsUssdPhone("");
    },
    onError: (e: any) => toast.error(`SMS failed: ${e.message}`),
  }) as any;
  const generateUssdCodes = async () => {
    const allItems = [
      ...zustandQueue.map((tx: any) => ({
        id: tx.id,
        txType: tx.type,
        amount: tx.amount,
        destinationAccount: tx.destinationAccount,
        destinationBank: tx.destinationBank,
        customerPhone: tx.customerPhone,
      })),
      ...rustQueue.map((item: any) => ({
        id: item.id,
        txType: item.tx_type,
        amount: item.amount,
        customerPhone: item.customer_phone,
        destinationAccount: undefined as string | undefined,
        destinationBank: undefined as string | undefined,
      })),
    ];
    if (allItems.length === 0) {
      toast.info("No pending transactions to encode");
      return;
    }
    setGeneratingUssd(true);
    const codes: typeof ussdCodes = [];
    for (const item of allItems.slice(0, 10)) {
      try {
        const result = await encodeUssd.mutateAsync({
          txType: item.txType,
          amount: item.amount,
          destinationAccount: item.destinationAccount,
          destinationBank: item.destinationBank,
          customerPhone: item.customerPhone,
        });
        codes.push({
          id: item.id,
          ussd_string: (result as any).ussd_string,
          instructions: (result as any).instructions,
          carrier_hint: (result as any).carrier_hint ?? null,
          tx_type: item.txType,
          amount: item.amount,
        });
      } catch {
        codes.push({
          id: item.id,
          ussd_string: `*966*${Math.round(item.amount)}#`,
          instructions: `Dial *966*${Math.round(item.amount)}# to pay via USSD.`,
          carrier_hint: null,
          tx_type: item.txType,
          amount: item.amount,
        });
      }
    }
    setUssdCodes(codes);
    setShowUssdPanel(true);
    setGeneratingUssd(false);
  };

  const connQuality: string =
    (probe as any)?.quality ?? (isOnline ? "Good" : "Offline");
  const connLatency: number | null = (probe as any)?.latency_ms ?? null;
  const connColor =
    connQuality === "Excellent"
      ? GREEN
      : connQuality === "Good"
        ? BLUE
        : connQuality === "Poor"
          ? GOLD
          : RED;

  // Log connectivity probe result whenever quality changes
  useEffect(() => {
    if (!agent?.agentCode) return;
    const q = connQuality as "Excellent" | "Good" | "Poor" | "Offline";
    if (["Excellent", "Good", "Poor", "Offline"].includes(q)) {
      logConnectivityMut.mutate({
        agentCode: agent.agentCode,
        quality: q,
        latencyMs: connLatency,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connQuality]);
  // Auto-alert owner when uptime drops below 80% (fires once per history refresh)
  useEffect(() => {
    if (!agent?.agentCode || !connHistory) return;
    if (connHistory.uptimePct < 80 && connHistory.rows.length >= 3) {
      alertOnPoorConnMut.mutate({ agentCode: agent.agentCode });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connHistory?.uptimePct]);

  const zustandQueue = offlineQueue;
  const rustQueue = (rustItems ?? []) as Array<{
    id: string;
    tx_type: string;
    amount: number;
    customer_name?: string;
    customer_phone?: string;
    channel?: string;
    queued_at?: string;
  }>;
  const totalPending = zustandQueue.length + rustQueue.length;

  const syncAll = async () => {
    setSyncing(true);
    const total = zustandQueue.length + rustQueue.length;
    setSyncTotal(total);
    setSyncProgress(0);
    let done = 0;
    for (const tx of [...zustandQueue]) {
      try {
        await createTx.mutateAsync({
          type: tx.type as any,
          amount: tx.amount,
          customerPhone: tx.customerPhone,
          customerName: tx.customerName,
          destinationBank: tx.destinationBank,
          destinationAccount: tx.destinationAccount,
          metadata: { offlineId: tx.id },
        });
        dequeueOfflineTx(tx.id);
        toast.success(`Synced: ₦${tx.amount.toLocaleString()} ${tx.type}`);
      } catch {
        toast.error(`Failed to sync ${tx.type} ₦${tx.amount}`);
      }
      done++;
      setSyncProgress(done);
    }
    for (let i = 0; i < 50; i++) {
      let item: any = null;
      try {
        const r = await dequeue.mutateAsync({});
        item = (r as any)?.item ?? null;
      } catch {
        break;
      }
      if (!item) break;
      try {
        await createTx.mutateAsync({
          type: item.tx_type as any,
          amount: item.amount,
          customerPhone: item.customer_phone,
          customerName: item.customer_name,
          metadata: { rustQueueId: item.id },
        });
        toast.success(`Synced (durable): ₦${item.amount} ${item.tx_type}`);
      } catch {
        await requeue.mutateAsync({
          txType: item.tx_type,
          amount: item.amount,
          customerName: item.customer_name,
          customerPhone: item.customer_phone,
        });
        toast.error(`Failed — re-queued: ${item.tx_type}`);
      }
      done++;
      setSyncProgress(done);
    }
    await utils.resilience.queueCount.invalidate();
    refetchRust();
    setSyncing(false);
    toast.success("Sync complete");
  };

  const discardItem = async (id: string) => {
    await discard.mutateAsync({ id });
    refetchRust();
    toast.info("Item discarded");
  };

  const badge = (label: string, ok: boolean, warn?: boolean) => (
    <span
      className="text-xs px-2 py-0.5 rounded-full font-bold"
      style={{
        background: ok ? `${GREEN}22` : warn ? `${GOLD}22` : `${RED}22`,
        color: ok ? GREEN : warn ? GOLD : RED,
        fontFamily: MONO,
      }}
    >
      {label}
    </span>
  );

  const sec = (title: string, icon: string) => (
    <div className="flex items-center gap-2 mb-3">
      <span style={{ fontSize: 16 }}>{icon}</span>
      <span
        className="text-sm font-bold text-white"
        style={{ fontFamily: DISP }}
      >
        {title}
      </span>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Offline &amp; Resilience" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Connection Quality */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `2px solid ${connColor}44` }}
        >
          {sec("Connection Quality", "📡")}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-end gap-0.5 h-5">
                {[0, 1, 2, 3].map((i: any) => (
                  <div
                    key={i}
                    className="w-2 rounded-sm"
                    style={{
                      height: `${(i + 1) * 25}%`,
                      background:
                        ["Offline", "Poor", "Good", "Excellent"].indexOf(
                          connQuality
                        ) >= i
                          ? connColor
                          : BORDER,
                    }}
                  />
                ))}
              </div>
              <div>
                <div
                  className="text-lg font-black"
                  style={{ color: connColor, fontFamily: MONO }}
                >
                  {connQuality}
                </div>
                {connLatency !== null && (
                  <div
                    className="text-xs"
                    style={{ color: "#6b7280", fontFamily: MONO }}
                  >
                    {connLatency}ms latency
                  </div>
                )}
              </div>
            </div>
            {badge(isOnline ? "ONLINE" : "OFFLINE", isOnline)}
          </div>
        </div>

        {/* Connectivity History Sparkline */}
        {connHistory && connHistory.rows.length > 0 && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            {sec("Connectivity History (24h)", "📊")}
            <div className="flex items-center justify-between mb-2">
              <div className="flex gap-4">
                <div>
                  <div
                    className="text-lg font-black"
                    style={{
                      color:
                        connHistory.uptimePct >= 95
                          ? GREEN
                          : connHistory.uptimePct >= 80
                            ? GOLD
                            : RED,
                      fontFamily: MONO,
                    }}
                  >
                    {connHistory.uptimePct}%
                  </div>
                  <div
                    className="text-xs"
                    style={{ color: "#6b7280", fontFamily: DISP }}
                  >
                    Uptime
                  </div>
                </div>
                <div>
                  <div
                    className="text-lg font-black"
                    style={{ color: BLUE, fontFamily: MONO }}
                  >
                    {connHistory.avgLatencyMs}ms
                  </div>
                  <div
                    className="text-xs"
                    style={{ color: "#6b7280", fontFamily: DISP }}
                  >
                    Avg Latency
                  </div>
                </div>
                <div>
                  <div
                    className="text-lg font-black text-white"
                    style={{ fontFamily: MONO }}
                  >
                    {connHistory.rows.length}
                  </div>
                  <div
                    className="text-xs"
                    style={{ color: "#6b7280", fontFamily: DISP }}
                  >
                    Probes
                  </div>
                </div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={60}>
              <LineChart
                data={connHistory.rows.map((r: any) => ({
                  t: new Date(r.recordedAt).getTime(),
                  latency: r.latencyMs ?? 0,
                  online: r.quality !== "Offline" ? 1 : 0,
                }))}
                margin={{ top: 4, right: 4, left: -30, bottom: 0 }}
              >
                <XAxis dataKey="t" hide />
                <YAxis hide />
                <Tooltip
                  contentStyle={{
                    background: "#0a0e1a",
                    border: `1px solid ${BORDER}`,
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                  labelFormatter={v =>
                    new Date(v as number).toLocaleTimeString()
                  }
                  formatter={(v: number, name: string) =>
                    name === "latency"
                      ? [`${v}ms`, "Latency"]
                      : [v === 1 ? "Online" : "Offline", "Status"]
                  }
                />
                <Line
                  type="monotone"
                  dataKey="latency"
                  stroke={BLUE}
                  dot={false}
                  strokeWidth={1.5}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Push Subscriptions — shows lastAlertedAt for throttle visibility */}
        {pushSubs && pushSubs.subscriptions.length > 0 && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            {sec("Push Subscriptions", "🔔")}
            <div className="flex flex-col gap-2 mt-2">
              {pushSubs.subscriptions.map((sub: any, i: any) => {
                const lastAlerted = sub.lastAlertedAt
                  ? new Date(sub.lastAlertedAt)
                  : null;
                const minutesAgo = lastAlerted
                  ? Math.round((Date.now() - lastAlerted.getTime()) / 60000)
                  : null;
                const throttleActive = minutesAgo !== null && minutesAgo < 30;
                return (
                  <div
                    key={sub.id}
                    className="flex items-center justify-between p-2 rounded-xl"
                    style={{
                      background: "oklch(0.10 0.01 240)",
                      border: `1px solid ${BORDER}`,
                    }}
                  >
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-xs font-bold text-white truncate"
                        style={{ fontFamily: MONO }}
                      >
                        Sub #{i + 1}
                      </div>
                      <div
                        className="text-xs truncate"
                        style={{ color: "#6b7280", fontFamily: MONO }}
                      >
                        {sub.endpoint.slice(0, 40)}…
                      </div>
                    </div>
                    <div className="text-right ml-2 flex-shrink-0">
                      <div
                        className="text-xs font-bold"
                        style={{
                          color: throttleActive ? GOLD : GREEN,
                          fontFamily: MONO,
                        }}
                      >
                        {lastAlerted
                          ? minutesAgo! < 60
                            ? `${minutesAgo}m ago`
                            : lastAlerted.toLocaleTimeString()
                          : "Never alerted"}
                      </div>
                      <div
                        className="text-xs"
                        style={{ color: "#6b7280", fontFamily: DISP }}
                      >
                        {throttleActive ? "⏸ Throttled" : "✓ Ready"}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
        {/* Sync Queue Summary */}
        <div
          className="rounded-2xl p-4"
          style={{
            background: CARD,
            border: `1px solid ${totalPending > 0 ? GOLD : BORDER}`,
          }}
        >
          {sec("Pending Sync Queue", "⏳")}
          <div className="flex items-center justify-between mb-3">
            <div>
              <div
                className="text-2xl font-black"
                style={{
                  color: totalPending > 0 ? GOLD : GREEN,
                  fontFamily: MONO,
                }}
              >
                {totalPending}
              </div>
              <div
                className="text-xs"
                style={{ color: "#6b7280", fontFamily: DISP }}
              >
                transactions pending
              </div>
            </div>
            <div className="flex flex-col gap-1 text-right">
              <div
                className="text-xs"
                style={{ color: "#6b7280", fontFamily: MONO }}
              >
                <span style={{ color: BLUE }}>In-memory:</span>{" "}
                {zustandQueue.length}
              </div>
              <div
                className="text-xs"
                style={{ color: "#6b7280", fontFamily: MONO }}
              >
                <span style={{ color: GOLD }}>Durable (SQLite):</span>{" "}
                {rustQueue.length}
              </div>
            </div>
          </div>
          {syncing ? (
            <div className="flex flex-col gap-2">
              <div
                className="w-full h-2 rounded-full"
                style={{ background: BORDER }}
              >
                <div
                  className="h-2 rounded-full transition-all"
                  style={{
                    width: `${syncTotal > 0 ? (syncProgress / syncTotal) * 100 : 0}%`,
                    background: BLUE,
                  }}
                />
              </div>
              <div
                className="text-xs text-center"
                style={{ color: BLUE, fontFamily: MONO }}
              >
                Syncing {syncProgress}/{syncTotal}...
              </div>
            </div>
          ) : (
            <button
              onClick={syncAll}
              disabled={totalPending === 0 || !isOnline}
              className="w-full py-2 rounded-xl text-sm font-bold transition-all active:scale-95"
              style={{
                background: totalPending > 0 && isOnline ? `${BLUE}22` : BORDER,
                color: totalPending > 0 && isOnline ? BLUE : "#4b5563",
                border: `1px solid ${totalPending > 0 && isOnline ? BLUE : BORDER}`,
                fontFamily: DISP,
              }}
            >
              {isOnline
                ? totalPending > 0
                  ? `⬆ Sync All (${totalPending})`
                  : "✓ Queue Empty"
                : "📵 Offline — Cannot Sync"}
            </button>
          )}
        </div>

        {/* In-Memory Queue */}
        {zustandQueue.length > 0 && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            {sec("In-Memory Queue (Session)", "🧠")}
            <div className="flex flex-col gap-2">
              {zustandQueue.map((tx: any) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between p-2 rounded-xl"
                  style={{
                    background: "oklch(0.10 0.01 240)",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  <div>
                    <div
                      className="text-xs font-bold text-white"
                      style={{ fontFamily: MONO }}
                    >
                      {tx.type.toUpperCase()} · ₦{tx.amount.toLocaleString()}
                    </div>
                    <div
                      className="text-xs"
                      style={{ color: "#6b7280", fontFamily: DISP }}
                    >
                      {tx.customerName ?? tx.customerPhone ?? "Unknown"}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: `${GOLD}22`,
                        color: GOLD,
                        fontFamily: MONO,
                      }}
                    >
                      QUEUED
                    </span>
                    <button
                      onClick={() => dequeueOfflineTx(tx.id)}
                      className="text-xs px-2 py-0.5 rounded-lg"
                      style={{
                        background: `${RED}22`,
                        color: RED,
                        fontFamily: MONO,
                      }}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Rust Durable Queue */}
        {rustQueue.length > 0 && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            {sec("Durable Queue (SQLite WAL)", "🦀")}
            <div className="flex flex-col gap-2">
              {rustQueue.map((item: any) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-2 rounded-xl"
                  style={{
                    background: "oklch(0.10 0.01 240)",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  <div>
                    <div
                      className="text-xs font-bold text-white"
                      style={{ fontFamily: MONO }}
                    >
                      {(item.tx_type ?? "TX").toUpperCase()} · ₦
                      {Number(item.amount).toLocaleString()}
                    </div>
                    <div
                      className="text-xs"
                      style={{ color: "#6b7280", fontFamily: DISP }}
                    >
                      {item.customer_name ?? item.customer_phone ?? "Unknown"}
                      {item.queued_at
                        ? ` · ${new Date(item.queued_at).toLocaleTimeString()}`
                        : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{
                        background: `${GOLD}22`,
                        color: GOLD,
                        fontFamily: MONO,
                      }}
                    >
                      DURABLE
                    </span>
                    <button
                      onClick={() => discardItem(item.id)}
                      className="text-xs px-2 py-0.5 rounded-lg"
                      style={{
                        background: `${RED}22`,
                        color: RED,
                        fontFamily: MONO,
                      }}
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Fluvio Event Bus */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {sec("Fluvio Event Bus", "⚡")}
          {statusLoading ? (
            <div
              className="text-xs"
              style={{ color: "#6b7280", fontFamily: MONO }}
            >
              Loading...
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Mode
                </span>
                {badge(
                  (sysStatus?.fluvio?.mode ?? "fallback").toUpperCase(),
                  sysStatus?.fluvio?.mode === "direct",
                  sysStatus?.fluvio?.mode === "proxy"
                )}
              </div>
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Buffered Events
                </span>
                <span
                  className="text-xs font-bold"
                  style={{
                    color:
                      (sysStatus?.fluvio?.bufferedEvents ?? 0) > 0
                        ? GOLD
                        : GREEN,
                    fontFamily: MONO,
                  }}
                >
                  {sysStatus?.fluvio?.bufferedEvents ?? 0}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Topics
                </span>
                <span
                  className="text-xs font-bold text-white"
                  style={{ fontFamily: MONO }}
                >
                  {sysStatus?.fluvio?.topicCount ?? 0}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Endpoint
                </span>
                <span
                  className="text-xs"
                  style={{ color: "#6b7280", fontFamily: MONO }}
                >
                  {(sysStatus?.fluvio?.endpoint ?? "none").slice(0, 30)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Redis Cache */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {sec("Redis Cache", "🔴")}
          {statusLoading ? (
            <div
              className="text-xs"
              style={{ color: "#6b7280", fontFamily: MONO }}
            >
              Loading...
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <div
                  className="text-sm font-bold text-white"
                  style={{ fontFamily: DISP }}
                >
                  {sysStatus?.redis?.mode === "direct"
                    ? "Direct (ioredis)"
                    : sysStatus?.redis?.mode === "proxy"
                      ? "APISix Proxy"
                      : "Unavailable"}
                </div>
                <div
                  className="text-xs"
                  style={{ color: "#6b7280", fontFamily: MONO }}
                >
                  Connection mode
                </div>
              </div>
              {badge(
                sysStatus?.redis?.healthy ? "HEALTHY" : "DEGRADED",
                sysStatus?.redis?.healthy ?? false
              )}
            </div>
          )}
        </div>

        {/* ERP Retry Worker */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {sec("ERP Retry Worker", "🔄")}
          {statusLoading ? (
            <div
              className="text-xs"
              style={{ color: "#6b7280", fontFamily: MONO }}
            >
              Loading...
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Pending Sync
                </span>
                <span
                  className="text-xs font-bold"
                  style={{
                    color:
                      (sysStatus?.erp?.pendingCount ?? 0) > 0 ? GOLD : GREEN,
                    fontFamily: MONO,
                  }}
                >
                  {sysStatus?.erp?.pendingCount ?? 0} entries
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Dead Letter
                </span>
                <span
                  className="text-xs font-bold"
                  style={{
                    color:
                      (sysStatus?.erp?.deadLetterCount ?? 0) > 0 ? RED : GREEN,
                    fontFamily: MONO,
                  }}
                >
                  {sysStatus?.erp?.deadLetterCount ?? 0} failed
                </span>
              </div>
              {sysStatus?.erp?.lastRetryAt && (
                <div className="flex items-center justify-between">
                  <span
                    className="text-xs"
                    style={{ color: "#9ca3af", fontFamily: DISP }}
                  >
                    Last Activity
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "#6b7280", fontFamily: MONO }}
                  >
                    {new Date(sysStatus.erp.lastRetryAt).toLocaleTimeString()}
                  </span>
                </div>
              )}
              {(sysStatus?.erp?.deadLetterCount ?? 0) > 0 && (
                <button
                  disabled={retryDeadLetterMut.isPending}
                  onClick={async () => {
                    try {
                      const r = await retryDeadLetterMut.mutateAsync();
                      toast.success(
                        `Re-queued ${(r as any).requeued ?? 0} dead-letter item(s)`
                      );
                      refetchStatus();
                    } catch {
                      toast.error("Failed to retry dead-letter items");
                    }
                  }}
                  className="w-full py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95 disabled:opacity-50"
                  style={{
                    background: `${RED}22`,
                    color: RED,
                    border: `1px solid ${RED}44`,
                    fontFamily: DISP,
                  }}
                >
                  {retryDeadLetterMut.isPending
                    ? "Retrying…"
                    : `↺ Retry All Dead-Letter (${sysStatus?.erp?.deadLetterCount})`}
                </button>
              )}
            </div>
          )}
        </div>

        {/* MQTT Bridge */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {sec("MQTT Bridge", "📶")}
          {statusLoading ? (
            <div
              className="text-xs"
              style={{ color: "#6b7280", fontFamily: MONO }}
            >
              Loading...
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Status
                </span>
                {badge(
                  (sysStatus?.mqtt?.status ?? "unconfigured").toUpperCase(),
                  sysStatus?.mqtt?.status === "success",
                  sysStatus?.mqtt?.status === "disabled" ||
                    sysStatus?.mqtt?.status === "never"
                )}
              </div>
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  QoS
                </span>
                <span
                  className="text-xs font-bold text-white"
                  style={{ fontFamily: MONO }}
                >
                  Level {sysStatus?.mqtt?.qos ?? "1"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span
                  className="text-xs"
                  style={{ color: "#9ca3af", fontFamily: DISP }}
                >
                  Topic Mappings
                </span>
                <span
                  className="text-xs font-bold text-white"
                  style={{ fontFamily: MONO }}
                >
                  {sysStatus?.mqtt?.topicCount ?? 0}
                </span>
              </div>
              {sysStatus?.mqtt?.broker && (
                <div className="flex items-center justify-between">
                  <span
                    className="text-xs"
                    style={{ color: "#9ca3af", fontFamily: DISP }}
                  >
                    Broker
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "#6b7280", fontFamily: MONO }}
                  >
                    {sysStatus.mqtt.broker.slice(0, 30)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Go Agent Retry History */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {sec("Go Agent Retry History", "🔁")}
          {statusLoading ? (
            <div
              className="text-xs"
              style={{ color: "#6b7280", fontFamily: MONO }}
            >
              Loading...
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {(sysStatus?.goAgent?.retryHistory ?? []).length === 0 ? (
                <div
                  className="text-xs"
                  style={{ color: "#4b5563", fontFamily: MONO }}
                >
                  No retry history — agent may be offline
                </div>
              ) : (
                (
                  sysStatus?.goAgent?.retryHistory as Array<{
                    attempt: number;
                    status: string;
                    latency_ms?: number;
                    timestamp: string;
                  }>
                ).map((h, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-xl"
                    style={{
                      background: "oklch(0.10 0.01 240)",
                      border: `1px solid ${BORDER}`,
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="text-xs"
                        style={{ color: "#6b7280", fontFamily: MONO }}
                      >
                        #{h.attempt}
                      </span>
                      <span
                        className="text-xs text-white"
                        style={{ fontFamily: MONO }}
                      >
                        {h.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {h.latency_ms && (
                        <span
                          className="text-xs"
                          style={{ color: BLUE, fontFamily: MONO }}
                        >
                          {h.latency_ms}ms
                        </span>
                      )}
                      <span
                        className="text-xs"
                        style={{ color: "#4b5563", fontFamily: MONO }}
                      >
                        {new Date(h.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* USSD Fallback Shortcut — shown when offline and queue has items */}
        {!isOnline && totalPending > 0 && (
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `2px solid ${GOLD}44` }}
          >
            {sec("USSD Fallback", "📞")}
            <p
              className="text-xs mb-3"
              style={{ color: "#9ca3af", fontFamily: DISP }}
            >
              You are offline with {totalPending} pending transaction
              {totalPending > 1 ? "s" : ""}. Generate USSD dial strings to
              complete them immediately without internet.
            </p>
            {showUssdPanel && ussdCodes.length > 0 ? (
              <div className="flex flex-col gap-3">
                {ussdCodes.map((code, i) => (
                  <div
                    key={code.id}
                    className="rounded-xl p-3"
                    style={{
                      background: "oklch(0.10 0.01 240)",
                      border: `1px solid ${GOLD}33`,
                    }}
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
                      className="text-base font-black mb-1"
                      style={{
                        color: "#ffffff",
                        fontFamily: MONO,
                        letterSpacing: "0.05em",
                      }}
                    >
                      {code.ussd_string}
                    </div>
                    <div
                      className="text-xs"
                      style={{ color: "#6b7280", fontFamily: DISP }}
                    >
                      {code.instructions}
                    </div>
                    <div className="flex gap-2 mt-2 flex-wrap">
                      <button
                        onClick={() => {
                          navigator.clipboard?.writeText(code.ussd_string);
                          toast.success("Copied!");
                        }}
                        className="text-xs px-3 py-1 rounded-lg"
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
                        onClick={() =>
                          setThermalPreviewCode({
                            ussd_string: code.ussd_string,
                            instructions: code.instructions,
                            tx_type: code.tx_type,
                            amount: code.amount,
                            carrier_hint: code.carrier_hint,
                          })
                        }
                        className="text-xs px-3 py-1 rounded-lg"
                        style={{
                          background: "oklch(0.25 0.02 240)",
                          color: "#e5e7eb",
                          border: "1px solid #374151",
                          fontFamily: MONO,
                        }}
                      >
                        👁 Preview
                      </button>
                      <button
                        disabled={printingUssdId === code.id}
                        onClick={async () => {
                          setPrintingUssdId(code.id);
                          try {
                            await printUssd.mutateAsync({
                              agentCode: agent?.agentCode ?? "UNKNOWN",
                              txType: code.tx_type,
                              amount: code.amount,
                              ussdString: code.ussd_string,
                              instructions: code.instructions,
                            });
                            toast.success("USSD receipt sent to printer");
                          } catch {
                            toast.error("Printer offline — receipt queued");
                          } finally {
                            setPrintingUssdId(null);
                          }
                        }}
                        className="text-xs px-3 py-1 rounded-lg disabled:opacity-50"
                        style={{
                          background: `${BLUE}22`,
                          color: BLUE,
                          border: `1px solid ${BLUE}44`,
                          fontFamily: MONO,
                        }}
                      >
                        {printingUssdId === code.id ? "Printing…" : "🖨 Print"}
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  onClick={() => setShowUssdPanel(false)}
                  className="text-xs text-center"
                  style={{ color: "#6b7280", fontFamily: DISP }}
                >
                  Hide USSD codes
                </button>
              </div>
            ) : (
              <button
                onClick={generateUssdCodes}
                disabled={generatingUssd}
                className="w-full py-2 rounded-xl text-sm font-bold transition-all active:scale-95"
                style={{
                  background: `${GOLD}22`,
                  color: GOLD,
                  border: `1px solid ${GOLD}44`,
                  fontFamily: DISP,
                }}
              >
                {generatingUssd
                  ? "Generating…"
                  : `📞 Generate USSD Codes (${totalPending})`}
              </button>
            )}
          </div>
        )}

        {/* Refresh */}
        <button
          onClick={() => {
            refetchStatus();
            refetchRust();
          }}
          className="w-full py-3 rounded-2xl text-sm font-bold transition-all active:scale-95"
          style={{
            background: `${BLUE}22`,
            color: BLUE,
            border: `1px solid ${BLUE}44`,
            fontFamily: DISP,
          }}
        >
          ↻ Refresh Status
        </button>
      </div>

      {/* ── Thermal Receipt Preview Modal ── */}
      {thermalPreviewCode && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.75)" }}
          onClick={() => setThermalPreviewCode(null)}
        >
          <div
            className="relative flex flex-col"
            style={{
              width: 320,
              background: "#fff",
              borderRadius: 4,
              boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
            }}
            onClick={e => e.stopPropagation()}
          >
            {/* Thermal paper top perforation */}
            <div
              style={{
                height: 12,
                background:
                  "repeating-linear-gradient(90deg, #fff 0 6px, #e5e7eb 6px 12px)",
                borderRadius: "4px 4px 0 0",
              }}
            />
            {/* Receipt body */}
            <div
              className="px-5 py-4"
              style={{
                fontFamily: "'Courier New', Courier, monospace",
                fontSize: 13,
                color: "#111",
                lineHeight: 1.6,
              }}
            >
              <div
                className="text-center font-black text-base mb-1"
                style={{ letterSpacing: "0.08em" }}
              >
                54LINK POS
              </div>
              <div
                className="text-center text-xs mb-3"
                style={{ color: "#555" }}
              >
                OFFLINE USSD RECEIPT
              </div>
              <div style={{ borderTop: "1px dashed #999", marginBottom: 8 }} />
              <div className="flex justify-between text-xs mb-1">
                <span>TYPE</span>
                <span className="font-bold">
                  {thermalPreviewCode.tx_type.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between text-xs mb-1">
                <span>AMOUNT</span>
                <span className="font-bold">
                  ₦
                  {Number(thermalPreviewCode.amount).toLocaleString("en-NG", {
                    minimumFractionDigits: 2,
                  })}
                </span>
              </div>
              {thermalPreviewCode.carrier_hint && (
                <div className="flex justify-between text-xs mb-1">
                  <span>CARRIER</span>
                  <span className="font-bold">
                    {thermalPreviewCode.carrier_hint}
                  </span>
                </div>
              )}
              <div className="flex justify-between text-xs mb-1">
                <span>DATE</span>
                <span>{new Date().toLocaleDateString("en-NG")}</span>
              </div>
              <div className="flex justify-between text-xs mb-3">
                <span>TIME</span>
                <span>
                  {new Date().toLocaleTimeString("en-NG", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <div style={{ borderTop: "1px dashed #999", marginBottom: 8 }} />
              <div
                className="text-center font-black text-xl mb-1"
                style={{ letterSpacing: "0.15em", wordBreak: "break-all" }}
              >
                {thermalPreviewCode.ussd_string}
              </div>
              <div
                className="text-center text-xs mb-3"
                style={{ color: "#555", whiteSpace: "pre-wrap" }}
              >
                {thermalPreviewCode.instructions}
              </div>
              <div style={{ borderTop: "1px dashed #999", marginBottom: 8 }} />
              <div className="text-center text-xs" style={{ color: "#888" }}>
                DIAL THE CODE ABOVE TO COMPLETE
              </div>
              <div className="text-center text-xs" style={{ color: "#888" }}>
                YOUR TRANSACTION OFFLINE
              </div>
              <div
                className="text-center text-xs mt-2"
                style={{ color: "#bbb" }}
              >
                www.54link.io
              </div>
            </div>
            {/* Thermal paper bottom perforation */}
            <div
              style={{
                height: 12,
                background:
                  "repeating-linear-gradient(90deg, #fff 0 6px, #e5e7eb 6px 12px)",
                borderRadius: "0 0 4px 4px",
              }}
            />
            {/* Action buttons */}
            <div
              className="flex gap-2 px-4 py-3 flex-wrap"
              style={{
                background: "#f9fafb",
                borderTop: "1px solid #e5e7eb",
                borderRadius: "0 0 4px 4px",
              }}
            >
              <button
                className="flex-1 py-2 rounded text-xs font-bold"
                style={{ background: "#1e3a5f", color: "#fff", minWidth: 80 }}
                onClick={async () => {
                  try {
                    await printUssd.mutateAsync({
                      agentCode: agent?.agentCode ?? "UNKNOWN",
                      txType: thermalPreviewCode.tx_type,
                      amount: thermalPreviewCode.amount,
                      ussdString: thermalPreviewCode.ussd_string,
                      instructions: thermalPreviewCode.instructions,
                    });
                    toast.success("USSD receipt sent to printer");
                    setThermalPreviewCode(null);
                  } catch {
                    toast.error("Printer offline — receipt queued");
                  }
                }}
              >
                🖨 Confirm &amp; Print
              </button>
              <button
                className="flex-1 py-2 rounded text-xs font-bold"
                style={{ background: "#065f46", color: "#fff", minWidth: 80 }}
                onClick={() => {
                  // Open a minimal print window with only the receipt content
                  const printWin = window.open(
                    "",
                    "_blank",
                    "width=400,height=600"
                  );
                  if (!printWin) {
                    toast.error("Pop-up blocked — allow pop-ups and try again");
                    return;
                  }
                  const now = new Date();
                  printWin.document.write(`<!DOCTYPE html>
<html><head><title>54Link USSD Receipt</title>
<style>
  @page { size: 80mm auto; margin: 4mm; }
  * { box-sizing: border-box; }
  body { font-family: 'Courier New', Courier, monospace; font-size: 12px; color: #000; background: #fff; width: 72mm; margin: 0 auto; }
  .center { text-align: center; }
  .bold { font-weight: bold; }
  .row { display: flex; justify-content: space-between; margin-bottom: 2px; }
  .divider { border-top: 1px dashed #999; margin: 6px 0; }
  .ussd { font-size: 18px; font-weight: 900; letter-spacing: 0.15em; word-break: break-all; text-align: center; margin: 6px 0; }
  .perf { height: 8px; background: repeating-linear-gradient(90deg, #fff 0 5px, #ccc 5px 10px); }
  .footer { font-size: 9px; color: #888; text-align: center; margin-top: 4px; }
  @media print { body { width: 100%; } }
</style></head><body>
<div class="perf"></div>
<div class="center bold" style="font-size:14px;margin:6px 0 2px">54LINK POS</div>
<div class="center" style="font-size:10px;color:#555;margin-bottom:6px">OFFLINE USSD RECEIPT</div>
<div class="divider"></div>
<div class="row"><span>TYPE</span><span class="bold">${thermalPreviewCode.tx_type.toUpperCase()}</span></div>
<div class="row"><span>AMOUNT</span><span class="bold">₦${Number(thermalPreviewCode.amount).toLocaleString("en-NG", { minimumFractionDigits: 2 })}</span></div>
${thermalPreviewCode.carrier_hint ? `<div class="row"><span>CARRIER</span><span class="bold">${thermalPreviewCode.carrier_hint}</span></div>` : ""}
<div class="row"><span>DATE</span><span>${now.toLocaleDateString("en-NG")}</span></div>
<div class="row"><span>TIME</span><span>${now.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" })}</span></div>
<div class="divider"></div>
<div class="ussd">${thermalPreviewCode.ussd_string}</div>
<div class="center" style="font-size:10px;color:#555;white-space:pre-wrap;margin-bottom:6px">${thermalPreviewCode.instructions}</div>
<div class="divider"></div>
<div class="center" style="font-size:10px;color:#888;margin-bottom:4px">SCAN QR OR DIAL CODE TO COMPLETE</div>
<div class="center" style="font-size:10px;color:#888">YOUR TRANSACTION OFFLINE</div>
<div id="qr-container" class="center" style="margin:6px 0"></div>
<script>
  (function(){
    var ussd = ${JSON.stringify(thermalPreviewCode.ussd_string)};
    var size = 80;
    var qr = document.getElementById('qr-container');
    // Use Google Charts QR API (works offline-capable via data URI in modern browsers)
    var img = document.createElement('img');
    img.src = 'https://chart.googleapis.com/chart?cht=qr&chs=' + size + 'x' + size + '&chl=' + encodeURIComponent(ussd) + '&choe=UTF-8';
    img.width = size; img.height = size;
    img.alt = ussd;
    img.onerror = function(){ qr.style.display='none'; };
    qr.appendChild(img);
  })();
<\/script>
<div class="footer">www.54link.io</div>
<div class="perf" style="margin-top:6px"></div>
</body></html>`);
                  printWin.document.close();
                  printWin.focus();
                  setTimeout(() => {
                    printWin.print();
                  }, 250);
                }}
              >
                📄 Save as PDF
              </button>
              <button
                className="flex-1 py-2 rounded text-xs font-bold"
                style={{
                  background: "#e5e7eb",
                  color: "#374151",
                  minWidth: 80,
                }}
                onClick={() => setThermalPreviewCode(null)}
              >
                Cancel
              </button>
            </div>
            {/* Send via SMS row */}
            <div className="flex gap-2 mt-2 items-center">
              <input
                type="tel"
                placeholder="Customer phone (e.g. 08012345678)"
                value={smsUssdPhone}
                onChange={e =>
                  setSmsUssdPhone(
                    e.target.value.replace(/\D/g, "").slice(0, 15)
                  )
                }
                className="flex-1 px-3 py-2 rounded text-xs outline-none"
                style={{
                  background: "#1a1a2e",
                  border: "1px solid #334155",
                  color: "#fff",
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              />
              <button
                className="py-2 px-3 rounded text-xs font-bold"
                style={{
                  background: sendUssdSms.isPending ? "#1e3a8a" : "#1d4ed8",
                  color: "#fff",
                  minWidth: 90,
                  opacity: sendUssdSms.isPending ? 0.7 : 1,
                }}
                disabled={sendUssdSms.isPending || smsUssdPhone.length < 10}
                onClick={() => {
                  if (!thermalPreviewCode) return;
                  sendUssdSms.mutate({
                    recipientPhone: smsUssdPhone,
                    ussdCode: thermalPreviewCode.ussd_string,
                    amount: thermalPreviewCode.amount,
                    agentCode: agent?.agentCode,
                  });
                }}
              >
                {sendUssdSms.isPending ? "Sending…" : "📱 Send SMS"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main POSShell Component ──────────────────────────────────────────────────
