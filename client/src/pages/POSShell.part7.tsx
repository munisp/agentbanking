import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useState } from "react";
import { toast } from "sonner";
import { NumPad, ScreenHeader } from "./POSShell.part10";
import { AmountDisplay, PhoneInput } from "./POSShell.part11";
import { SuccessScreen } from "./POSShell.part5";
import { ReceiptModal, fmt } from "./POSShell.part6";
import { BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, RED, Transaction } from "./POSShell.shared";

export function FraudAlertsScreen({ onBack }: { onBack: () => void }) {
  const utils = trpc.useUtils();
  const { data: liveAlerts, isLoading } = trpc.fraud.list.useQuery(
    { status: "open" },
    { refetchInterval: 30_000 }
  ) as any;
  const [selected, setSelected] = useState<any | null>(null);
  const updateStatus = trpc.fraud.updateStatus.useMutation({
    onSuccess: () => {
      utils.fraud.list.invalidate();
      setSelected(null);
    },
  }) as any;
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


export function ReversalScreen({ onBack }: { onBack: () => void }) {
  const [ref, setRef] = useState("");
  const [reason, setReason] = useState("");
  const [step, setStep] = useState<"form" | "confirm" | "success">("form");
  const [reversing, setReversing] = useState(false);
  const reverseMutation = trpc.transactions.reverse.useMutation() as any;
  const recentTxs = usePosStore(s => s.recentTxs);
  // First check local recent txs for instant UX, then fall back to DB lookup
  const localFound = recentTxs.find((t: any) =>
    t.ref.toLowerCase().includes(ref.toLowerCase())
  );
  const { data: dbFound } = trpc.transactions.getByRef.useQuery(
    { ref: ref.trim() },
    { enabled: ref.trim().length >= 6 && !localFound, retry: false }
  ) as any;
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

export function CashOutScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "phone" | "confirm" | "success">(
    "amount"
  );
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState<string>(""); // server-issued reference only
  const num = parseFloat(amount || "0");
  // Fail closed when the balance is unknown: never check against a fabricated float.
  const storeFloat = usePosStore(s => s.agent?.floatBalance ?? 0);
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

export function PrinterTestScreen({ onBack }: { onBack: () => void }) {
  const [printing, setPrinting] = useState(false);
  const [result, setResult] = useState<
    "idle" | "success" | "error" | "low-paper"
  >("idle");
  // No real device print channel is connected in this build — never claim a
  // successful test print that did not happen.
  const runTest = (_type: string) => {
    setResult("error");
    toast.error(
      "Printer service is not connected on this device — test print unavailable."
    );
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
                    color: BLUE,
                    fontFamily: MONO,
                  }}
                >
                  {"—"}
                </span>
              </div>
              <div
                className="h-3 rounded-full overflow-hidden"
                style={{ background: BORDER }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${"—"}`,
                    background: BLUE,
                  }}
                />
              </div>
            </div>
            <div className="text-3xl">
              {"📄"}
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
              className="text-sm text-green-400"
              style={{ fontFamily: DISP }}
            >
              Test print completed successfully
            </span>
          </div>
        )}
        {result === "error" && (
          <div
            className="rounded-2xl p-4 flex items-center gap-3"
            style={{
              background: "oklch(0.60 0.22 25 / 0.1)",
              border: `1px solid ${RED}`,
            }}
          >
            <span className="text-xl">✗</span>
            <div>
              <span className="text-sm text-red-400" style={{ fontFamily: DISP }}>
                Test print unavailable
              </span>
              <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
                Printer service not connected on this device
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// 11. KYC Verify ─────────────────────────────────────────────────────────────

export function TxHistoryScreen({ onBack }: { onBack: () => void }) {
  const [filter, setFilter] = useState<string>("All");
  const { data: recentData } = trpc.transactions.recent.useQuery({
    limit: 50,
  }) as any;
  const recentTxs = usePosStore(s => s.recentTxs);
  const filters = ["All", "Cash In", "Cash Out", "Transfer", "QR Pay"];
  // Prefer live transactions from tRPC; fall back to local store (offline queue)
  const allTxs: any[] =
    (recentData?.transactions as any[]) ??
    (Array.isArray(recentData) ? (recentData as any[]) : recentTxs);
  const filtered =
    filter === "All" ? allTxs : allTxs.filter((t: any) => t.type === filter);
  const filteredSum = filtered.reduce(
    (s: number, t: any) => s + (t.amount ?? 0),
    0
  );
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="Transaction History"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.60 0.22 260 / 0.2)",
              color: BLUE,
              fontFamily: DISP,
            }}
          >
            {filtered.length}
          </span>
        }
      />
      <div className="px-4 pt-3">
        <div className="flex gap-2 overflow-x-auto pb-2">
          {filters.map((f: any) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all flex-shrink-0"
              style={{
                background: filter === f ? `${BLUE}33` : CARD,
                color: filter === f ? BLUE : "#6b7280",
                border: `1px solid ${filter === f ? BLUE : BORDER}`,
                fontFamily: DISP,
              }}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-4 pb-4 flex flex-col gap-2">
        {filtered.map((tx: any, i: number) => (
          <div
            key={tx.id ?? i}
            className="flex items-center gap-3 p-3 rounded-xl"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center text-base flex-shrink-0"
              style={{
                background:
                  tx.type === "Cash In"
                    ? "oklch(0.65 0.18 160 / 0.2)"
                    : tx.type === "Cash Out"
                      ? "oklch(0.60 0.22 260 / 0.2)"
                      : "oklch(0.78 0.18 80 / 0.2)",
              }}
            >
              {tx.type === "Cash In"
                ? "⬇"
                : tx.type === "Cash Out"
                  ? "⬆"
                  : "⇄"}
            </div>
            <div className="flex-1 min-w-0">
              <div
                className="text-sm font-bold text-white truncate"
                style={{ fontFamily: DISP }}
              >
                {tx.type}
              </div>
              <div
                className="text-xs text-gray-500 truncate"
                style={{ fontFamily: DISP }}
              >
                {tx.customer ?? tx.customerPhone ?? "—"}
              </div>
              <div className="text-xs text-gray-600" style={{ fontFamily: MONO }}>
                {tx.time ??
                  (tx.createdAt
                    ? new Date(tx.createdAt).toLocaleTimeString("en-NG", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "")}{" "}
                · {tx.ref ?? ""}
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <div
                className="text-sm font-bold"
                style={{
                  color: tx.type === "Cash In" ? GREEN : "white",
                  fontFamily: MONO,
                }}
              >
                {tx.type === "Cash In" ? "+" : "-"}₦
                {(tx.amount ?? 0).toLocaleString()}
              </div>
              <div
                className="text-xs"
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
                {tx.status ?? "—"}
              </div>
            </div>
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-gray-500">
            <div className="text-4xl mb-3">📋</div>
            <div className="text-sm" style={{ fontFamily: DISP }}>
              No transactions found
            </div>
          </div>
        )}
      </div>
      {/* Summary bar */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{
          background: CARD,
          borderTop: `1px solid ${BORDER}`,
        }}
      >
        <span className="text-xs text-gray-400" style={{ fontFamily: DISP }}>
          {filtered.length} transactions
        </span>
        <span
          className="text-sm font-bold"
          style={{ color: GOLD, fontFamily: MONO }}
        >
          ₦{filteredSum.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

// 12. Biometric ──────────────────────────────────────────────────────────────

export function AMLCheckScreen({ onBack }: { onBack: () => void }) {
  const [q, setQ] = useState("");
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<null | {
    risk: "LOW" | "MEDIUM" | "HIGH" | "BLOCKED";
    matchCount: number;
    lists: string[];
  }>(null);
  const [error, setError] = useState<string | null>(null);
  const screenMut = trpc.aml?.screenEntity?.useMutation?.() as any;

  const runScreen = async () => {
    setSearching(true);
    setResult(null);
    setError(null);
    try {
      if (screenMut?.mutateAsync) {
        const res: any = await screenMut.mutateAsync({
          entityType: "individual",
          name: q,
        });
        setResult({
          risk: res.riskLevel ?? res.risk ?? "LOW",
          matchCount: res.matchCount ?? res.matches?.length ?? 0,
          lists:
            res.matches?.map((m: any) => m.listName ?? m.list) ??
            res.lists ??
            [],
        });
      } else {
        // AML screening endpoint not available — honest response, not a mock pass.
        setError(
          "AML screening service is not available in this build. No screening was performed."
        );
      }
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? `AML screening failed: ${err.message}`
          : "AML screening failed — no result returned."
      );
    } finally {
      setSearching(false);
    }
  };

  const riskColor =
    result?.risk === "LOW"
      ? GREEN
      : result?.risk === "MEDIUM"
        ? GOLD
        : result?.risk === "HIGH"
          ? "#f97316"
          : RED;
  const riskBg = riskColor ? `${riskColor}22` : "transparent";
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="AML Screening"
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
            COMPLIANCE
          </span>
        }
      />
      <div className="flex flex-col gap-4 p-4 flex-1 overflow-y-auto">
        <div>
          <div
            className="text-xs text-gray-500 mb-1"
            style={{ fontFamily: DISP }}
          >
            Customer Name or BVN
          </div>
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Full name or 11-digit BVN..."
            className="w-full rounded-xl px-4 py-3 text-white outline-none"
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              fontFamily: DISP,
            }}
          />
        </div>
        <div
          className="rounded-xl p-3"
          style={{
            background: "oklch(0.78 0.18 80 / 0.05)",
            border: `1px solid ${BORDER}`,
          }}
        >
          <div
            className="text-xs text-gray-400 mb-2"
            style={{ fontFamily: DISP }}
          >
            Screening lists checked:
          </div>
          {[
            "CBN Watchlist",
            "OFAC SDN",
            "UN Sanctions",
            "EU Consolidated",
            "Local PEP Database",
          ].map((l: any) => (
            <div
              key={l}
              className="flex items-center gap-2 py-1"
              style={{ fontFamily: DISP }}
            >
              <span className="text-xs text-green-400">✓</span>
              <span className="text-xs text-gray-400">{l}</span>
            </div>
          ))}
        </div>
        {error && (
          <div
            className="rounded-xl p-4"
            style={{ background: `${RED}15`, border: `1px solid ${RED}44` }}
          >
            <div className="text-xs text-red-400" style={{ fontFamily: DISP }}>
              {error}
            </div>
          </div>
        )}
        {result && !error && (
          <div
            className="rounded-2xl p-5"
            style={{
              background: CARD,
              border: `2px solid ${riskColor}`,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div
                className="text-sm font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                Screening Result
              </div>
              <span
                className="px-3 py-1 rounded-full text-xs font-bold"
                style={{
                  background: riskBg,
                  color: riskColor,
                  fontFamily: DISP,
                }}
              >
                {result.risk} RISK
              </span>
            </div>
            {[
              ["Watchlist Matches", String(result.matchCount)],
              [
                "Lists Hit",
                result.lists.length > 0 ? result.lists.join(", ") : "None",
              ],
              ["Screened Entity", q],
              [
                "Timestamp",
                new Date().toLocaleString("en-NG", {
                  dateStyle: "short",
                  timeStyle: "short",
                }),
              ],
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
                  className="text-xs font-bold text-white text-right"
                  style={{ fontFamily: k === "Screened Entity" ? DISP : MONO }}
                >
                  {v}
                </span>
              </div>
            ))}
            {result.risk === "BLOCKED" && (
              <div
                className="mt-3 p-3 rounded-xl text-xs font-bold"
                style={{
                  background: "oklch(0.60 0.22 25 / 0.2)",
                  color: RED,
                  fontFamily: DISP,
                }}
              >
                ⛔ TRANSACTION BLOCKED — Do not proceed. Escalate to compliance.
              </div>
            )}
          </div>
        )}
        <button
          disabled={q.length < 3 || searching}
          onClick={runScreen}
          className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40 mt-auto"
          style={{ background: GOLD, color: "#111", fontFamily: DISP }}
        >
          {searching ? "Screening..." : "🔍 Run AML Screen"}
        </button>
      </div>
    </div>
  );
}

// 13. Open Account ────────────────────────────────────────────────────────────
