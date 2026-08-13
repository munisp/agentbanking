// @ts-nocheck
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useState } from "react";
import { toast } from "sonner";
import { BG, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TerminalInfo, Transaction } from "./POSShell.shared";

function DisputeScreen({ onBack }: { onBack: () => void }) {
  const agent = usePosStore(s => s.agent);
  const [view, setView] = useState<
    "list" | "raise" | "thread" | "refund" | "refund-list"
  >("list");
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [txRef, setTxRef] = useState("");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [replyText, setReplyText] = useState("");
  const [refundTxRef, setRefundTxRef] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundCategory, setRefundCategory] = useState("failed_transaction");
  const [custName, setCustName] = useState("");
  const [custPhone, setCustPhone] = useState("");
  const [activeTab, setActiveTab] = useState<"disputes" | "refunds">(
    "disputes"
  );
  const BG2 = "#0a0e1a";
  const CARD2 = "oklch(0.14 0.02 240)";
  const BORDER2 = "oklch(0.22 0.02 240)";
  const GREEN2 = "oklch(0.65 0.18 160)";
  const RED2 = "oklch(0.60 0.22 25)";
  const GOLD2 = "oklch(0.78 0.18 80)";
  const BLUE2 = "oklch(0.60 0.22 260)";
  const PURPLE2 = "oklch(0.55 0.22 300)";
  const AMBER2 = "oklch(0.75 0.16 70)";
  const DISP2 = "'Space Grotesk', sans-serif";
  const MONO2 = "'JetBrains Mono', monospace";
  const statusColor: Record<string, string> = {
    raised: GOLD2,
    reviewing: BLUE2,
    resolved: GREEN2,
    rejected: RED2,
    open: GOLD2,
    pending: AMBER2,
    approved: BLUE2,
    processed: GREEN2,
  };

  const {
    data: myDisputesData,
    isLoading,
    refetch,
  } = trpc.disputes.myDisputes.useQuery({});
  const myDisputes = myDisputesData?.disputes ?? [];
  const { data: detail, refetch: refetchDetail } =
    trpc.disputes.getDispute.useQuery(
      { ref: selectedRef! },
      { enabled: selectedRef !== null && view === "thread" }
    );
  const {
    data: refundsData,
    isLoading: refundsLoading,
    refetch: refetchRefunds,
  } = trpc.disputeRefund.listRefunds.useQuery({ limit: 50 });
  const myRefunds = refundsData?.refunds ?? [];
  const { data: statsData } = trpc.disputeRefund.stats.useQuery({});

  const raise = trpc.disputes.raise.useMutation({
    onSuccess: res => {
      toast.success("Dispute raised: " + res.disputeRef);
      setTxRef("");
      setReason("");
      setEvidence("");
      setView("list");
      refetch();
    },
    onError: (e: any) => toast.error(e.message),
  });
  const addMessage = trpc.disputes.addMessage.useMutation({
    onSuccess: () => {
      setReplyText("");
      refetchDetail();
    },
    onError: (e: any) => toast.error(e.message),
  });
  const requestRefund = trpc.disputeRefund.requestRefund.useMutation({
    onSuccess: res => {
      toast.success("Refund requested: " + res.refundRef);
      setRefundTxRef("");
      setRefundReason("");
      setRefundAmount("");
      setCustName("");
      setCustPhone("");
      setView("list");
      setActiveTab("refunds");
      refetchRefunds();
    },
    onError: (e: any) => toast.error(e.message),
  });

  const refundStatusIcon: Record<string, string> = {
    pending: "⏳",
    approved: "✅",
    processed: "💰",
    rejected: "❌",
  };

  return (
    <div className="flex flex-col h-full" style={{ background: BG2 }}>
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-b"
        style={{ background: CARD2, borderColor: BORDER2 }}
      >
        <button
          onClick={
            view === "list" || view === "refund-list"
              ? onBack
              : () => setView(activeTab === "refunds" ? "refund-list" : "list")
          }
          className="w-8 h-8 rounded-full flex items-center justify-center"
          style={{ background: "oklch(0.22 0.02 240)", color: "white" }}
        >
          ←
        </button>
        <div className="flex-1">
          <div
            className="text-sm font-black text-white"
            style={{ fontFamily: DISP2 }}
          >
            Disputes & Refunds
          </div>
          <div className="text-xs text-gray-500" style={{ fontFamily: MONO2 }}>
            {view === "list"
              ? `${myDisputes.length} dispute(s)`
              : view === "raise"
                ? "Raise New Dispute"
                : view === "refund"
                  ? "Request Refund"
                  : view === "refund-list"
                    ? `${myRefunds.length} refund(s)`
                    : `Thread: ${selectedRef}`}
          </div>
        </div>
        {(view === "list" || view === "refund-list") && (
          <div className="flex gap-1.5">
            <button
              onClick={() => setView("raise")}
              className="px-2.5 py-1.5 rounded-xl text-xs font-bold text-white"
              style={{ background: BLUE2, fontFamily: DISP2 }}
            >
              + Dispute
            </button>
            <button
              onClick={() => setView("refund")}
              className="px-2.5 py-1.5 rounded-xl text-xs font-bold text-white"
              style={{ background: PURPLE2, fontFamily: DISP2 }}
            >
              + Refund
            </button>
          </div>
        )}
      </div>
      {/* Tab switcher */}
      {(view === "list" || view === "refund-list") && (
        <div className="flex border-b" style={{ borderColor: BORDER2 }}>
          <button
            onClick={() => {
              setActiveTab("disputes");
              setView("list");
            }}
            className="flex-1 py-2.5 text-xs font-bold text-center transition-all"
            style={{
              fontFamily: DISP2,
              color: activeTab === "disputes" ? BLUE2 : "#666",
              borderBottom:
                activeTab === "disputes"
                  ? `2px solid ${BLUE2}`
                  : "2px solid transparent",
            }}
          >
            ⚖ Disputes{" "}
            {statsData?.disputes?.open ? `(${statsData.disputes.open})` : ""}
          </button>
          <button
            onClick={() => {
              setActiveTab("refunds");
              setView("refund-list");
            }}
            className="flex-1 py-2.5 text-xs font-bold text-center transition-all"
            style={{
              fontFamily: DISP2,
              color: activeTab === "refunds" ? PURPLE2 : "#666",
              borderBottom:
                activeTab === "refunds"
                  ? `2px solid ${PURPLE2}`
                  : "2px solid transparent",
            }}
          >
            💰 Refunds{" "}
            {statsData?.refunds?.pending
              ? `(${statsData.refunds.pending})`
              : ""}
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-4">
        {/* ── Disputes List ── */}
        {view === "list" && (
          <div className="flex flex-col gap-3">
            {isLoading ? (
              <div
                className="text-center py-12 text-gray-500"
                style={{ fontFamily: DISP2 }}
              >
                Loading...
              </div>
            ) : myDisputes.length === 0 ? (
              <div className="text-center py-12" style={{ fontFamily: DISP2 }}>
                <div className="text-4xl mb-3">⚖️</div>
                <div className="text-sm text-gray-500">
                  No disputes raised yet.
                </div>
                <div className="text-xs text-gray-600 mt-1">
                  Tap + Dispute to report a transaction issue.
                </div>
              </div>
            ) : (
              myDisputes.map((d: any) => (
                <button
                  key={d.id}
                  onClick={() => {
                    setSelectedRef(d.ref);
                    setView("thread");
                  }}
                  className="w-full text-left rounded-2xl p-4 transition-all"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="text-xs font-mono"
                      style={{ color: BLUE2 }}
                    >
                      {d.ref}
                    </span>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-bold"
                      style={{
                        background: `${statusColor[d.status] ?? GOLD2}20`,
                        color: statusColor[d.status] ?? GOLD2,
                        fontFamily: DISP2,
                      }}
                    >
                      {d.status}
                    </span>
                  </div>
                  <div
                    className="text-sm font-semibold text-white mb-1"
                    style={{ fontFamily: DISP2 }}
                  >
                    {d.reason}
                  </div>
                  <div
                    className="text-xs text-gray-500"
                    style={{ fontFamily: MONO2 }}
                  >
                    Tx: {d.transactionRef}
                  </div>
                  <div
                    className="text-xs text-gray-600 mt-1"
                    style={{ fontFamily: MONO2 }}
                  >
                    {new Date(d.createdAt).toLocaleString("en-NG")}
                  </div>
                </button>
              ))
            )}
          </div>
        )}
        {/* ── Refunds List ── */}
        {view === "refund-list" && (
          <div className="flex flex-col gap-3">
            {/* Summary cards */}
            <div className="grid grid-cols-3 gap-2 mb-2">
              <div
                className="rounded-xl p-3 text-center"
                style={{
                  background: `${AMBER2}15`,
                  border: `1px solid ${AMBER2}30`,
                }}
              >
                <div
                  className="text-lg font-black"
                  style={{ color: AMBER2, fontFamily: DISP2 }}
                >
                  {statsData?.refunds?.pending ?? 0}
                </div>
                <div
                  className="text-[10px] text-gray-500"
                  style={{ fontFamily: DISP2 }}
                >
                  Pending
                </div>
              </div>
              <div
                className="rounded-xl p-3 text-center"
                style={{
                  background: `${GREEN2}15`,
                  border: `1px solid ${GREEN2}30`,
                }}
              >
                <div
                  className="text-lg font-black"
                  style={{ color: GREEN2, fontFamily: DISP2 }}
                >
                  {statsData?.refunds?.processed ?? 0}
                </div>
                <div
                  className="text-[10px] text-gray-500"
                  style={{ fontFamily: DISP2 }}
                >
                  Processed
                </div>
              </div>
              <div
                className="rounded-xl p-3 text-center"
                style={{
                  background: `${RED2}15`,
                  border: `1px solid ${RED2}30`,
                }}
              >
                <div
                  className="text-lg font-black"
                  style={{ color: RED2, fontFamily: DISP2 }}
                >
                  {statsData?.refunds?.rejected ?? 0}
                </div>
                <div
                  className="text-[10px] text-gray-500"
                  style={{ fontFamily: DISP2 }}
                >
                  Rejected
                </div>
              </div>
            </div>
            {refundsLoading ? (
              <div
                className="text-center py-12 text-gray-500"
                style={{ fontFamily: DISP2 }}
              >
                Loading...
              </div>
            ) : myRefunds.length === 0 ? (
              <div className="text-center py-12" style={{ fontFamily: DISP2 }}>
                <div className="text-4xl mb-3">💰</div>
                <div className="text-sm text-gray-500">
                  No refunds requested yet.
                </div>
                <div className="text-xs text-gray-600 mt-1">
                  Tap + Refund to request a transaction refund.
                </div>
              </div>
            ) : (
              myRefunds.map((r: any) => (
                <div
                  key={r.refund.id}
                  className="rounded-2xl p-4"
                  style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="text-xs font-mono"
                      style={{ color: PURPLE2 }}
                    >
                      {r.refund.ref}
                    </span>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full font-bold"
                      style={{
                        background: `${statusColor[r.refund.status] ?? GOLD2}20`,
                        color: statusColor[r.refund.status] ?? GOLD2,
                        fontFamily: DISP2,
                      }}
                    >
                      {refundStatusIcon[r.refund.status] ?? ""}{" "}
                      {r.refund.status}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="text-sm font-bold text-white"
                      style={{ fontFamily: DISP2 }}
                    >
                      ₦{(r.refund.refundAmount ?? 0).toLocaleString()}
                    </span>
                    <span
                      className="text-xs text-gray-500"
                      style={{ fontFamily: MONO2 }}
                    >
                      of ₦{(r.refund.originalAmount ?? 0).toLocaleString()}
                    </span>
                  </div>
                  <div
                    className="text-xs text-gray-400 mb-1"
                    style={{ fontFamily: DISP2 }}
                  >
                    {r.refund.reason}
                  </div>
                  <div className="flex items-center justify-between">
                    <span
                      className="text-xs text-gray-500"
                      style={{ fontFamily: MONO2 }}
                    >
                      Tx: {r.refund.transactionRef}
                    </span>
                    <span
                      className="text-xs text-gray-600"
                      style={{ fontFamily: MONO2 }}
                    >
                      {new Date(r.refund.createdAt).toLocaleString("en-NG")}
                    </span>
                  </div>
                  {r.refund.status === "rejected" &&
                    r.refund.rejectionReason && (
                      <div
                        className="mt-2 rounded-lg p-2 text-xs"
                        style={{
                          background: `${RED2}10`,
                          border: `1px solid ${RED2}30`,
                          color: RED2,
                          fontFamily: DISP2,
                        }}
                      >
                        ❌ {r.refund.rejectionReason}
                      </div>
                    )}
                  {r.refund.status === "processed" && (
                    <div
                      className="mt-2 rounded-lg p-2 text-xs"
                      style={{
                        background: `${GREEN2}10`,
                        border: `1px solid ${GREEN2}30`,
                        color: GREEN2,
                        fontFamily: DISP2,
                      }}
                    >
                      ✅ Refund processed on{" "}
                      {new Date(r.refund.processedAt).toLocaleString("en-NG")}{" "}
                      via {r.refund.method?.replace("_", " ")}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
        {/* ── Raise Dispute Form ── */}
        {view === "raise" && (
          <div className="flex flex-col gap-4">
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Transaction Reference *
              </div>
              <input
                value={txRef}
                onChange={e => setTxRef(e.target.value)}
                placeholder="e.g. TXN-2024-001847"
                className="w-full bg-transparent text-white text-sm outline-none"
                style={{ fontFamily: MONO2 }}
              />
            </div>
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Reason for Dispute *
              </div>
              <textarea
                value={reason}
                onChange={e => setReason(e.target.value)}
                placeholder="Describe the issue clearly..."
                rows={4}
                className="w-full bg-transparent text-white text-sm outline-none resize-none"
                style={{ fontFamily: DISP2 }}
              />
            </div>
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Supporting Evidence (optional)
              </div>
              <textarea
                value={evidence}
                onChange={e => setEvidence(e.target.value)}
                placeholder="Receipt number, customer phone..."
                rows={3}
                className="w-full bg-transparent text-white text-sm outline-none resize-none"
                style={{ fontFamily: DISP2 }}
              />
            </div>
            <button
              onClick={() =>
                raise.mutate({
                  transactionRef: txRef,
                  reason,
                  evidence: evidence || undefined,
                })
              }
              disabled={
                raise.isPending || !txRef.trim() || reason.trim().length < 10
              }
              className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95 disabled:opacity-50"
              style={{ background: BLUE2, fontFamily: DISP2 }}
            >
              {raise.isPending ? "Submitting..." : "Submit Dispute"}
            </button>
            <div
              className="text-xs text-center text-gray-600"
              style={{ fontFamily: DISP2 }}
            >
              Disputes are reviewed within 24–48 hours. You will receive an SMS
              update.
            </div>
          </div>
        )}
        {/* ── Request Refund Form ── */}
        {view === "refund" && (
          <div className="flex flex-col gap-4">
            <div
              className="rounded-2xl p-3"
              style={{
                background: `${PURPLE2}10`,
                border: `1px solid ${PURPLE2}30`,
              }}
            >
              <div
                className="text-xs font-bold"
                style={{ color: PURPLE2, fontFamily: DISP2 }}
              >
                💰 Request Transaction Refund
              </div>
              <div
                className="text-[10px] text-gray-500 mt-1"
                style={{ fontFamily: DISP2 }}
              >
                Refund requests are reviewed by admin within 24 hours. Amount
                cannot exceed original transaction.
              </div>
            </div>
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Transaction Reference *
              </div>
              <input
                value={refundTxRef}
                onChange={e => setRefundTxRef(e.target.value)}
                placeholder="e.g. TXN-2024-001847"
                className="w-full bg-transparent text-white text-sm outline-none"
                style={{ fontFamily: MONO2 }}
              />
            </div>
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Refund Category *
              </div>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {[
                  "failed_transaction",
                  "wrong_amount",
                  "duplicate_charge",
                  "service_not_received",
                  "other",
                ].map(cat => (
                  <button
                    key={cat}
                    onClick={() => setRefundCategory(cat)}
                    className="px-2.5 py-1 rounded-lg text-[10px] font-bold transition-all"
                    style={{
                      background:
                        refundCategory === cat
                          ? `${PURPLE2}30`
                          : "oklch(0.18 0.02 240)",
                      color: refundCategory === cat ? PURPLE2 : "#888",
                      border: `1px solid ${refundCategory === cat ? PURPLE2 : BORDER2}`,
                      fontFamily: DISP2,
                    }}
                  >
                    {cat.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Refund Amount (₦) — leave blank for full refund
              </div>
              <input
                value={refundAmount}
                onChange={e =>
                  setRefundAmount(e.target.value.replace(/[^0-9]/g, ""))
                }
                placeholder="e.g. 5000"
                className="w-full bg-transparent text-white text-sm outline-none"
                style={{ fontFamily: MONO2 }}
              />
            </div>
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP2 }}
              >
                Reason for Refund *
              </div>
              <textarea
                value={refundReason}
                onChange={e => setRefundReason(e.target.value)}
                placeholder="Describe why this refund is needed..."
                rows={3}
                className="w-full bg-transparent text-white text-sm outline-none resize-none"
                style={{ fontFamily: DISP2 }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div
                className="rounded-2xl p-4"
                style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
              >
                <div
                  className="text-xs text-gray-500 mb-1"
                  style={{ fontFamily: DISP2 }}
                >
                  Customer Name
                </div>
                <input
                  value={custName}
                  onChange={e => setCustName(e.target.value)}
                  placeholder="Optional"
                  className="w-full bg-transparent text-white text-sm outline-none"
                  style={{ fontFamily: DISP2 }}
                />
              </div>
              <div
                className="rounded-2xl p-4"
                style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
              >
                <div
                  className="text-xs text-gray-500 mb-1"
                  style={{ fontFamily: DISP2 }}
                >
                  Customer Phone
                </div>
                <input
                  value={custPhone}
                  onChange={e => setCustPhone(e.target.value)}
                  placeholder="Optional"
                  className="w-full bg-transparent text-white text-sm outline-none"
                  style={{ fontFamily: MONO2 }}
                />
              </div>
            </div>
            <button
              onClick={() =>
                requestRefund.mutate({
                  transactionRef: refundTxRef,
                  reason: refundReason,
                  category: refundCategory as any,
                  refundAmount: refundAmount
                    ? parseInt(refundAmount)
                    : undefined,
                  customerName: custName || undefined,
                  customerPhone: custPhone || undefined,
                })
              }
              disabled={
                requestRefund.isPending ||
                !refundTxRef.trim() ||
                refundReason.trim().length < 10
              }
              className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95 disabled:opacity-50"
              style={{ background: PURPLE2, fontFamily: DISP2 }}
            >
              {requestRefund.isPending
                ? "Submitting..."
                : "Submit Refund Request"}
            </button>
          </div>
        )}
        {/* ── Dispute Thread ── */}
        {view === "thread" && detail && (
          <div className="flex flex-col gap-3">
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD2, border: `1px solid ${BORDER2}` }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono" style={{ color: BLUE2 }}>
                  {detail.ref}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-bold"
                  style={{
                    background: `${statusColor[detail.status] ?? GOLD2}20`,
                    color: statusColor[detail.status] ?? GOLD2,
                    fontFamily: DISP2,
                  }}
                >
                  {detail.status}
                </span>
              </div>
              <div
                className="text-sm font-semibold text-white mb-1"
                style={{ fontFamily: DISP2 }}
              >
                {detail.reason}
              </div>
              <div
                className="text-xs text-gray-500"
                style={{ fontFamily: MONO2 }}
              >
                Tx: {detail.transactionRef}
              </div>
              {detail.evidence && (
                <div
                  className="text-xs text-gray-600 mt-1 italic"
                  style={{ fontFamily: DISP2 }}
                >
                  {detail.evidence}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2">
              {(detail.messages ?? []).map((msg: any) => (
                <div
                  key={msg.id}
                  className={`rounded-xl p-3 text-xs ${msg.authorRole === "agent" ? "ml-0 mr-8" : "ml-8 mr-0"}`}
                  style={{
                    background:
                      msg.authorRole === "agent"
                        ? "oklch(0.22 0.02 240)"
                        : "oklch(0.60 0.22 260 / 0.15)",
                    border: `1px solid ${msg.authorRole === "agent" ? BORDER2 : "oklch(0.60 0.22 260 / 0.3)"}`,
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span
                      className="font-semibold"
                      style={{
                        color: msg.authorRole === "agent" ? GOLD2 : BLUE2,
                        fontFamily: DISP2,
                      }}
                    >
                      {msg.authorName}
                    </span>
                    <span
                      className="text-gray-600"
                      style={{ fontFamily: MONO2 }}
                    >
                      {new Date(msg.createdAt).toLocaleTimeString("en-NG")}
                    </span>
                  </div>
                  <p
                    className="text-gray-300 whitespace-pre-wrap"
                    style={{ fontFamily: DISP2 }}
                  >
                    {msg.message}
                  </p>
                </div>
              ))}
            </div>
            {(detail.status === "resolved" || detail.status === "rejected") &&
              detail.resolution && (
                <div
                  className="rounded-2xl p-4"
                  style={{
                    background:
                      detail.status === "resolved"
                        ? "oklch(0.65 0.18 160 / 0.1)"
                        : "oklch(0.60 0.22 25 / 0.1)",
                    border: `1px solid ${detail.status === "resolved" ? GREEN2 : RED2}`,
                  }}
                >
                  <div
                    className="text-xs font-bold mb-1"
                    style={{
                      color: detail.status === "resolved" ? GREEN2 : RED2,
                      fontFamily: DISP2,
                    }}
                  >
                    {detail.status === "resolved" ? "✓ Resolved" : "✗ Rejected"}
                  </div>
                  <p
                    className="text-xs text-gray-300"
                    style={{ fontFamily: DISP2 }}
                  >
                    {detail.resolution}
                  </p>
                </div>
              )}
            {detail.status !== "resolved" && detail.status !== "rejected" && (
              <div className="flex gap-2">
                <input
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  placeholder="Add a message..."
                  className="flex-1 px-4 py-3 rounded-xl text-sm text-white outline-none"
                  style={{
                    background: CARD2,
                    border: `1px solid ${BORDER2}`,
                    fontFamily: DISP2,
                  }}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      if (replyText.trim())
                        addMessage.mutate({
                          disputeRef: selectedRef!,
                          message: replyText.trim(),
                        });
                    }
                  }}
                />
                <button
                  onClick={() => {
                    if (replyText.trim())
                      addMessage.mutate({
                        disputeRef: selectedRef!,
                        message: replyText.trim(),
                      });
                  }}
                  disabled={addMessage.isPending || !replyText.trim()}
                  className="px-4 py-3 rounded-xl font-bold text-white disabled:opacity-50"
                  style={{ background: BLUE2, fontFamily: DISP2 }}
                >
                  Send
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Offline & Resilience Screen ────────────────────────────────────────────

export function DisputesScreen({ onBack }: { onBack: () => void }) {
  const [view, setView] = useState<"list" | "raise" | "detail">("list");
  const [selectedRef, setSelectedRef] = useState<string | null>(null);
  const [txRef, setTxRef] = useState("");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [msg, setMsg] = useState("");
  const [page, setPage] = useState(0);
  const utils = trpc.useUtils();

  const { data, isLoading } = trpc.disputes.myDisputes.useQuery(
    { limit: 10, offset: page * 10 },
    { enabled: view === "list" }
  );
  const { data: detail } = trpc.disputes.getDispute.useQuery(
    { ref: selectedRef! },
    { enabled: view === "detail" && !!selectedRef, refetchInterval: 15_000 }
  );

  const raise = trpc.disputes.raise.useMutation({
    onSuccess: () => {
      toast.success("Dispute raised successfully");
      utils.disputes.myDisputes.invalidate();
      setView("list");
      setTxRef("");
      setReason("");
      setEvidence("");
    },
    onError: e => toast.error(e.message),
  });

  const addMsg = trpc.disputes.addMessage.useMutation({
    onSuccess: () => {
      utils.disputes.getDispute.invalidate({ ref: selectedRef! });
      setMsg("");
    },
    onError: e => toast.error(e.message),
  });

  const statusColor: Record<string, string> = {
    raised: "#f59e0b",
    investigating: "#3b82f6",
    resolved: "#10b981",
    escalated: "#ef4444",
    closed: "#6b7280",
  };

  return (
    <div
      className="flex flex-col h-screen"
      style={{ background: BG, fontFamily: DISP }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 pt-safe pt-4 pb-3 flex-shrink-0"
        style={{ borderBottom: `1px solid ${BORDER}` }}
      >
        <button
          onClick={view === "list" ? onBack : () => setView("list")}
          className="text-gray-400 hover:text-white text-xl"
        >
          ←
        </button>
        <div>
          <div className="text-base font-bold text-white">My Disputes</div>
          <div className="text-xs text-gray-500">
            Raise & track transaction disputes
          </div>
        </div>
        {view === "list" && (
          <button
            onClick={() => setView("raise")}
            className="ml-auto px-3 py-1.5 rounded-xl text-xs font-bold"
            style={{ background: "#8b5cf6", color: "white" }}
          >
            + Raise
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {/* ── List view ── */}
        {view === "list" && (
          <div className="flex flex-col gap-3">
            {isLoading && (
              <div className="text-center text-gray-500 py-8">
                Loading disputes…
              </div>
            )}
            {!isLoading && (!data?.disputes || data.disputes.length === 0) && (
              <div className="text-center text-gray-500 py-12">
                <div className="text-4xl mb-3">⚖</div>
                <div className="text-sm">No disputes raised yet</div>
                <div className="text-xs text-gray-600 mt-1">
                  Tap "+ Raise" to dispute a transaction
                </div>
              </div>
            )}
            {data?.disputes.map((d: any) => (
              <button
                key={d.ref}
                onClick={() => {
                  setSelectedRef(d.ref);
                  setView("detail");
                }}
                className="w-full text-left rounded-2xl p-4 transition-all hover:opacity-90"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white font-mono">
                    {d.ref}
                  </span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full font-bold uppercase"
                    style={{
                      background: `${statusColor[d.status] ?? "#6b7280"}22`,
                      color: statusColor[d.status] ?? "#6b7280",
                    }}
                  >
                    {d.status}
                  </span>
                </div>
                <div className="text-xs text-gray-400 truncate">{d.reason}</div>
                <div className="text-xs text-gray-600 mt-1">
                  Tx: {d.transactionRef}
                </div>
              </button>
            ))}
            {/* Pagination */}
            {data && data.total > 10 && (
              <div className="flex justify-between mt-2">
                <button
                  disabled={page === 0}
                  onClick={() => setPage(p => p - 1)}
                  className="px-3 py-1.5 rounded-xl text-xs font-bold disabled:opacity-40"
                  style={{
                    background: CARD,
                    color: "white",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  ← Prev
                </button>
                <span className="text-xs text-gray-500 self-center">
                  {page * 10 + 1}–{Math.min((page + 1) * 10, data.total)} of{" "}
                  {data.total}
                </span>
                <button
                  disabled={(page + 1) * 10 >= data.total}
                  onClick={() => setPage(p => p + 1)}
                  className="px-3 py-1.5 rounded-xl text-xs font-bold disabled:opacity-40"
                  style={{
                    background: CARD,
                    color: "white",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Raise view ── */}
        {view === "raise" && (
          <div className="flex flex-col gap-4">
            <div className="text-sm font-bold text-white">Raise a Dispute</div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 uppercase tracking-widest">
                Transaction Reference *
              </label>
              <input
                value={txRef}
                onChange={e => setTxRef(e.target.value)}
                placeholder="TXN-XXXXXXXX"
                className="rounded-xl px-3 py-2.5 text-sm text-white outline-none"
                style={{
                  background: CARD,
                  border: `1px solid ${BORDER}`,
                  fontFamily: MONO,
                }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 uppercase tracking-widest">
                Reason * (min 10 chars)
              </label>
              <textarea
                value={reason}
                onChange={e => setReason(e.target.value)}
                rows={3}
                placeholder="Describe the issue with this transaction…"
                className="rounded-xl px-3 py-2.5 text-sm text-white outline-none resize-none"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 uppercase tracking-widest">
                Evidence (optional)
              </label>
              <textarea
                value={evidence}
                onChange={e => setEvidence(e.target.value)}
                rows={2}
                placeholder="Attach any supporting notes or reference numbers…"
                className="rounded-xl px-3 py-2.5 text-sm text-white outline-none resize-none"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              />
            </div>
            <button
              onClick={() =>
                raise.mutate({
                  transactionRef: txRef,
                  reason,
                  evidence: evidence || undefined,
                })
              }
              disabled={raise.isPending || !txRef || reason.length < 10}
              className="w-full py-3 rounded-2xl font-bold text-sm transition-all disabled:opacity-50"
              style={{
                background: raise.isPending ? "#374151" : "#8b5cf6",
                color: "white",
              }}
            >
              {raise.isPending ? "Submitting…" : "Submit Dispute"}
            </button>
          </div>
        )}

        {/* ── Detail view ── */}
        {view === "detail" && detail && (
          <div className="flex flex-col gap-4">
            <div
              className="rounded-2xl p-4"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-white font-mono">
                  {detail.ref}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-bold uppercase"
                  style={{
                    background: `${statusColor[detail.status] ?? "#6b7280"}22`,
                    color: statusColor[detail.status] ?? "#6b7280",
                  }}
                >
                  {detail.status}
                </span>
              </div>
              <div className="text-xs text-gray-400 mb-1">
                Tx:{" "}
                <span className="text-white font-mono">
                  {detail.transactionRef}
                </span>
              </div>
              <div className="text-xs text-gray-300">{detail.reason}</div>
              {detail.resolution && (
                <div
                  className="mt-2 p-2 rounded-xl text-xs text-green-400"
                  style={{ background: "#10b98120" }}
                >
                  Resolution: {detail.resolution}
                </div>
              )}
            </div>

            {/* Messages thread */}
            <div className="text-xs font-bold text-gray-400 uppercase tracking-widest">
              Thread
            </div>
            <div className="flex flex-col gap-2">
              {detail.messages.map((m: any) => (
                <div
                  key={m.id}
                  className="rounded-xl p-3"
                  style={{
                    background:
                      m.authorRole === "agent"
                        ? "oklch(0.18 0.02 260)"
                        : "oklch(0.14 0.015 240)",
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className="text-xs font-bold"
                      style={{
                        color: m.authorRole === "agent" ? "#3b82f6" : "#10b981",
                      }}
                    >
                      {m.authorName}
                    </span>
                    <span className="text-xs text-gray-600">
                      {new Date(m.createdAt).toLocaleString("en-NG", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </span>
                  </div>
                  <div className="text-xs text-gray-300 whitespace-pre-wrap">
                    {m.message}
                  </div>
                </div>
              ))}
            </div>

            {/* Reply box */}
            {detail.status !== "resolved" && detail.status !== "rejected" && (
              <div className="flex gap-2 mt-2">
                <input
                  value={msg}
                  onChange={e => setMsg(e.target.value)}
                  placeholder="Add a message…"
                  className="flex-1 rounded-xl px-3 py-2.5 text-sm text-white outline-none"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                />
                <button
                  onClick={() =>
                    addMsg.mutate({ disputeRef: detail.ref, message: msg })
                  }
                  disabled={addMsg.isPending || !msg.trim()}
                  className="px-4 py-2.5 rounded-xl font-bold text-sm disabled:opacity-50"
                  style={{ background: "#3b82f6", color: "white" }}
                >
                  {addMsg.isPending ? "…" : "Send"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sprint 75: USSD Transaction Screen ──────────────────────────────────────

function StatusBar({
  terminal,
  time,
}: {
  terminal: TerminalInfo;
  time: string;
}) {
  const tierColor = {
    Bronze: "#cd7f32",
    Silver: "#9ca3af",
    Gold: GOLD,
    Platinum: "#a78bfa",
  }[terminal.tier];
  return (
    <div
      className="flex items-center justify-between px-4 py-2 text-xs flex-shrink-0"
      style={{
        background: "oklch(0.07 0.012 240)",
        borderBottom: `1px solid ${BORDER}`,
      }}
    >
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <div
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: terminal.online ? GREEN : RED }}
          />
          <span
            className="font-semibold text-white"
            style={{ fontFamily: DISP }}
          >
            {terminal.agentName.split(" ")[0]}
          </span>
        </div>
        <span className="text-gray-500">|</span>
        <span style={{ color: "oklch(0.65 0.015 230)", fontFamily: MONO }}>
          {terminal.agentCode}
        </span>
        <span className="text-gray-500">|</span>
        <span
          className="font-bold px-1.5 py-0.5 rounded text-xs"
          style={{
            color: tierColor,
            background: `${tierColor}22`,
            fontFamily: DISP,
          }}
        >
          {terminal.tier}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div
          className="px-2 py-0.5 rounded text-xs font-bold"
          style={{
            background: "oklch(0.60 0.22 260 / 0.2)",
            color: "#3b82f6",
            fontFamily: DISP,
          }}
        >
          {terminal.model}
        </div>
        <span style={{ fontFamily: MONO, color: "oklch(0.65 0.015 230)" }}>
          {terminal.serialNo.slice(-4)}
        </span>
        <span className="text-gray-500">|</span>
        <span
          style={{
            color: terminal.network === "Offline" ? RED : GREEN,
            fontFamily: MONO,
          }}
        >
          {terminal.network === "4G"
            ? "📶"
            : terminal.network === "WiFi"
              ? "📡"
              : "📶"}{" "}
          {terminal.network}
        </span>
        <span
          style={{
            color: terminal.batteryLevel > 30 ? GREEN : RED,
            fontFamily: MONO,
          }}
        >
          🔋{terminal.batteryLevel}%
        </span>
        {terminal.paperLevel < 30 && (
          <span style={{ color: GOLD }}>📄{terminal.paperLevel}%</span>
        )}
        <span
          className="font-bold"
          style={{ fontFamily: MONO, color: "white" }}
        >
          {time}
        </span>
      </div>
    </div>
  );
}

// ─── Float Header ─────────────────────────────────────────────────────────────
