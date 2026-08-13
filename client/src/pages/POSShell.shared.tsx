

export type TileSize = "sm" | "md" | "lg" | "wide";

export type TileCategory =
  | "transactions"
  | "customers"
  | "finance"
  | "inventory"
  | "compliance"
  | "reports"
  | "settings"
  | "communication";


export interface Tile {
  id: string;
  label: string;
  icon: string;
  color: string;
  bgColor: string;
  category: TileCategory;
  size: TileSize;
  screen: string;
  badge?: number;
  hot?: boolean;
  description: string;
  usageCount?: number;
}


export interface Transaction {
  id: string;
  type: string;
  amount: number;
  customer: string;
  phone?: string;
  status: "success" | "pending" | "failed";
  time: string;
  ref: string;
  channel?: string;
}


export interface TerminalInfo {
  model: string | null;
  serialNo: string | null;
  agentName: string | null;
  agentCode: string | null;
  floatBalance: number | null;
  commissionBalance: number | null;
  network: "4G" | "3G" | "WiFi" | "Offline" | null;
  signalStrength: number | null;
  batteryLevel: number | null;
  online: boolean;
  location: string | null;
  tier: "Bronze" | "Silver" | "Gold" | "Platinum" | null;
  paperLevel: number | null;
  txToday: number;
  txTarget: number;
}


interface FraudAlert {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  type: string;
  customer: string;
  amount: number;
  time: string;
  reason: string;
  explanation: string[];
  description?: string;
}


export interface GamificationData {
  streak: number | null;
  points: number | null;
  level: string | null;
  badges: string[];
  weeklyTarget: number | null;
  weeklyProgress: number | null;
  rank: number | null;
  totalAgents: number | null;
}

// ─── Terminal identity ──────────────────────────────────────────────────────
// No fabricated agent identity, float, or device telemetry: every field starts
// UNKNOWN and is populated only from the signed-in agent's profile / store.

export const TERMINAL_UNKNOWN: TerminalInfo = {
  model: null,
  serialNo: null,
  agentName: null,
  agentCode: null,
  floatBalance: null,
  commissionBalance: null,
  network: null,
  signalStrength: null,
  batteryLevel: null,
  online: false,
  location: null,
  tier: null,
  paperLevel: null,
  txToday: 0,
  txTarget: 0,
};

// No fabricated streaks/points/ranks: populated only from the live
// loyalty profile / agent store; null renders as "—".

export const GAMIFICATION_EMPTY: GamificationData = {
  streak: null,
  points: null,
  level: null,
  badges: [],
  weeklyTarget: null,
  weeklyProgress: null,
  rank: null,
  totalAgents: null,
};

/** Live gamification data (loyalty profile + agent store); nulls render as "—". */

