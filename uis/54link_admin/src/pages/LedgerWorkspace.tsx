import { BookOpen } from "lucide-react";
import CrudWorkspace, { type CrudConfig } from "@/components/CrudWorkspace";

const config: CrudConfig = {
  domainKey: "tigerbeetle-ledger",
  title: "Double-Entry Ledger",
  subtitle: "TigerBeetle-style accounts, transfers, journal entries, and trial balance",
  icon: BookOpen,
  accentColor: "bg-violet-700",
  idField: "id",
  statusField: "status",
  searchFields: ["id", "debit_account_id", "credit_account_id", "user_data"],
  apiBase: "/api/db/transfers",
  fields: [
    { key: "debit_account_id", label: "Debit Account", type: "text", required: true },
    { key: "credit_account_id", label: "Credit Account", type: "text", required: true },
    { key: "amount", label: "Amount (₦)", type: "number", required: true },
    { key: "code", label: "Transfer Code", type: "select", options: ["1", "2", "3", "4", "5", "6"], defaultValue: "1" },
    { key: "user_data", label: "Reference / Narration", type: "text" },
  ],
  columns: [
    { key: "id", label: "Transfer ID" },
    { key: "debit_account_id", label: "Debit Account" },
    { key: "credit_account_id", label: "Credit Account" },
    { key: "amount", label: "Amount", render: (v) => `₦${Number(v).toLocaleString()}` },
    { key: "ledger", label: "Ledger" },
    { key: "status", label: "Status" },
  ],
  actions: [],
};

export default function LedgerWorkspace() {
  return <CrudWorkspace config={config} />;
}
