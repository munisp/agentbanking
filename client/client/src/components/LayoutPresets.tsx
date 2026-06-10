/**
 * LayoutPresets — Predefined tile layout configurations for different agent roles (P2).
 */

export interface LayoutPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  tileIds: string[];
}

export const LAYOUT_PRESETS: LayoutPreset[] = [
  {
    id: "cashier",
    name: "Cashier Mode",
    description: "Optimized for high-speed cash transactions",
    icon: "💵",
    tileIds: [
      "cash-in",
      "cash-out",
      "float-bal",
      "transfer",
      "commission",
      "reversal",
    ],
  },
  {
    id: "full",
    name: "Full Agent",
    description: "All tiles visible — complete agent dashboard",
    icon: "📊",
    tileIds: [
      "cash-in",
      "cash-out",
      "transfer",
      "card-payment",
      "qr-payment",
      "nfc-payment",
      "airtime",
      "bills",
      "reversal",
      "cust-lookup",
      "kyc",
      "biometric",
      "acct-open",
      "float-bal",
      "commission",
      "settlement",
      "reconcile",
      "fraud-alerts",
      "aml-check",
      "audit-log",
      "my-limits",
      "daily-report",
      "tx-history",
      "analytics",
      "scorecard",
      "terminal-config",
      "printer-test",
      "network-test",
      "firmware-ota",
      "nano-loan",
      "eod-reconcile",
      "micro-insurance",
      "disputes",
      "offline-resilience",
      "ussd-tx",
      "carrier-switch",
    ],
  },
  {
    id: "supervisor",
    name: "Supervisor Mode",
    description: "Monitoring and oversight focused",
    icon: "👁️",
    tileIds: [
      "fraud-alerts",
      "audit-log",
      "daily-report",
      "analytics",
      "settlement",
      "reconcile",
      "my-limits",
      "scorecard",
      "disputes",
    ],
  },
  {
    id: "field",
    name: "Field Agent",
    description: "Optimized for outdoor agent operations",
    icon: "🏃",
    tileIds: [
      "cash-in",
      "cash-out",
      "kyc",
      "acct-open",
      "cust-lookup",
      "biometric",
      "airtime",
      "bills",
      "float-bal",
      "offline-resilience",
      "ussd-tx",
      "carrier-switch",
    ],
  },
  {
    id: "custom",
    name: "Custom",
    description: "Your personal layout",
    icon: "✨",
    tileIds: [],
  },
];

export function getPresetById(id: string): LayoutPreset | undefined {
  return LAYOUT_PRESETS.find(p => p.id === id);
}