export const TILE_REGISTRY: Tile[] = [
  // Transactions
  {
    id: "cash-in",
    label: "Cash In",
    icon: "⬇",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "transactions",
    size: "lg",
    screen: "CashIn",
    hot: true,
    description: "Accept cash deposits",
    badge: 0,
    usageCount: 142,
  },
  {
    id: "cash-out",
    label: "Cash Out",
    icon: "⬆",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "transactions",
    size: "lg",
    screen: "CashOut",
    hot: true,
    description: "Dispense cash withdrawals",
    badge: 0,
    usageCount: 98,
  },
  {
    id: "transfer",
    label: "Transfer",
    icon: "⇄",
    color: "#8b5cf6",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "transactions",
    size: "md",
    screen: "Transfer",
    hot: false,
    description: "Send money transfers",
    badge: 0,
    usageCount: 67,
  },
  {
    id: "card-payment",
    label: "Card Payment",
    icon: "💳",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "transactions",
    size: "md",
    screen: "CardPayment",
    hot: true,
    description: "Process card transactions",
    badge: 0,
    usageCount: 55,
  },
  {
    id: "qr-payment",
    label: "QR Payment",
    icon: "▦",
    color: "#06b6d4",
    bgColor: "oklch(0.65 0.18 200 / 0.15)",
    category: "transactions",
    size: "md",
    screen: "QRPayment",
    hot: false,
    description: "Scan QR code to pay",
    badge: 0,
    usageCount: 33,
  },
  {
    id: "nfc-payment",
    label: "NFC / Tap",
    icon: "⟡",
    color: "#ec4899",
    bgColor: "oklch(0.60 0.22 340 / 0.15)",
    category: "transactions",
    size: "sm",
    screen: "NFCPayment",
    hot: false,
    description: "Contactless NFC payment",
    badge: 0,
    usageCount: 28,
  },
  {
    id: "airtime",
    label: "Airtime",
    icon: "📶",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "transactions",
    size: "sm",
    screen: "Airtime",
    hot: false,
    description: "Sell airtime & data",
    badge: 0,
    usageCount: 89,
  },
  {
    id: "bills",
    label: "Bill Payment",
    icon: "🧾",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "transactions",
    size: "sm",
    screen: "Bills",
    hot: false,
    description: "Pay utility bills",
    badge: 0,
    usageCount: 44,
  },
  {
    id: "reversal",
    label: "Reversal",
    icon: "↺",
    color: "#ef4444",
    bgColor: "oklch(0.60 0.22 25 / 0.15)",
    category: "transactions",
    size: "sm",
    screen: "Reversal",
    hot: false,
    description: "Reverse a transaction",
    badge: 0,
    usageCount: 8,
  },
  // Customers
  {
    id: "cust-lookup",
    label: "Customer",
    icon: "👤",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "customers",
    size: "md",
    screen: "CustomerLookup",
    hot: false,
    description: "Look up customer account",
    badge: 0,
    usageCount: 71,
  },
  {
    id: "kyc",
    label: "KYC Verify",
    icon: "✓",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "customers",
    size: "sm",
    screen: "KYCVerify",
    hot: false,
    description: "Verify customer identity",
    badge: 3,
    usageCount: 22,
  },
  {
    id: "biometric",
    label: "Biometric",
    icon: "☝",
    color: "#8b5cf6",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "customers",
    size: "sm",
    screen: "Biometric",
    hot: false,
    description: "Fingerprint enrollment",
    badge: 0,
    usageCount: 15,
  },
  {
    id: "acct-open",
    label: "Open Account",
    icon: "+",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "customers",
    size: "md",
    screen: "OpenAccount",
    hot: false,
    description: "Open a new bank account",
    badge: 0,
    usageCount: 18,
  },
  // Finance
  {
    id: "float-bal",
    label: "Float Balance",
    icon: "₦",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "finance",
    size: "wide",
    screen: "FloatBalance",
    hot: true,
    description: "Check your float balance",
    badge: 0,
    usageCount: 120,
  },
  {
    id: "commission",
    label: "Commission",
    icon: "%",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "finance",
    size: "md",
    screen: "Commission",
    hot: false,
    description: "View earned commissions",
    badge: 0,
    usageCount: 45,
  },
  {
    id: "settlement",
    label: "Settlement",
    icon: "⊡",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "finance",
    size: "md",
    screen: "Settlement",
    hot: false,
    description: "Daily settlement report",
    badge: 0,
    usageCount: 30,
  },
  {
    id: "reconcile",
    label: "Reconcile",
    icon: "⊞",
    color: "#8b5cf6",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "finance",
    size: "sm",
    screen: "Reconcile",
    hot: false,
    description: "End-of-day reconciliation",
    badge: 0,
    usageCount: 20,
  },
  // Compliance
  {
    id: "fraud-alerts",
    label: "Fraud Alerts",
    icon: "⚠",
    color: "#ef4444",
    bgColor: "oklch(0.60 0.22 25 / 0.15)",
    category: "compliance",
    size: "md",
    screen: "FraudAlerts",
    hot: false,
    description: "View fraud alerts",
    badge: 2,
    usageCount: 12,
  },
  {
    id: "aml-check",
    label: "AML Check",
    icon: "🔍",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "compliance",
    size: "sm",
    screen: "AMLCheck",
    hot: false,
    description: "Anti-money laundering check",
    badge: 0,
    usageCount: 9,
  },
  {
    id: "audit-log",
    label: "Audit Log",
    icon: "📋",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "compliance",
    size: "sm",
    screen: "AuditLog",
    hot: false,
    description: "View audit trail",
    badge: 0,
    usageCount: 7,
  },
  {
    id: "my-limits",
    label: "My Limits",
    icon: "⚡",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "compliance",
    size: "md",
    screen: "MyLimits",
    hot: false,
    description: "View your tier velocity limits",
    badge: 0,
    usageCount: 0,
  },
  // Reports
  {
    id: "daily-report",
    label: "Daily Report",
    icon: "📊",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "reports",
    size: "md",
    screen: "DailyReport",
    hot: false,
    description: "Today's summary report",
    badge: 0,
    usageCount: 38,
  },
  {
    id: "tx-history",
    label: "Tx History",
    icon: "⏱",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "reports",
    size: "md",
    screen: "TxHistory",
    hot: false,
    description: "Transaction history",
    badge: 0,
    usageCount: 60,
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: "📈",
    color: "#8b5cf6",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "reports",
    size: "sm",
    screen: "Analytics",
    hot: false,
    description: "Performance analytics",
    badge: 0,
    usageCount: 25,
  },
  {
    id: "scorecard",
    label: "Scorecard",
    icon: "🏅",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "reports",
    size: "sm",
    screen: "Scorecard",
    hot: false,
    description: "Agent performance scorecard",
    badge: 0,
    usageCount: 18,
  },
  // Settings
  {
    id: "terminal-cfg",
    label: "Terminal",
    icon: "⚙",
    color: "#6b7280",
    bgColor: "oklch(0.40 0.01 240 / 0.3)",
    category: "settings",
    size: "sm",
    screen: "TerminalConfig",
    hot: false,
    description: "Terminal configuration",
    badge: 0,
    usageCount: 5,
  },
  {
    id: "printer-test",
    label: "Print Test",
    icon: "🖨",
    color: "#6b7280",
    bgColor: "oklch(0.40 0.01 240 / 0.3)",
    category: "settings",
    size: "sm",
    screen: "PrinterTest",
    hot: false,
    description: "Test receipt printer",
    badge: 0,
    usageCount: 4,
  },
  {
    id: "network-test",
    label: "Network",
    icon: "📡",
    color: "#6b7280",
    bgColor: "oklch(0.40 0.01 240 / 0.3)",
    category: "settings",
    size: "sm",
    screen: "NetworkTest",
    hot: false,
    description: "Network diagnostics",
    badge: 0,
    usageCount: 3,
  },
  {
    id: "firmware",
    label: "Firmware OTA",
    icon: "⬆",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "settings",
    size: "sm",
    screen: "FirmwareOTA",
    hot: false,
    description: "Update terminal firmware",
    badge: 1,
    usageCount: 2,
  },
  // Embedded Finance
  {
    id: "nano-loan",
    label: "Nano Loan",
    icon: "💰",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "finance",
    size: "md",
    screen: "NanoLoan",
    hot: true,
    description: "Apply for instant float loan",
    badge: 0,
    usageCount: 15,
  },
  {
    id: "eod-reconcile",
    label: "EOD Wizard",
    icon: "📋",
    color: "#8b5cf6",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "reports",
    size: "md",
    screen: "EODReconcile",
    hot: false,
    description: "End-of-day reconciliation wizard",
    badge: 0,
    usageCount: 10,
  },
  {
    id: "ussd-sim",
    label: "USSD Test",
    icon: "#",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "settings",
    size: "sm",
    screen: "__ussd__",
    hot: false,
    description: "USSD channel simulator",
    badge: 0,
    usageCount: 6,
  },
  {
    id: "micro-insurance",
    label: "Insurance",
    icon: "🛡",
    color: "#a855f7",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "finance",
    size: "md",
    screen: "MicroInsurance",
    hot: true,
    description: "Micro-insurance products",
    badge: 0,
    usageCount: 8,
  },
  {
    id: "architecture",
    label: "Architecture",
    icon: "⬡",
    color: "#06b6d4",
    bgColor: "oklch(0.65 0.18 200 / 0.15)",
    category: "settings",
    size: "sm",
    screen: "__arch__",
    hot: false,
    description: "Platform architecture",
    badge: 0,
    usageCount: 2,
  },
  // New features
  {
    id: "fraud-dash",
    label: "Fraud Monitor",
    icon: "🔴",
    color: "#ef4444",
    bgColor: "oklch(0.60 0.22 25 / 0.15)",
    category: "compliance",
    size: "md",
    screen: "__fraud_dash__",
    hot: true,
    description: "Real-time fraud detection",
    badge: 3,
    usageCount: 20,
  },
  {
    id: "live-chat",
    label: "Live Support",
    icon: "💬",
    color: "#3b82f6",
    bgColor: "oklch(0.60 0.22 260 / 0.15)",
    category: "communication",
    size: "md",
    screen: "__live_chat__",
    hot: false,
    description: "Chat with support team",
    badge: 0,
    usageCount: 14,
  },
  {
    id: "loyalty",
    label: "My Rewards",
    icon: "⭐",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "finance",
    size: "md",
    screen: "__loyalty__",
    hot: true,
    description: "Points, tiers & rewards",
    badge: 0,
    usageCount: 22,
  },
  {
    id: "disputes",
    label: "My Disputes",
    icon: "⚖",
    color: "#a855f7",
    bgColor: "oklch(0.55 0.22 300 / 0.15)",
    category: "compliance",
    size: "md",
    screen: "Disputes",
    hot: false,
    description: "Raise & track disputes",
    badge: 0,
    usageCount: 5,
  },
  {
    id: "offline-resilience",
    label: "Offline & Sync",
    icon: "📶",
    color: "#f59e0b",
    bgColor: "oklch(0.78 0.18 80 / 0.15)",
    category: "settings",
    size: "md",
    screen: "OfflineResilience",
    hot: false,
    description: "Offline queue, sync & resilience status",
    badge: 0,
    usageCount: 0,
  },
  // Sprint 75: USSD Transactions & Carrier Switching
  {
    id: "ussd-tx",
    label: "USSD Transact",
    icon: "#",
    color: "#10b981",
    bgColor: "oklch(0.65 0.18 160 / 0.15)",
    category: "transactions",
    size: "md",
    screen: "UssdTransaction",
    hot: true,
    description: "Process transactions via USSD codes",
    badge: 0,
    usageCount: 12,
  },
  {
    id: "carrier-switch",
    label: "Carrier Switch",
    icon: "📡",
    color: "#06b6d4",
    bgColor: "oklch(0.65 0.18 200 / 0.15)",
    category: "settings",
    size: "md",
    screen: "CarrierSwitch",
    hot: true,
    description: "Switch carriers based on signal",
    badge: 0,
    usageCount: 8,
  },
];

