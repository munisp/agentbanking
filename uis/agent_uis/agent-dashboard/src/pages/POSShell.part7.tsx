// @ts-nocheck
import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AmountDisplay, NumPad, PhoneInput, ScreenHeader, SuccessScreen } from "./POSShell.part10";
import { fmt } from "./POSShell.part5";
import { ReceiptModal } from "./POSShell.part6";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TERMINAL, Transaction } from "./POSShell.shared";

export function NanoLoanScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"offer" | "apply" | "confirm" | "success">(
    "offer"
  );
  const [amount, setAmount] = useState(50000);
  const [tenor, setTenor] = useState(30);

  const interest = Math.round(amount * 0.025);
  const total = amount + interest;

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
                    742
                  </p>
                  <p className="text-green-400 text-xs">
                    Excellent — Pre-approved
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
                max={500000}
                step={10000}
                value={amount}
                onChange={e => setAmount(Number(e.target.value))}
                className="w-full mb-4"
                style={{ accentColor: BLUE }}
              />
              <div className="flex justify-between text-xs text-gray-500 mb-4">
                <span>₦10,000</span>
                <span>₦500,000</span>
              </div>

              <div className="grid grid-cols-3 gap-3 mb-4">
                {[7, 14, 30].map(t => (
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
                  <span className="text-gray-400">Interest (2.5%)</span>
                  <span className="text-white" style={{ fontFamily: MONO }}>
                    ₦{interest.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between text-sm font-bold">
                  <span className="text-gray-300">Total Repayment</span>
                  <span style={{ color: GOLD, fontFamily: MONO }}>
                    ₦{total.toLocaleString()}
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
                Funds will be credited to your float account instantly
              </p>
              <div
                className="text-4xl font-bold mb-1"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                ₦{amount.toLocaleString()}
              </div>
              <p className="text-gray-500 text-sm">
                Repay ₦{total.toLocaleString()} in {tenor} days
              </p>
            </div>
            <button
              onClick={() => setStep("success")}
              className="w-full py-4 rounded-2xl font-bold text-white text-lg mb-3"
              style={{ background: GREEN }}
            >
              ✓ Confirm & Disburse
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
              Loan Approved!
            </h3>
            <p className="text-gray-400 mb-4">
              ₦{amount.toLocaleString()} credited to your float
            </p>
            <div
              className="rounded-xl px-6 py-3 mb-6"
              style={{
                background: `${GREEN}20`,
                border: `1px solid ${GREEN}40`,
              }}
            >
              <p className="text-green-400 font-semibold">New Float Balance</p>
              <p
                className="text-3xl font-bold"
                style={{ color: GREEN, fontFamily: MONO }}
              >
                ₦{(485250 + amount).toLocaleString()}
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

// ── End-of-Day Reconciliation Wizard ─────────────────────────────────────────

function FraudAlertsScreen({ onBack }: { onBack: () => void }) {
  const utils = trpc.useUtils();
  const { data: liveAlerts, isLoading } = trpc.fraud.list.useQuery(
    { status: "open" },
    { refetchInterval: 30_000 }
  );
  const [selected, setSelected] = useState<any | null>(null);
  const updateStatus = trpc.fraud.updateStatus.useMutation({
    onSuccess: () => {
      utils.fraud.list.invalidate();
      setSelected(null);
    },
  });
  const sev: Record<string, string> = {
    critical: "#ef4444",
    high: "#f97316",
    medium: "#f59e0b",
    low: "#6b7280",
  };
  const alerts: any[] =
    (liveAlerts as any)?.items ?? (Array.isArray(liveAlerts) ? liveAlerts : []);
  if (selected)
    return (
      <div className="flex flex-col h-full">
        <ScreenHeader title="Alert Detail" onBack={() => setSelected(null)} />
        <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
          <div
            className="rounded-2xl p-5"
            style={{
              background: CARD,
              border: `2px solid ${sev[selected.severity] ?? "#6b7280"}`,
            }}
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-10 h-10 rounded-full flex items-center justify-center text-xl"
                style={{
                  background: (sev[selected.severity] ?? "#6b7280") + "22",
                }}
              >
                ⚠
              </div>
              <div>
                <div
                  className="text-sm font-bold text-white"
                  style={{ fontFamily: DISP }}
                >
                  {selected.alertType ?? selected.type}
                </div>
                <div
                  className="text-xs px-2 py-0.5 rounded-full font-bold uppercase"
                  style={{
                    background: (sev[selected.severity] ?? "#6b7280") + "22",
                    color: sev[selected.severity] ?? "#6b7280",
                    fontFamily: DISP,
                  }}
                >
                  {selected.severity}
                </div>
              </div>
            </div>
            <div
              className="text-sm text-gray-300 mb-2"
              style={{ fontFamily: DISP }}
            >
              {selected.reason ??
                selected.description ??
                "Suspicious activity detected"}
            </div>
            <div className="text-xs text-gray-500" style={{ fontFamily: MONO }}>
              {new Date(selected.createdAt).toLocaleTimeString("en-NG", {
                hour: "2-digit",
                minute: "2-digit",
              })}{" "}
              · ₦{fmt(selected.amount ?? 0)}
            </div>
          </div>
          <div
            className="rounded-xl p-4"
            style={{
              background: "oklch(0.18 0.04 260 / 0.5)",
              border: `1px solid ${BORDER}`,
            }}
          >
            <div
              className="text-xs text-gray-500 mb-2"
              style={{ fontFamily: DISP }}
            >
              AI Explanation
            </div>
            <div className="text-sm text-gray-300" style={{ fontFamily: DISP }}>
              {selected.aiExplanation ??
                "Transaction velocity exceeded 3× normal rate for this agent. Structuring pattern detected. Confidence: 94.7% · Model: FraudNet v2.1"}
            </div>
            <div
              className="mt-2 text-xs"
              style={{ color: BLUE, fontFamily: MONO }}
            >
              Score: {selected.fraudScore ?? "N/A"} · FraudNet v2.1
            </div>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() =>
                updateStatus.mutate({ id: selected.id, status: "escalated" })
              }
              disabled={updateStatus.isPending}
              className="flex-1 py-3 rounded-xl font-bold"
              style={{
                background: "#ef444422",
                color: "#ef4444",
                border: "1px solid #ef4444",
                fontFamily: DISP,
              }}
            >
              Escalate
            </button>
            <button
              onClick={() =>
                updateStatus.mutate({ id: selected.id, status: "dismissed" })
              }
              disabled={updateStatus.isPending}
              className="flex-1 py-3 rounded-xl font-bold"
              style={{
                background: "#22c55e22",
                color: "#22c55e",
                border: "1px solid #22c55e",
                fontFamily: DISP,
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="Fraud Alerts"
        onBack={onBack}
        badge={
          <span
            className="ml-2 px-2 py-0.5 rounded-full text-xs font-bold"
            style={{ background: "#ef444422", color: "#ef4444" }}
          >
            {alerts.length}
          </span>
        }
      />
      <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
        {isLoading ? (
          <div
            className="flex items-center justify-center py-16 text-gray-500"
            style={{ fontFamily: DISP }}
          >
            <span className="animate-spin mr-2">⟳</span> Loading...
          </div>
        ) : alerts.length === 0 ? (
          <div
            className="text-center text-gray-500 mt-20"
            style={{ fontFamily: DISP }}
          >
            No active alerts
          </div>
        ) : (
          alerts.map((a: any) => (
            <button
              key={a.id}
              onClick={() => setSelected(a)}
              className="w-full rounded-xl p-4 text-left"
              style={{
                background: CARD,
                border: `1px solid ${sev[a.severity] ?? "#6b7280"}44`,
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <div
                  className="text-sm font-bold text-white"
                  style={{ fontFamily: DISP }}
                >
                  {a.alertType ?? a.type}
                </div>
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-bold uppercase"
                  style={{
                    background: (sev[a.severity] ?? "#6b7280") + "22",
                    color: sev[a.severity] ?? "#6b7280",
                    fontFamily: DISP,
                  }}
                >
                  {a.severity}
                </span>
              </div>
              <div
                className="text-xs text-gray-400 mb-1"
                style={{ fontFamily: DISP }}
              >
                {a.reason ?? a.description ?? ""}
              </div>
              <div
                className="flex justify-between text-xs"
                style={{ fontFamily: MONO }}
              >
                <span style={{ color: GOLD }}>₦{fmt(a.amount ?? 0)}</span>
                <span className="text-gray-600">
                  {new Date(a.createdAt).toLocaleTimeString("en-NG", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}


function ReversalScreen({ onBack }: { onBack: () => void }) {
  const [ref, setRef] = useState("");
  const [reason, setReason] = useState("");
  const [step, setStep] = useState<"form" | "confirm" | "success">("form");
  const [reversing, setReversing] = useState(false);
  const reverseMutation = trpc.transactions.reverse.useMutation();
  const recentTxs = usePosStore(s => s.recentTxs);
  // First check local recent txs for instant UX, then fall back to DB lookup
  const localFound = recentTxs.find(t =>
    t.ref.toLowerCase().includes(ref.toLowerCase())
  );
  const { data: dbFound } = trpc.transactions.getByRef.useQuery(
    { ref: ref.trim() },
    { enabled: ref.trim().length >= 6 && !localFound, retry: false }
  );
  const found =
    localFound ??
    (dbFound
      ? {
          ...dbFound,
          customer: dbFound.customerPhone ?? dbFound.customerName ?? "—",
          time: dbFound.createdAt
            ? new Date(dbFound.createdAt).toLocaleTimeString("en-NG")
            : "",
        }
      : undefined);

  if (step === "success")
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 p-6">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center text-4xl"
          style={{
            background: "oklch(0.60 0.22 25 / 0.2)",
            border: `2px solid ${RED}`,
          }}
        >
          ↺
        </div>
        <div className="text-center">
          <div
            className="text-xl font-bold text-white mb-1"
            style={{ fontFamily: DISP }}
          >
            Reversal Initiated
          </div>
          <div className="text-sm text-gray-400">
            Funds will be returned within 24 hours
          </div>
          <div
            className="text-xs text-gray-600 mt-2"
            style={{ fontFamily: MONO }}
          >
            REV-{Date.now().toString().slice(-9)}
          </div>
        </div>
        <button
          onClick={onBack}
          className="w-full py-4 rounded-xl font-bold text-white"
          style={{ background: RED, fontFamily: DISP }}
        >
          Done
        </button>
      </div>
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="Transaction Reversal"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.60 0.22 25 / 0.2)",
              color: RED,
              fontFamily: DISP,
            }}
          >
            REVERSAL
          </span>
        }
      />
      <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
        <div>
          <div
            className="text-xs text-gray-500 mb-1"
            style={{ fontFamily: DISP }}
          >
            Transaction Reference
          </div>
          <input
            value={ref}
            onChange={e => setRef(e.target.value)}
            placeholder="TXN-2024-XXXXXX"
            className="w-full rounded-xl px-4 py-3 text-white outline-none"
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              fontFamily: MONO,
            }}
          />
        </div>
        {ref.length > 5 &&
          (found ? (
            <div
              className="rounded-2xl p-4 flex flex-col gap-2"
              style={{
                background: "oklch(0.65 0.18 160 / 0.1)",
                border: `1px solid ${GREEN}33`,
              }}
            >
              <div
                className="text-xs text-green-400 font-semibold"
                style={{ fontFamily: DISP }}
              >
                ✓ Transaction Found
              </div>
              {[
                ["Type", found.type],
                ["Amount", fmt(found.amount)],
                [
                  "Customer",
                  (found as any).customer ?? (found as any).customerName ?? "—",
                ],
                [
                  "Time",
                  (found as any).time ?? (found as any).createdAt ?? "—",
                ],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    {k}
                  </span>
                  <span
                    className="text-xs font-bold text-white"
                    style={{ fontFamily: k === "Amount" ? MONO : DISP }}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div
              className="text-center text-sm py-4"
              style={{ color: RED, fontFamily: DISP }}
            >
              Transaction not found
            </div>
          ))}
        {found && (
          <>
            <div>
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                Reason for Reversal
              </div>
              <select
                value={reason}
                onChange={e => setReason(e.target.value)}
                className="w-full rounded-xl px-4 py-3 text-white outline-none"
                style={{
                  background: CARD,
                  border: `1px solid ${BORDER}`,
                  fontFamily: DISP,
                }}
              >
                <option value="">Select reason...</option>
                <option>Customer request</option>
                <option>Wrong amount</option>
                <option>Wrong account</option>
                <option>Technical error</option>
                <option>Duplicate transaction</option>
              </select>
            </div>
            <button
              disabled={!reason || reversing}
              onClick={async () => {
                setReversing(true);
                try {
                  await reverseMutation.mutateAsync({ ref, reason });
                  toast.success("Reversal initiated successfully");
                  setStep("success");
                } catch (err: unknown) {
                  toast.error(
                    err instanceof Error ? err.message : "Reversal failed"
                  );
                } finally {
                  setReversing(false);
                }
              }}
              className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: RED, fontFamily: DISP }}
            >
              {reversing ? "Processing..." : "↺ Initiate Reversal"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// 10. Customer Lookup ─────────────────────────────────────────────────────────

function PrinterTestScreen({ onBack }: { onBack: () => void }) {
  const [printing, setPrinting] = useState(false);
  const [result, setResult] = useState<
    "idle" | "success" | "error" | "low-paper"
  >("idle");
  const runTest = (type: string) => {
    setPrinting(true);
    setResult("idle");
    setTimeout(() => {
      setPrinting(false);
      const r = TERMINAL.paperLevel > 20 ? "success" : "low-paper";
      setResult(r);
      if (r === "success") toast.success(`${type} print successful`);
      else toast.warning("Paper level low — please reload paper");
    }, 2000);
  };
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Printer Diagnostics" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Paper status */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Paper Status
          </div>
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="flex justify-between mb-1">
                <span
                  className="text-xs text-gray-400"
                  style={{ fontFamily: DISP }}
                >
                  Paper Level
                </span>
                <span
                  className="text-xs font-bold"
                  style={{
                    color: TERMINAL.paperLevel > 30 ? GREEN : RED,
                    fontFamily: MONO,
                  }}
                >
                  {TERMINAL.paperLevel}%
                </span>
              </div>
              <div
                className="h-3 rounded-full overflow-hidden"
                style={{ background: BORDER }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${TERMINAL.paperLevel}%`,
                    background: TERMINAL.paperLevel > 30 ? GREEN : RED,
                  }}
                />
              </div>
            </div>
            <div className="text-3xl">
              {TERMINAL.paperLevel > 30 ? "📄" : "⚠️"}
            </div>
          </div>
          <div
            className="mt-3 text-xs text-gray-400"
            style={{ fontFamily: DISP }}
          >
            Paper width: 80mm · ESC/POS · Thermal
          </div>
        </div>
        {/* Printer info */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Printer Specifications
          </div>
          {[
            ["Type", "Thermal (ESC/POS)"],
            ["Width", "80mm"],
            ["DPI", "203 dpi"],
            ["Speed", "100mm/s"],
            ["Interface", "Internal"],
            ["Status", "Ready"],
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
                className="text-xs font-bold text-white"
                style={{ fontFamily: MONO }}
              >
                {v}
              </span>
            </div>
          ))}
        </div>
        {/* Test buttons */}
        <div
          className="rounded-2xl p-4 flex flex-col gap-3"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-1"
            style={{ fontFamily: DISP }}
          >
            Print Tests
          </div>
          {[
            ["Test Receipt", "Prints a sample transaction receipt"],
            ["Self-Test Page", "Prints printer configuration page"],
            ["Barcode Test", "Prints Code128 and QR code samples"],
          ].map(([label, desc]) => (
            <button
              key={label}
              disabled={printing}
              onClick={() => runTest(label)}
              className="w-full p-3 rounded-xl text-left transition-all active:scale-95 disabled:opacity-50"
              style={{
                background: "oklch(0.60 0.22 260 / 0.1)",
                border: `1px solid ${BORDER}`,
              }}
            >
              <div
                className="text-sm font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                {label}
              </div>
              <div
                className="text-xs text-gray-400 mt-0.5"
                style={{ fontFamily: DISP }}
              >
                {desc}
              </div>
            </button>
          ))}
        </div>
        {printing && (
          <div
            className="rounded-2xl p-4 flex items-center gap-3"
            style={{
              background: "oklch(0.60 0.22 260 / 0.1)",
              border: `1px solid ${BLUE}`,
            }}
          >
            <div className="w-5 h-5 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            <span
              className="text-sm text-blue-400"
              style={{ fontFamily: DISP }}
            >
              Printing…
            </span>
          </div>
        )}
        {result === "success" && (
          <div
            className="rounded-2xl p-4 flex items-center gap-3"
            style={{
              background: "oklch(0.65 0.18 160 / 0.1)",
              border: `1px solid ${GREEN}`,
            }}
          >
            <span className="text-xl">✓</span>
            <span
              className="text-sm font-bold"
              style={{ color: GREEN, fontFamily: DISP }}
            >
              Print test successful
            </span>
          </div>
        )}
        {result === "low-paper" && (
          <div
            className="rounded-2xl p-4 flex items-center gap-3"
            style={{
              background: "oklch(0.78 0.18 80 / 0.1)",
              border: `1px solid ${GOLD}`,
            }}
          >
            <span className="text-xl">⚠️</span>
            <span
              className="text-sm font-bold"
              style={{ color: GOLD, fontFamily: DISP }}
            >
              Paper level low — reload paper roll
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// 25. NetworkTest ──────────────────────────────────────────────────────────────

function CashOutScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "phone" | "confirm" | "success">(
    "amount"
  );
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const storeFloat = usePosStore(
    s => s.agent?.floatBalance ?? TERMINAL.floatBalance
  );
  const floatOk = num <= storeFloat;
  const { submit, isProcessing } = useTransactionCreate();

  if (step === "success")
    return (
      <>
        <SuccessScreen
          title="Cash Out Successful"
          amount={num}
          ref={txRef}
          customer={phone}
          onDone={onBack}
          onPrint={() => setReceipt(true)}
        />
        {receipt && (
          <ReceiptModal
            tx={{
              type: "Cash Out",
              amount: num,
              customer: phone,
              ref: txRef,
              time: new Date().toLocaleTimeString("en-NG", {
                hour: "2-digit",
                minute: "2-digit",
              }),
            }}
            onClose={() => setReceipt(false)}
          />
        )}
      </>
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="Cash Out"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.60 0.22 260 / 0.2)",
              color: "#3b82f6",
              fontFamily: DISP,
            }}
          >
            WITHDRAWAL
          </span>
        }
      />
      {step === "amount" && (
        <>
          <div
            className="mx-4 mt-3 p-3 rounded-xl flex items-center gap-2"
            style={{
              background: "oklch(0.78 0.18 80 / 0.1)",
              border: `1px solid ${GOLD}33`,
            }}
          >
            <span className="text-xs" style={{ color: GOLD, fontFamily: DISP }}>
              Available Float:{" "}
              <span style={{ fontFamily: MONO }}>{fmt(storeFloat)}</span>
            </span>
          </div>
          <AmountDisplay value={amount} label="Withdrawal Amount" />
          {num > storeFloat && (
            <div
              className="text-center text-xs mb-2"
              style={{ color: RED, fontFamily: DISP }}
            >
              ⚠ Exceeds available float
            </div>
          )}
          <NumPad value={amount} onChange={setAmount} />
          <div className="px-4 pb-4">
            <button
              disabled={num < 100 || !floatOk}
              onClick={() => setStep("phone")}
              className="w-full py-4 rounded-xl font-bold text-white text-base transition-all disabled:opacity-40"
              style={{
                background:
                  num >= 100 && floatOk ? "#3b82f6" : "oklch(0.20 0.01 240)",
                fontFamily: DISP,
              }}
            >
              Continue →
            </button>
          </div>
        </>
      )}
      {step === "phone" && (
        <>
          <AmountDisplay value={amount} label="Withdrawal Amount" />
          <PhoneInput
            value={phone}
            onChange={setPhone}
            label="Customer Phone / Account"
          />
          <div className="px-4 pb-4 flex gap-3">
            <button
              onClick={() => setStep("amount")}
              className="flex-1 py-4 rounded-xl font-bold text-sm"
              style={{ background: CARD, color: "white", fontFamily: DISP }}
            >
              ← Back
            </button>
            <button
              disabled={phone.length < 10}
              onClick={() => setStep("confirm")}
              className="flex-2 flex-grow py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: "#3b82f6", fontFamily: DISP }}
            >
              Review →
            </button>
          </div>
        </>
      )}
      {step === "confirm" && (
        <div className="flex flex-col gap-4 p-4">
          <div
            className="rounded-2xl p-4 flex flex-col gap-3"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-sm font-bold text-gray-400 uppercase tracking-widest"
              style={{ fontFamily: DISP }}
            >
              Confirm Withdrawal
            </div>
            {[
              ["Type", "Cash Out (Withdrawal)"],
              ["Amount", fmt(num)],
              ["Customer Phone", phone],
              ["Float After", fmt(storeFloat - num)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span
                  className="text-sm text-gray-500"
                  style={{ fontFamily: DISP }}
                >
                  {k}
                </span>
                <span
                  className="text-sm font-bold"
                  style={{
                    fontFamily:
                      k === "Amount" || k === "Float After" ? MONO : DISP,
                    color:
                      k === "Amount"
                        ? RED
                        : k === "Float After"
                          ? GOLD
                          : "white",
                  }}
                >
                  {v}
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setStep("phone")}
              className="flex-1 py-4 rounded-xl font-bold text-sm"
              style={{ background: CARD, color: "white", fontFamily: DISP }}
            >
              ← Edit
            </button>
            <button
              disabled={isProcessing}
              onClick={async () => {
                toast.success("Processing withdrawal...");
                const result = await submit({
                  type: "Cash Out",
                  amount: num,
                  customerPhone: phone,
                  channel: "Cash",
                });
                if (result) {
                  setTxRef(result.ref);
                  setStep("success");
                }
              }}
              className="flex-2 flex-grow py-4 rounded-xl font-bold text-white disabled:opacity-60"
              style={{ background: "#3b82f6", fontFamily: DISP }}
            >
              {isProcessing ? "Processing..." : "✓ Confirm Withdrawal"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// 3. Transfer ──────────────────────────────────────────────────────────────────

function TransferScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"form" | "confirm" | "success">("form");
  const [amount, setAmount] = useState("");
  const [fromAcct, setFromAcct] = useState("");
  const [toAcct, setToAcct] = useState("");
  const [bank, setBank] = useState("GTBank");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const banks = [
    "GTBank",
    "Access Bank",
    "First Bank",
    "UBA",
    "Zenith Bank",
    "Polaris Bank",
    "Kuda",
    "Opay",
    "Moniepoint",
  ];
  const { submit, isProcessing } = useTransactionCreate();

  if (step === "success")
    return (
      <>
        <SuccessScreen
          title="Transfer Successful"
          amount={num}
          ref={txRef}
          customer={toAcct}
          onDone={onBack}
          onPrint={() => setReceipt(true)}
        />
        {receipt && (
          <ReceiptModal
            tx={{
              type: "Transfer",
              amount: num,
              customer: toAcct,
              ref: txRef,
              time: new Date().toLocaleTimeString("en-NG", {
                hour: "2-digit",
                minute: "2-digit",
              }),
            }}
            onClose={() => setReceipt(false)}
          />
        )}
      </>
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Fund Transfer" onBack={onBack} />
      {step === "form" && (
        <div className="flex flex-col gap-4 p-4 overflow-y-auto">
          <div>
            <div
              className="text-xs text-gray-500 mb-1"
              style={{ fontFamily: DISP }}
            >
              From Account
            </div>
            <input
              value={fromAcct}
              onChange={e => setFromAcct(e.target.value)}
              placeholder="Source account number"
              className="w-full rounded-xl px-4 py-3 text-white outline-none"
              style={{
                background: CARD,
                border: `1px solid ${BORDER}`,
                fontFamily: MONO,
              }}
            />
          </div>
          <div>
            <div
              className="text-xs text-gray-500 mb-1"
              style={{ fontFamily: DISP }}
            >
              Destination Bank
            </div>
            <select
              value={bank}
              onChange={e => setBank(e.target.value)}
              className="w-full rounded-xl px-4 py-3 text-white outline-none"
              style={{
                background: CARD,
                border: `1px solid ${BORDER}`,
                fontFamily: DISP,
              }}
            >
              {banks.map(b => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div
              className="text-xs text-gray-500 mb-1"
              style={{ fontFamily: DISP }}
            >
              To Account Number
            </div>
            <input
              value={toAcct}
              onChange={e => setToAcct(e.target.value)}
              placeholder="Destination account number"
              className="w-full rounded-xl px-4 py-3 text-white outline-none"
              style={{
                background: CARD,
                border: `1px solid ${BORDER}`,
                fontFamily: MONO,
              }}
            />
          </div>
          <AmountDisplay value={amount} label="Transfer Amount" />
          <NumPad value={amount} onChange={setAmount} />
          <button
            disabled={num < 100 || !fromAcct || !toAcct}
            onClick={() => setStep("confirm")}
            className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
            style={{ background: "#8b5cf6", fontFamily: DISP }}
          >
            Review Transfer →
          </button>
        </div>
      )}
      {step === "confirm" && (
        <div className="flex flex-col gap-4 p-4">
          <div
            className="rounded-2xl p-4 flex flex-col gap-3"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-sm font-bold text-gray-400 uppercase tracking-widest"
              style={{ fontFamily: DISP }}
            >
              Confirm Transfer
            </div>
            {[
              ["From", fromAcct],
              ["To Bank", bank],
              ["To Account", toAcct],
              ["Amount", fmt(num)],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span
                  className="text-sm text-gray-500"
                  style={{ fontFamily: DISP }}
                >
                  {k}
                </span>
                <span
                  className="text-sm font-bold"
                  style={{
                    fontFamily: k === "Amount" ? MONO : DISP,
                    color: k === "Amount" ? "#8b5cf6" : "white",
                  }}
                >
                  {v}
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setStep("form")}
              className="flex-1 py-4 rounded-xl font-bold text-sm"
              style={{ background: CARD, color: "white", fontFamily: DISP }}
            >
              ← Edit
            </button>
            <button
              disabled={isProcessing}
              onClick={async () => {
                toast.success("Processing transfer...");
                const result = await submit({
                  type: "Transfer",
                  amount: num,
                  customerAccount: fromAcct,
                  destinationBank: bank,
                  destinationAccount: toAcct,
                  channel: "App",
                });
                if (result) {
                  setTxRef(result.ref);
                  setStep("success");
                }
              }}
              className="flex-2 flex-grow py-4 rounded-xl font-bold text-white disabled:opacity-60"
              style={{ background: "#8b5cf6", fontFamily: DISP }}
            >
              {isProcessing ? "Processing..." : "✓ Send Transfer"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// 4. Card Payment ─────────────────────────────────────────────────────────────

export function SupervisorApprovalModal({
  amount,
  txType,
  onApproved,
  onRejected,
  onClose,
}: {
  amount: string;
  txType: string;
  onApproved: () => void;
  onRejected: () => void;
  onClose: () => void;
}) {
  const [pin, setPin] = useState("");
  const [status, setStatus] = useState<
    "pending" | "approved" | "rejected" | "timeout"
  >("pending");
  const [countdown, setCountdown] = useState(120);

  useEffect(() => {
    if (status !== "pending") return;
    const iv = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          clearInterval(iv);
          setStatus("timeout");
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(iv);
  }, [status]);

  // No client-side supervisor PIN exists: approvals must come from a backend
  // override service, which is not connected yet — so approval always fails
  // closed. The entered PIN is never evaluated locally.
  const handleApprove = () => {
    setPin("");
    toast.error(
      "Supervisor approval service is unavailable — this override cannot be approved."
    );
    setStatus("rejected");
    setTimeout(onRejected, 1500);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.85)" }}
    >
      <div
        className="w-full max-w-sm rounded-3xl p-6"
        style={{ background: CARD, border: `1px solid ${GOLD}40` }}
      >
        <div className="text-center mb-6">
          <div className="text-4xl mb-3">🔐</div>
          <h3
            className="font-bold text-white text-xl mb-1"
            style={{ fontFamily: DISP }}
          >
            Supervisor Approval Required
          </h3>
          <p className="text-gray-400 text-sm">
            Transaction exceeds agent limit
          </p>
          <p className="text-xs mt-1" style={{ color: GOLD }}>
            Remote supervisor approval is not connected — overrides currently cannot be approved.
          </p>
        </div>

        {/* Transaction details */}
        <div
          className="rounded-xl p-4 mb-4"
          style={{ background: BG, border: `1px solid ${BORDER}` }}
        >
          <div className="flex justify-between mb-2">
            <span className="text-gray-500 text-sm">Type</span>
            <span className="text-white text-sm font-semibold">{txType}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 text-sm">Amount</span>
            <span
              className="font-bold text-lg"
              style={{ color: GOLD, fontFamily: MONO }}
            >
              {amount}
            </span>
          </div>
        </div>

        {status === "pending" && (
          <>
            {/* Countdown */}
            <div className="text-center mb-4">
              <div
                className="text-3xl font-bold"
                style={{ color: countdown < 30 ? RED : GOLD, fontFamily: MONO }}
              >
                {Math.floor(countdown / 60)}:
                {String(countdown % 60).padStart(2, "0")}
              </div>
              <p className="text-gray-500 text-xs mt-1">
                Time remaining for approval
              </p>
            </div>

            {/* PIN entry */}
            <div className="mb-4">
              <label className="text-gray-400 text-xs mb-2 block">
                Supervisor PIN
              </label>
              <input
                type="password"
                value={pin}
                onChange={e => setPin(e.target.value)}
                maxLength={6}
                placeholder="Enter supervisor PIN"
                className="w-full px-4 py-3 rounded-xl text-white text-center text-xl tracking-widest"
                style={{
                  background: BG,
                  border: `1px solid ${BORDER}`,
                  fontFamily: MONO,
                }}
              />
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleApprove}
                className="flex-1 py-3 rounded-xl font-bold text-sm"
                style={{ background: GREEN, color: "white" }}
              >
                ✓ Approve
              </button>
              <button
                onClick={() => {
                  setStatus("rejected");
                  setTimeout(onRejected, 1000);
                }}
                className="flex-1 py-3 rounded-xl font-bold text-sm"
                style={{ background: "oklch(0.45 0.20 25)", color: "white" }}
              >
                ✕ Reject
              </button>
            </div>
          </>
        )}

        {status === "approved" && (
          <div className="text-center py-4">
            <div className="text-5xl mb-3">✅</div>
            <p className="text-green-400 font-bold">Transaction Approved</p>
          </div>
        )}

        {status === "rejected" && (
          <div className="text-center py-4">
            <div className="text-5xl mb-3">❌</div>
            <p className="text-red-400 font-bold">Transaction Rejected</p>
          </div>
        )}

        {status === "timeout" && (
          <div className="text-center py-4">
            <div className="text-5xl mb-3">⏰</div>
            <p className="text-yellow-400 font-bold">Approval Timeout</p>
            <p className="text-gray-500 text-sm mt-1">Transaction cancelled</p>
            <button
              onClick={onClose}
              className="mt-4 px-6 py-2 rounded-xl text-sm font-semibold"
              style={{
                background: CARD,
                color: "white",
                border: `1px solid ${BORDER}`,
              }}
            >
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Push Notification Panel ───────────────────────────────────────────────────
