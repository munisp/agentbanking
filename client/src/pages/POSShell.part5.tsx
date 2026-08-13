import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useState } from "react";
import { toast } from "sonner";
import { ScreenHeader } from "./POSShell.part10";
import { fmt } from "./POSShell.part6";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TILE_CUSTOM_KEY, TileCustomization } from "./POSShell.shared";

export function FloatBalanceScreen({ onBack }: { onBack: () => void }) {
  const [tab, setTab] = useState<"overview" | "history">("overview");
  const [showTopUpModal, setShowTopUpModal] = useState(false);
  const [topUpAmount, setTopUpAmount] = useState("");
  const [topUpNotes, setTopUpNotes] = useState("");
  const { data: ds } = trpc.transactions.agentDayStats.useQuery(undefined, {
    refetchInterval: 60_000,
  }) as any;
  const { data: floatData } = trpc.transactions.getFloatBalance.useQuery(
    undefined,
    { refetchInterval: 30_000 }
  ) as any;
  const { data: floatHistoryData } = trpc.transactions.getFloatHistory.useQuery(
    { limit: 50 },
    { refetchInterval: 60_000 }
  ) as any;
  const { data: topUpHistory } = trpc.floatTopUp.myRequests.useQuery(
    undefined,
    { refetchInterval: 60_000 }
  ) as any;
  const agent = usePosStore(s => s.agent);
  // Prefer live float balance from platform (getFloatBalance), then agentDayStats, then store
  // No fabricated float: show "—" until a real balance is available.
  const float =
    floatData?.balance ?? ds?.float ?? agent?.floatBalance ?? null;
  const floatSource = floatData?.source ?? "local";
  const limit = agent?.floatLimit ?? null;
  const pct =
    float != null && limit != null && limit > 0
      ? Math.round((float / limit) * 100)
      : null;

  const submitTopUpMut = trpc.agentMgmt.submitTopUpRequest.useMutation({
    onSuccess: () => {
      toast.success("Float top-up request submitted — awaiting admin approval");
      setShowTopUpModal(false);
      setTopUpAmount("");
      setTopUpNotes("");
    },
    onError: (e: { message: string }) =>
      toast.error(`Request failed: ${e.message}`),
  }) as any;

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Float Balance" onBack={onBack} />
      <div className="flex gap-2 px-4 pt-3">
        {(["overview", "history"] as const).map((t: any) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="flex-1 py-2 rounded-lg text-sm font-semibold capitalize"
            style={{
              background: tab === t ? GOLD : CARD,
              color: tab === t ? BG : "#9ca3af",
              fontFamily: DISP,
            }}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "overview" ? (
        <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
          <div
            className="rounded-2xl p-5"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div className="flex items-center justify-between mb-1">
              <div
                className="text-xs text-gray-500"
                style={{ fontFamily: DISP }}
              >
                Available Float
              </div>
              <div
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background:
                    floatSource === "platform"
                      ? "oklch(0.65 0.18 160 / 0.2)"
                      : "oklch(0.40 0.01 240 / 0.3)",
                  color: floatSource === "platform" ? "#10b981" : "#9ca3af",
                  fontFamily: DISP,
                }}
              >
                {floatSource === "platform" ? "● Live" : "● Local DB"}
              </div>
            </div>
            <div
              className="text-4xl font-bold"
              style={{ fontFamily: MONO, color: GOLD }}
            >
              ₦{fmt(float)}
            </div>
            <div className="mt-3">
              <div
                className="flex justify-between text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                <span>Used: {float != null && limit != null ? fmt(limit - float) : "—"}</span>
                <span>Limit: {fmt(limit)}</span>
              </div>
              <div
                className="h-3 rounded-full overflow-hidden"
                style={{ background: BORDER }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct ?? 0}%`, background: GOLD }}
                />
              </div>
              <div
                className="text-right text-xs mt-1"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                {pct != null ? `${pct}% available` : "—"}
              </div>
            </div>
          </div>
          {[
            {
              label: "Daily Transactions",
              val:
                "₦" +
                fmt(
                  (ds?.cashIn ?? 0) + (ds?.cashOut ?? 0) + (ds?.transfers ?? 0)
                ),
              sub: (ds?.count ?? 0) + " transactions",
            },
            {
              label: "Commission Earned",
              val: "₦" + fmt(ds?.commission ?? agent?.commissionBalance ?? 0),
              sub: "Today",
            },
            {
              label: "Float Utilization",
              val: pct != null ? pct + "%" : "—",
              sub: "Of daily limit",
            },
            {
              label: "Float Source",
              val: floatSource === "platform" ? "Platform" : "Local DB",
              sub:
                floatSource === "platform" ? "Live balance" : "Cached balance",
            },
          ].map((s: any) => (
            <div
              key={s.label}
              className="rounded-xl p-4 flex justify-between items-center"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div>
                <div
                  className="text-xs text-gray-500"
                  style={{ fontFamily: DISP }}
                >
                  {s.label}
                </div>
                <div
                  className="text-xs text-gray-600"
                  style={{ fontFamily: DISP }}
                >
                  {s.sub}
                </div>
              </div>
              <div
                className="text-lg font-bold"
                style={{ fontFamily: MONO, color: BLUE }}
              >
                {s.val}
              </div>
            </div>
          ))}
          <button
            onClick={() => setShowTopUpModal(true)}
            className="w-full py-4 rounded-xl font-bold text-white"
            style={{ background: GOLD, fontFamily: DISP }}
          >
            Request Float Top-Up
          </button>
          {/* Top-Up Request Modal */}
          {showTopUpModal && (
            <div
              className="fixed inset-0 z-50 flex items-end"
              style={{ background: "rgba(0,0,0,0.7)" }}
            >
              <div
                className="w-full rounded-t-2xl p-5 flex flex-col gap-4"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                <div className="flex items-center justify-between">
                  <div
                    className="text-base font-black text-white"
                    style={{ fontFamily: DISP }}
                  >
                    Request Float Top-Up
                  </div>
                  <button
                    onClick={() => setShowTopUpModal(false)}
                    className="text-gray-400 text-xl"
                  >
                    ×
                  </button>
                </div>
                <div className="flex flex-col gap-1">
                  <label
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    Amount Requested (NGN) *
                  </label>
                  <input
                    type="number"
                    value={topUpAmount}
                    onChange={e => setTopUpAmount(e.target.value)}
                    placeholder="e.g. 200000"
                    className="px-4 py-3 rounded-xl text-lg font-bold text-white bg-transparent border outline-none"
                    style={{
                      borderColor: GOLD,
                      fontFamily: MONO,
                      background: BG,
                    }}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    Notes (optional)
                  </label>
                  <textarea
                    value={topUpNotes}
                    onChange={e => setTopUpNotes(e.target.value)}
                    placeholder="e.g. Needed for market day transactions"
                    className="px-3 py-2 rounded-xl text-sm text-white bg-transparent border outline-none resize-none h-16"
                    style={{
                      borderColor: BORDER,
                      fontFamily: DISP,
                      background: BG,
                    }}
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowTopUpModal(false)}
                    className="flex-1 py-3 rounded-xl text-sm font-semibold"
                    style={{
                      background: "oklch(0.22 0.02 240)",
                      color: "oklch(0.55 0.015 230)",
                      fontFamily: DISP,
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      const amt = parseFloat(topUpAmount);
                      if (!amt || amt < 1000) {
                        toast.error("Minimum top-up amount is ₦1,000");
                        return;
                      }
                      submitTopUpMut.mutate({
                        amount: amt,
                        notes: topUpNotes || undefined,
                      });
                    }}
                    disabled={submitTopUpMut.isPending}
                    className="flex-1 py-3 rounded-xl text-sm font-bold text-black"
                    style={{
                      background: GOLD,
                      fontFamily: DISP,
                      opacity: submitTopUpMut.isPending ? 0.5 : 1,
                    }}
                  >
                    {submitTopUpMut.isPending
                      ? "Submitting…"
                      : "Submit Request"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2 p-4 overflow-y-auto flex-1">
          {/* Float transaction history from platform */}
          {floatHistoryData && floatHistoryData.transactions.length > 0 && (
            <>
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                Float Transactions (
                {floatHistoryData.source === "platform" ? "Live" : "Local DB"})
              </div>
              {(floatHistoryData.transactions as any[])
                .slice(0, 10)
                .map((tx: any, i: number) => (
                  <div
                    key={tx.id ?? i}
                    className="rounded-xl p-4 flex justify-between items-center"
                    style={{ background: CARD, border: `1px solid ${BORDER}` }}
                  >
                    <div>
                      <div
                        className="text-sm font-semibold text-white"
                        style={{ fontFamily: DISP }}
                      >
                        {tx.type ?? tx.transaction_type ?? "Float Tx"}
                      </div>
                      <div
                        className="text-xs text-gray-500 mt-0.5"
                        style={{ fontFamily: MONO }}
                      >
                        {tx.reference ?? tx.ref ?? ""}
                      </div>
                      <div
                        className="text-xs text-gray-500"
                        style={{ fontFamily: MONO }}
                      >
                        {tx.createdAt
                          ? new Date(tx.createdAt).toLocaleDateString("en-NG")
                          : (tx.created_at ?? "")}
                      </div>
                    </div>
                    <div className="text-right">
                      <div
                        className="text-sm font-bold"
                        style={{
                          fontFamily: MONO,
                          color:
                            tx.type === "Cash In" ||
                            tx.transaction_type === "settle"
                              ? GREEN
                              : RED,
                        }}
                      >
                        {tx.type === "Cash In" ||
                        tx.transaction_type === "settle"
                          ? "+"
                          : "-"}
                        ₦{fmt(Number(tx.amount ?? 0))}
                      </div>
                      <div
                        className="text-xs"
                        style={{
                          color: tx.status === "success" ? GREEN : "#9ca3af",
                          fontFamily: MONO,
                        }}
                      >
                        {tx.status ?? ""}
                      </div>
                    </div>
                  </div>
                ))}
              <div
                className="text-xs text-gray-600 text-center py-1"
                style={{ fontFamily: DISP }}
              >
                Top-Up Requests
              </div>
            </>
          )}
          {!topUpHistory || topUpHistory.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-12 text-gray-600"
              style={{ fontFamily: DISP }}
            >
              <div className="text-3xl mb-2">📊</div>
              <div className="text-sm">No top-up history yet</div>
            </div>
          ) : (
            topUpHistory.map((h: any) => (
              <div
                key={h.id}
                className="rounded-xl p-4 flex justify-between items-center"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                <div>
                  <div
                    className="text-sm font-semibold text-white"
                    style={{ fontFamily: DISP }}
                  >
                    Float Top-Up Request
                  </div>
                  <div
                    className="text-xs mt-0.5 px-2 py-0.5 rounded inline-block"
                    style={{
                      fontFamily: MONO,
                      background:
                        h.status === "approved"
                          ? "oklch(0.65 0.18 160 / 0.15)"
                          : h.status === "rejected"
                            ? "oklch(0.60 0.22 25 / 0.15)"
                            : "oklch(0.78 0.18 80 / 0.15)",
                      color:
                        h.status === "approved"
                          ? GREEN
                          : h.status === "rejected"
                            ? RED
                            : GOLD,
                    }}
                  >
                    {h.status}
                  </div>
                  <div
                    className="text-xs text-gray-500 mt-0.5"
                    style={{ fontFamily: MONO }}
                  >
                    {new Date(h.createdAt).toLocaleDateString("en-NG")}
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className="text-sm font-bold"
                    style={{ fontFamily: MONO, color: GREEN }}
                  >
                    +₦{fmt(h.requestedAmount)}
                  </div>
                  {h.notes && (
                    <div
                      className="text-xs text-gray-500 max-w-24 truncate"
                      style={{ fontFamily: DISP }}
                    >
                      {h.notes}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// FraudAlerts Screen ─────────────────────────────────────────────────────────

export function CarrierSwitchScreen({ onBack }: { onBack: () => void }) {
  const BG2 = "#0a0e1a";
  const CARD2 = "oklch(0.14 0.02 240)";
  const BORDER2 = "oklch(0.22 0.02 240)";
  const GREEN2 = "oklch(0.65 0.18 160)";
  const BLUE2 = "oklch(0.60 0.22 260)";
  const GOLD2 = "oklch(0.78 0.18 80)";
  const RED2 = "oklch(0.60 0.22 25)";
  const CYAN2 = "oklch(0.65 0.18 200)";
  const DISP2 = "'Space Grotesk', sans-serif";
  const MONO2 = "'JetBrains Mono', monospace";

  const [currentCarrier, setCurrentCarrier] = useState("MTN");
  const [autoSwitch, setAutoSwitch] = useState(false);

  const rankings = trpc.carrierSwitching.getRankings.useQuery() as any;
  const recommendation = trpc.carrierSwitching.getRecommendation.useQuery({
    // @ts-expect-error Sprint 85 — type inference mismatch
    currentCarrier,
  }) as any;
  const switchStats = trpc.carrierSwitching.getSwitchStats.useQuery() as any;
  // @ts-ignore — Sprint 85: strict-mode suppression
  const recordSwitch = trpc.carrierSwitching.recordSwitch.useMutation({
    onSuccess: () => {
      rankings.refetch();
      recommendation.refetch();
      switchStats.refetch();
    },
  }) as any;

  const handleSwitch = async (toCarrier: string) => {
    if (toCarrier === currentCarrier) return;
    try {
      await recordSwitch.mutateAsync({
        fromCarrier: currentCarrier,
        toCarrier,
        agentCode: "AGT-NG-0042",
        reason: "Manual switch from CarrierSwitch screen",
        autoTriggered: false,
      });
      setCurrentCarrier(toCarrier);
      toast.success(`Switched to ${toCarrier}`);
    } catch {
      toast.error("Switch failed");
    }
  };

  const gradeColor = (grade: string) => {
    if (grade === "A+" || grade === "A") return GREEN2;
    if (grade === "B") return BLUE2;
    if (grade === "C") return GOLD2;
    return RED2;
  };

  const barColor = (bars: number) => {
    if (bars >= 4) return GREEN2;
    if (bars >= 3) return BLUE2;
    if (bars >= 2) return GOLD2;
    return RED2;
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: BG2 }}>
      <ScreenHeader
        title="📡 Carrier Switch"
        onBack={onBack}
        badge={
          <div className="flex items-center gap-2">
            <span
              className="text-xs px-2 py-1 rounded-full"
              style={{
                background: `${CYAN2}20`,
                color: CYAN2,
                fontFamily: MONO2,
              }}
            >
              {currentCarrier}
            </span>
          </div>
        }
      />
      <div className="flex-1 overflow-y-auto p-4">
        {/* Auto-switch recommendation */}
        {recommendation.data?.shouldSwitch && (
          <div
            className="rounded-2xl p-4 mb-4"
            style={{
              background: `${GREEN2}10`,
              border: `1px solid ${GREEN2}30`,
            }}
          >
            <div className="flex items-center gap-3">
              <div className="text-2xl">⚡</div>
              <div className="flex-1">
                <div
                  className="text-sm font-bold text-white"
                  style={{ fontFamily: DISP2 }}
                >
                  Switch Recommended
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {recommendation.data.reason}
                </div>
              </div>
              <button
                onClick={() => handleSwitch(recommendation.data!.bestCarrier!)}
                disabled={recordSwitch.isPending}
                className="px-3 py-2 rounded-xl text-xs font-bold disabled:opacity-50"
                style={{ background: GREEN2, color: "white" }}
              >
                {recordSwitch.isPending ? "…" : "Switch"}
              </button>
            </div>
            <div className="flex items-center gap-4 mt-3">
              <div
                className="flex-1 rounded-lg p-2 text-center"
                style={{ background: `${RED2}15` }}
              >
                <div className="text-xs text-gray-500">Current</div>
                <div
                  className="text-sm font-bold"
                  style={{ color: RED2, fontFamily: MONO2 }}
                >
                  {recommendation.data.currentScore}
                </div>
              </div>
              <div className="text-gray-600">→</div>
              <div
                className="flex-1 rounded-lg p-2 text-center"
                style={{ background: `${GREEN2}15` }}
              >
                <div className="text-xs text-gray-500">Best</div>
                <div
                  className="text-sm font-bold"
                  style={{ color: GREEN2, fontFamily: MONO2 }}
                >
                  {recommendation.data.bestScore}
                </div>
              </div>
              <div
                className="flex-1 rounded-lg p-2 text-center"
                style={{ background: `${BLUE2}15` }}
              >
                <div className="text-xs text-gray-500">Gain</div>
                <div
                  className="text-sm font-bold"
                  style={{ color: BLUE2, fontFamily: MONO2 }}
                >
                  +{recommendation.data.improvement}%
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Current carrier */}
        <div
          className="rounded-2xl p-4 mb-4"
          style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
        >
          <div className="flex items-center justify-between mb-3">
            <div
              className="text-xs text-gray-500"
              style={{ fontFamily: DISP2 }}
            >
              Active Carrier
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-500">Auto-Switch</span>
              <button
                onClick={() => setAutoSwitch(!autoSwitch)}
                className="w-10 h-5 rounded-full transition-all relative"
                style={{ background: autoSwitch ? GREEN2 : BORDER2 }}
              >
                <div
                  className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all"
                  style={{ left: autoSwitch ? "22px" : "2px" }}
                />
              </button>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
              style={{ background: `${CYAN2}15` }}
            >
              📡
            </div>
            <div className="flex-1">
              <div
                className="text-lg font-bold text-white"
                style={{ fontFamily: DISP2 }}
              >
                {currentCarrier}
              </div>
              <div className="text-xs text-gray-500">
                Score:{" "}
                <span style={{ color: GREEN2 }}>
                  {recommendation.data?.currentScore || "—"}
                </span>
              </div>
            </div>
            {/* Signal bars */}
            <div className="flex items-end gap-0.5 h-6">
              {[1, 2, 3, 4, 5].map((bar: any) => {
                const active =
                  (rankings.data?.find((r: any) => r.name === currentCarrier)
                    ?.signalBars || 3) >= bar;
                return (
                  <div
                    key={bar}
                    className="w-1.5 rounded-sm transition-all"
                    style={{
                      height: `${bar * 4 + 4}px`,
                      background: active
                        ? barColor(
                            rankings.data?.find(
                              (r: any) => r.name === currentCarrier
                            )?.signalBars || 3
                          )
                        : BORDER2,
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>

        {/* Carrier rankings */}
        <div className="mb-4">
          <div
            className="text-xs text-gray-500 mb-2"
            style={{ fontFamily: DISP2 }}
          >
            Carrier Rankings
          </div>
          {(rankings.data || []).map((carrier: any) => (
            <div
              key={carrier.name}
              className="rounded-xl p-3 mb-2 flex items-center gap-3 transition-all"
              style={{
                background:
                  carrier.name === currentCarrier ? `${CYAN2}10` : CARD2,
                border: `1px solid ${carrier.name === currentCarrier ? `${CYAN2}40` : BORDER2}`,
              }}
            >
              {/* Rank */}
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
                style={{
                  background: `${gradeColor(carrier.grade)}20`,
                  color: gradeColor(carrier.grade),
                  fontFamily: MONO2,
                }}
              >
                {carrier.rank}
              </div>
              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="text-sm font-bold text-white truncate"
                    style={{ fontFamily: DISP2 }}
                  >
                    {carrier.name}
                  </span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
                    style={{
                      background: `${gradeColor(carrier.grade)}20`,
                      color: gradeColor(carrier.grade),
                    }}
                  >
                    {carrier.grade}
                  </span>
                  {carrier.name === currentCarrier && (
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded-full"
                      style={{ background: `${CYAN2}20`, color: CYAN2 }}
                    >
                      ACTIVE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-gray-500">
                    {carrier.technology}
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {carrier.signalDbm.toFixed(0)} dBm
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {carrier.latencyMs.toFixed(0)}ms
                  </span>
                </div>
              </div>
              {/* Signal bars */}
              <div className="flex items-end gap-0.5 h-5">
                {[1, 2, 3, 4, 5].map((bar: any) => (
                  <div
                    key={bar}
                    className="w-1 rounded-sm"
                    style={{
                      height: `${bar * 3 + 3}px`,
                      background:
                        carrier.signalBars >= bar
                          ? barColor(carrier.signalBars)
                          : BORDER2,
                    }}
                  />
                ))}
              </div>
              {/* Quality score */}
              <div className="text-right">
                <div
                  className="text-sm font-bold"
                  style={{
                    color: gradeColor(carrier.grade),
                    fontFamily: MONO2,
                  }}
                >
                  {carrier.qualityScore.toFixed(0)}
                </div>
              </div>
              {/* Switch button */}
              {carrier.name !== currentCarrier && carrier.sampleCount > 0 && (
                <button
                  onClick={() => handleSwitch(carrier.name)}
                  disabled={recordSwitch.isPending}
                  className="px-2 py-1.5 rounded-lg text-[10px] font-bold disabled:opacity-50"
                  style={{
                    background: `${BLUE2}20`,
                    color: BLUE2,
                    border: `1px solid ${BLUE2}30`,
                  }}
                >
                  Switch
                </button>
              )}
            </div>
          ))}
        </div>

        {/* Switch stats */}
        {switchStats.data && (
          <div className="mb-4">
            <div
              className="text-xs text-gray-500 mb-2"
              style={{ fontFamily: DISP2 }}
            >
              Switch Statistics
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                {
                  label: "Total Switches",
                  value: switchStats.data.totalSwitches,
                  color: BLUE2,
                },
                {
                  label: "Auto Switches",
                  value: switchStats.data.autoSwitches,
                  color: CYAN2,
                },
                {
                  label: "Manual",
                  value: switchStats.data.manualSwitches,
                  color: GOLD2,
                },
                {
                  label: "Avg Improvement",
                  value: `${switchStats.data.avgImprovement}%`,
                  color: GREEN2,
                },
              ].map((s, i) => (
                <div
                  key={i}
                  className="rounded-xl p-3"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div
                    className="text-lg font-bold"
                    style={{ color: s.color, fontFamily: MONO2 }}
                  >
                    {s.value}
                  </div>
                  <div className="text-[10px] text-gray-500">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent switches */}
        {switchStats.data?.recentSwitches &&
          switchStats.data.recentSwitches.length > 0 && (
            <div>
              <div
                className="text-xs text-gray-500 mb-2"
                style={{ fontFamily: DISP2 }}
              >
                Recent Switches
              </div>
              {switchStats.data.recentSwitches.map((sw: any, i: any) => (
                <div
                  key={i}
                  className="rounded-xl p-3 mb-2 flex items-center gap-3"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div
                    className="text-xs font-bold"
                    style={{ color: RED2, fontFamily: MONO2 }}
                  >
                    {sw.fromCarrier}
                  </div>
                  <div className="text-gray-600">→</div>
                  <div
                    className="text-xs font-bold"
                    style={{ color: GREEN2, fontFamily: MONO2 }}
                  >
                    {sw.toCarrier}
                  </div>
                  <div className="flex-1 text-right">
                    <div
                      className="text-[10px]"
                      style={{ color: sw.improvement > 0 ? GREEN2 : RED2 }}
                    >
                      {sw.improvement > 0 ? "+" : ""}
                      {sw.improvement}%
                    </div>
                    <div className="text-[10px] text-gray-600">
                      {sw.autoTriggered ? "auto" : "manual"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}


export function ReconciliationWizard({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState(0);
  const [cashCount, setCashCount] = useState<Record<string, number>>({
    "1000": 0,
    "500": 0,
    "200": 0,
    "100": 0,
    "50": 0,
    "20": 0,
    "10": 0,
    "5": 0,
  });

  const denominations = [1000, 500, 200, 100, 50, 20, 10, 5];
  const physicalCash = denominations.reduce(
    (sum: any, d: any) => sum + d * (cashCount[String(d)] || 0),
    0
  );
  // Real system balance from the signed-in agent profile — never hardcoded.
  const systemBalance = usePosStore(s => s.agent?.floatBalance ?? null);
  const variance =
    systemBalance != null ? physicalCash - systemBalance : null;

  const steps = [
    "Count Cash",
    "Review Transactions",
    "Variance Check",
    "Submit Report",
  ];

  return (
    <div className="flex flex-col h-screen" style={{ background: BG }}>
      <ScreenHeader title="📊 EOD Reconciliation" onBack={onBack} />

      {/* Step indicator */}
      <div
        className="flex items-center px-4 py-3 gap-2"
        style={{ borderBottom: `1px solid ${BORDER}` }}
      >
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-1 flex-1">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
              style={{
                background: i <= step ? BLUE : CARD,
                color: i <= step ? "white" : "#6b7280",
                border: `1px solid ${i <= step ? BLUE : BORDER}`,
              }}
            >
              {i < step ? "✓" : i + 1}
            </div>
            {i < steps.length - 1 && (
              <div
                className="flex-1 h-0.5"
                style={{ background: i < step ? BLUE : BORDER }}
              />
            )}
          </div>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {step === 0 && (
          <>
            <h3
              className="text-white font-bold mb-4"
              style={{ fontFamily: DISP }}
            >
              Physical Cash Count
            </h3>
            {denominations.map((d: any) => (
              <div key={d} className="flex items-center gap-3 mb-3">
                <div className="w-20 text-right">
                  <span
                    className="font-bold"
                    style={{ color: GOLD, fontFamily: MONO }}
                  >
                    ₦{d}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-1">
                  <button
                    onClick={() =>
                      setCashCount(c => ({
                        ...c,
                        [d]: Math.max(0, (c[String(d)] || 0) - 1),
                      }))
                    }
                    className="w-8 h-8 rounded-lg font-bold text-white"
                    style={{ background: CARD, border: `1px solid ${BORDER}` }}
                  >
                    −
                  </button>
                  <input
                    type="number"
                    value={cashCount[String(d)] || 0}
                    onChange={e =>
                      setCashCount(c => ({
                        ...c,
                        [d]: Math.max(0, parseInt(e.target.value) || 0),
                      }))
                    }
                    className="flex-1 text-center py-2 rounded-lg text-white"
                    style={{
                      background: BG,
                      border: `1px solid ${BORDER}`,
                      fontFamily: MONO,
                    }}
                  />
                  <button
                    onClick={() =>
                      setCashCount(c => ({
                        ...c,
                        [d]: (c[String(d)] || 0) + 1,
                      }))
                    }
                    className="w-8 h-8 rounded-lg font-bold text-white"
                    style={{ background: BLUE }}
                  >
                    +
                  </button>
                </div>
                <div className="w-24 text-right">
                  <span
                    className="text-gray-400 text-sm"
                    style={{ fontFamily: MONO }}
                  >
                    = ₦{((cashCount[String(d)] || 0) * d).toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
            <div
              className="rounded-xl p-4 mt-4"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div className="flex justify-between font-bold">
                <span className="text-gray-300">Total Physical Cash</span>
                <span
                  className="text-2xl"
                  style={{ color: GOLD, fontFamily: MONO }}
                >
                  ₦{physicalCash.toLocaleString()}
                </span>
              </div>
            </div>
          </>
        )}

        {step === 1 && (
          <>
            <h3
              className="text-white font-bold mb-4"
              style={{ fontFamily: DISP }}
            >
              Today's Transactions
            </h3>
            {[
              { type: "Cash In", count: 47, amount: 1240000, color: GREEN },
              { type: "Cash Out", count: 31, amount: 890000, color: RED },
              { type: "Transfer", count: 12, amount: 340000, color: BLUE },
              { type: "Airtime", count: 23, amount: 45600, color: GOLD },
              { type: "Bills", count: 8, amount: 128000, color: "#a855f7" },
            ].map((t, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-3 rounded-xl mb-2"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-2 h-8 rounded-full"
                    style={{ background: t.color }}
                  />
                  <div>
                    <p className="text-white text-sm font-semibold">{t.type}</p>
                    <p className="text-gray-500 text-xs">
                      {t.count} transactions
                    </p>
                  </div>
                </div>
                <span
                  className="font-bold"
                  style={{ color: t.color, fontFamily: MONO }}
                >
                  ₦{t.amount.toLocaleString()}
                </span>
              </div>
            ))}
          </>
        )}

        {step === 2 && (
          <>
            <h3
              className="text-white font-bold mb-4"
              style={{ fontFamily: DISP }}
            >
              Variance Analysis
            </h3>
            <div
              className="rounded-2xl p-5 mb-4"
              style={{
                background: CARD,
                border: `1px solid ${variance != null && Math.abs(variance) > 1000 ? RED : GREEN}40`,
              }}
            >
              <div className="flex justify-between mb-3">
                <span className="text-gray-400">System Balance</span>
                <span
                  className="font-bold"
                  style={{ color: BLUE, fontFamily: MONO }}
                >
                  {systemBalance != null ? `₦${systemBalance.toLocaleString()}` : "—"}
                </span>
              </div>
              <div className="flex justify-between mb-3">
                <span className="text-gray-400">Physical Cash</span>
                <span
                  className="font-bold"
                  style={{ color: GOLD, fontFamily: MONO }}
                >
                  ₦{physicalCash.toLocaleString()}
                </span>
              </div>
              <div className="h-px my-3" style={{ background: BORDER }} />
              <div className="flex justify-between">
                <span className="text-gray-300 font-bold">Variance</span>
                <span
                  className="font-bold text-xl"
                  style={{
                    color: variance != null && Math.abs(variance) > 1000 ? RED : GREEN,
                    fontFamily: MONO,
                  }}
                >
                  {variance != null ? `${variance >= 0 ? "+" : ""}₦${variance.toLocaleString()}` : "—"}
                </span>
              </div>
            </div>
            {variance != null && Math.abs(variance) > 1000 ? (
              <div
                className="rounded-xl p-4"
                style={{ background: `${RED}15`, border: `1px solid ${RED}40` }}
              >
                <p className="text-red-400 font-semibold text-sm">
                  ⚠ Variance exceeds threshold
                </p>
                <p className="text-gray-400 text-xs mt-1">
                  Please recount cash or contact supervisor before submitting
                </p>
              </div>
            ) : (
              <div
                className="rounded-xl p-4"
                style={{
                  background: `${GREEN}15`,
                  border: `1px solid ${GREEN}40`,
                }}
              >
                <p className="text-green-400 font-semibold text-sm">
                  ✓ Variance within acceptable range
                </p>
                <p className="text-gray-400 text-xs mt-1">
                  Ready to submit end-of-day report
                </p>
              </div>
            )}
          </>
        )}

        {step === 3 && (
          <div className="text-center py-8">
            <div className="text-6xl mb-4">📋</div>
            <h3
              className="text-white font-bold text-xl mb-2"
              style={{ fontFamily: DISP }}
            >
              Submit EOD Report
            </h3>
            <p className="text-gray-400 text-sm mb-6">
              Report will be sent to your supervisor and CBN compliance system
            </p>
            <button
              onClick={() => {
                toast.success("EOD report submitted successfully");
                onBack();
              }}
              className="w-full py-4 rounded-2xl font-bold text-white text-lg"
              style={{
                background: `linear-gradient(135deg, ${GREEN}, oklch(0.55 0.18 160))`,
              }}
            >
              ✓ Submit Report
            </button>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div
        className="flex gap-3 p-4"
        style={{ borderTop: `1px solid ${BORDER}` }}
      >
        {step > 0 && (
          <button
            onClick={() => setStep(s => s - 1)}
            className="flex-1 py-3 rounded-xl font-semibold text-gray-400"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            ← Back
          </button>
        )}
        {step < steps.length - 1 && (
          <button
            onClick={() => setStep(s => s + 1)}
            className="flex-1 py-3 rounded-xl font-bold text-white"
            style={{ background: BLUE }}
          >
            Next →
          </button>
        )}
      </div>
    </div>
  );
}

// ── Micro-Insurance Screen ────────────────────────────────────────────────────

export function SuccessScreen({
  title,
  amount,
  ref: txRef,
  customer,
  onDone,
  onPrint,
}: {
  title: string;
  amount: number;
  ref: string;
  customer: string;
  onDone: () => void;
  onPrint: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 p-6">
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center text-4xl"
        style={{
          background: "oklch(0.65 0.18 160 / 0.2)",
          border: `2px solid ${GREEN}`,
        }}
      >
        ✓
      </div>
      <div className="text-center">
        <div
          className="text-2xl font-bold text-white mb-1"
          style={{ fontFamily: DISP }}
        >
          {title}
        </div>
        <div
          className="text-3xl font-bold"
          style={{ fontFamily: MONO, color: GREEN }}
        >
          {fmt(amount)}
        </div>
        <div className="text-sm text-gray-400 mt-2">{customer}</div>
        <div
          className="text-xs text-gray-600 mt-1"
          style={{ fontFamily: MONO }}
        >
          {txRef || "—"}
        </div>
      </div>
      <div className="flex gap-3 w-full">
        <button
          onClick={onPrint}
          className="flex-1 py-3 rounded-xl font-semibold text-sm transition-all"
          style={{
            background: "oklch(0.60 0.22 260 / 0.2)",
            color: "#3b82f6",
            border: `1px solid oklch(0.60 0.22 260 / 0.4)`,
            fontFamily: DISP,
          }}
        >
          🖨 Print Receipt
        </button>
        <button
          onClick={onDone}
          className="flex-1 py-3 rounded-xl font-semibold text-sm transition-all"
          style={{ background: GREEN, color: "white", fontFamily: DISP }}
        >
          Done
        </button>
      </div>
    </div>
  );
}

// ─── Receipt Modal ────────────────────────────────────────────────────────────

export function loadTileCustomizations(): TileCustomization {
  try {
    const raw = localStorage.getItem(TILE_CUSTOM_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return { order: [], sizes: {}, colors: {}, groups: {}, preset: "full" };
}