// ─── UX Enhancement Constants ─────────────────────────────────────────────────

// Tiles that work offline (P2: offline dimming)

export const OFFLINE_CAPABLE_TILES = new Set([
  "cash-in",
  "cash-out",
  "airtime",
  "bills",
  "transfer",
  "float-bal",
  "commission",
  "daily-report",
  "tx-history",
  "offline-resilience",
  "ussd-tx",
  "carrier-switch",
  "cust-lookup",
  "kyc",
  "biometric",
  "acct-open",
]);

// Quick-action definitions per tile (P1: long-press menu)

export const TILE_QUICK_ACTIONS: Record<
  string,
  Array<{
    label: string;
    icon: string;
    screenOverride?: string;
    amount?: number;
  }>
> = {
  "cash-in": [
    { label: "Quick ₦1,000", icon: "💵", amount: 1000 },
    { label: "Quick ₦5,000", icon: "💵", amount: 5000 },
    { label: "Quick ₦10,000", icon: "💵", amount: 10000 },
    { label: "Quick ₦20,000", icon: "💵", amount: 20000 },
  ],
  "cash-out": [
    { label: "Quick ₦1,000", icon: "💵", amount: 1000 },
    { label: "Quick ₦5,000", icon: "💵", amount: 5000 },
    { label: "Quick ₦10,000", icon: "💵", amount: 10000 },
    { label: "Quick ₦50,000", icon: "💵", amount: 50000 },
  ],
  transfer: [
    { label: "Repeat Last Transfer", icon: "↺" },
    { label: "Favorites", icon: "⭐" },
  ],
  "float-bal": [
    { label: "Request Top-Up", icon: "📤" },
    { label: "Transfer to Bank", icon: "🏦" },
    { label: "View History", icon: "📊" },
  ],
  commission: [
    { label: "Withdraw Commission", icon: "💰" },
    { label: "View Breakdown", icon: "📊" },
  ],
  "cust-lookup": [
    { label: "Recent Customers", icon: "🕐" },
    { label: "New Customer", icon: "➕" },
    { label: "Search by Phone", icon: "📱" },
  ],
};

