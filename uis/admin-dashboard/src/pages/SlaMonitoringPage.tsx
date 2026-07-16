import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Timer,
  RefreshCw,
  Plus,
  Eye,
  Edit,
  CheckCircle,
  AlertTriangle,
  XCircle,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  met: "bg-emerald-500/20 text-emerald-400",
  at_risk: "bg-yellow-500/20 text-yellow-400",
  breached: "bg-red-500/20 text-red-400",
  active: "bg-blue-500/20 text-blue-400",
};

export default function SlaMonitoringPage() {
  const [tab, setTab] = useState<"policies" | "breaches">("policies");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [form, setForm] = useState({
    name: "",
    service: "",
    metric: "uptime",
    target_value: "99.9",
    unit: "percent",
    measurement_window: "monthly",
  });

  const policiesQuery = trpc.slaMonitoringProd.listDefinitions.useQuery({
    limit: 100,
  });
  const breachesQuery = trpc.slaMonitoringProd.listBreaches.useQuery({
    limit: 100,
  });
  const statsQuery = trpc.slaMonitoringProd.summary.useQuery();
  const createMutation = trpc.slaMonitoringProd.createDefinition.useMutation({
    onSuccess: () => {
      policiesQuery.refetch();
      setShowCreate(false);
      toast.success("SLA policy created");
    },
    onError: (e: any) => toast.error(e.message),
  });

  const stats = statsQuery.data as any;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Timer className="h-6 w-6 text-rose-400" /> SLA Monitoring
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Service level agreements, uptime tracking, and breach management
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              policiesQuery.refetch();
              breachesQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Policy
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Policies",
            value: stats?.totalPolicies ?? 0,
            icon: Timer,
            color: "text-rose-400",
          },
          {
            label: "SLAs Met",
            value: stats?.met ?? 0,
            icon: CheckCircle,
            color: "text-emerald-400",
          },
          {
            label: "At Risk",
            value: stats?.atRisk ?? 0,
            icon: AlertTriangle,
            color: "text-yellow-400",
          },
          {
            label: "Breached",
            value: stats?.breached ?? 0,
            icon: XCircle,
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

      <div className="flex gap-2">
        {(["policies", "breaches"] as const).map((t: any) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize ${tab === t ? "bg-rose-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "policies" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Policy Name</th>
                <th className="text-left p-4 font-medium">Service</th>
                <th className="text-left p-4 font-medium">Metric</th>
                <th className="text-left p-4 font-medium">Target</th>
                <th className="text-left p-4 font-medium">Current</th>
                <th className="text-left p-4 font-medium">Status</th>
                <th className="text-left p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {policiesQuery.isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="border-b border-zinc-700/30">
                    <td colSpan={7} className="p-4">
                      <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : ((policiesQuery.data ?? []) as any[]).length === 0 ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-zinc-500">
                    No SLA policies found
                  </td>
                </tr>
              ) : (
                ((policiesQuery.data ?? []) as any[]).map((p: any) => (
                  <tr
                    key={p.id}
                    className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                  >
                    <td className="p-4 text-white font-medium">{p.name}</td>
                    <td className="p-4 text-zinc-300">{p.service}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 bg-rose-500/20 text-rose-400 rounded text-xs">
                        {p.metric}
                      </span>
                    </td>
                    <td className="p-4 text-zinc-300">
                      {p.target_value}
                      {p.unit === "percent" ? "%" : ` ${p.unit}`}
                    </td>
                    <td className="p-4 text-white font-bold">
                      {p.current_value ?? "—"}
                      {p.unit === "percent" ? "%" : ""}
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[p.status] || "bg-zinc-500/20 text-zinc-400"}`}
                      >
                        {p.status?.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="p-4">
                      <button
                        onClick={() => setSelectedItem(p)}
                        className="p-1.5 hover:bg-zinc-700 rounded-lg"
                      >
                        <Eye className="h-4 w-4 text-zinc-400" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "breaches" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Policy</th>
                <th className="text-left p-4 font-medium">Severity</th>
                <th className="text-left p-4 font-medium">Actual Value</th>
                <th className="text-left p-4 font-medium">Target</th>
                <th className="text-left p-4 font-medium">Duration</th>
                <th className="text-left p-4 font-medium">Occurred</th>
              </tr>
            </thead>
            <tbody>
              {breachesQuery.isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="border-b border-zinc-700/30">
                    <td colSpan={6} className="p-4">
                      <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : ((breachesQuery.data ?? []) as any[]).length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-zinc-500">
                    No SLA breaches recorded
                  </td>
                </tr>
              ) : (
                ((breachesQuery.data ?? []) as any[]).map((b: any) => (
                  <tr
                    key={b.id}
                    className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                  >
                    <td className="p-4 text-white">
                      {b.policy_name || `Policy ${b.policy_id}`}
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${b.severity === "critical" ? "bg-red-500/20 text-red-400" : b.severity === "major" ? "bg-orange-500/20 text-orange-400" : "bg-yellow-500/20 text-yellow-400"}`}
                      >
                        {b.severity}
                      </span>
                    </td>
                    <td className="p-4 text-red-400 font-bold">
                      {b.actual_value}
                    </td>
                    <td className="p-4 text-zinc-400">{b.target_value}</td>
                    <td className="p-4 text-zinc-300">{b.duration || "—"}</td>
                    <td className="p-4 text-zinc-400 text-xs">
                      {b.occurred_at
                        ? new Date(b.occurred_at).toLocaleString()
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

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
              New SLA Policy
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Policy Name"
                value={form.name}
                onChange={(e: any) =>
                  setForm({ ...form, name: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <input
                type="text"
                placeholder="Service Name"
                value={form.service}
                onChange={(e: any) =>
                  setForm({ ...form, service: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <select
                value={form.metric}
                onChange={(e: any) =>
                  setForm({ ...form, metric: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                {[
                  "uptime",
                  "response_time",
                  "error_rate",
                  "throughput",
                  "availability",
                ].map((m: any) => (
                  <option key={m} value={m}>
                    {m.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  placeholder="Target Value"
                  step="0.1"
                  value={form.target_value}
                  onChange={(e: any) =>
                    setForm({ ...form, target_value: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
                <select
                  value={form.unit}
                  onChange={(e: any) =>
                    setForm({ ...form, unit: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                >
                  {["percent", "ms", "seconds", "requests_per_second"].map(
                    (u: any) => (
                      <option key={u} value={u}>
                        {u.replace(/_/g, " ")}
                      </option>
                    )
                  )}
                </select>
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
                  onClick={() =>
                    createMutation.mutate({
                      ...form,
                      // @ts-ignore Sprint 85
                      target_value: parseFloat(form.target_value),
                    })
                  }
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedItem && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedItem(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-white">Policy Details</h3>
              <button
                onClick={() => setSelectedItem(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedItem).map(([key, value]) => (
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
