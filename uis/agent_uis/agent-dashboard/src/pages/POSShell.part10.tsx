// @ts-nocheck
import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { useEffect, useState } from "react";
import { Area, AreaChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { fmt } from "./POSShell.part5";
import { ReceiptModal } from "./POSShell.part6";
import { BLUE, BORDER, CARD, CHART_DATA, DISP, GOLD, GREEN, MONO, RED, Tile, TileSize, Transaction } from "./POSShell.shared";

function AnalyticsScreen({
  onBack,
  chartData,
}: {
  onBack: () => void;
  chartData?: typeof CHART_DATA;
}) {
  // Derived from the live hourly chart data only — no fabricated category
  // breakdown. Categories without a live source are omitted entirely.
  const series = chartData ?? CHART_DATA;
  const pieData = [
    {
      name: "Cash In",
      value: series.reduce((acc, b) => acc + (Number(b?.in) || 0), 0),
      color: GREEN,
    },
    {
      name: "Cash Out",
      value: series.reduce((acc, b) => acc + (Number(b?.out) || 0), 0),
      color: BLUE,
    },
  ];
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Performance Analytics" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Transaction Mix
          </div>
          <div className="flex items-center gap-4">
            <ResponsiveContainer width={120} height={120}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={35}
                  outerRadius={55}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {pieData.map((e, i) => (
                    <Cell key={i} fill={e.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-col gap-2">
              {pieData.map(d => (
                <div key={d.name} className="flex items-center gap-2">
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ background: d.color }}
                  />
                  <span
                    className="text-xs text-gray-400"
                    style={{ fontFamily: DISP }}
                  >
                    {d.name}
                  </span>
                  <span
                    className="text-xs font-bold text-white ml-auto"
                    style={{ fontFamily: MONO }}
                  >
                    {fmt(d.value)}
                  </span>
                </div>
              ))}
            </div>
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
            Cash Flow (Today)
          </div>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={chartData ?? CHART_DATA}>
              <XAxis
                dataKey="h"
                tick={{
                  fill: "#6b7280",
                  fontSize: 10,
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
              />
              <Area
                type="monotone"
                dataKey="in"
                stroke={GREEN}
                fill="oklch(0.65 0.18 160 / 0.15)"
                strokeWidth={2}
                name="Cash In"
              />
              <Area
                type="monotone"
                dataKey="out"
                stroke={RED}
                fill="oklch(0.60 0.22 25 / 0.1)"
                strokeWidth={2}
                name="Cash Out"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {(() => {
            const rows = chartData ?? CHART_DATA;
            let peak = "—";
            if (rows.length > 0) {
              const top = rows.reduce((a, b) =>
                (Number(b?.in) || 0) + (Number(b?.out) || 0) >
                (Number(a?.in) || 0) + (Number(a?.out) || 0)
                  ? b
                  : a
              );
              peak = String(top?.h ?? "—");
            }
            return [
              ["Avg Tx", "—"],
              ["Peak Hour", peak],
              ["Busiest Day", "—"],
            ];
          })().map(([k, v]) => (
            <div
              key={k}
              className="rounded-2xl p-3 text-center"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                {k}
              </div>
              <div
                className="text-sm font-bold text-white"
                style={{ fontFamily: MONO }}
              >
                {v}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// 22. Scorecard ───────────────────────────────────────────────────────────────

function SettlementScreen({ onBack }: { onBack: () => void }) {
  const { data: outstandingData, isLoading } =
    trpc.settlement.getOutstanding.useQuery(undefined, {
      refetchInterval: 60_000,
    });
  const { data: ds } = trpc.transactions.agentDayStats.useQuery(undefined, {
    refetchInterval: 60_000,
  });
  const netPosition = ds
    ? ds.cashIn - ds.cashOut - ds.transfers + ds.commission
    : 0;
  const items: any[] = outstandingData?.outstanding ?? [];
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Daily Settlement" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        <div
          className="rounded-2xl p-4 flex justify-between items-center"
          style={{
            background: "oklch(0.60 0.22 260 / 0.1)",
            border: `1px solid ${BLUE}33`,
          }}
        >
          <div>
            <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
              Settlement Status
            </div>
            <div
              className="font-bold text-blue-400"
              style={{ fontFamily: DISP }}
            >
              {items.length > 0
                ? `${items.length} pending batch${items.length > 1 ? "es" : ""}`
                : "Up to date"}
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
              Net Position
            </div>
            <div
              className="text-xl font-bold"
              style={{ fontFamily: MONO, color: GREEN }}
            >
              {fmt(netPosition)}
            </div>
          </div>
        </div>
        {isLoading ? (
          <div
            className="flex items-center justify-center py-12 text-gray-500"
            style={{ fontFamily: DISP }}
          >
            <span className="animate-spin mr-2">⟳</span> Loading...
          </div>
        ) : items.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-12 text-gray-600"
            style={{ fontFamily: DISP }}
          >
            <div className="text-3xl mb-2">✓</div>
            <div className="text-sm">All transactions settled</div>
          </div>
        ) : (
          items.map((item: any, i: number) => (
            <div
              key={item.id ?? i}
              className="flex items-center justify-between p-3 rounded-xl"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
                  style={{
                    background:
                      item.type === "Cash Out" || item.type === "Transfer"
                        ? "oklch(0.60 0.22 25 / 0.2)"
                        : "oklch(0.65 0.18 160 / 0.2)",
                  }}
                >
                  {item.type === "Cash Out" || item.type === "Transfer"
                    ? "↑"
                    : "↓"}
                </div>
                <div>
                  <div
                    className="text-sm font-semibold text-white"
                    style={{ fontFamily: DISP }}
                  >
                    {item.type}
                  </div>
                  <div
                    className="text-xs text-gray-500"
                    style={{ fontFamily: MONO }}
                  >
                    {new Date(item.createdAt).toLocaleTimeString("en-NG", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                </div>
              </div>
              <div
                className="font-bold"
                style={{
                  fontFamily: MONO,
                  color:
                    item.type === "Cash Out" || item.type === "Transfer"
                      ? RED
                      : GREEN,
                }}
              >
                {item.type === "Cash Out" || item.type === "Transfer"
                  ? "-"
                  : "+"}
                {fmt(Number(item.amount))}
              </div>
            </div>
          ))
        )}
        <button
          onClick={() => toast.info("Settlement report exported")}
          className="w-full py-4 rounded-xl font-bold text-white"
          style={{ background: BLUE, fontFamily: DISP }}
        >
          Export Settlement Report
        </button>
      </div>
    </div>
  );
}

// 16. Reconcile ───────────────────────────────────────────────────────────────

function DailyReportScreen({
  onBack,
  chartData,
}: {
  onBack: () => void;
  chartData?: typeof CHART_DATA;
}) {
  const { data: ds } = trpc.transactions.agentDayStats.useQuery(undefined, {
    refetchInterval: 60_000,
  });
  const stats = ds
    ? [
        { label: "Total Transactions", value: String(ds.count), color: BLUE },
        {
          label: "Total Volume",
          value: fmt(ds.cashIn + ds.cashOut + ds.transfers),
          color: GREEN,
        },
        { label: "Cash In", value: fmt(ds.cashIn), color: GREEN },
        { label: "Cash Out", value: fmt(ds.cashOut), color: RED },
        { label: "Transfers", value: fmt(ds.transfers), color: "#8b5cf6" },
        { label: "Commission", value: fmt(ds.commission), color: GOLD },
        {
          label: "Success Rate",
          value: `${ds.successRate}%`,
          color: ds.successRate >= 95 ? GREEN : GOLD,
        },
        { label: "Float Balance", value: fmt(ds.float), color: GOLD },
      ]
    : [
        { label: "Total Transactions", value: "—", color: BLUE },
        { label: "Total Volume", value: "—", color: GREEN },
        { label: "Cash In", value: "—", color: GREEN },
        { label: "Cash Out", value: "—", color: RED },
        { label: "Transfers", value: "—", color: "#8b5cf6" },
        { label: "Commission", value: "—", color: GOLD },
        { label: "Success Rate", value: "—", color: GREEN },
        { label: "Float Balance", value: "—", color: GOLD },
      ];
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader
        title="Daily Report"
        onBack={onBack}
        badge={
          <span className="text-xs text-gray-500" style={{ fontFamily: MONO }}>
            {new Date().toLocaleDateString("en-NG")}
          </span>
        }
      />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          {stats.map(s => (
            <div
              key={s.label}
              className="rounded-2xl p-4"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                {s.label}
              </div>
              <div
                className="text-xl font-bold"
                style={{ fontFamily: MONO, color: s.color }}
              >
                {s.value}
              </div>
            </div>
          ))}
        </div>
        <div
          className="rounded-2xl p-4"
          style={{ background: CARD, border: `1px solid ${BORDER}` }}
        >
          <div
            className="text-sm font-bold text-white mb-3"
            style={{ fontFamily: DISP }}
          >
            Hourly Volume
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={chartData ?? CHART_DATA}>
              <XAxis
                dataKey="h"
                tick={{
                  fill: "#6b7280",
                  fontSize: 10,
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
              />
              <Area
                type="monotone"
                dataKey="in"
                stroke={GREEN}
                fill="oklch(0.65 0.18 160 / 0.15)"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="out"
                stroke={BLUE}
                fill="oklch(0.60 0.22 260 / 0.1)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <button
          onClick={() => toast.info("Report exported as PDF")}
          className="w-full py-4 rounded-xl font-bold text-white"
          style={{ background: BLUE, fontFamily: DISP }}
        >
          Export PDF Report
        </button>
      </div>
    </div>
  );
}

// 20. Transaction History ─────────────────────────────────────────────────────

function BillsScreen({ onBack }: { onBack: () => void }) {
  const [biller, setBiller] = useState("");
  const [account, setAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<"form" | "success">("form");
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const { submit, isProcessing } = useTransactionCreate();
  const billers = [
    { id: "dstv", name: "DSTV", icon: "📺" },
    { id: "gotv", name: "GOtv", icon: "📡" },
    { id: "ekedc", name: "EKEDC", icon: "⚡" },
    { id: "ikedc", name: "IKEDC", icon: "💡" },
    { id: "lawma", name: "LAWMA", icon: "🗑" },
    { id: "lcc", name: "LCC Toll", icon: "🛣" },
    { id: "waec", name: "WAEC", icon: "📚" },
    { id: "jamb", name: "JAMB", icon: "🎓" },
  ];

  if (step === "success")
    return (
      <SuccessScreen
        title="Bill Payment Successful"
        amount={num}
        ref={txRef}
        customer={account}
        onDone={onBack}
        onPrint={() => toast.info("Printing receipt...")}
      />
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Bill Payment" onBack={onBack} />
      <div className="flex flex-col gap-4 p-4 overflow-y-auto flex-1">
        <div>
          <div
            className="text-xs text-gray-500 mb-2"
            style={{ fontFamily: DISP }}
          >
            Select Biller
          </div>
          <div className="grid grid-cols-4 gap-2">
            {billers.map(b => (
              <button
                key={b.id}
                onClick={() => setBiller(b.id)}
                className="flex flex-col items-center gap-1 py-3 rounded-xl transition-all"
                style={{
                  background:
                    biller === b.id ? "oklch(0.78 0.18 80 / 0.3)" : CARD,
                  border:
                    biller === b.id
                      ? `1px solid ${GOLD}44`
                      : `1px solid ${BORDER}`,
                }}
              >
                <span className="text-2xl">{b.icon}</span>
                <span
                  className="text-xs font-semibold text-white"
                  style={{ fontFamily: DISP }}
                >
                  {b.name}
                </span>
              </button>
            ))}
          </div>
        </div>
        {biller && (
          <>
            <div>
              <div
                className="text-xs text-gray-500 mb-1"
                style={{ fontFamily: DISP }}
              >
                Account / Smart Card Number
              </div>
              <input
                value={account}
                onChange={e => setAccount(e.target.value)}
                placeholder="Enter account number"
                className="w-full rounded-xl px-4 py-3 text-white outline-none"
                style={{
                  background: CARD,
                  border: `1px solid ${BORDER}`,
                  fontFamily: MONO,
                }}
              />
            </div>
            <AmountDisplay value={amount} label="Payment Amount" />
            <NumPad value={amount} onChange={setAmount} />
            <button
              disabled={num < 100 || !account || isProcessing}
              onClick={async () => {
                toast.success("Processing payment...");
                const selectedBiller = billers.find(b => b.id === biller);
                const result = await submit({
                  type: "Bill Payment",
                  amount: num,
                  customerAccount: account,
                  customerName: selectedBiller?.name,
                  channel: "App",
                });
                if (result) {
                  setTxRef(result.ref);
                  setStep("success");
                }
              }}
              className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: GOLD, fontFamily: DISP }}
            >
              {isProcessing ? "Processing..." : "✓ Pay Bill"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// 9. Reversal ─────────────────────────────────────────────────────────────────

function NFCPaymentScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "tap" | "success">("amount");
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const num = parseFloat(amount || "0");
  const { submit } = useTransactionCreate();

  if (step === "success")
    return (
      <>
        <SuccessScreen
          title="NFC Payment Approved"
          amount={num}
          ref={txRef}
          customer="Contactless"
          onDone={onBack}
          onPrint={() => setReceipt(true)}
        />
        {receipt && (
          <ReceiptModal
            tx={{
              type: "NFC Payment",
              amount: num,
              customer: "Contactless",
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
      <ScreenHeader title="NFC / Tap to Pay" onBack={onBack} />
      {step === "amount" && (
        <>
          <AmountDisplay value={amount} label="Payment Amount" />
          <NumPad value={amount} onChange={setAmount} />
          <div className="px-4 pb-4">
            <button
              disabled={num < 50}
              onClick={() => setStep("tap")}
              className="w-full py-4 rounded-xl font-bold text-white disabled:opacity-40"
              style={{ background: "#ec4899", fontFamily: DISP }}
            >
              Continue →
            </button>
          </div>
        </>
      )}
      {step === "tap" && (
        <div className="flex flex-col items-center justify-center flex-1 gap-6 p-6">
          <AmountDisplay value={amount} label="Payment Amount" />
          <div
            className="w-40 h-40 rounded-full flex items-center justify-center text-7xl animate-ping"
            style={{
              background: "oklch(0.60 0.22 340 / 0.1)",
              border: `3px solid #ec4899`,
            }}
          >
            ⟡
          </div>
          <div className="text-center">
            <div
              className="text-base font-bold text-white mb-1"
              style={{ fontFamily: DISP }}
            >
              Tap Card or Phone
            </div>
            <div className="text-sm text-gray-500">
              ISO 14443-A/B · Visa Paywave · Mastercard Tap
            </div>
          </div>
          <button
            onClick={async () => {
              toast.success("NFC tap detected!");
              const result = await submit({
                type: "NFC Payment",
                amount: num,
                customerName: "Contactless",
                channel: "NFC",
              });
              if (result) {
                setTxRef(result.ref);
                setStep("success");
              }
            }}
            className="w-full py-4 rounded-xl font-bold text-white"
            style={{ background: "#ec4899", fontFamily: DISP }}
          >
            Simulate NFC Tap
          </button>
        </div>
      )}
    </div>
  );
}

// 7. Airtime ───────────────────────────────────────────────────────────────────

function AuditLogScreen({ onBack }: { onBack: () => void }) {
  const { data: logs, isLoading } = trpc.auditLog.list.useQuery(
    { limit: 50, offset: 0 },
    { refetchInterval: 30_000 }
  );
  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="Audit Trail" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
        {isLoading ? (
          <div
            className="flex items-center justify-center py-16 text-gray-500"
            style={{ fontFamily: DISP }}
          >
            <span className="animate-spin mr-2">⟳</span> Loading...
          </div>
        ) : !logs || logs.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-16 text-gray-600"
            style={{ fontFamily: DISP }}
          >
            <div className="text-3xl mb-3">📋</div>
            <div className="text-sm">No audit entries yet</div>
          </div>
        ) : (
          logs.map((l: any, i: number) => (
            <div
              key={l.id ?? i}
              className="flex items-start gap-3 p-3 rounded-xl"
              style={{ background: CARD, border: `1px solid ${BORDER}` }}
            >
              <div
                className="text-xs text-gray-500 mt-0.5 w-14 flex-shrink-0"
                style={{ fontFamily: MONO }}
              >
                {new Date(l.createdAt).toLocaleTimeString("en-NG", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between gap-2">
                  <div
                    className="text-sm font-semibold text-white"
                    style={{ fontFamily: DISP }}
                  >
                    {l.action}
                  </div>
                  <span
                    className="text-xs px-1.5 py-0.5 rounded flex-shrink-0"
                    style={{
                      background:
                        l.status === "success"
                          ? "oklch(0.65 0.18 160 / 0.15)"
                          : "oklch(0.60 0.22 25 / 0.15)",
                      color: l.status === "success" ? GREEN : RED,
                      fontFamily: DISP,
                    }}
                  >
                    {l.status}
                  </span>
                </div>
                <div
                  className="text-xs text-gray-500 mt-0.5"
                  style={{ fontFamily: MONO }}
                >
                  {l.resource}
                  {l.resourceId ? ` · ${l.resourceId}` : ""}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// 19. Daily Report ────────────────────────────────────────────────────────────

function SuccessScreen({
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
          {txRef}
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

function TileComponent({
  tile,
  editMode,
  onPress,
  style,
}: {
  tile: Tile;
  editMode: boolean;
  onPress: (t: Tile) => void;
  style?: React.CSSProperties;
}) {
  const [wobble, setWobble] = useState(false);
  useEffect(() => {
    if (!editMode) {
      setWobble(false);
      return;
    }
    const delay = Math.random() * 300;
    const t = setTimeout(() => setWobble(true), delay);
    return () => clearTimeout(t);
  }, [editMode]);

  return (
    <button
      onClick={() => !editMode && onPress(tile)}
      className="relative flex flex-col justify-between p-3 rounded-2xl transition-all active:scale-95"
      style={{
        background: tile.bgColor,
        border: `1px solid ${tile.color}33`,
        animation: wobble
          ? "wobble 0.3s ease-in-out infinite alternate"
          : "none",
        ...style,
      }}
    >
      {tile.badge ? (
        <div
          className="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white z-10"
          style={{ background: RED, fontFamily: MONO }}
        >
          {tile.badge}
        </div>
      ) : null}
      {tile.hot && !tile.badge && (
        <div className="absolute top-2 right-2 text-xs">🔥</div>
      )}
      <div className="text-2xl">{tile.icon}</div>
      <div>
        <div
          className="text-sm font-bold text-white leading-tight"
          style={{ fontFamily: DISP }}
        >
          {tile.label}
        </div>
        <div
          className="text-xs mt-0.5 line-clamp-2"
          style={{
            color: tile.color,
            opacity: 0.8,
            fontFamily: "var(--font-body)",
          }}
        >
          {tile.description}
        </div>
      </div>
    </button>
  );
}

// ─── Tile Grid ────────────────────────────────────────────────────────────────

function TileGrid({
  tiles,
  editMode,
  onPress,
}: {
  tiles: Tile[];
  editMode: boolean;
  onPress: (t: Tile) => void;
}) {
  const sizeMap: Record<TileSize, string> = {
    sm: "col-span-1 row-span-1",
    md: "col-span-2 row-span-1",
    lg: "col-span-2 row-span-2",
    wide: "col-span-4 row-span-1",
  };
  const heightMap: Record<TileSize, string> = {
    sm: "h-24",
    md: "h-24",
    lg: "h-52",
    wide: "h-20",
  };
  return (
    <div className="grid grid-cols-4 gap-2 p-4 auto-rows-min">
      {tiles.map(t => (
        <TileComponent
          key={t.id}
          tile={t}
          editMode={editMode}
          onPress={onPress}
          style={
            {
              gridColumn: sizeMap[t.size]
                .split(" ")[0]
                .replace("col-span-", "span ")
                .replace("span ", "span "),
              height:
                heightMap[t.size] === "h-24"
                  ? 96
                  : heightMap[t.size] === "h-52"
                    ? 208
                    : 80,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ─── ALL 26 SCREENS ──────────────────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════════

// 1. Cash In ──────────────────────────────────────────────────────────────────

function QuickAccessStrip({
  tiles,
  onPress,
}: {
  tiles: Tile[];
  onPress: (t: Tile) => void;
}) {
  const top4 = [...tiles]
    .sort((a: any, b: any) => (b.usageCount || 0) - (a.usageCount || 0))
    .slice(0, 4);
  return (
    <div
      className="flex gap-2 px-4 py-2 border-b flex-shrink-0"
      style={{ borderColor: BORDER, background: "oklch(0.10 0.01 240)" }}
    >
      <div
        className="text-xs text-gray-600 self-center mr-1 whitespace-nowrap"
        style={{ fontFamily: DISP }}
      >
        Quick
      </div>
      {top4.map(t => (
        <button
          key={t.id}
          onClick={() => onPress(t)}
          className="flex-1 flex flex-col items-center gap-1 py-2 px-1 rounded-xl transition-all hover:scale-105 active:scale-95"
          style={{ background: t.bgColor, border: `1px solid ${t.color}44` }}
        >
          <span className="text-lg">{t.icon}</span>
          <span
            className="text-xs font-semibold truncate w-full text-center"
            style={{ color: t.color, fontFamily: DISP }}
          >
            {t.label}
          </span>
        </button>
      ))}
    </div>
  );
}

// ─── Live Ticker ──────────────────────────────────────────────────────────────

function NumPad({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "⌫"];
  return (
    <div className="grid grid-cols-3 gap-2 p-4">
      {keys.map(k => (
        <button
          key={k}
          onClick={() => {
            if (k === "⌫") onChange(value.slice(0, -1));
            else if (k === "." && value.includes(".")) return;
            else if (value.length >= 10) return;
            else onChange(value + k);
          }}
          className="h-14 rounded-xl text-xl font-semibold transition-all active:scale-95"
          style={{
            background: k === "⌫" ? "oklch(0.60 0.22 25 / 0.2)" : CARD,
            color: k === "⌫" ? RED : "white",
            border: `1px solid ${BORDER}`,
            fontFamily: MONO,
          }}
        >
          {k}
        </button>
      ))}
    </div>
  );
}


function PhoneInput({
  value,
  onChange,
  label = "Customer Phone Number",
}: {
  value: string;
  onChange: (v: string) => void;
  label?: string;
}) {
  return (
    <div className="px-4 pb-2">
      <div className="text-xs text-gray-500 mb-1" style={{ fontFamily: DISP }}>
        {label}
      </div>
      <input
        type="tel"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="0800 000 0000"
        className="w-full rounded-xl px-4 py-3 text-white text-base outline-none"
        style={{
          background: CARD,
          border: `1px solid ${BORDER}`,
          fontFamily: MONO,
        }}
      />
    </div>
  );
}


function ScreenHeader({
  title,
  onBack,
  badge,
}: {
  title: string;
  onBack: () => void;
  badge?: React.ReactNode;
}) {
  return (
    <div
      className="flex items-center gap-3 px-4 py-3 border-b flex-shrink-0"
      style={{ borderColor: BORDER }}
    >
      <button
        onClick={onBack}
        className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:bg-white/10 text-gray-400 hover:text-white text-lg"
      >
        ←
      </button>
      <div
        className="text-base font-bold text-white flex-1"
        style={{ fontFamily: DISP }}
      >
        {title}
      </div>
      {badge}
    </div>
  );
}


function AmountDisplay({ value, label }: { value: string; label: string }) {
  const num = parseFloat(value || "0");
  return (
    <div className="flex flex-col items-center py-6 gap-1">
      <div
        className="text-xs text-gray-500 uppercase tracking-widest"
        style={{ fontFamily: DISP }}
      >
        {label}
      </div>
      <div
        className="text-4xl font-bold"
        style={{ fontFamily: MONO, color: GOLD }}
      >
        ₦
        {num.toLocaleString("en-NG", {
          minimumFractionDigits: value.includes(".") ? 2 : 0,
        })}
      </div>
    </div>
  );
}

