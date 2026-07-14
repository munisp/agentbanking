import { CreditCard } from "lucide-react";
import CrudWorkspace, { type CrudConfig } from "@/components/CrudWorkspace";

const config: CrudConfig = {
  domainKey: "card-management",
  title: "Card Management",
  subtitle: "Card issuance, PIN management, transaction limits, controls, tokenization",
  icon: CreditCard,
  accentColor: "bg-purple-600",
  idField: "id",
  statusField: "status",
  searchFields: ["id", "customerId", "cardNumber", "cardType", "network"],
  apiBase: "/api/db/accounts",
  fields: [
    { key: "customerId", label: "Customer ID", type: "text", required: true },
    { key: "cardType", label: "Card Type", type: "select", options: ["debit", "credit", "prepaid", "virtual"], required: true },
    { key: "nameOnCard", label: "Name on Card", type: "text", required: true },
    { key: "dailyLimit", label: "Daily Limit (₦)", type: "number", defaultValue: 500000 },
  ],
  columns: [
    { key: "id", label: "Card ID" },
    { key: "cardType", label: "Type" },
    { key: "cardNumber", label: "Card Number" },
    { key: "network", label: "Network" },
    { key: "expiryDate", label: "Expiry" },
    { key: "dailyLimit", label: "Daily Limit", render: (v) => `₦${Number(v).toLocaleString()}` },
    { key: "status", label: "Status" },
  ],
  actions: [
    { label: "Activate", key: "activate", condition: (r) => r.status === "requested" || r.status === "dispatched" },
    { label: "Block", key: "block", condition: (r) => r.status === "active" },
    { label: "Unblock", key: "unblock", condition: (r) => r.status === "blocked" },
    { label: "Set PIN", key: "set_pin", condition: (r) => !r.pinSet },
  ],
};

export default function CardManagementWorkspace() {
  return <CrudWorkspace config={config} />;
}