// Tile theme color presets (P3: tile theming)

export const TILE_THEME_COLORS = [
  { name: "Default", hue: -1 },
  { name: "Blue", hue: 260 },
  { name: "Green", hue: 160 },
  { name: "Gold", hue: 80 },
  { name: "Red", hue: 25 },
  { name: "Purple", hue: 300 },
  { name: "Cyan", hue: 200 },
  { name: "Pink", hue: 340 },
];

// Amount chips for quick entry strip (P1)

export const QUICK_AMOUNTS = [500, 1_000, 2_000, 5_000, 10_000, 20_000, 50_000];

// Tile customization persistence key

export const TILE_CUSTOM_KEY = "pos_tile_customizations";

export const TILE_USAGE_KEY = "pos_tile_usage";

const LAYOUT_PRESET_KEY = "pos_layout_preset";


export interface TileCustomization {
  order: string[];
  sizes: Record<string, TileSize>;
  colors: Record<string, number>;
  groups: Record<string, string[]>;
  preset: string;
}


export const DEFAULT_LAYOUT = [
  "cash-in",
  "cash-out",
  "transfer",
  "card-payment",
  "qr-payment",
  "float-bal",
  "nfc-payment",
  "airtime",
  "bills",
  "cust-lookup",
  "kyc",
  "commission",
  "fraud-alerts",
  "daily-report",
  "tx-history",
  "terminal-cfg",
  "nano-loan",
  "eod-reconcile",
  "fraud-dash",
  "live-chat",
  "loyalty",
  "disputes",
];









