// @ts-nocheck
import type { ChallengeType as MotionChallengeType } from "./useFaceMotionDetection";

type TileSize = "sm" | "md" | "lg" | "wide";

type TileCategory =
  | "transactions"
  | "customers"
  | "finance"
  | "inventory"
  | "compliance"
  | "reports"
  | "settings"
  | "communication";


interface Tile {
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


interface Transaction {
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


interface TerminalInfo {
  model: string;
  serialNo: string;
  agentName: string;
  agentCode: string;
  floatBalance: number;
  commissionBalance: number;
  network: "4G" | "3G" | "WiFi" | "Offline";
  signalStrength: number;
  batteryLevel: number;
  online: boolean;
  location: string;
  tier: "Bronze" | "Silver" | "Gold" | "Platinum";
  paperLevel: number;
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


interface GamificationData {
  streak: number;
  points: number;
  level: string;
  badges: string[];
  weeklyTarget: number;
  weeklyProgress: number;
  rank: number;
  totalAgents: number;
}

// ─── Mock Data ────────────────────────────────────────────────────────────────

const TERMINAL: TerminalInfo = {
  model: "PAX A920 MAX",
  serialNo: "A920M-NG-20240315-0042",
  agentName: "Adaeze Okonkwo",
  agentCode: "AG-LOS-004821",
  floatBalance: 485_250.0,
  commissionBalance: 12_840.5,
  network: "4G",
  signalStrength: 87,
  batteryLevel: 73,
  online: true,
  location: "Ikeja, Lagos",
  tier: "Gold",
  paperLevel: 68,
  txToday: 5,
  txTarget: 7,
};


const GAMIFICATION: GamificationData = {
  streak: 12,
  points: 8_450,
  level: "Gold Agent",
  badges: [
    "🏆 First ₦1M Day",
    "⚡ Speed Demon",
    "🛡️ Zero Fraud Month",
    "👥 100 Customers",
  ],
  weeklyTarget: 50,
  weeklyProgress: 38,
  rank: 14,
  totalAgents: 1_247,
};


const TILE_REGISTRY: Tile[] = [
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


const DEFAULT_LAYOUT = [
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


const FRAUD_ALERTS: FraudAlert[] = [
  {
    id: "FA-001",
    severity: "critical",
    type: "Velocity Breach",
    customer: "Unknown Customer",
    amount: 450000,
    time: "09:44",
    reason: "Amount 340% above 30-day average",
    explanation: [
      "Amount ₦450,000 exceeds your 30-day average by 340%",
      "Customer has 3 failed attempts in the last hour",
      "Transaction originates from flagged device ID",
      "CBN Tier 2 daily limit would be exceeded",
    ],
  },
  {
    id: "FA-002",
    severity: "high",
    type: "Structuring Detected",
    customer: "Emeka Eze",
    amount: 199500,
    time: "09:12",
    reason: "Multiple sub-threshold transactions",
    explanation: [
      "3 transactions of ₦199,500 within 2 hours",
      "Pattern matches known structuring behaviour",
      "Customer BVN linked to 2 other flagged accounts",
    ],
  },
];


const TICKER_ITEMS = [
  { label: "CASH-IN", value: "₦485,250", change: "+12.4%", up: true },
  { label: "CASH-OUT", value: "₦312,000", change: "+8.1%", up: true },
  { label: "TRANSFERS", value: "₦94,500", change: "-3.2%", up: false },
  { label: "FLOAT", value: "₦485,250", change: "+2.1%", up: true },
  { label: "COMMISSION", value: "₦12,840", change: "+18.7%", up: true },
  { label: "TX COUNT", value: "247", change: "+31", up: true },
  { label: "SUCCESS", value: "98.4%", change: "+0.3%", up: true },
  { label: "ALERTS", value: "2", change: "+2", up: false },
  { label: "STREAK", value: "12 days", change: "🔥", up: true },
  { label: "RANK", value: "#14", change: "↑3", up: true },
];


const CHART_DATA = [
  { h: "08:00", in: 45000, out: 12000 },
  { h: "09:00", in: 82000, out: 35000 },
  { h: "10:00", in: 120000, out: 67000 },
  { h: "11:00", in: 95000, out: 48000 },
  { h: "12:00", in: 150000, out: 89000 },
  { h: "13:00", in: 78000, out: 42000 },
  { h: "14:00", in: 110000, out: 55000 },
];


const COMMISSION_DATA = [
  { day: "Mon", earned: 1800 },
  { day: "Tue", earned: 2400 },
  { day: "Wed", earned: 1950 },
  { day: "Thu", earned: 3100 },
  { day: "Fri", earned: 2800 },
  { day: "Sat", earned: 4200 },
  { day: "Sun", earned: 590 },
];

// ─── Utility ──────────────────────────────────────────────────────────────────

const BG = "oklch(0.09 0.01 240)";

const CARD = "oklch(0.13 0.012 240)";

const BORDER = "oklch(0.18 0.012 240)";

const BLUE = "oklch(0.60 0.22 260)";

const GREEN = "#10b981";

const GOLD = "#f59e0b";

const RED = "#ef4444";

const MONO = "var(--font-mono)";

const DISP = "var(--font-display)";


const QR_TTL_MS = 15 * 60 * 1000;


type KycStep = "status" | "liveness" | "document" | "complete";

type DocType =
  | "NIN"
  | "BVN_CARD"
  | "PASSPORT"
  | "DRIVERS_LICENCE"
  | "VOTER_CARD";

// Liveness challenge pool for multi-challenge active verification

const KYC_CHALLENGE_POOL: Array<{
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

