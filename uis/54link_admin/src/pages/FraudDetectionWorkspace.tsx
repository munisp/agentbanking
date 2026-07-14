import { Shield } from "lucide-react";
import CrudWorkspace, { type CrudConfig } from "@/components/CrudWorkspace";

const config: CrudConfig = {
  domainKey: "fraud-detection",
  title: "Fraud Detection",
  subtitle: "Real-time transaction screening, risk scoring, watchlist management, behavioral analysis",
  icon: Shield,
  accentColor: "bg-red-700",
  idField: "screening_id",
  statusField: "decision",
  searchFields: ["screening_id", "transaction_id", "risk_level", "decision"],
  apiBase: "/api/db/accounts",
  fields: [
    { key: "transaction_id", label: "Transaction ID", type: "text", required: true },
    { key: "customer_id", label: "Customer ID", type: "text", required: true },
    { key: "amount", label: "Amount (₦)", type: "number", required: true },
    { key: "channel", label: "Channel", type: "select", options: ["pos", "atm", "online", "mobile", "branch"], required: true },
    { key: "merchant", label: "Merchant", type: "text" },
  ],
  columns: [
    { key: "screening_id", label: "Screening ID" },
    { key: "transaction_id", label: "Transaction" },
    { key: "score", label: "Risk Score", render: (v) => {
      const score = Number(v);
      return `${score.toFixed(0)}/100`;
    }},
    { key: "risk_level", label: "Risk Level" },
    { key: "decision", label: "Decision" },
    { key: "latency_ms", label: "Latency", render: (v) => `${v}ms` },
  ],
  actions: [
    { label: "Review", key: "review", condition: (r) => r.decision === "review" },
    { label: "Override Allow", key: "override_allow", condition: (r) => r.decision === "block" },
  ],
};

export default function FraudDetectionWorkspace() {
  return <CrudWorkspace config={config} />;
}