// ─── Utility ──────────────────────────────────────────────────────────────────

export const BG = "oklch(0.09 0.01 240)";

export const CARD = "oklch(0.13 0.012 240)";

export const BORDER = "oklch(0.18 0.012 240)";

export const BLUE = "oklch(0.60 0.22 260)";

export const GREEN = "#10b981";

export const GOLD = "#f59e0b";

export const RED = "#ef4444";

export const MONO = "var(--font-mono)";

export const DISP = "var(--font-display)";


export const QR_TTL_MS = 15 * 60 * 1000;


export type KycStep = "status" | "liveness" | "document" | "complete";

export type DocType =
  | "NIN"
  | "BVN_CARD"
  | "PASSPORT"
  | "DRIVERS_LICENCE"
  | "VOTER_CARD";

export type MotionChallengeType =
  | "blink"
  | "turn_left"
  | "turn_right"
  | "nod"
  | "smile"
  | "open_mouth";

// Liveness challenge pool for multi-challenge active verification

export const KYC_CHALLENGE_POOL: Array<{
  type: MotionChallengeType;
  instruction: string;
}> = [
  { type: "blink", instruction: "Please blink your eyes" },
  { type: "turn_left", instruction: "Turn your head slowly to the left" },
  { type: "turn_right", instruction: "Turn your head slowly to the right" },
  { type: "nod", instruction: "Nod your head up and down" },
  { type: "smile", instruction: "Please smile" },
  { type: "open_mouth", instruction: "Open your mouth slightly" },
];

