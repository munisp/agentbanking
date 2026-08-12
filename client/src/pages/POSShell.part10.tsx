import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { haptic } from "../lib/haptics";
import { trpc } from "../lib/trpc";
import { usePosStore } from "../store/posStore";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AmountDisplay, useGamification } from "./POSShell.part11";
import { SuccessScreen } from "./POSShell.part5";
import { ReceiptModal, fmt } from "./POSShell.part6";
import { BG, BLUE, BORDER, CARD, DISP, GOLD, GREEN, MONO, OFFLINE_CAPABLE_TILES, RED, TILE_USAGE_KEY, TerminalInfo, Tile, TileSize } from "./POSShell.shared";

export function NotificationPanel({ onClose }: { onClose: () => void }) {
  // Real notifications from the backend inbox — never fabricated alerts.
  const inboxUser = usePosStore(s => s.agent);
  const { data: inboxData, isLoading: inboxLoading } =
    trpc.notificationInbox.list.useQuery(
      { userId: String(inboxUser?.id ?? "") , limit: 20 },
      { enabled: !!inboxUser?.id, retry: false }
    ) as any;
  const notifications: any[] = (inboxData?.items ?? inboxData?.notifications ?? []).map(
    (n: any, idx: number) => ({
      id: n.id ?? idx,
      type: n.type ?? "info",
      title: n.title ?? "Notification",
      body: n.body ?? n.message ?? "",
      time: n.createdAt ? new Date(n.createdAt).toLocaleString("en-NG") : "",
      read: !!n.read,
      color: BLUE,
    })
  );

  const [items, setItems] = useState(notifications);
  const unread = items.filter((n: any) => !n.read).length;

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
              onClick={() =>
                setItems(items.map((n: any) => ({ ...n, read: true })))
              }
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
          {items.map((n: any) => (
            <div
              key={n.id}
              onClick={() =>
                setItems(
                  items.map((i: any) =>
                    i.id === n.id ? { ...i, read: true } : i
                  )
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
          {notifications.length === 0 && (
            <div className="text-center text-gray-500 text-sm py-8">
              {inboxLoading ? "Loading notifications…" : inboxUser?.id ? "No notifications." : "Sign in to view notifications."}
            </div>
          )}
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

export function CardPaymentScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "card" | "pin" | "success">(
    "amount"
  );
  const [amount, setAmount] = useState("");
  const [pin, setPin] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState<string>(""); // server-issued reference only
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
            {[0, 1, 2, 3].map((i: any) => (
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
                toast.success("Processing payment...");
                const result = await submit({
                  type: "Card Payment",
                  amount: num,
                  customerName: "Card Holder",
                  channel: "Card",
                });
                if (result) {
                  setTxRef(result.ref);
                  setStep("success");
                }
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

export function SettlementScreen({ onBack }: { onBack: () => void }) {
  const { data: outstandingData, isLoading } =
    trpc.settlement.getOutstanding.useQuery(undefined, {
      refetchInterval: 60_000,
    }) as any;
  const { data: ds } = trpc.transactions.agentDayStats.useQuery(undefined, {
    refetchInterval: 60_000,
  }) as any;
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

export function BillsScreen({ onBack }: { onBack: () => void }) {
  const [biller, setBiller] = useState("");
  const [account, setAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<"form" | "success">("form");
  const [txRef, setTxRef] = useState<string>(""); // server-issued reference only
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
            {billers.map((b: any) => (
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
                const selectedBiller = billers.find(
                  (b: any) => b.id === biller
                );
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

export function GamificationPanel({ onClose }: { onClose: () => void }) {
  const g = useGamification();
  const pct =
    g.weeklyProgress != null && g.weeklyTarget != null && g.weeklyTarget > 0
      ? Math.round((g.weeklyProgress / g.weeklyTarget) * 100)
      : null;
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
            {g.rank != null ? `#${g.rank}` : "—"}
          </div>
          <div>
            <div
              className="text-sm font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              {g.level ?? "—"}
            </div>
            <div className="text-xs text-gray-400">
              {g.points != null ? g.points.toLocaleString() : "—"} pts
            </div>
            <div className="text-xs mt-1" style={{ color: GOLD }}>
              🔥 {g.streak != null ? `${g.streak}-day streak` : "—"}
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
              {g.weeklyProgress ?? "—"}/{g.weeklyTarget ?? "—"} tx
            </span>
          </div>
          <div
            className="h-3 rounded-full overflow-hidden"
            style={{ background: BORDER }}
          >
            <div
              className="h-full rounded-full"
              style={{
                width: `${pct ?? 0}%`,
                background: (pct ?? 0) >= 100 ? GREEN : BLUE,
              }}
            />
          </div>
          <div
            className="text-xs text-gray-400 mt-1"
            style={{ fontFamily: DISP }}
          >
            {g.weeklyTarget != null && g.weeklyProgress != null
              ? `${Math.max(g.weeklyTarget - g.weeklyProgress, 0)} more to hit target`
              : "Weekly target unavailable"}
          </div>
        </div>
        {/* Badges */}
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
  );
}

// ─── Tile Editor Sheet ────────────────────────────────────────────────────────

export function SortableTile({
  tile,
  editMode,
  isOnline,
  onPress,
  customSize,
  customColor,
  liveData,
  children,
}: {
  tile: Tile;
  editMode: boolean;
  isOnline: boolean;
  onPress: (t: Tile) => void;
  customSize?: TileSize;
  customColor?: number;
  liveData?: React.ReactNode;
  children?: React.ReactNode;
}) {
  const size = customSize || tile.size;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tile.id, disabled: !editMode });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.7 : 1,
  };

  const colSpan =
    size === "wide"
      ? "col-span-4"
      : size === "lg"
        ? "col-span-2"
        : size === "md"
          ? "col-span-2"
          : "col-span-1";
  const rowSpan = size === "lg" ? "row-span-2" : "";
  const h = size === "lg" ? "h-28" : size === "wide" ? "h-16" : "h-20";

  const isOfflineDisabled = !isOnline && !OFFLINE_CAPABLE_TILES.has(tile.id);

  const bgColor =
    customColor && customColor >= 0
      ? `oklch(0.55 0.18 ${customColor} / 0.15)`
      : tile.bgColor;
  const color =
    customColor && customColor >= 0
      ? `oklch(0.65 0.20 ${customColor})`
      : tile.color;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...(editMode ? listeners : {})}
      className={`${colSpan} ${rowSpan} ${h} ${isOfflineDisabled ? "tile-offline-only" : ""} ${isDragging ? "tile-dragging" : ""}`}
    >
      <button
        onClick={() => {
          if (!editMode && !isOfflineDisabled) {
            haptic("tap");
            onPress(tile);
          }
        }}
        className={`w-full h-full rounded-2xl p-3 flex flex-col justify-between transition-all active:scale-95 relative overflow-hidden touch-target`}
        style={{
          background: bgColor,
          border: `1px solid ${color}30`,
        }}
        aria-label={`${tile.label}: ${tile.description}`}
      >
        {editMode && (
          <div
            className="absolute inset-0 rounded-2xl border-2 tile-edit-mode"
            style={{ borderColor: color }}
          />
        )}
        {editMode && (
          <div
            className="absolute top-1.5 left-1.5 text-xs opacity-60 z-10"
            style={{ color }}
          >
            ⋮⋮
          </div>
        )}
        {(tile.badge || 0) > 0 && (
          <div
            className="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold text-white z-10"
            style={{ background: RED }}
          >
            {tile.badge}
          </div>
        )}
        {tile.hot && !editMode && (
          <div
            className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: color }}
          />
        )}
        <div className="text-2xl leading-none">{tile.icon}</div>
        <div>
          {liveData && size !== "sm" && (
            <div
              className="text-xs font-bold mb-0.5"
              style={{ color, fontFamily: MONO }}
            >
              {liveData}
            </div>
          )}
          <div
            className="text-xs font-bold text-white leading-tight"
            style={{ fontFamily: DISP }}
          >
            {tile.label}
          </div>
          {tile.size !== "sm" && !liveData && (
            <div
              className="text-xs mt-0.5 leading-tight"
              style={{ color, fontFamily: DISP, fontSize: 10, opacity: 0.8 }}
            >
              {tile.description}
            </div>
          )}
        </div>
        {children}
      </button>
    </div>
  );
}


export function NFCPaymentScreen({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<"amount" | "tap" | "success">("amount");
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState<string>(""); // server-issued reference only
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

export function AuditLogScreen({ onBack }: { onBack: () => void }) {
  const { data: logs, isLoading } = trpc.auditLog.list.useQuery(
    { limit: 50, offset: 0 },
    { refetchInterval: 30_000 }
  ) as any;
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

function StatusBar({
  terminal,
  time,
}: {
  terminal: TerminalInfo;
  time: string;
}) {
  const tierColor = terminal.tier
    ? {
        Bronze: "#cd7f32",
        Silver: "#9ca3af",
        Gold: GOLD,
        Platinum: "#a78bfa",
      }[terminal.tier]
    : "#6b7280";
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
            {terminal.agentName ? terminal.agentName.split(" ")[0] : "—"}
          </span>
        </div>
        <span className="text-gray-500">|</span>
        <span style={{ color: "oklch(0.65 0.015 230)", fontFamily: MONO }}>
          {terminal.agentCode ?? "—"}
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
          {terminal.tier ?? "—"}
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
          {terminal.model ?? "—"}
        </div>
        <span style={{ fontFamily: MONO, color: "oklch(0.65 0.015 230)" }}>
          {terminal.serialNo ? terminal.serialNo.slice(-4) : "—"}
        </span>
        <span className="text-gray-500">|</span>
        <span
          style={{
            color: terminal.network === "Offline" ? RED : GREEN,
            fontFamily: MONO,
          }}
        >
          {terminal.network ?? "—"}
        </span>
        <span
          style={{
            fontFamily: MONO,
          }}
        >
          🔋{terminal.batteryLevel != null ? `${terminal.batteryLevel}%` : "—"}
        </span>
        {terminal.paperLevel != null && terminal.paperLevel < 30 && (
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

function FloatHeader({ terminal }: { terminal: TerminalInfo }) {
  const gam = useGamification();
  const progress =
    terminal.txTarget > 0 ? (terminal.txToday / terminal.txTarget) * 100 : 0;
  return (
    <div
      className="px-4 py-3 flex-shrink-0"
      style={{
        background: "oklch(0.11 0.012 240)",
        borderBottom: `1px solid ${BORDER}`,
      }}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <div
            className="text-xs text-gray-500 uppercase tracking-widest mb-0.5"
            style={{ fontFamily: DISP }}
          >
            Float Balance
          </div>
          <div
            className="text-2xl font-bold"
            style={{ fontFamily: MONO, color: GOLD }}
          >
            {fmt(terminal.floatBalance)}
          </div>
        </div>
        <div className="w-px h-10 bg-white/10" />
        <div>
          <div
            className="text-xs text-gray-500 uppercase tracking-widest mb-0.5"
            style={{ fontFamily: DISP }}
          >
            Commission
          </div>
          <div
            className="text-2xl font-bold"
            style={{ fontFamily: MONO, color: GREEN }}
          >
            {fmt(terminal.commissionBalance)}
          </div>
        </div>
        <div className="w-px h-10 bg-white/10" />
        <div className="flex flex-col items-end gap-1">
          <div className="text-xs text-gray-500" style={{ fontFamily: DISP }}>
            Today{" "}
            <span className="font-bold text-white">{terminal.txToday}</span> /{" "}
            {terminal.txTarget} tx
          </div>
          <div
            className="w-20 h-1.5 rounded-full overflow-hidden"
            style={{ background: "oklch(0.20 0.01 240)" }}
          >
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${progress}%`,
                background: progress >= 100 ? GREEN : BLUE,
              }}
            />
          </div>
          <div
            className="flex items-center gap-1 text-xs"
            style={{ color: GOLD, fontFamily: MONO }}
          >
            🔥 {terminal.tier ?? "—"} ·{" "}
            {gam.streak != null ? `${gam.streak}d streak` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Quick Access Strip ───────────────────────────────────────────────────────

export function TileComponent({
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
    const delay =
      (crypto.getRandomValues(new Uint32Array(1))[0] / 4294967295) * 300;
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

function LiveTicker({ items: tickerItems }: { items?: { label: string; value: string; change: string; up: boolean }[] }) {
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
    ...(tickerItems ?? []),
    ...(tickerItems ?? []),
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

export function MicroInsuranceScreen({ onBack }: { onBack: () => void }) {
  // The micro-insurance product catalog and enrolment endpoints are not
  // connected to this build. We therefore show an honest unavailable state
  // instead of fabricated products, premiums, or a fake "subscription" success.
  return (
    <div className="flex flex-col h-screen" style={{ background: BG }}>
      <ScreenHeader
        title="🛡️ Micro-Insurance"
        onBack={onBack}
        badge={
          <span
            className="text-xs px-2 py-0.5 rounded-full font-semibold"
            style={{
              background: "oklch(0.55 0.22 300 / 0.2)",
              color: "#a855f7",
              fontFamily: DISP,
            }}
          >
            EMBEDDED FINANCE
          </span>
        }
      />
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
        <div className="text-5xl">🛡️</div>
        <p className="text-white font-bold" style={{ fontFamily: DISP }}>
          Micro-insurance is currently unavailable
        </p>
        <p className="text-gray-400 text-sm">
          Insurance products will appear here once the insurance service is
          connected. No premiums can be purchased in this build.
        </p>
      </div>
    </div>
  );
}


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
      {top4.map((t: any) => (
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

export function NumPad({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "⌫"];
  return (
    <div className="grid grid-cols-3 gap-2 p-4">
      {keys.map((k: any) => (
        <button
          key={k}
          onClick={() => {
            haptic("micro");
            if (k === "⌫") onChange(value.slice(0, -1));
            else if (k === "." && value.includes(".")) return;
            else if (value.length >= 10) return;
            else onChange(value + k);
          }}
          className="h-14 rounded-xl text-xl font-semibold transition-all active:scale-95 touch-target"
          aria-label={k === "⌫" ? "Delete" : k}
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


export function ScreenHeader({
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
        onClick={() => {
          haptic("micro");
          onBack();
        }}
        className="w-10 h-10 rounded-lg flex items-center justify-center transition-colors hover:bg-white/10 text-gray-400 hover:text-white text-lg touch-target"
        aria-label="Go back"
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


export function loadTileUsage(): Record<string, number> {
  try {
    const raw = localStorage.getItem(TILE_USAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return {};
}

