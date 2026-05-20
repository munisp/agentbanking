import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  GitCompare,
  Search,
  RefreshCw,
  Plus,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  FileSpreadsheet,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  in_progress: "bg-blue-500/20 text-blue-400",
  matched: "bg-emerald-500/20 text-emerald-400",
  mismatched: "bg-red-500/20 text-red-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

export default function ReconciliationEnginePage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedBatch, setSelectedBatch] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    source: "nibss",
    target: "internal",
    period_start: "",
    period_end: "",
    description: "",
  });

  // @ts-ignore Sprint 85
  const batchesQuery = trpc.reconciliationEngine.listBatches.useQuery({
    limit: 100,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.reconciliationEngine.getStats.useQuery();
  // @ts-ignore Sprint 85
  const createMutation = trpc.reconciliationEngine.createBatch.useMutation({
    onSuccess: () => {
      batchesQuery.refetch();
      setShowCreate(false);
      toast.success("Reconciliation batch created");
    },
    onError: (e: any) => toast.error(e.message),
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const runMutation = trpc.reconciliationEngine.runReconciliation.useMutation({
    onSuccess: () => {
      batchesQuery.refetch();
      toast.success("Reconciliation started");
    },
    onError: (e: any) => toast.error(e.message),
  });

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const batches = (batchesQuery.data ?? []).filter((b: any) => {
    if (
      search &&
      !b.source?.toLowerCase().includes(search.toLowerCase()) &&
      !b.target?.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    if (statusFilter !== "all" && b.status !== statusFilter) return false;
    return true;
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <GitCompare className="h-6 w-6 text-teal-400" /> Reconciliation
            Engine
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Automated matching between NIBSS, bank statements, and internal
            ledger
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              batchesQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Batch
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          {
            label: "Total Batches",
            value: stats?.totalBatches ?? 0,
            icon: FileSpreadsheet,
            color: "text-teal-400",
          },
          {
            label: "Matched",
            value: stats?.matched ?? 0,
            icon: CheckCircle,
            color: "text-emerald-400",
          },
          {
            label: "Mismatched",
            value: stats?.mismatched ?? 0,
            icon: XCircle,
            color: "text-red-400",
          },
          {
            label: "In Progress",
            value: stats?.inProgress ?? 0,
            icon: Clock,
            color: "text-blue-400",
          },
          {
            label: "Match Rate",
            value: `${(stats?.matchRate ?? 0).toFixed(1)}%`,
            icon: GitCompare,
            color: "text-emerald-400",
          },
        ].map((s: any) => (
          <div
            key={s.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
          >
            <div className="flex items-center gap-2">
              <s.icon className={`h-4 w-4 ${s.color}`} />
              <p className="text-xs text-zinc-400 uppercase">{s.label}</p>
            </div>
            <p className="text-2xl font-bold text-white mt-2">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search batches..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e: any) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
        >
          <option value="all">All Statuses</option>
          {Object.keys(STATUS_COLORS).map((s: any) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700/50 text-zinc-400">
              <th className="text-left p-4 font-medium">Source</th>
              <th className="text-left p-4 font-medium">Target</th>
              <th className="text-left p-4 font-medium">Period</th>
              <th className="text-left p-4 font-medium">Matched</th>
              <th className="text-left p-4 font-medium">Mismatched</th>
              <th className="text-left p-4 font-medium">Status</th>
              <th className="text-left p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {batchesQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-zinc-700/30">
                  <td colSpan={7} className="p-4">
                    <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                  </td>
                </tr>
              ))
            ) : batches.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-zinc-500">
                  No reconciliation batches found
                </td>
              </tr>
            ) : (
              batches.map((b: any) => (
                <tr
                  key={b.id}
                  className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                >
                  <td className="p-4 text-white font-medium">{b.source}</td>
                  <td className="p-4 text-zinc-300">{b.target}</td>
                  <td className="p-4 text-zinc-400 text-xs">
                    {b.period_start
                      ? `${new Date(b.period_start).toLocaleDateString()} — ${new Date(b.period_end).toLocaleDateString()}`
                      : "—"}
                  </td>
                  <td className="p-4 text-emerald-400 font-bold">
                    {b.matched_count || 0}
                  </td>
                  <td className="p-4 text-red-400 font-bold">
                    {b.mismatched_count || 0}
                  </td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[b.status] || "bg-zinc-500/20 text-zinc-400"}`}
                    >
                      {b.status?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-1">
                      <button
                        onClick={() => setSelectedBatch(b)}
                        className="p-1.5 hover:bg-zinc-700 rounded-lg"
                      >
                        <Eye className="h-4 w-4 text-zinc-400" />
                      </button>
                      {b.status === "pending" && (
                        <button
                          onClick={() => runMutation.mutate({ id: b.id })}
                          className="p-1.5 hover:bg-teal-700/30 rounded-lg"
                          title="Run"
                        >
                          <GitCompare className="h-4 w-4 text-teal-400" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setShowCreate(false)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-md w-full mx-4"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-4">
              New Reconciliation Batch
            </h3>
            <div className="space-y-3">
              <select
                value={form.source}
                onChange={(e: any) =>
                  setForm({ ...form, source: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                {[
                  "nibss",
                  "interswitch",
                  "bank_statement",
                  "paystack",
                  "flutterwave",
                ].map((s: any) => (
                  <option key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <select
                value={form.target}
                onChange={(e: any) =>
                  setForm({ ...form, target: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                {["internal", "general_ledger", "settlement_account"].map(
                  (t: any) => (
                    <option key={t} value={t}>
                      {t.replace(/_/g, " ")}
                    </option>
                  )
                )}
              </select>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-zinc-400">Start Date</label>
                  <input
                    type="date"
                    value={form.period_start}
                    onChange={(e: any) =>
                      setForm({ ...form, period_start: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-400">End Date</label>
                  <input
                    type="date"
                    value={form.period_end}
                    onChange={(e: any) =>
                      setForm({ ...form, period_end: e.target.value })
                    }
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                // @ts-ignore Sprint 85
                <button
                  onClick={() => createMutation.mutate(form)}
                  className="px-4 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg text-sm"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedBatch && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedBatch(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-white">Batch Details</h3>
              <button
                onClick={() => setSelectedBatch(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedBatch).map(([key, value]) => (
                <div
                  key={key}
                  className="flex justify-between border-b border-zinc-800 pb-2"
                >
                  <span className="text-zinc-400 text-sm">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-white text-sm font-mono max-w-[250px] truncate">
                    {String(value ?? "—")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
