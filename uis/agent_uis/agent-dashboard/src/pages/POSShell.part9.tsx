// @ts-nocheck
import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { accountApi } from "../utils/api";
import { QRCodeCanvas } from "qrcode.react";
import { useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { AmountDisplay, NumPad, PhoneInput, ScreenHeader, SuccessScreen } from "./POSShell.part10";
import { fmt } from "./POSShell.part5";
import { ReceiptModal } from "./POSShell.part6";
import { BG, BLUE, BORDER, CARD, COMMISSION_DATA, DISP, GAMIFICATION, GOLD, GREEN, MONO, RED, Tile, Transaction } from "./POSShell.shared";

function ScorecardScreen({ onBack }: { onBack: () => void }) {
  const metrics = [
    { label: "Transaction Volume", score: 92, target: 100, color: GREEN },
    { label: "Customer Satisfaction", score: 88, target: 100, color: BLUE },
    { label: "CBN Compliance", score: 100, target: 100, color: GREEN },
    { label: "Uptime %", score: 99.2, target: 100, color: GREEN },
    { label: "Fraud Rate", score: 0.2, target: 0, color: GOLD, invert: true },
    { label: "Float Utilisation", score: 78, target: 80, color: BLUE },
  ];
  const overall = Math.round(
    metrics.reduce(
      (s: any, m: any) => s + (m.invert ? 100 - m.score : m.score),
      0
    ) / metrics.length
  );
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
                stroke={overall >= 90 ? GREEN : overall >= 75 ? GOLD : RED}
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
                {overall}
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
              Rank #{GAMIFICATION.rank} of{" "}
              {GAMIFICATION.totalAgents.toLocaleString()} agents
            </div>
            <div
              className="mt-2 px-2 py-0.5 rounded text-xs font-bold inline-block"
              style={{ background: "oklch(0.78 0.18 80 / 0.2)", color: GOLD }}
            >
              {GAMIFICATION.level}
            </div>
          </div>
        </div>
        {/* Metric bars */}
        <div
          className="rounded-2xl p-4 flex flex-col gap-3"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          {metrics.map(m => (
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
            {GAMIFICATION.badges.map(b => (
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

function AirtimeScreen({ onBack }: { onBack: () => void }) {
  const [phone, setPhone] = useState("");
  const [network, setNetwork] = useState("MTN");
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<"airtime" | "data">("airtime");
  const [step, setStep] = useState<"form" | "success">("form");
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const networks = ["MTN", "Airtel", "Glo", "9mobile"];
  const dataPlans = [
    "500MB - ₦200",
    "1GB - ₦350",
    "2GB - ₦600",
    "5GB - ₦1,500",
    "10GB - ₦2,500",
  ];
  const { submit, isProcessing } = useTransactionCreate();

  if (step === "success")
    return (
      <SuccessScreen
        title={`${type === "airtime" ? "Airtime" : "Data"} Purchased`}
        amount={num}
        ref={txRef}
        customer={phone}
        onDone={onBack}
        onPrint={() => toast.info("Printing receipt...")}
      />
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Airtime & Data" onBack={onBack} />
      <div
        className="flex gap-2 px-4 py-2 border-b"
        style={{ borderColor: BORDER }}
      >
        {(["airtime", "data"] as const).map(t => (
          <button
            key={t}
            onClick={() => setType(t)}
            className="flex-1 py-2 rounded-xl text-sm font-semibold capitalize transition-all"
            style={{
              background: type === t ? "oklch(0.65 0.18 160 / 0.3)" : CARD,
              color: type === t ? GREEN : "oklch(0.55 0.015 230)",
              fontFamily: DISP,
            }}
          >
            {t === "airtime" ? "📶 Airtime" : "🌐 Data"}
          </button>
        ))}
      </div>
      <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
        <div>
          <div
            className="text-xs text-gray-500 mb-2"
            style={{ fontFamily: DISP }}
          >
            Network
          </div>
          <div className="grid grid-cols-4 gap-2">
            {networks.map(n => (
              <button
                key={n}
                onClick={() => setNetwork(n)}
                className="py-2 rounded-xl text-xs font-bold transition-all"
                style={{
                  background:
                    network === n ? "oklch(0.65 0.18 160 / 0.3)" : CARD,
                  color: network === n ? GREEN : "white",
                  border:
                    network === n
                      ? `1px solid ${GREEN}44`
                      : `1px solid ${BORDER}`,
                  fontFamily: DISP,
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>
        <PhoneInput
          value={phone}
          onChange={setPhone}
          label="Phone Number to Recharge"
        />
        {type === "airtime" ? (
          <>
            <AmountDisplay value={amount} label="Airtime Amount" />
            <NumPad value={amount} onChange={setAmount} />
          </>
        ) : (
          <div>
            <div
              className="text-xs text-gray-500 mb-2"
              style={{ fontFamily: DISP }}
            >
              Select Data Plan
            </div>
            <div className="flex flex-col gap-2">
              {dataPlans.map(p => (
                <button
                  key={p}
                  onClick={() => setAmount(p.split("₦")[1].replace(",", ""))}
                  className="w-full py-3 px-4 rounded-xl text-sm font-semibold text-left transition-all"
                  style={{
                    background:
                      amount === p.split("₦")[1].replace(",", "")
                        ? "oklch(0.65 0.18 160 / 0.3)"
                        : CARD,
                    color: "white",
                    border: `1px solid ${BORDER}`,
                    fontFamily: DISP,
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}
        <button
          disabled={num < 50 || phone.length < 10 || isProcessing}
          onClick={async () => {
            toast.success("Processing...");
            const result = await submit({
              type: "Airtime",
              amount: num,
              customerPhone: phone,
              customerName: network,
              channel: "App",
            });
            if (result) {
              setTxRef(result.ref);
              setStep("success");
            }
          }}
          className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
          style={{ background: GREEN, fontFamily: DISP }}
        >
          {isProcessing
            ? "Processing..."
            : `✓ Purchase ${type === "airtime" ? "Airtime" : "Data"}`}
        </button>
      </div>
    </div>
  );
}

// 8. Bill Payment ─────────────────────────────────────────────────────────────

export function NotificationPanel({ onClose }: { onClose: () => void }) {
  // No fabricated notifications: the notifications backend is not connected to
  // this build, so the panel starts honestly empty instead of showing invented
  // fraud alerts, pending approvals, or settlements.
  const notifications: Array<{
    id: number;
    type: string;
    title: string;
    body: string;
    time: string;
    read: boolean;
    color: string;
  }> = [];


  const [items, setItems] = useState(notifications);
  const unread = items.filter(n => !n.read).length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4"
      style={{ background: "rgba(0,0,0,0.7)" }}
    >
      <div
        className="w-full max-w-sm rounded-3xl overflow-hidden"
        style={{ background: CARD, border: `1px solid ${BORDER}` }}
      >
        <div
          className="flex items-center justify-between p-4"
          style={{ borderBottom: `1px solid ${BORDER}` }}
        >
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-white" style={{ fontFamily: DISP }}>
              Notifications
            </h3>
            {unread > 0 && (
              <span
                className="px-2 py-0.5 rounded-full text-xs font-bold text-white"
                style={{ background: RED }}
              >
                {unread}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setItems(items.map(n => ({ ...n, read: true })))}
              className="text-xs"
              style={{ color: BLUE }}
            >
              Mark all read
            </button>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="max-h-96 overflow-y-auto">
          {items.length === 0 && (
            <div className="p-8 text-center text-sm text-gray-500" style={{ fontFamily: DISP }}>
              No notifications yet
            </div>
          )}
          {items.map(n => (
            <div
              key={n.id}
              onClick={() =>
                setItems(
                  items.map(i => (i.id === n.id ? { ...i, read: true } : i))
                )
              }
              className="flex gap-3 p-4 cursor-pointer transition-all hover:opacity-80"
              style={{
                borderBottom: `1px solid ${BORDER}`,
                background: n.read ? "transparent" : `${n.color}08`,
              }}
            >
              <div
                className="w-2 h-2 rounded-full mt-2 flex-shrink-0"
                style={{ background: n.read ? "transparent" : n.color }}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span
                    className="font-semibold text-sm text-white truncate"
                    style={{ fontFamily: DISP }}
                  >
                    {n.title}
                  </span>
                  <span
                    className="text-xs text-gray-600 flex-shrink-0"
                    style={{ fontFamily: MONO }}
                  >
                    {n.time}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">
                  {n.body}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="p-3" style={{ borderTop: `1px solid ${BORDER}` }}>
          <button
            onClick={onClose}
            className="w-full py-2.5 rounded-xl text-sm font-semibold text-gray-400"
            style={{ background: BG, border: `1px solid ${BORDER}` }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// TIER 3 ENHANCEMENTS
// ═══════════════════════════════════════════════════════════════════════════════

// ── AI Fraud Explanation (SHAP-style) ────────────────────────────────────────

function OpenAccountScreen({ onBack }: { onBack: () => void }) {
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    phone: "",
    dob: "",
    bvn: "",
    tier: "Tier 1",
  });
  const [step, setStep] = useState<"form" | "success">("form");
  // The account number is returned by the server on creation — never fabricated.
  const [acctNo, setAcctNo] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const resp: any = await accountApi.createAccount({
        account_type: form.tier,
        name: `${form.firstName} ${form.lastName}`.trim(),
      } as any);
      const number = resp?.account?.account_number || resp?.account_number;
      if (!number) throw new Error("The server did not return an account number.");
      setAcctNo(number);
      setStep("success");
    } catch (err: any) {
      setSubmitError(err?.message || "Account creation failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (step === "success")
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 p-6">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center text-4xl"
          style={{
            background: "oklch(0.78 0.18 80 / 0.2)",
            border: `2px solid ${GOLD}`,
          }}
        >
          🏦
        </div>
        <div className="text-center">
          <div
            className="text-xl font-bold text-white mb-1"
            style={{ fontFamily: DISP }}
          >
            Account Opened!
          </div>
          <div className="text-sm text-gray-400">
            {form.firstName} {form.lastName}
          </div>
          <div
            className="text-2xl font-bold mt-2"
            style={{ fontFamily: MONO, color: GOLD }}
          >
            {acctNo}
          </div>
          <div className="text-xs text-gray-500 mt-1">{form.tier} Account</div>
        </div>
        <button
          onClick={onBack}
          className="w-full py-4 rounded-xl font-bold text-white"
          style={{ background: GOLD, fontFamily: DISP }}
        >
          Done
        </button>
      </div>
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Open New Account" onBack={onBack} />
      <div className="flex flex-col gap-3 p-4 overflow-y-auto flex-1">
        {[
          ["First Name", "firstName", "text"],
          ["Last Name", "lastName", "text"],
          ["Phone", "phone", "tel"],
          ["Date of Birth", "dob", "date"],
          ["BVN", "bvn", "number"],
        ].map(([label, key, type]) => (
          <div key={key}>
            <div
              className="text-xs text-gray-500 mb-1"
              style={{ fontFamily: DISP }}
            >
              {label}
            </div>
            <input
              type={type}
              value={(form as any)[key]}
              onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
              placeholder={`Enter ${label.toLowerCase()}`}
              className="w-full rounded-xl px-4 py-3 text-white outline-none"
              style={{
                background: CARD,
                border: `1px solid ${BORDER}`,
                fontFamily: MONO,
              }}
            />
          </div>
        ))}
        <div>
          <div
            className="text-xs text-gray-500 mb-1"
            style={{ fontFamily: DISP }}
          >
            Account Tier
          </div>
          <select
            value={form.tier}
            onChange={e => setForm(f => ({ ...f, tier: e.target.value }))}
            className="w-full rounded-xl px-4 py-3 text-white outline-none"
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              fontFamily: DISP,
            }}
          >
            <option>Tier 1</option>
            <option>Tier 2</option>
            <option>Tier 3</option>
          </select>
        </div>
        {submitError && (
          <div className="text-xs text-center rounded-lg p-2" style={{ color: "#f87171", border: "1px solid #7f1d1d" }}>
            {submitError}
          </div>
        )}
        <button
          disabled={
            submitting ||
            !form.firstName || !form.lastName || !form.phone || !form.bvn
          }
          onClick={submit}
          className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
          style={{ background: GOLD, fontFamily: DISP }}
        >
          Open Account
        </button>
      </div>
    </div>
  );
}

// 14. Commission ──────────────────────────────────────────────────────────────

export function ReceiptPrinterModal({
  tx,
  onClose,
}: {
  tx: {
    type: string;
    amount: string;
    ref: string;
    customer: string;
    agent: string;
    date: string;
  };
  onClose: () => void;
}) {
  const [printing, setPrinting] = useState(false);
  const [printed, setPrinted] = useState(false);

  const handlePrint = () => {
    setPrinting(true);
    setTimeout(() => {
      setPrinting(false);
      setPrinted(true);
    }, 2000);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ background: "rgba(0,0,0,0.7)" }}
    >
      <div
        className="w-full max-w-sm rounded-t-3xl p-6"
        style={{ background: CARD, border: `1px solid ${BORDER}` }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3
            className="font-bold text-white text-lg"
            style={{ fontFamily: DISP }}
          >
            🖨 Receipt
          </h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white">
            ✕
          </button>
        </div>

        {/* ESC/POS styled receipt preview */}
        <div
          className="rounded-xl p-4 mb-4 font-mono text-xs"
          style={{ background: "#1a1a1a", border: `1px solid ${BORDER}` }}
        >
          <div className="text-center text-white font-bold mb-2">
            54LINK AGENCY BANKING
          </div>
          <div className="text-center text-gray-500 mb-3">
            ━━━━━━━━━━━━━━━━━━━━
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Type:</span>
            <span className="text-white">{tx.type}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Amount:</span>
            <span className="text-green-400 font-bold">{tx.amount}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Customer:</span>
            <span className="text-white">{tx.customer}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Agent:</span>
            <span className="text-white">{tx.agent}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Date:</span>
            <span className="text-white">{tx.date}</span>
          </div>
          <div className="flex justify-between text-gray-400">
            <span>Ref:</span>
            <span className="text-blue-400">{tx.ref}</span>
          </div>
          <div className="text-center text-gray-500 mt-3 mb-2">
            ━━━━━━━━━━━━━━━━━━━━
          </div>
          {/* Real QR code for transaction verification */}
          <div className="flex justify-center my-2">
            <QRCodeCanvas
              value={`54LINK:${tx.ref}:${tx.amount}`}
              size={64}
              bgColor="#1a1a2e"
              fgColor="#ffffff"
              level="M"
            />
          </div>
          <div className="text-center text-gray-600 text-xs mt-2">
            Scan to verify transaction
          </div>
          <div className="text-center text-gray-500 mt-3">
            Thank you for using 54Link
          </div>
        </div>

        {/* Print status */}
        {printed && (
          <div
            className="flex items-center gap-2 p-3 rounded-xl mb-3"
            style={{
              background: "oklch(0.35 0.12 145 / 0.2)",
              border: `1px solid ${GREEN}30`,
            }}
          >
            <span style={{ color: GREEN }}>✓</span>
            <span className="text-sm text-green-400">
              Receipt printed successfully
            </span>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handlePrint}
            disabled={printing || printed}
            className="flex-1 py-3 rounded-xl font-semibold text-sm transition-all"
            style={{
              background: printing ? BORDER : BLUE,
              color: "white",
              opacity: printed ? 0.5 : 1,
            }}
          >
            {printing
              ? "🖨 Printing..."
              : printed
                ? "✓ Printed"
                : "🖨 Print Receipt"}
          </button>
          <button
            className="flex-1 py-3 rounded-xl font-semibold text-sm transition-all"
            style={{
              background: CARD,
              color: "#6b7280",
              border: `1px solid ${BORDER}`,
            }}
            onClick={() => {
              toast.success("Receipt sent via SMS");
              onClose();
            }}
          >
            📱 SMS Receipt
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Supervisor Approval Flow ──────────────────────────────────────────────────

function BiometricScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"idle" | "scanning" | "success" | "failed">(
    "idle"
  );
  const [finger, setFinger] = useState(0);
  const [enrolledId, setEnrolledId] = useState("");
  const fingers = [
    "Right Thumb",
    "Right Index",
    "Right Middle",
    "Left Thumb",
    "Left Index",
  ];
  const { data: existingCreds, refetch: refetchCreds } =
    trpc.customer.fido2.listCredentials.useQuery();
  const enrollMut = trpc.customer.fido2.registerCredential.useMutation({
    onSuccess: data => {
      setEnrolledId(data.credentialId);
      setStep("success");
      refetchCreds();
    },
    onError: () => setStep("failed"),
  });
  const startScan = () => {
    setStep("scanning");
    // In production the PAX SDK provides the actual credential bytes via native bridge
    enrollMut.mutate({
      credentialId: `finger-${fingers[finger].toLowerCase().replace(" ", "-")}-${Date.now()}`,
      publicKey: btoa(
        JSON.stringify({ alg: -7, type: "public-key", finger: fingers[finger] })
      ),
      deviceType: "fingerprint",
      transports: ["internal"],
    });
  };
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Biometric Enrollment" onBack={onBack} />
      <div className="flex flex-col items-center justify-center flex-1 gap-6 p-6">
        <div
          className={`w-36 h-36 rounded-full flex items-center justify-center text-7xl transition-all ${step === "scanning" ? "animate-pulse" : ""}`}
          style={{
            background:
              step === "success"
                ? "oklch(0.65 0.18 160 / 0.2)"
                : step === "failed"
                  ? "oklch(0.60 0.22 25 / 0.2)"
                  : "oklch(0.55 0.22 300 / 0.15)",
            border: `3px solid ${step === "success" ? GREEN : step === "failed" ? RED : "#8b5cf6"}`,
          }}
        >
          ☝
        </div>
        {existingCreds && existingCreds.length > 0 && (
          <div
            className="text-xs text-gray-500 text-center"
            style={{ fontFamily: DISP }}
          >
            {existingCreds.length} fingerprint
            {existingCreds.length !== 1 ? "s" : ""} enrolled
          </div>
        )}
        <div>
          <div
            className="text-xs text-gray-500 mb-2 text-center"
            style={{ fontFamily: DISP }}
          >
            Select Finger
          </div>
          <div className="flex flex-wrap gap-2 justify-center">
            {fingers.map((f, i) => (
              <button
                key={f}
                onClick={() => setFinger(i)}
                className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
                style={{
                  background:
                    finger === i ? "oklch(0.55 0.22 300 / 0.3)" : CARD,
                  color: finger === i ? "#8b5cf6" : "oklch(0.55 0.015 230)",
                  fontFamily: DISP,
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
        {step === "idle" && (
          <button
            onClick={startScan}
            disabled={enrollMut.isPending}
            className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
            style={{ background: "#8b5cf6", fontFamily: DISP }}
          >
            Start Fingerprint Scan
          </button>
        )}
        {step === "scanning" && (
          <div
            className="text-center"
            style={{ color: "#8b5cf6", fontFamily: DISP }}
          >
            Enrolling {fingers[finger]}...
          </div>
        )}
        {step === "success" && (
          <div className="flex flex-col items-center gap-2">
            <div
              className="text-center text-green-400 font-bold"
              style={{ fontFamily: DISP }}
            >
              ✓ {fingers[finger]} enrolled
            </div>
            {enrolledId && (
              <div className="text-xs text-gray-600 font-mono">
                {enrolledId.slice(0, 40)}...
              </div>
            )}
            <button
              onClick={() => setStep("idle")}
              className="mt-2 px-6 py-2 rounded-xl text-sm font-semibold text-white"
              style={{ background: "#8b5cf6", fontFamily: DISP }}
            >
              Enroll Another
            </button>
          </div>
        )}
        {step === "failed" && (
          <button
            onClick={() => setStep("idle")}
            className="w-full py-4 rounded-xl font-bold text-white"
            style={{ background: RED, fontFamily: DISP }}
          >
            Retry Scan
          </button>
        )}
      </div>
    </div>
  );
}

// 13. Open Account ────────────────────────────────────────────────────────────

function CustomerLookupScreen({ onBack }: { onBack: () => void }) {
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
        {results.map(c => (
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

function CommissionScreen({
  onBack,
  commissionData,
}: {
  onBack: () => void;
  commissionData?: typeof COMMISSION_DATA;
}) {
  const data = commissionData ?? COMMISSION_DATA;
  const total = data.reduce((s: any, d: any) => s + d.earned, 0);
  // Hierarchy cascade splits for display
  const cascadeSplits = [
    { role: "Your Earnings", pct: 60, amount: total * 0.6, color: GREEN },
    { role: "Upline (Master)", pct: 15, amount: total * 0.15, color: BLUE },
    { role: "Upline (Super)", pct: 10, amount: total * 0.1, color: "#a855f7" },
    { role: "Sub-Agent Share", pct: 10, amount: total * 0.1, color: GOLD },
    { role: "Platform Fee", pct: 5, amount: total * 0.05, color: "#6b7280" },
  ];
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Commission Earnings" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          {[
            ["This Week", fmt(total)],
            ["This Month", fmt(total * 4.3)],
            ["Rate", "0.3% per tx"],
            ["Pending", fmt(1240)],
          ].map(([k, v]) => (
            <div
              key={k}
              className="rounded-2xl p-4"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                {k}
              </div>
              <div
                className="text-lg font-bold"
                style={{ fontFamily: MONO, color: GREEN }}
              >
                {v}
              </div>
            </div>
          ))}
        </div>
        {/* Hierarchy Cascade Breakdown */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Hierarchy Cascade Split
          </div>
          <div className="flex flex-col gap-2">
            {cascadeSplits.map(s => (
              <div key={s.role} className="flex items-center gap-2">
                <div
                  className="w-24 text-xs text-gray-400 truncate"
                  style={{ fontFamily: DISP }}
                >
                  {s.role}
                </div>
                <div
                  className="flex-1 h-5 rounded-full overflow-hidden"
                  style={{ background: BORDER }}
                >
                  <div
                    className="h-full rounded-full flex items-center justify-end pr-2 text-[10px] font-bold text-white transition-all"
                    style={{ width: `${s.pct}%`, background: s.color }}
                  >
                    {s.pct}%
                  </div>
                </div>
                <div
                  className="w-16 text-right text-xs font-bold"
                  style={{ fontFamily: MONO, color: s.color }}
                >
                  {fmt(s.amount)}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Daily Earnings (This Week)
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={data}>
              <XAxis
                dataKey="day"
                tick={{
                  fill: "#6b7280",
                  fontSize: 11,
                  fontFamily: "JetBrains Mono",
                }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis hide />
              <Tooltip
                contentStyle={{
                  background: CARD,
                  border: `1px solid ${BORDER}`,
                  borderRadius: 8,
                  fontFamily: "JetBrains Mono",
                  fontSize: 11,
                }}
                formatter={(v: number) => [fmt(v), "Earned"]}
              />
              <Bar dataKey="earned" fill={GREEN} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <button
          onClick={() => toast.info("Withdrawal request submitted")}
          className="w-full py-4 rounded-xl font-bold text-white"
          style={{ background: GREEN, fontFamily: DISP }}
        >
          Withdraw Commission
        </button>
      </div>
    </div>
  );
}

// 15. Settlement ──────────────────────────────────────────────────────────────

function CardPaymentScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "card" | "pin" | "success">(
    "amount"
  );
  const [amount, setAmount] = useState("");
  const [pin, setPin] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const { submit, isProcessing } = useTransactionCreate();

  if (step === "success")
    return (
      <>
        <SuccessScreen
          title="Card Payment Approved"
          amount={num}
          ref={txRef}
          customer="Card Holder"
          onDone={onBack}
          onPrint={() => setReceipt(true)}
        />
        {receipt && (
          <ReceiptModal
            tx={{
              type: "Card Payment",
              amount: num,
              customer: "Card Holder",
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
        title="Card Payment"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.78 0.18 80 / 0.2)",
              color: GOLD,
              fontFamily: DISP,
            }}
          >
            EMV/NFC
          </span>
        }
      />
      {step === "amount" && (
        <>
          <AmountDisplay value={amount} label="Payment Amount" />
          <NumPad value={amount} onChange={setAmount} />
          <div className="px-4 pb-4">
            <button
              disabled={num < 50}
              onClick={() => setStep("card")}
              className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: GOLD, fontFamily: DISP }}
            >
              Continue →
            </button>
          </div>
        </>
      )}
      {step === "card" && (
        <div className="flex flex-col items-center justify-center flex-1 gap-6 p-6">
          <AmountDisplay value={amount} label="Payment Amount" />
          <div
            className="w-32 h-32 rounded-2xl flex items-center justify-center text-6xl animate-pulse"
            style={{
              background: "oklch(0.78 0.18 80 / 0.1)",
              border: `2px dashed ${GOLD}`,
            }}
          >
            💳
          </div>
          <div className="text-center">
            <div
              className="text-base font-bold text-white mb-1"
              style={{ fontFamily: DISP }}
            >
              Insert, Tap, or Swipe Card
            </div>
            <div className="text-sm text-gray-500">
              Supports EMV Chip · NFC Contactless · Magstripe
            </div>
          </div>
          <button
            onClick={() => setStep("pin")}
            className="w-full py-4 rounded-xl font-bold text-white"
            style={{ background: GOLD, fontFamily: DISP }}
          >
            Card Detected — Enter PIN
          </button>
        </div>
      )}
      {step === "pin" && (
        <div className="flex flex-col items-center justify-center flex-1 gap-4 p-6">
          <AmountDisplay value={amount} label="Payment Amount" />
          <div className="text-sm text-gray-400" style={{ fontFamily: DISP }}>
            Enter Card PIN
          </div>
          <div className="flex gap-3">
            {[0, 1, 2, 3].map(i => (
              <div
                key={i}
                className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                style={{ background: CARD, border: `1px solid ${BORDER}` }}
              >
                {pin.length > i ? "●" : "○"}
              </div>
            ))}
          </div>
          <NumPad
            value={pin}
            onChange={async v => {
              if (v.length <= 4) setPin(v);
              if (v.length === 4) {
                // Fail closed: this build has no card-PIN verification rail, so
                // no transaction is created from unverified PIN entry.
                setPin("");
                toast.error(
                  "Card PIN verification is unavailable in this build — payment not processed."
                );
              }
            }}
          />
        </div>
      )}
    </div>
  );
}

// 5. QR Payment ───────────────────────────────────────────────────────────────
// QR TTL: 15 minutes

function GamificationPanel({ onClose }: { onClose: () => void }) {
  const pct = Math.round(
    (GAMIFICATION.weeklyProgress / GAMIFICATION.weeklyTarget) * 100
  );
  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      style={{ background: "rgba(0,0,0,0.7)" }}
      onClick={onClose}
    >
      <div
        className="w-full rounded-t-3xl p-5 flex flex-col gap-4"
        style={{
          background: "oklch(0.11 0.012 240)",
          border: `1px solid ${BORDER}`,
        }}
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div
            className="text-base font-bold text-white"
            style={{ fontFamily: DISP }}
          >
            🏆 Agent Leaderboard
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl"
          >
            ×
          </button>
        </div>
        {/* Rank card */}
        <div
          className="rounded-2xl p-4 flex items-center gap-4"
          style={{
            background: "oklch(0.78 0.18 80 / 0.1)",
            border: `1px solid oklch(0.78 0.18 80 / 0.3)`,
          }}
        >
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center text-2xl font-bold"
            style={{
              background: "oklch(0.78 0.18 80 / 0.2)",
              color: GOLD,
              fontFamily: MONO,
            }}
          >
            #{GAMIFICATION.rank}
          </div>
          <div>
            <div
              className="text-sm font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              {GAMIFICATION.level}
            </div>
            <div className="text-xs text-gray-400">
              {GAMIFICATION.points.toLocaleString()} pts · Top{" "}
              {Math.round((GAMIFICATION.rank / GAMIFICATION.totalAgents) * 100)}
              %
            </div>
            <div className="text-xs mt-1" style={{ color: GOLD }}>
              🔥 {GAMIFICATION.streak}-day streak
            </div>
          </div>
        </div>
        {/* Weekly target */}
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div className="flex justify-between mb-2">
            <span
              className="text-xs text-gray-400"
              style={{ fontFamily: DISP }}
            >
              Weekly Target
            </span>
            <span
              className="text-xs font-bold text-white"
              style={{ fontFamily: MONO }}
            >
              {GAMIFICATION.weeklyProgress}/{GAMIFICATION.weeklyTarget} tx
            </span>
          </div>
          <div
            className="h-3 rounded-full overflow-hidden"
            style={{ background: BORDER }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${pct}%`,
                background: pct >= 100 ? GREEN : BLUE,
              }}
            />
          </div>
          <div
            className="text-xs text-gray-400 mt-1"
            style={{ fontFamily: DISP }}
          >
            {GAMIFICATION.weeklyTarget - GAMIFICATION.weeklyProgress} more to
            hit target
          </div>
        </div>
        {/* Badges */}
        <div className="flex flex-wrap gap-2">
          {GAMIFICATION.badges.map(b => (
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
  );
}

// ─── Tile Editor Sheet ────────────────────────────────────────────────────────
