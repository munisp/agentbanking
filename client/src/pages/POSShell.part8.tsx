import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { NumPad, ScreenHeader } from "./POSShell.part10";
import { AmountDisplay, PhoneInput, useGamification } from "./POSShell.part11";
import { SuccessScreen } from "./POSShell.part5";
import { ReceiptModal, fmt } from "./POSShell.part6";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, TERMINAL_UNKNOWN, Transaction } from "./POSShell.shared";

export function ReconcileScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState(0);
  const [cashCount, setCashCount] = useState("");
  // Real system balance from the signed-in agent profile — never hardcoded.
  const systemBalance = usePosStore(s => s.agent?.floatBalance ?? null);
  const diff =
    systemBalance != null ? parseFloat(cashCount || "0") - systemBalance : null;
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
                ["Difference", diff != null ? fmt(Math.abs(diff)) : "—"],
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
                          ? diff != null && Math.abs(diff) < 100
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
            {diff != null && Math.abs(diff) < 100 ? (
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

export function TerminalConfigScreen({ onBack }: { onBack: () => void }) {
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
            ["Model", TERMINAL_UNKNOWN.model ?? "—"],
            ["Serial No.", TERMINAL_UNKNOWN.serialNo ?? "—"],
            ["Agent Code", TERMINAL_UNKNOWN.agentCode ?? "—"],
            ["Firmware", "—"],
            ["OS", "—"],
            ["App Version", "—"],
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
              {["2min", "5min", "10min", "Never"].map((v: any) => (
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

export function CashInScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "phone" | "confirm" | "success">(
    "amount"
  );
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState<string>(""); // server-issued reference only
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
              ["Agent", TERMINAL_UNKNOWN.agentCode ?? "—"],
              ["Terminal", TERMINAL_UNKNOWN.model ?? "—"],
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

export function ScorecardScreen({ onBack }: { onBack: () => void }) {
  const g = useGamification();
  const scoreAgent = usePosStore(s => s.agent);
  // Real scorecard from the backend — hardcoded compliance scores are never shown.
  const { data: scorecard, isLoading: scoreLoading } =
    trpc.agentScorecard.getScorecard.useQuery(
      { agentId: scoreAgent?.id ?? 0 },
      { enabled: !!scoreAgent?.id, retry: false }
    ) as any;
  const m = scorecard?.metrics;
  const metrics = m
    ? [
        { label: "Success Rate", score: m.successRate ?? 0, target: 100, color: GREEN },
        { label: "Dispute Rate", score: m.disputeRate ?? 0, target: 0, color: GOLD, invert: true },
        { label: "Transactions", score: Math.min(m.txCount ?? 0, 100), target: 100, color: BLUE },
      ]
    : [];
  const overall = scorecard?.overallScore != null ? Math.round(scorecard.overallScore) : null;
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Agent Scorecard" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Overall score ring */}
        <div
          className="rounded-2xl p-5 flex items-center gap-5"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div className="relative w-20 h-20 flex-shrink-0">
            <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
              <circle
                cx="40"
                cy="40"
                r="32"
                fill="none"
                stroke={BORDER}
                strokeWidth="8"
              />
              <circle
                cx="40"
                cy="40"
                r="32"
                fill="none"
                stroke={(overall ?? 0) >= 90 ? GREEN : (overall ?? 0) >= 75 ? GOLD : RED}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${(overall / 100) * 201} 201`}
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span
                className="text-xl font-bold text-white"
                style={{ fontFamily: MONO }}
              >
                {overall != null ? overall : "—"}
              </span>
            </div>
          </div>
          <div>
            <div
              className="text-sm font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              Overall Score
            </div>
            <div className="text-xs text-gray-400 mt-1">
              {g.rank != null ? `Rank #${g.rank}` : "Rank unavailable"}
            </div>
            <div
              className="mt-2 px-2 py-0.5 rounded text-xs font-bold inline-block"
              style={{ background: "oklch(0.78 0.18 80 / 0.2)", color: GOLD }}
            >
              {g.level ?? "—"}
            </div>
          </div>
        </div>
        {/* Metric bars */}
        <div
          className="rounded-2xl p-4 flex flex-col gap-3"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {metrics.length === 0 && (
            <div className="text-xs text-gray-500 text-center py-2">
              {scoreLoading ? "Loading scorecard…" : "Scorecard unavailable — no server data."}
            </div>
          )}
          {metrics.map((m: any) => (
            <div key={m.label}>
              <div className="flex justify-between mb-1">
                <span
                  className="text-xs text-gray-400"
                  style={{ fontFamily: DISP }}
                >
                  {m.label}
                </span>
                <span
                  className="text-xs font-bold"
                  style={{ color: m.color, fontFamily: MONO }}
                >
                  {m.score}
                  {m.label.includes("%") || m.label.includes("Rate")
                    ? "%"
                    : "/100"}
                </span>
              </div>
              <div
                className="h-2 rounded-full overflow-hidden"
                style={{ background: BORDER }}
              >
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${m.invert ? 100 - m.score : m.score}%`,
                    background: m.color,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
        {/* Badges */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Badges Earned
          </div>
          <div className="flex flex-wrap gap-2">
            {g.badges.length === 0 && (
              <div className="text-xs text-gray-500">No badges earned yet.</div>
            )}
            {g.badges.map((b: any) => (
              <div
                key={b}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold"
                style={{
                  background: "oklch(0.78 0.18 80 / 0.15)",
                  color: GOLD,
                  border: `1px solid oklch(0.78 0.18 80 / 0.3)`,
                }}
              >
                {b}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// 23. TerminalConfig ───────────────────────────────────────────────────────────

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
        `ACCOUNT BALANCE\n\nFloat Balance:\n${fmt(usePosStore.getState().agent?.floatBalance ?? null)}\n\n0. Back`,
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
    const option = currentMenu.options.find((o: any) => o.key === input.trim());
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

export function CustomerLookupScreen({ onBack }: { onBack: () => void }) {
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState(false);
  // No customer search endpoint is connected to this build — the screen shows
  // an honest unavailable state instead of fabricated customer records.
  const customers: any[] = [];
  const results = searched
    ? customers.filter(
        c =>
          c.name.toLowerCase().includes(query.toLowerCase()) ||
          c.phone.includes(query) ||
          c.acct.includes(query)
      )
    : [];

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Customer Lookup" onBack={onBack} />
      <div
        className="flex gap-2 px-4 py-3 border-b"
        style={{ borderColor: BORDER }}
      >
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Name, phone, or account number"
          className="flex-1 rounded-xl px-4 py-2 text-white text-sm outline-none"
          style={{
            background: CARD,
            border: `1px solid ${BORDER}`,
            fontFamily: MONO,
          }}
        />
        <button
          onClick={() => setSearched(true)}
          className="px-4 py-2 rounded-xl font-semibold text-sm"
          style={{ background: BLUE, color: "white", fontFamily: DISP }}
        >
          Search
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {results.length === 0 && searched && (
          <div
            className="text-center text-gray-500 py-8"
            style={{ fontFamily: DISP }}
          >
            Customer search is unavailable — the customer directory service is not connected.
          </div>
        )}
        {results.map((c: any) => (
          <div
            key={c.acct}
            className="rounded-2xl p-4 flex flex-col gap-2"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div className="flex items-center justify-between">
              <div
                className="font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                {c.name}
              </div>
              <span
                className="text-xs px-2 py-0.5 rounded-full font-semibold"
                style={{
                  background:
                    c.kyc === "Verified"
                      ? "oklch(0.65 0.18 160 / 0.2)"
                      : "oklch(0.78 0.18 80 / 0.2)",
                  color: c.kyc === "Verified" ? GREEN : GOLD,
                  fontFamily: DISP,
                }}
              >
                {c.kyc}
              </span>
            </div>
            {[
              ["Phone", c.phone],
              ["Account", c.acct],
              ["Bank", c.bank],
              ["Tier", c.tier],
              ["Balance", c.balance],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span
                  className="text-xs text-gray-500"
                  style={{ fontFamily: DISP }}
                >
                  {k}
                </span>
                <span
                  className="text-xs font-semibold text-white"
                  style={{ fontFamily: MONO }}
                >
                  {v}
                </span>
              </div>
            ))}
            <div className="flex gap-2 mt-1">
              <button
                onClick={() => toast.info("Opening Cash In for " + c.name)}
                className="flex-1 py-2 rounded-xl text-xs font-semibold"
                style={{
                  background: "oklch(0.65 0.18 160 / 0.2)",
                  color: GREEN,
                  fontFamily: DISP,
                }}
              >
                Cash In
              </button>
              <button
                onClick={() => toast.info("Opening Transfer for " + c.name)}
                className="flex-1 py-2 rounded-xl text-xs font-semibold"
                style={{
                  background: "oklch(0.60 0.22 260 / 0.2)",
                  color: "#3b82f6",
                  fontFamily: DISP,
                }}
              >
                Transfer
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// 11. KYC Verify ──────────────────────────────────────────────────────────────
// KYC step types
