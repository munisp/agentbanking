import { useEffect, useState } from "react";
import { billingApi } from "@/utils/api";
import { toast } from "sonner";
import { BookOpen, RefreshCw, Filter } from "lucide-react";

function fmtNGN(n: number): string {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n || 0);
}

function padTwo(n: number) {
  return n < 10 ? `0${n}` : String(n);
}

const BILLING_MODELS = ["", "revenue_share", "subscription", "hybrid"];

export default function BillingLedgerPage() {
  const now = new Date();
  const [dateFrom, setDateFrom] = useState(`${now.getFullYear()}-${padTwo(now.getMonth() + 1)}-01`);
  const [dateTo, setDateTo] = useState(now.toISOString().slice(0, 10));
  const [billingModel, setBillingModel] = useState("");
  const [page, setPage] = useState(1);

  const [entries, setEntries] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [aggregate, setAggregate] = useState<any[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const [ledger, agg] = await Promise.allSettled([
        billingApi.queryLedger({
          date_from: dateFrom,
          date_to: dateTo,
          ...(billingModel ? { billing_model: billingModel } : {}),
          page,
          page_size: 50,
        }),
        billingApi.aggregateRevenue({ date_from: dateFrom, date_to: dateTo }),
      ]);

      if (ledger.status === "fulfilled") {
        setEntries(ledger.value?.entries ?? ledger.value?.data ?? []);
        setTotal(ledger.value?.total ?? 0);
      } else {
        toast.error("Failed to load ledger entries");
      }
      if (agg.status === "fulfilled") {
        setAggregate(agg.value?.periods ?? agg.value?.data ?? []);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page]);

  const applyFilters = () => {
    setPage(1);
    load();
  };

  const totalGross = entries.reduce((s, e) => s + Number(e.gross_fee ?? 0), 0);
  const totalPlatform = entries.reduce((s, e) => s + Number(e.platform_revenue ?? e.platform_net_fee ?? 0), 0);
  const totalAgent = entries.reduce((s, e) => s + Number(e.agent_commission ?? 0), 0);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3">
        <BookOpen size={22} className="text-blue-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing Ledger</h1>
          <p className="text-sm text-gray-500">Transaction-level fee splits and revenue records</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Billing Model</label>
            <select
              value={billingModel}
              onChange={(e) => setBillingModel(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {BILLING_MODELS.map((m) => (
                <option key={m} value={m}>{m ? m.replace(/_/g, " ") : "All Models"}</option>
              ))}
            </select>
          </div>
          <button
            onClick={applyFilters}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-60"
          >
            <Filter size={14} />
            {loading ? "Loading..." : "Apply Filters"}
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1 px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs text-gray-500">Total Gross Fees (page)</p>
          <p className="text-xl font-bold mt-1">{fmtNGN(totalGross)}</p>
          <p className="text-xs text-gray-400">{entries.length} entries</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs text-gray-500">Platform Revenue (page)</p>
          <p className="text-xl font-bold mt-1 text-green-600">{fmtNGN(totalPlatform)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs text-gray-500">Agent Commissions (page)</p>
          <p className="text-xl font-bold mt-1 text-blue-600">{fmtNGN(totalAgent)}</p>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">Ledger Entries</h2>
          <span className="text-xs text-gray-400">Total: {total}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-3 font-medium">Tx Ref</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Model</th>
                <th className="px-4 py-3 font-medium text-right">Gross Fee</th>
                <th className="px-4 py-3 font-medium text-right">Platform Rev</th>
                <th className="px-4 py-3 font-medium text-right">Agent Comm</th>
                <th className="px-4 py-3 font-medium text-right">Switch Fee</th>
                <th className="px-4 py-3 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">Loading...</td>
                </tr>
              )}
              {!loading && entries.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-gray-400">No entries found for the selected period</td>
                </tr>
              )}
              {entries.map((e: any, i: number) => (
                <tr key={e.id ?? i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-blue-700">{e.transaction_ref}</td>
                  <td className="px-4 py-3 text-gray-600">{e.transaction_type ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                      {e.billing_model?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium">{fmtNGN(e.gross_fee)}</td>
                  <td className="px-4 py-3 text-right text-green-600">{fmtNGN(e.platform_revenue ?? e.platform_net_fee)}</td>
                  <td className="px-4 py-3 text-right text-blue-600">{fmtNGN(e.agent_commission)}</td>
                  <td className="px-4 py-3 text-right text-gray-500">{fmtNGN(e.switch_fee)}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-5 py-3 border-t border-gray-200 flex items-center justify-between">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">Page {page}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={entries.length < 50 || loading}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      </div>

      {/* Aggregate Periods */}
      {aggregate.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200">
            <h2 className="text-sm font-semibold text-gray-700">Revenue by Period</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 font-medium">Period</th>
                  <th className="px-4 py-3 font-medium text-right">Tx Count</th>
                  <th className="px-4 py-3 font-medium text-right">Gross Fees</th>
                  <th className="px-4 py-3 font-medium text-right">Platform Revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {aggregate.map((row: any, i: number) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{row.period ?? row.date}</td>
                    <td className="px-4 py-3 text-right">{row.transaction_count ?? 0}</td>
                    <td className="px-4 py-3 text-right font-medium">{fmtNGN(row.total_gross_fees ?? row.gross_fees ?? 0)}</td>
                    <td className="px-4 py-3 text-right text-green-600">{fmtNGN(row.total_platform_revenue ?? row.platform_revenue ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
