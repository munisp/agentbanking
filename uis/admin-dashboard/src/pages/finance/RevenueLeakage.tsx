import { TrendingDown, RefreshCw, AlertTriangle } from "lucide-react";
import React, { useState } from "react";

interface LeakageItem {
  id: string;
  category: "fee_waiver" | "double_credit" | "uncollected_fee" | "failed_reversal" | "commission_overpay";
  description: string;
  amount: number;
  transaction_ref?: string;
  detected_at: string;
  status: "open" | "under_review" | "resolved" | "waived";
  assigned_to?: string;
}

const MOCK_LEAKAGES: LeakageItem[] = [
  { id: "leak-001", category: "uncollected_fee", description: "Card maintenance fee not collected for 234 dormant accounts", amount: 117000, detected_at: "2024-11-28", status: "open" },
  { id: "leak-002", category: "commission_overpay", description: "Agent ACE-0023 received duplicate commission for Nov batch", amount: 45000, transaction_ref: "TXN-20241128-0045", detected_at: "2024-11-29", status: "under_review", assigned_to: "Finance Team" },
  { id: "leak-003", category: "failed_reversal", description: "3 failed NIP reversals stuck — funds debited but not returned", amount: 230000, detected_at: "2024-11-25", status: "open" },
  { id: "leak-004", category: "double_credit", description: "Customer CNT-00812 received double credit on Nov 20 transfer", amount: 50000, transaction_ref: "TXN-20241120-0812", detected_at: "2024-11-21", status: "resolved" },
  { id: "leak-005", category: "fee_waiver", description: "Bulk fee waivers approved without management sign-off", amount: 88500, detected_at: "2024-11-27", status: "under_review", assigned_to: "Compliance" },
];

const CAT_LABELS: Record<string, string> = {
  fee_waiver: "Fee Waiver", double_credit: "Double Credit", uncollected_fee: "Uncollected Fee",
  failed_reversal: "Failed Reversal", commission_overpay: "Commission Overpay",
};
const STATUS_STYLES: Record<string, string> = {
  open: "bg-red-100 text-red-700", under_review: "bg-amber-100 text-amber-700",
  resolved: "bg-emerald-100 text-emerald-700", waived: "bg-gray-100 text-gray-600",
};

const RevenueLeakage: React.FC = () => {
  const [items, setItems] = useState<LeakageItem[]>(MOCK_LEAKAGES);
  const [loading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const updateStatus = (id: string, newStatus: string) => {
    setItems(prev => prev.map(i => i.id === id ? { ...i, status: newStatus as LeakageItem["status"] } : i));
  };

  const filtered = items.filter(i => statusFilter === "all" || i.status === statusFilter);
  const totalOpen = items.filter(i => i.status === "open" || i.status === "under_review").reduce((s, i) => s + i.amount, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingDown className="w-7 h-7 text-red-600" /> Revenue Leakage Detection
          </h1>
          <p className="text-gray-500 text-sm mt-1">Identify and recover uncollected fees, duplicate credits and commission errors</p>
        </div>
        <button onClick={() => setItems(MOCK_LEAKAGES)} className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-4">
        <AlertTriangle className="w-6 h-6 text-red-600 shrink-0" />
        <div>
          <p className="font-semibold text-red-800">₦{totalOpen.toLocaleString()} at risk</p>
          <p className="text-sm text-red-700">Total unresolved leakage requiring action</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Open", value: items.filter(i => i.status === "open").length, color: "text-red-600" },
          { label: "Under Review", value: items.filter(i => i.status === "under_review").length, color: "text-amber-600" },
          { label: "Resolved", value: items.filter(i => i.status === "resolved").length, color: "text-emerald-600" },
          { label: "Waived", value: items.filter(i => i.status === "waived").length, color: "text-gray-500" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        {["all", "open", "under_review", "resolved", "waived"].map(f => (
          <button key={f} onClick={() => setStatusFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-colors ${statusFilter === f ? "bg-red-600 border-red-500 text-white" : "bg-white border-gray-200 text-gray-600"}`}>
            {f.replace("_", " ")}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {["Category", "Description", "Amount", "Detected", "Status", "Actions"].map(h => (
                <th key={h} className="text-left py-3 px-4 text-xs font-medium text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-10"><RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-400" /></td></tr>
            ) : filtered.map(item => (
              <tr key={item.id} className="hover:bg-gray-50/50">
                <td className="py-3 px-4"><span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded">{CAT_LABELS[item.category]}</span></td>
                <td className="py-3 px-4">
                  <p className="text-gray-900">{item.description}</p>
                  {item.transaction_ref && <p className="text-xs text-gray-400 font-mono">{item.transaction_ref}</p>}
                  {item.assigned_to && <p className="text-xs text-blue-600">Assigned: {item.assigned_to}</p>}
                </td>
                <td className="py-3 px-4 font-semibold text-red-600">₦{item.amount.toLocaleString()}</td>
                <td className="py-3 px-4 text-gray-500">{item.detected_at}</td>
                <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_STYLES[item.status]}`}>{item.status.replace("_", " ")}</span></td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    {item.status === "open" && (
                      <button onClick={() => updateStatus(item.id, "under_review")} className="text-xs px-2 py-1 bg-amber-50 text-amber-600 hover:bg-amber-100 rounded">Review</button>
                    )}
                    {item.status === "under_review" && (
                      <>
                        <button onClick={() => updateStatus(item.id, "resolved")} className="text-xs px-2 py-1 bg-emerald-50 text-emerald-600 hover:bg-emerald-100 rounded">Resolve</button>
                        <button onClick={() => updateStatus(item.id, "waived")} className="text-xs px-2 py-1 bg-gray-50 text-gray-600 hover:bg-gray-100 rounded">Waive</button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RevenueLeakage;
