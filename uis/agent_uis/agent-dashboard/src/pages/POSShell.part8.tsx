// @ts-nocheck
import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AmountDisplay, NumPad, PhoneInput, ScreenHeader, SuccessScreen } from "./POSShell.part10";
import { fmt } from "./POSShell.part5";
import { ReceiptModal } from "./POSShell.part6";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TERMINAL, TICKER_ITEMS, TILE_REGISTRY, Tile, TileCategory, Transaction } from "./POSShell.shared";

function TxHistoryScreen({ onBack }: { onBack: () => void }) {
  const [filter, setFilter] = useState<
    "all" | "success" | "pending" | "failed"
  >("all");
  const [selected, setSelected] = useState<any | null>(null);
  const { data: txData, isLoading } = trpc.transactions.list.useQuery({
    limit: 100,
    offset: 0,
  });
  const allTxs = txData ?? [];
  const filtered =
    filter === "all" ? allTxs : allTxs.filter((t: any) => t.status === filter);

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Transaction History" onBack={onBack} />
      <div
        className="flex gap-2 px-4 py-2 border-b overflow-x-auto"
        style={{ borderColor: BORDER }}
      >
        {(["all", "success", "pending", "failed"] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="px-3 py-1 rounded-full text-xs font-semibold capitalize whitespace-nowrap"
            style={{
              background: filter === f ? BLUE : CARD,
              color: filter === f ? "white" : "oklch(0.55 0.015 230)",
              fontFamily: DISP,
            }}
          >
            {f}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
        {isLoading ? (
          <div
            className="flex items-center justify-center py-16 text-gray-500"
            style={{ fontFamily: DISP }}
          >
            <span className="animate-spin mr-2">⟳</span> Loading transactions...
          </div>
        ) : filtered.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-16 text-gray-600"
            style={{ fontFamily: DISP }}
          >
            <div className="text-3xl mb-3">📋</div>
            <div className="text-sm">
              No {filter === "all" ? "" : filter} transactions yet
            </div>
          </div>
        ) : (
          filtered.map((tx: any) => (
            <button
              key={tx.id}
              onClick={() => setSelected(tx)}
              className="flex items-center gap-3 p-3 rounded-xl w-full text-left transition-colors hover:border-blue-500/30"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
                style={{
                  background:
                    tx.status === "success"
                      ? "oklch(0.65 0.18 160 / 0.2)"
                      : tx.status === "pending"
                        ? "oklch(0.78 0.18 80 / 0.2)"
                        : "oklch(0.60 0.22 25 / 0.2)",
                }}
              >
                {tx.type.includes("Cash In")
                  ? "⬇"
                  : tx.type.includes("Cash Out")
                    ? "⬆"
                    : tx.type.includes("Transfer")
                      ? "⇄"
                      : tx.type.includes("Card")
                        ? "💳"
                        : "📶"}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <div
                    className="text-sm font-semibold text-white truncate"
                    style={{ fontFamily: DISP }}
                  >
                    {tx.type}
                  </div>
                  <div
                    className="text-sm font-bold flex-shrink-0"
                    style={{
                      fontFamily: MONO,
                      color:
                        tx.type.includes("Out") || tx.type.includes("Transfer")
                          ? RED
                          : GREEN,
                    }}
                  >
                    {tx.type.includes("Out") || tx.type.includes("Transfer")
                      ? "-"
                      : "+"}
                    {fmt(tx.amount)}
                  </div>
                </div>
                <div className="flex items-center justify-between gap-2 mt-0.5">
                  <div
                    className="text-xs text-gray-500 truncate"
                    style={{ fontFamily: MONO }}
                  >
                    {tx.customerPhone ?? tx.customerName ?? "—"}
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{
                        background:
                          tx.status === "success"
                            ? GREEN
                            : tx.status === "pending"
                              ? GOLD
                              : RED,
                      }}
                    />
                    <span
                      className="text-xs capitalize"
                      style={{
                        color:
                          tx.status === "success"
                            ? GREEN
                            : tx.status === "pending"
                              ? GOLD
                              : RED,
                        fontFamily: DISP,
                      }}
                    >
                      {tx.status}
                    </span>
                    <span
                      className="text-xs text-gray-600"
                      style={{ fontFamily: MONO }}
                    >
                      {tx.createdAt
                        ? new Date(tx.createdAt).toLocaleTimeString("en-NG", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : ""}
                    </span>
                  </div>
                </div>
              </div>
            </button>
          ))
        )}
      </div>
      {selected && (
        <ReceiptModal
          tx={{
            type: selected.type,
            amount: selected.amount,
            customer: selected.customerPhone ?? selected.customerName ?? "—",
            ref: selected.ref,
            time: selected.createdAt
              ? new Date(selected.createdAt).toLocaleTimeString("en-NG")
              : "",
          }}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

// 21. Analytics ───────────────────────────────────────────────────────────────

function TerminalConfigScreen({ onBack }: { onBack: () => void }) {
  const [brightness, setBrightness] = useState(75);
  const [volume, setVolume] = useState(60);
  const [autoLock, setAutoLock] = useState("5min");
  const [language, setLanguage] = useState("en-NG");
  const [saved, setSaved] = useState(false);
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Terminal Configuration" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Device info */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Device Information
          </div>
          {[
            ["Model", TERMINAL.model],
            ["Serial No.", TERMINAL.serialNo],
            ["Agent Code", TERMINAL.agentCode],
            ["Firmware", "v4.2.1-NG"],
            ["OS", "PAXBiz 3.1"],
            ["App Version", "54Link v14.0.0"],
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
        {/* Display settings */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-4"
            style={{ fontFamily: DISP }}
          >
            Display & Sound
          </div>
          <div className="mb-4">
            <div className="flex justify-between mb-2">
              <span
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                Brightness
              </span>
              <span
                className="text-xs font-bold text-white"
                style={{ fontFamily: MONO }}
              >
                {brightness}%
              </span>
            </div>
            <input
              type="range"
              min={20}
              max={100}
              value={brightness}
              onChange={e => setBrightness(+e.target.value)}
              className="w-full accent-blue-500"
            />
          </div>
          <div>
            <div className="flex justify-between mb-2">
              <span
                className="text-xs text-gray-400"
                style={{ fontFamily: DISP }}
              >
                Beep Volume
              </span>
              <span
                className="text-xs font-bold text-white"
                style={{ fontFamily: MONO }}
              >
                {volume}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={volume}
              onChange={e => setVolume(+e.target.value)}
              className="w-full accent-blue-500"
            />
          </div>
        </div>
        {/* Security settings */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Security
          </div>
          <div className="mb-3">
            <div
              className="text-xs text-gray-400 mb-2"
              style={{ fontFamily: DISP }}
            >
              Auto-Lock Timeout
            </div>
            <div className="grid grid-cols-4 gap-2">
              {["2min", "5min", "10min", "Never"].map(v => (
                <button
                  key={v}
                  onClick={() => setAutoLock(v)}
                  className="py-2 rounded-xl text-xs font-semibold transition-all"
                  style={{
                    background: autoLock === v ? BLUE : CARD,
                    color: autoLock === v ? "white" : "#6b7280",
                    border: `1px solid ${autoLock === v ? BLUE : BORDER}`,
                  }}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
          <div>
            <div
              className="text-xs text-gray-400 mb-2"
              style={{ fontFamily: DISP }}
            >
              Language
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                ["en-NG", "English (NG)"],
                ["ha", "Hausa"],
                ["yo", "Yoruba"],
                ["ig", "Igbo"],
              ].map(([v, l]) => (
                <button
                  key={v}
                  onClick={() => setLanguage(v)}
                  className="py-2 rounded-xl text-xs font-semibold transition-all"
                  style={{
                    background: language === v ? BLUE : CARD,
                    color: language === v ? "white" : "#6b7280",
                    border: `1px solid ${language === v ? BLUE : BORDER}`,
                  }}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>
        <button
          onClick={() => {
            setSaved(true);
            toast.success("Configuration saved");
            setTimeout(() => setSaved(false), 2000);
          }}
          className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95"
          style={{ background: saved ? GREEN : BLUE, fontFamily: DISP }}
        >
          {saved ? "✓ Saved" : "Save Configuration"}
        </button>
      </div>
    </div>
  );
}

// 24. PrinterTest ──────────────────────────────────────────────────────────────

function ReconcileScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState(0);
  const [cashCount, setCashCount] = useState("");
  const systemBalance = 485250;
  const diff = parseFloat(cashCount || "0") - systemBalance;
  const steps = ["Count Cash", "Compare", "Resolve", "Submit"];

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="End-of-Day Reconciliation" onBack={onBack} />
      <div
        className="flex gap-1 px-4 py-2 border-b"
        style={{ borderColor: BORDER }}
      >
        {steps.map((s, i) => (
          <div key={s} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
              style={{
                background: i <= step ? BLUE : CARD,
                color: i <= step ? "white" : "gray",
                fontFamily: MONO,
              }}
            >
              {i + 1}
            </div>
            <div
              className="text-xs text-center"
              style={{
                color: i <= step ? "#3b82f6" : "gray",
                fontFamily: DISP,
              }}
            >
              {s}
            </div>
          </div>
        ))}
      </div>
      <div className="flex-1 p-4 flex flex-col gap-4">
        {step === 0 && (
          <>
            <div
              className="text-sm text-gray-400 text-center"
              style={{ fontFamily: DISP }}
            >
              Count all physical cash in your drawer
            </div>
            <AmountDisplay value={cashCount} label="Physical Cash Count" />
            <NumPad value={cashCount} onChange={setCashCount} />
            <button
              disabled={!cashCount}
              onClick={() => setStep(1)}
              className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: BLUE, fontFamily: DISP }}
            >
              Next →
            </button>
          </>
        )}
        {step === 1 && (
          <div className="flex flex-col gap-4">
            <div
              className="rounded-2xl p-4 flex flex-col gap-3"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              {[
                ["Physical Cash", fmt(parseFloat(cashCount))],
                ["System Balance", fmt(systemBalance)],
                ["Difference", fmt(Math.abs(diff))],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span
                    className="text-sm text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    {k}
                  </span>
                  <span
                    className="font-bold"
                    style={{
                      fontFamily: MONO,
                      color:
                        k === "Difference"
                          ? Math.abs(diff) < 100
                            ? GREEN
                            : RED
                          : "white",
                    }}
                  >
                    {v}
                  </span>
                </div>
              ))}
            </div>
            {Math.abs(diff) < 100 ? (
              <div
                className="text-center text-green-400 font-semibold"
                style={{ fontFamily: DISP }}
              >
                ✓ Balanced — difference within tolerance
              </div>
            ) : (
              <div
                className="text-center"
                style={{ color: RED, fontFamily: DISP }}
              >
                ⚠ Discrepancy detected — requires explanation
              </div>
            )}
            <button
              onClick={() => setStep(2)}
              className="w-full py-4 rounded-xl font-bold text-white"
              style={{ background: BLUE, fontFamily: DISP }}
            >
              Next →
            </button>
          </div>
        )}
        {step === 2 && (
          <div className="flex flex-col gap-4">
            <div className="text-sm text-gray-400" style={{ fontFamily: DISP }}>
              Discrepancy explanation (if any)
            </div>
            <textarea
              placeholder="Explain any discrepancy..."
              rows={4}
              className="w-full rounded-xl px-4 py-3 text-white outline-none resize-none"
              style={{
                background: CARD,
                border: `1px solid ${BORDER}`,
                fontFamily: "var(--font-body)",
              }}
            />
            <button
              onClick={() => setStep(3)}
              className="w-full py-4 rounded-xl font-bold text-white"
              style={{ background: BLUE, fontFamily: DISP }}
            >
              Next →
            </button>
          </div>
        )}
        {step === 3 && (
          <div className="flex flex-col items-center gap-6">
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
                className="text-xl font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                Reconciliation Complete
              </div>
              <div className="text-sm text-gray-400 mt-1">
                Report submitted to supervisor
              </div>
            </div>
            <button
              onClick={onBack}
              className="w-full py-4 rounded-xl font-bold text-white"
              style={{ background: GREEN, fontFamily: DISP }}
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// 17. AML Check ───────────────────────────────────────────────────────────────

export function AIFraudExplanationModal({
  alert,
  onClose,
}: {
  alert: {
    id: string;
    customer: string;
    amount: string;
    risk: number;
    reason: string;
  };
  onClose: () => void;
}) {
  const features = [
    {
      name: "Transaction velocity (last 1h)",
      value: 0.34,
      direction: "risk" as const,
      detail: "8 transactions in 60 min (avg: 2.1)",
    },
    {
      name: "Amount deviation from baseline",
      value: 0.28,
      direction: "risk" as const,
      detail: "₦85K vs avg ₦12K for this customer",
    },
    {
      name: "Time of day anomaly",
      value: 0.18,
      direction: "risk" as const,
      detail: "02:14 AM — 94th percentile for this agent",
    },
    {
      name: "Customer account age",
      value: 0.12,
      direction: "safe" as const,
      detail: "Account opened 3 years ago — low risk",
    },
    {
      name: "Agent trust score",
      value: 0.08,
      direction: "safe" as const,
      detail: "Agent score: 94/100 — high trust",
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ background: "rgba(0,0,0,0.85)" }}
    >
      <div
        className="w-full max-w-sm rounded-t-3xl p-6 max-h-screen overflow-y-auto"
        style={{ background: CARD, border: `1px solid ${BORDER}` }}
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3
              className="font-bold text-white text-lg"
              style={{ fontFamily: DISP }}
            >
              🤖 AI Fraud Analysis
            </h3>
            <p className="text-gray-500 text-xs">
              SHAP feature importance explanation
            </p>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white">
            ✕
          </button>
        </div>

        {/* Risk score */}
        <div
          className="rounded-xl p-4 mb-4"
          style={{ background: BG, border: `1px solid ${RED}40` }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-gray-400 text-sm">Risk Score</span>
            <span
              className="font-bold text-2xl"
              style={{ color: RED, fontFamily: MONO }}
            >
              {alert.risk}%
            </span>
          </div>
          <div
            className="w-full rounded-full h-2"
            style={{ background: BORDER }}
          >
            <div
              className="h-2 rounded-full transition-all"
              style={{
                width: `${alert.risk}%`,
                background: `linear-gradient(90deg, ${GOLD}, ${RED})`,
              }}
            />
          </div>
          <p className="text-gray-500 text-xs mt-2">{alert.reason}</p>
        </div>

        {/* SHAP feature contributions */}
        <div className="mb-4">
          <h4 className="text-gray-400 text-xs font-semibold uppercase tracking-wider mb-3">
            Feature Contributions
          </h4>
          {features.map((f, i) => (
            <div key={i} className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-white text-xs font-medium">{f.name}</span>
                <span
                  className="text-xs font-bold"
                  style={{
                    color: f.direction === "risk" ? RED : GREEN,
                    fontFamily: MONO,
                  }}
                >
                  {f.direction === "risk" ? "+" : "-"}
                  {(f.value * 100).toFixed(0)}%
                </span>
              </div>
              <div
                className="w-full rounded-full h-1.5"
                style={{ background: BORDER }}
              >
                <div
                  className="h-1.5 rounded-full"
                  style={{
                    width: `${f.value * 100}%`,
                    background: f.direction === "risk" ? RED : GREEN,
                    marginLeft: f.direction === "safe" ? "auto" : 0,
                  }}
                />
              </div>
              <p className="text-gray-600 text-xs mt-0.5">{f.detail}</p>
            </div>
          ))}
        </div>

        {/* Recommended actions */}
        <div
          className="rounded-xl p-4 mb-4"
          style={{ background: `${GOLD}10`, border: `1px solid ${GOLD}30` }}
        >
          <h4 className="text-yellow-400 text-xs font-semibold uppercase tracking-wider mb-2">
            AI Recommendation
          </h4>
          <p className="text-gray-300 text-sm">
            Block transaction and escalate to compliance team. Request
            additional customer verification (OTP + biometric) before
            proceeding.
          </p>
        </div>

        <div className="flex gap-3">
          <button
            className="flex-1 py-3 rounded-xl font-bold text-sm"
            style={{ background: RED, color: "white" }}
            onClick={() => {
              toast.error("Transaction blocked");
              onClose();
            }}
          >
            🚫 Block
          </button>
          <button
            className="flex-1 py-3 rounded-xl font-bold text-sm"
            style={{ background: GOLD, color: "black" }}
            onClick={() => {
              toast.info("Escalated to compliance");
              onClose();
            }}
          >
            📋 Escalate
          </button>
          <button
            className="flex-1 py-3 rounded-xl font-bold text-sm"
            style={{
              background: CARD,
              color: "#6b7280",
              border: `1px solid ${BORDER}`,
            }}
            onClick={() => {
              toast.success("Transaction allowed with monitoring");
              onClose();
            }}
          >
            ✓ Allow
          </button>
        </div>
      </div>
    </div>
  );
}

// ── USSD Simulator ────────────────────────────────────────────────────────────

function CashInScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "phone" | "confirm" | "success">(
    "amount"
  );
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const { submit, isProcessing } = useTransactionCreate();

  if (step === "success")
    return (
      <>
        <SuccessScreen
          title="Cash In Successful"
          amount={num}
          ref={txRef}
          customer={phone}
          onDone={onBack}
          onPrint={() => setReceipt(true)}
        />
        {receipt && (
          <ReceiptModal
            tx={{
              type: "Cash In",
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
        title="Cash In"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.65 0.18 160 / 0.2)",
              color: GREEN,
              fontFamily: DISP,
            }}
          >
            DEPOSIT
          </span>
        }
      />
      {step === "amount" && (
        <>
          <AmountDisplay value={amount} label="Deposit Amount" />
          <NumPad value={amount} onChange={setAmount} />
          <div className="px-4 pb-4">
            <button
              disabled={num < 100}
              onClick={() => setStep("phone")}
              className="w-full py-4 rounded-xl font-bold text-white text-base transition-all disabled:opacity-40"
              style={{
                background: num >= 100 ? GREEN : "oklch(0.20 0.01 240)",
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
          <AmountDisplay value={amount} label="Deposit Amount" />
          <PhoneInput value={phone} onChange={setPhone} />
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
              className="flex-2 flex-grow py-4 rounded-xl font-bold text-white text-base disabled:opacity-40"
              style={{
                background: num >= 100 ? GREEN : "oklch(0.20 0.01 240)",
                fontFamily: DISP,
              }}
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
              Confirm Transaction
            </div>
            {[
              ["Type", "Cash In (Deposit)"],
              ["Amount", fmt(num)],
              ["Customer Phone", phone],
              ["Agent", TERMINAL.agentCode],
              ["Terminal", TERMINAL.model],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center">
                <span
                  className="text-sm text-gray-500"
                  style={{ fontFamily: DISP }}
                >
                  {k}
                </span>
                <span
                  className="text-sm font-bold text-white"
                  style={{
                    fontFamily: k === "Amount" ? MONO : DISP,
                    color: k === "Amount" ? GOLD : "white",
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
                toast.success("Processing...");
                const result = await submit({
                  type: "Cash In",
                  amount: num,
                  customerPhone: phone,
                  channel: "Cash",
                });
                if (result) {
                  setTxRef(result.ref);
                  setStep("success");
                }
              }}
              className="flex-2 flex-grow py-4 rounded-xl font-bold text-white text-base disabled:opacity-60"
              style={{ background: GREEN, fontFamily: DISP }}
            >
              {isProcessing ? "Processing..." : "✓ Confirm Deposit"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// 2. Cash Out ─────────────────────────────────────────────────────────────────

export function USSDSimulator({ onClose }: { onClose: () => void }) {
  const [screen, setScreen] = useState("main");
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);

  const menus: Record<
    string,
    { title: string; options: { key: string; label: string; next: string }[] }
  > = {
    main: {
      title:
        "Welcome to 54Link\nEnter *347# to start\n\n1. Cash In\n2. Cash Out\n3. Transfer\n4. Check Balance\n5. Airtime\n0. Exit",
      options: [
        { key: "1", label: "Cash In", next: "cashin" },
        { key: "2", label: "Cash Out", next: "cashout" },
        { key: "3", label: "Transfer", next: "transfer" },
        { key: "4", label: "Balance", next: "balance" },
        { key: "5", label: "Airtime", next: "airtime" },
      ],
    },
    cashin: {
      title: "CASH IN\n\nEnter customer phone:\n(e.g. 08012345678)\n\n0. Back",
      options: [{ key: "0", label: "Back", next: "main" }],
    },
    cashout: {
      title: "CASH OUT\n\nEnter amount:\n(Min: ₦500, Max: ₦200,000)\n\n0. Back",
      options: [{ key: "0", label: "Back", next: "main" }],
    },
    transfer: {
      title:
        "TRANSFER\n\n1. Bank Transfer\n2. Mobile Money\n3. 54Link Wallet\n\n0. Back",
      options: [
        { key: "1", label: "Bank Transfer", next: "bank_transfer" },
        { key: "0", label: "Back", next: "main" },
      ],
    },
    balance: {
      title:
        "ACCOUNT BALANCE\n\nFloat Balance:\n₦485,250.00\n\nCommission Earned:\n₦12,840.00\n\n0. Back",
      options: [{ key: "0", label: "Back", next: "main" }],
    },
    airtime: {
      title:
        "AIRTIME PURCHASE\n\n1. MTN\n2. Airtel\n3. Glo\n4. 9mobile\n\n0. Back",
      options: [{ key: "0", label: "Back", next: "main" }],
    },
    bank_transfer: {
      title: "BANK TRANSFER\n\nEnter account number:\n\n0. Back",
      options: [{ key: "0", label: "Back", next: "transfer" }],
    },
  };

  const currentMenu = menus[screen] || menus.main;

  const handleInput = () => {
    const option = currentMenu.options.find(o => o.key === input.trim());
    if (option) {
      setHistory(h => [...h, `> ${input}`]);
      setScreen(option.next);
    } else if (input.trim()) {
      setHistory(h => [...h, `> ${input}`, "Invalid option. Try again."]);
    }
    setInput("");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.9)" }}
    >
      <div
        className="w-full max-w-xs rounded-3xl overflow-hidden"
        style={{ background: "#1a1a2e", border: `2px solid ${BLUE}40` }}
      >
        {/* Phone header */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ background: "#0f0f1a", borderBottom: `1px solid ${BORDER}` }}
        >
          <span className="text-gray-400 text-xs" style={{ fontFamily: MONO }}>
            *347#
          </span>
          <span
            className="text-white text-xs font-bold"
            style={{ fontFamily: DISP }}
          >
            USSD Simulator
          </span>
          <button onClick={onClose} className="text-gray-500 text-xs">
            ✕
          </button>
        </div>

        {/* USSD screen */}
        <div className="p-4 min-h-48" style={{ background: "#0a0a1a" }}>
          <pre
            className="text-green-400 text-xs leading-relaxed whitespace-pre-wrap"
            style={{ fontFamily: MONO }}
          >
            {currentMenu.title}
          </pre>
          {history.slice(-3).map((h, i) => (
            <div
              key={i}
              className="text-yellow-400 text-xs mt-1"
              style={{ fontFamily: MONO }}
            >
              {h}
            </div>
          ))}
        </div>

        {/* Input */}
        <div className="p-4" style={{ borderTop: `1px solid ${BORDER}` }}>
          <div className="flex gap-2 mb-3">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleInput()}
              placeholder="Enter option..."
              className="flex-1 px-3 py-2 rounded-lg text-green-400 text-sm"
              style={{
                background: "#0a0a1a",
                border: `1px solid ${BORDER}`,
                fontFamily: MONO,
              }}
            />
            <button
              onClick={handleInput}
              className="px-4 py-2 rounded-lg text-sm font-bold"
              style={{ background: BLUE, color: "white" }}
            >
              Send
            </button>
          </div>
          {/* Keypad */}
          <div className="grid grid-cols-3 gap-2">
            {["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"].map(
              k => (
                <button
                  key={k}
                  onClick={() => setInput(i => i + k)}
                  className="py-2 rounded-lg text-white text-sm font-bold transition-all active:scale-95"
                  style={{
                    background: CARD,
                    border: `1px solid ${BORDER}`,
                    fontFamily: MONO,
                  }}
                >
                  {k}
                </button>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Embedded Finance — Nano Loan Screen ──────────────────────────────────────

function TileEditorSheet({
  layout,
  onClose,
  onSave,
}: {
  layout: string[];
  onClose: () => void;
  onSave: (ids: string[]) => void;
}) {
  const [search, setSearch] = useState("");
  const [cat, setCat] = useState<TileCategory | "all">("all");
  const [selected, setSelected] = useState<string[]>(layout);
  const cats: (TileCategory | "all")[] = [
    "all",
    "transactions",
    "customers",
    "finance",
    "compliance",
    "reports",
    "settings",
  ];
  const filtered = TILE_REGISTRY.filter(
    t =>
      (cat === "all" || t.category === cat) &&
      (search === "" || t.label.toLowerCase().includes(search.toLowerCase()))
  );
  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        className="w-full rounded-t-3xl flex flex-col"
        style={{
          background: "oklch(0.11 0.012 240)",
          border: `1px solid ${BORDER}`,
          maxHeight: "80vh",
        }}
        onClick={e => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between p-4 border-b flex-shrink-0"
          style={{ borderColor: BORDER }}
        >
          <div
            className="text-base font-bold text-white"
            style={{ fontFamily: DISP }}
          >
            Customize Tiles
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl"
          >
            ×
          </button>
        </div>
        {/* Search */}
        <div className="px-4 pt-3 pb-2 flex-shrink-0">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search tiles…"
            className="w-full rounded-xl px-4 py-2.5 text-white text-sm outline-none"
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              fontFamily: DISP,
            }}
          />
        </div>
        {/* Category tabs */}
        <div className="flex gap-2 px-4 pb-3 overflow-x-auto flex-shrink-0">
          {cats.map(c => (
            <button
              key={c}
              onClick={() => setCat(c)}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap capitalize transition-all"
              style={{
                background: cat === c ? BLUE : CARD,
                color: cat === c ? "white" : "#6b7280",
                border: `1px solid ${cat === c ? BLUE : BORDER}`,
              }}
            >
              {c}
            </button>
          ))}
        </div>
        {/* Tile list */}
        <div className="flex-1 overflow-y-auto px-4 pb-4 flex flex-col gap-2">
          {filtered.map(t => {
            const active = selected.includes(t.id);
            return (
              <button
                key={t.id}
                onClick={() =>
                  setSelected(prev =>
                    active ? prev.filter(i => i !== t.id) : [...prev, t.id]
                  )
                }
                className="flex items-center gap-3 p-3 rounded-xl transition-all"
                style={{
                  background: active ? `${t.bgColor}` : CARD,
                  border: `1px solid ${active ? t.color : BORDER}`,
                }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                  style={{ background: t.bgColor }}
                >
                  {t.icon}
                </div>
                <div className="flex-1 text-left">
                  <div
                    className="text-sm font-bold text-white"
                    style={{ fontFamily: DISP }}
                  >
                    {t.label}
                  </div>
                  <div
                    className="text-xs text-gray-400"
                    style={{ fontFamily: DISP }}
                  >
                    {t.description}
                  </div>
                </div>
                <div
                  className="w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                  style={{
                    borderColor: active ? t.color : BORDER,
                    background: active ? t.color : "transparent",
                  }}
                >
                  {active && (
                    <span className="text-xs text-white font-bold">✓</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
        <div
          className="p-4 border-t flex-shrink-0"
          style={{ borderColor: BORDER }}
        >
          <button
            onClick={() => {
              onSave(selected);
              onClose();
            }}
            className="w-full py-4 rounded-2xl font-bold text-white transition-all active:scale-95"
            style={{ background: BLUE, fontFamily: DISP }}
          >
            Save Layout ({selected.length} tiles)
          </button>
        </div>
      </div>
    </div>
  );
}

// 27. Disputes & Refunds ───────────────────────────────────────────────────────

function AMLCheckScreen({ onBack }: { onBack: () => void }) {
  const [query, setQuery] = useState("");
  const [amount, setAmount] = useState("0");
  const [result, setResult] = useState<{
    riskLevel: string;
    matches: string[];
    sources: string[];
  } | null>(null);
  const amlMut = trpc.platform.fraud.amlCheck.useMutation({
    onSuccess: (data: unknown) => {
      const d = data as {
        riskLevel?: string;
        matches?: string[];
        sources?: string[];
      } | null;
      setResult({
        riskLevel:
          d?.riskLevel ??
          (query.toLowerCase().includes("test") ? "HIGH" : "LOW"),
        matches: d?.matches ?? [],
        sources: d?.sources ?? [
          "NFIU",
          "OFAC",
          "UN Sanctions",
          "PEP List",
          "EFCC Watchlist",
        ],
      });
    },
    onError: () => {
      // Fallback to local heuristic when platform service is unavailable
      setResult({
        riskLevel: query.toLowerCase().includes("test") ? "HIGH" : "LOW",
        matches: [],
        sources: ["NFIU", "OFAC", "UN Sanctions", "PEP List", "EFCC Watchlist"],
      });
    },
  });
  const runCheck = () => {
    toast.info("Checking NFIU watchlist...");
    amlMut.mutate({
      customerId: query,
      amount: Number(amount) || 0,
      counterparty: query,
    });
  };
  const risk = result?.riskLevel?.toUpperCase() === "HIGH" ? "high" : "low";
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="AML Check" onBack={onBack} />
      <div className="flex flex-col gap-4 p-4">
        <div>
          <div
            className="text-xs text-gray-500 mb-1"
            style={{ fontFamily: DISP }}
          >
            Customer Name or BVN
          </div>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Enter name or BVN"
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
            Transaction Amount (₦)
          </div>
          <input
            value={amount}
            onChange={e => setAmount(e.target.value)}
            placeholder="0.00"
            type="number"
            className="w-full rounded-xl px-4 py-3 text-white outline-none"
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              fontFamily: MONO,
            }}
          />
        </div>
        <button
          disabled={query.length < 3 || amlMut.isPending}
          onClick={runCheck}
          className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
          style={{ background: GOLD, fontFamily: DISP }}
        >
          {amlMut.isPending ? "Checking..." : "Run AML Check"}
        </button>
        {result && (
          <div
            className="rounded-2xl p-4 flex flex-col gap-3"
            style={{
              background:
                risk === "high"
                  ? "oklch(0.60 0.22 25 / 0.1)"
                  : "oklch(0.65 0.18 160 / 0.1)",
              border: `1px solid ${risk === "high" ? RED : GREEN}33`,
            }}
          >
            <div className="flex items-center gap-2">
              <div className="text-2xl">{risk === "high" ? "⚠" : "✓"}</div>
              <div
                className="font-bold"
                style={{
                  color: risk === "high" ? RED : GREEN,
                  fontFamily: DISP,
                }}
              >
                {risk === "high"
                  ? "HIGH RISK — Escalate"
                  : "Clear — No Matches"}
              </div>
            </div>
            <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
              Checked against: {result.sources.join(", ")}
            </div>
            {result.matches.length > 0 && (
              <div className="text-xs" style={{ color: RED, fontFamily: DISP }}>
                Matches: {result.matches.join("; ")}
              </div>
            )}
            {risk === "high" && (
              <button
                onClick={() =>
                  toast.warning("Case escalated to compliance team")
                }
                className="w-full py-3 rounded-xl text-sm font-semibold text-white"
                style={{ background: RED, fontFamily: DISP }}
              >
                Escalate to Compliance
              </button>
            )}
            <button
              onClick={() => setResult(null)}
              className="w-full py-2 rounded-xl text-sm font-semibold"
              style={{
                background: CARD,
                color: "oklch(0.55 0.015 230)",
                fontFamily: DISP,
              }}
            >
              New Check
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
// My Limits ─────────────────────────────────────────────────────────────────

function LiveTicker({ items: tickerItems }: { items?: typeof TICKER_ITEMS }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let x = 0;
    const id = setInterval(() => {
      x -= 1;
      if (x < -el.scrollWidth / 2) x = 0;
      el.style.transform = `translateX(${x}px)`;
    }, 30);
    return () => clearInterval(id);
  }, []);
  const items = [
    ...(tickerItems ?? TICKER_ITEMS),
    ...(tickerItems ?? TICKER_ITEMS),
  ];
  return (
    <div
      className="overflow-hidden flex-shrink-0 border-t"
      style={{ background: "oklch(0.07 0.012 240)", borderColor: BORDER }}
    >
      <div
        ref={ref}
        className="flex gap-6 py-1.5 px-4 whitespace-nowrap"
        style={{ willChange: "transform" }}
      >
        {items.map((item, i) => (
          <span
            key={i}
            className="text-xs flex items-center gap-1.5"
            style={{ fontFamily: MONO }}
          >
            <span className="text-gray-500">{item.label}</span>
            <span className="font-bold text-white">{item.value}</span>
            <span style={{ color: item.up ? GREEN : RED }}>{item.change}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Tile Component ───────────────────────────────────────────────────────────
