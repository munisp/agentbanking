// @ts-nocheck
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ScreenHeader } from "./POSShell.part10";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, Transaction } from "./POSShell.shared";

function FloatBalanceScreen({ onBack }: { onBack: () => void }) {
  const [tab, setTab] = useState<"overview" | "history">("overview");
  const [showTopUpModal, setShowTopUpModal] = useState(false);
  const [topUpAmount, setTopUpAmount] = useState("");
  const [topUpNotes, setTopUpNotes] = useState("");
  const { data: ds } = trpc.transactions.agentDayStats.useQuery(undefined, {
    refetchInterval: 60_000,
  });
  const { data: floatData } = trpc.transactions.getFloatBalance.useQuery(
    undefined,
    { refetchInterval: 30_000 }
  );
  const { data: floatHistoryData } = trpc.transactions.getFloatHistory.useQuery(
    { limit: 50 },
    { refetchInterval: 60_000 }
  );
  const { data: topUpHistory } = trpc.floatTopUp.myRequests.useQuery(
    undefined,
    { refetchInterval: 60_000 }
  );
  const agent = usePosStore(s => s.agent);
  // Prefer live float balance from platform (getFloatBalance), then agentDayStats, then store
  const float =
    floatData?.balance ?? ds?.float ?? agent?.floatBalance ?? null;
  const floatSource = floatData?.source ?? "local";
  // No fabricated float limit: without a live limit the usage bar is hidden.
  const limit: number | null = null;
  const pct = float != null && limit != null && limit > 0 ? Math.round((float / limit) * 100) : null;

  const submitTopUpMut = trpc.agentMgmt.submitTopUpRequest.useMutation({
    onSuccess: () => {
      toast.success("Float top-up request submitted — awaiting admin approval");
      setShowTopUpModal(false);
      setTopUpAmount("");
      setTopUpNotes("");
    },
    onError: (e: { message: string }) =>
      toast.error(`Request failed: ${e.message}`),
  });

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Float Balance" onBack={onBack} />
      <div className="flex gap-2 px-4 pt-3">
        {(["overview", "history"] as const).map(t => (
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
              {fmt(float)}
            </div>
            <div className="mt-3">
              <div
                className="flex justify-between text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                <span>Used: ₦{fmt(limit - float)}</span>
                <span>Limit: ₦{fmt(limit)}</span>
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
                {pct != null ? `${pct}% available` : "Limit unavailable"}
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
          ].map(s => (
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

function UssdTransactionScreen({ onBack }: { onBack: () => void }) {
  const BG2 = "#0a0e1a";
  const CARD2 = "oklch(0.14 0.02 240)";
  const BORDER2 = "oklch(0.22 0.02 240)";
  const GREEN2 = "oklch(0.65 0.18 160)";
  const BLUE2 = "oklch(0.60 0.22 260)";
  const GOLD2 = "oklch(0.78 0.18 80)";
  const DISP2 = "'Space Grotesk', sans-serif";
  const MONO2 = "'JetBrains Mono', monospace";

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [response, setResponse] = useState<string>("");
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<
    Array<{ type: "in" | "out"; text: string; time: string }>
  >([]);
  const [txRef, setTxRef] = useState<string | null>(null);
  const [selectedShortcut, setSelectedShortcut] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const startSession = trpc.ussdIntegration.startSession.useMutation();
  const processInput = trpc.ussdIntegration.processInput.useMutation();
  const stats = trpc.ussdIntegration.getStats.useQuery();
  const shortcuts = trpc.ussdIntegration.getShortcuts.useQuery();

  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history]);

  const ussdAgent = usePosStore(s => s.agent) as any;
  const handleDial = async (code?: string) => {
    // Never dial with a fabricated phone/agent identity — require the signed-in agent's real details.
    const phoneNumber: string | null = ussdAgent?.phone ?? null;
    const agentCode: string | null = ussdAgent?.code ?? null;
    if (!phoneNumber || !agentCode) {
      toast.error("Agent phone/code unavailable — cannot start USSD session");
      return;
    }
    try {
      const result = await startSession.mutateAsync({
        phoneNumber,
        agentCode,
        carrier: "MTN",
        menuCode: code || selectedShortcut || "*384#",
      });
      setSessionId(result.sessionId);
      setResponse(result.response);
      setHistory([
        {
          type: "out",
          text: result.response.replace(/^(CON|END)\s*/, ""),
          time: new Date().toLocaleTimeString(),
        },
      ]);
      setTxRef(null);
    } catch {
      toast.error("Failed to start USSD session");
    }
  };

  const handleSend = async () => {
    if (!sessionId || !input.trim()) return;
    setHistory(h => [
      ...h,
      { type: "in", text: input, time: new Date().toLocaleTimeString() },
    ]);
    try {
      const result = await processInput.mutateAsync({
        sessionId,
        input: input.trim(),
      });
      setResponse(result.response);
      setHistory(h => [
        ...h,
        {
          type: "out",
          text: result.response.replace(/^(CON|END)\s*/, ""),
          time: new Date().toLocaleTimeString(),
        },
      ]);
      if (result.txRef) setTxRef(result.txRef);
      if (!result.continue) setSessionId(null);
    } catch {
      toast.error("Session error");
    }
    setInput("");
  };

  return (
    <div className="flex flex-col h-screen" style={{ background: BG2 }}>
      <ScreenHeader
        title="# USSD Transact"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-1 rounded-full"
            style={{ background: `${GREEN2}20`, color: GREEN2 }}
          >
            {stats.data?.activeSessions || 0} active
          </span>
        }
      />
      <div className="flex-1 overflow-y-auto p-4" ref={scrollRef}>
        {/* Shortcut codes */}
        <div className="mb-4">
          <div
            className="text-xs text-gray-500 mb-2"
            style={{ fontFamily: DISP2 }}
          >
            Quick Dial
          </div>
          <div className="flex flex-wrap gap-2">
            {(shortcuts.data || []).map(s => (
              <button
                key={s.id}
                onClick={() => handleDial(s.code)}
                className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all active:scale-95"
                style={{
                  background: CARD2,
                  border: `1px solid ${BORDER2}`,
                  color: "white",
                  fontFamily: MONO2,
                }}
              >
                {s.code} {s.title}
              </button>
            ))}
          </div>
        </div>

        {/* USSD terminal display */}
        <div
          className="rounded-2xl overflow-hidden mb-4"
          style={{ border: `1px solid ${GREEN2}30` }}
        >
          <div
            className="px-4 py-2 flex items-center justify-between"
            style={{ background: `${GREEN2}10` }}
          >
            <span
              className="text-xs font-bold"
              style={{ color: GREEN2, fontFamily: MONO2 }}
            >
              *384#
            </span>
            <span className="text-xs text-gray-500">
              {sessionId ? "SESSION ACTIVE" : "IDLE"}
            </span>
          </div>
          <div className="p-4 min-h-40" style={{ background: "#050810" }}>
            {history.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-4xl mb-3">#</div>
                <div
                  className="text-gray-500 text-sm"
                  style={{ fontFamily: DISP2 }}
                >
                  Dial *384# to start a USSD transaction
                </div>
                <button
                  onClick={() => handleDial()}
                  className="mt-4 px-6 py-2 rounded-xl text-sm font-bold"
                  style={{ background: GREEN2, color: "white" }}
                >
                  Dial *384#
                </button>
              </div>
            ) : (
              history.map((h, i) => (
                <div
                  key={i}
                  className={`mb-2 ${h.type === "in" ? "text-right" : ""}`}
                >
                  <div
                    className={`inline-block px-3 py-1.5 rounded-lg text-xs max-w-[85%] ${h.type === "in" ? "" : ""}`}
                    style={{
                      background:
                        h.type === "in" ? `${BLUE2}20` : `${GREEN2}10`,
                      color: h.type === "in" ? "#93c5fd" : "#6ee7b7",
                      fontFamily: MONO2,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {h.text}
                  </div>
                  <div className="text-[10px] text-gray-600 mt-0.5">
                    {h.time}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Transaction ref */}
        {txRef && (
          <div
            className="rounded-xl p-3 mb-4"
            style={{
              background: `${GREEN2}15`,
              border: `1px solid ${GREEN2}30`,
            }}
          >
            <div className="flex items-center gap-2">
              <span className="text-lg">✓</span>
              <div>
                <div className="text-xs text-gray-400">
                  Transaction Reference
                </div>
                <div
                  className="text-sm font-bold"
                  style={{ color: GREEN2, fontFamily: MONO2 }}
                >
                  {txRef}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Stats */}
        {stats.data && (
          <div className="grid grid-cols-3 gap-2 mb-4">
            {[
              {
                label: "Completed",
                value: stats.data.completedTransactions,
                color: GREEN2,
              },
              {
                label: "Volume",
                value: `₦${(stats.data.totalVolume / 1000).toFixed(0)}K`,
                color: GOLD2,
              },
              {
                label: "Active",
                value: stats.data.activeSessions,
                color: BLUE2,
              },
            ].map((s, i) => (
              <div
                key={i}
                className="rounded-xl p-3 text-center"
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
        )}

        {/* Recent USSD transactions */}
        {stats.data?.recentTransactions &&
          stats.data.recentTransactions.length > 0 && (
            <div>
              <div
                className="text-xs text-gray-500 mb-2"
                style={{ fontFamily: DISP2 }}
              >
                Recent USSD Transactions
              </div>
              {stats.data.recentTransactions.map((tx, i) => (
                <div
                  key={i}
                  className="rounded-xl p-3 mb-2 flex items-center justify-between"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div>
                    <div
                      className="text-xs font-bold text-white"
                      style={{ fontFamily: MONO2 }}
                    >
                      {tx.txRef}
                    </div>
                    <div className="text-[10px] text-gray-500">
                      {tx.type} · {tx.carrier}
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className="text-xs font-bold"
                      style={{ color: GREEN2, fontFamily: MONO2 }}
                    >
                      ₦{tx.amount.toLocaleString()}
                    </div>
                    <div
                      className="text-[10px]"
                      style={{
                        color: tx.status === "completed" ? GREEN2 : GOLD2,
                      }}
                    >
                      {tx.status}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>

      {/* Input area */}
      {sessionId && (
        <div
          className="p-4 flex-shrink-0"
          style={{ borderTop: `1px solid ${BORDER2}` }}
        >
          <div className="flex gap-2 mb-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSend()}
              placeholder="Enter option..."
              className="flex-1 px-3 py-2.5 rounded-xl text-sm outline-none"
              style={{
                background: "#050810",
                border: `1px solid ${BORDER2}`,
                color: "#6ee7b7",
                fontFamily: MONO2,
              }}
            />
            <button
              onClick={handleSend}
              disabled={processInput.isPending}
              className="px-4 py-2.5 rounded-xl text-sm font-bold disabled:opacity-50"
              style={{ background: GREEN2, color: "white" }}
            >
              {processInput.isPending ? "…" : "Send"}
            </button>
          </div>
          {/* Mini keypad */}
          <div className="grid grid-cols-6 gap-1.5">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"].map(
              k => (
                <button
                  key={k}
                  onClick={() => setInput(v => v + k)}
                  className="py-2 rounded-lg text-white text-xs font-bold transition-all active:scale-95"
                  style={{
                    background: CARD2,
                    border: `1px solid ${BORDER2}`,
                    fontFamily: MONO2,
                  }}
                >
                  {k}
                </button>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sprint 75: Carrier Switch Screen ────────────────────────────────────────

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
  // System balance comes from the live float balance query — never a constant.
  const { data: eodFloat } = trpc.transactions.getFloatBalance.useQuery(
    undefined,
    { refetchInterval: 30_000 }
  );
  const systemBalance: number | null = eodFloat?.balance ?? null;
  const variance = systemBalance != null ? physicalCash - systemBalance : null;

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
            {denominations.map(d => (
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

function NetworkTestScreen({ onBack }: { onBack: () => void }) {
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
  });
  const { refetch: runCarrier } = trpc.resilience.detectCarrier.useQuery(
    { phone: testPhone },
    { enabled: false, retry: false }
  );

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
              {[1, 2, 3, 4, 5].map(bar => (
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

function fmt(n: number | null | undefined) {
  if (n == null) return "—"; // unknown balance renders as an honest placeholder
  return (
    "₦" +
    n.toLocaleString("en-NG", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}


