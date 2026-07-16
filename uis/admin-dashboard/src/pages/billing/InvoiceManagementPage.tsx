import { useEffect, useState } from "react";
import { billingApi } from "@/utils/api";
import { Activity, FileText, RefreshCw } from "lucide-react";

function fmtNGN(n: number): string {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n || 0);
}

const STATUS_COLORS: Record<string, string> = {
  paid: "bg-green-100 text-green-700",
  draft: "bg-gray-100 text-gray-600",
  pending: "bg-amber-100 text-amber-700",
  overdue: "bg-red-100 text-red-700",
  cancelled: "bg-red-100 text-red-500",
};

const STATUS_OPTIONS = ["", "paid", "draft", "pending", "overdue"];

export default function InvoiceManagementPage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const res = await billingApi.listInvoices({ page, page_size: 20, ...(statusFilter ? { status: statusFilter } : {}) });
      const d = res ?? {};
      setInvoices(Array.isArray(d) ? d : d?.invoices ?? d?.data ?? []);
      setTotal(d?.total ?? 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3">
        <FileText size={22} className="text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Invoices</h1>
          <p className="text-sm text-gray-500">Invoices issued to your account</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>{s ? s.charAt(0).toUpperCase() + s.slice(1) : "All Statuses"}</option>
            ))}
          </select>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
        <span className="ml-auto text-sm text-gray-500">Total: {total}</span>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center">
            <Activity size={40} className="animate-spin text-gray-300 mx-auto mb-4" />
            <p className="text-gray-400">Loading invoices...</p>
          </div>
        ) : invoices.length === 0 ? (
          <div className="p-12 text-center">
            <FileText size={40} className="text-gray-300 mx-auto mb-4" />
            <p className="text-gray-400">No invoices found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr className="text-left text-xs text-gray-500">
                  <th className="px-5 py-3 font-medium">Invoice #</th>
                  <th className="px-5 py-3 font-medium">Period</th>
                  <th className="px-5 py-3 font-medium text-right">Subtotal</th>
                  <th className="px-5 py-3 font-medium text-right">Tax</th>
                  <th className="px-5 py-3 font-medium text-right">Total</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Due Date</th>
                  <th className="px-5 py-3 font-medium">Paid At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {invoices.map((inv: any, i: number) => (
                  <tr key={inv.id ?? i} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-blue-600">{inv.invoice_number ?? inv.id}</td>
                    <td className="px-5 py-3 text-gray-600 text-xs">
                      {inv.period_start?.slice(0, 10)} → {inv.period_end?.slice(0, 10)}
                    </td>
                    <td className="px-5 py-3 text-right">{fmtNGN(inv.subtotal ?? 0)}</td>
                    <td className="px-5 py-3 text-right text-gray-500">{fmtNGN(inv.tax_amount ?? 0)}</td>
                    <td className="px-5 py-3 text-right font-semibold">{fmtNGN(inv.total ?? inv.total_amount ?? 0)}</td>
                    <td className="px-5 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[inv.status] ?? "bg-gray-100 text-gray-600"}`}>
                        {inv.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-500">{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "—"}</td>
                    <td className="px-5 py-3 text-xs text-gray-500">{inv.paid_at ? new Date(inv.paid_at).toLocaleDateString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-5 py-3 border-t border-gray-200 flex items-center justify-between">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1 || loading} className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50">Previous</button>
          <span className="text-sm text-gray-500">Page {page}</span>
          <button onClick={() => setPage((p) => p + 1)} disabled={invoices.length < 20 || loading} className="px-4 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50">Next</button>
        </div>
      </div>
    </div>
  );
}
