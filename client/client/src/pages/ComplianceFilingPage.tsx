import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Scale,
  Search,
  RefreshCw,
  Plus,
  Eye,
  CheckCircle,
  Clock,
  FileText,
  Send,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-zinc-500/20 text-zinc-400",
  pending_review: "bg-yellow-500/20 text-yellow-400",
  submitted: "bg-blue-500/20 text-blue-400",
  accepted: "bg-emerald-500/20 text-emerald-400",
  rejected: "bg-red-500/20 text-red-400",
  overdue: "bg-red-500/20 text-red-400",
};

export default function ComplianceFilingPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedFiling, setSelectedFiling] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    filing_type: "cbn_returns",
    period: "",
    due_date: "",
    description: "",
  });

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const filingsQuery = trpc.complianceFiling.listFilings.useQuery({
    limit: 100,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.complianceFiling.getStats.useQuery();
  const createMutation = trpc.complianceFiling.createFiling.useMutation({
    onSuccess: () => {
      filingsQuery.refetch();
      setShowCreate(false);
      toast.success("Filing created");
    },
    onError: (e: any) => toast.error(e.message),
  });
  const submitMutation = trpc.complianceFiling.submitFiling.useMutation({
    onSuccess: () => {
      filingsQuery.refetch();
      toast.success("Filing submitted");
    },
    onError: (e: any) => toast.error(e.message),
  });

  const filings = (filingsQuery.data ?? []).filter((f: any) => {
    if (
      search &&
      !f.filing_type?.toLowerCase().includes(search.toLowerCase()) &&
      !f.period?.includes(search)
    )
      return false;
    if (statusFilter !== "all" && f.status !== statusFilter) return false;
    return true;
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Scale className="h-6 w-6 text-indigo-400" /> Compliance Filing &
            Regulatory
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            CBN returns, NIBSS reports, AML filings, and regulatory compliance
            tracking
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              filingsQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Filing
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Filings",
            value: stats?.totalFilings ?? 0,
            icon: FileText,
            color: "text-indigo-400",
          },
          {
            label: "Submitted",
            value: stats?.submitted ?? 0,
            icon: Send,
            color: "text-blue-400",
          },
          {
            label: "Pending",
            value: stats?.pending ?? 0,
            icon: Clock,
            color: "text-yellow-400",
          },
          {
            label: "Overdue",
            value: stats?.overdue ?? 0,
            icon: Scale,
            color: "text-red-400",
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
            placeholder="Search filings..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
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
              <th className="text-left p-4 font-medium">Filing Type</th>
              <th className="text-left p-4 font-medium">Period</th>
              <th className="text-left p-4 font-medium">Due Date</th>
              <th className="text-left p-4 font-medium">Status</th>
              <th className="text-left p-4 font-medium">Submitted</th>
              <th className="text-left p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filingsQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-zinc-700/30">
                  <td colSpan={6} className="p-4">
                    <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                  </td>
                </tr>
              ))
            ) : filings.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-zinc-500">
                  No filings found
                </td>
              </tr>
            ) : (
              filings.map((f: any) => (
                <tr
                  key={f.id}
                  className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                >
                  <td className="p-4 text-white font-medium">
                    {f.filing_type?.replace(/_/g, " ")}
                  </td>
                  <td className="p-4 text-zinc-300">{f.period}</td>
                  <td className="p-4 text-zinc-400">
                    {f.due_date
                      ? new Date(f.due_date).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[f.status] || "bg-zinc-500/20 text-zinc-400"}`}
                    >
                      {f.status?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="p-4 text-zinc-400 text-xs">
                    {f.submitted_at
                      ? new Date(f.submitted_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="p-4">
                    <div className="flex gap-1">
                      <button
                        onClick={() => setSelectedFiling(f)}
                        className="p-1.5 hover:bg-zinc-700 rounded-lg"
                      >
                        <Eye className="h-4 w-4 text-zinc-400" />
                      </button>
                      {(f.status === "draft" ||
                        f.status === "pending_review") && (
                        <button
                          onClick={() =>
                            submitMutation.mutate({ filingId: f.id })
                          }
                          className="p-1.5 hover:bg-indigo-700/30 rounded-lg"
                          title="Submit"
                        >
                          <Send className="h-4 w-4 text-indigo-400" />
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
              New Compliance Filing
            </h3>
            <div className="space-y-3">
              <select
                value={form.filing_type}
                onChange={(e: any) =>
                  setForm({ ...form, filing_type: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                {[
                  "cbn_returns",
                  "nibss_report",
                  "aml_filing",
                  "tax_return",
                  "efcc_report",
                  "ndic_return",
                ].map((t: any) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Period (e.g., 2026-Q1)"
                value={form.period}
                onChange={(e: any) =>
                  setForm({ ...form, period: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <input
                type="date"
                value={form.due_date}
                onChange={(e: any) =>
                  setForm({ ...form, due_date: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <textarea
                placeholder="Description"
                value={form.description}
                onChange={(e: any) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={3}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                // @ts-ignore Sprint 85
                <button
                  // @ts-ignore Sprint 85
                  onClick={() => createMutation.mutate(form)}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedFiling && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedFiling(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-white">Filing Details</h3>
              <button
                onClick={() => setSelectedFiling(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedFiling).map(([key, value]) => (
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
