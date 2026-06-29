import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Workflow,
  Search,
  RefreshCw,
  Plus,
  Eye,
  Play,
  Pause,
  CheckCircle,
  Clock,
  XCircle,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-500/20 text-emerald-400",
  draft: "bg-zinc-500/20 text-zinc-400",
  paused: "bg-yellow-500/20 text-yellow-400",
  completed: "bg-blue-500/20 text-blue-400",
  failed: "bg-red-500/20 text-red-400",
  running: "bg-blue-500/20 text-blue-400",
  pending: "bg-yellow-500/20 text-yellow-400",
};

export default function WorkflowEnginePage() {
  const [tab, setTab] = useState<"definitions" | "instances">("definitions");
  const [search, setSearch] = useState("");
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    category: "general",
    steps: [{ name: "Step 1", type: "approval" }] as {
      name: string;
      type: string;
      assigneeRole?: string;
      autoApprove?: boolean;
      timeoutHours?: number;
    }[],
  });

  const defsQuery = trpc.workflowEngine.listDefinitions.useQuery({
    limit: 100,
  });
  const instancesQuery = trpc.workflowEngine.listInstances.useQuery({
    limit: 100,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.workflowEngine.getStats.useQuery();
  const createMutation = trpc.workflowEngine.createDefinition.useMutation({
    onSuccess: () => {
      defsQuery.refetch();
      setShowCreate(false);
      toast.success("Workflow created");
    },
    onError: (e: any) => toast.error(e.message),
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const triggerMutation = trpc.workflowEngine.triggerWorkflow.useMutation({
    onSuccess: () => {
      instancesQuery.refetch();
      toast.success("Workflow triggered");
    },
    onError: (e: any) => toast.error(e.message),
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Workflow className="h-6 w-6 text-sky-400" /> Workflow Engine
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Automated business workflows, approval chains, and process
            orchestration
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              defsQuery.refetch();
              instancesQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Workflow
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Definitions",
            value: stats?.totalDefinitions ?? 0,
            icon: Workflow,
            color: "text-sky-400",
          },
          {
            label: "Running",
            value: stats?.running ?? 0,
            icon: Play,
            color: "text-blue-400",
          },
          {
            label: "Completed",
            value: stats?.completed ?? 0,
            icon: CheckCircle,
            color: "text-emerald-400",
          },
          {
            label: "Failed",
            value: stats?.failed ?? 0,
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
        {(["definitions", "instances"] as const).map((t: any) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize ${tab === t ? "bg-sky-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "definitions" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Name</th>
                <th className="text-left p-4 font-medium">Trigger</th>
                <th className="text-left p-4 font-medium">Steps</th>
                <th className="text-left p-4 font-medium">Status</th>
                <th className="text-left p-4 font-medium">Runs</th>
                <th className="text-left p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {defsQuery.isLoading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-700/30">
                      <td colSpan={6} className="p-4">
                        <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                      </td>
                    </tr>
                    // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
                  ))
                : // @ts-ignore Sprint 85
                  (defsQuery.data ?? []).map((d: any) => (
                    <tr
                      key={d.id}
                      className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                    >
                      <td className="p-4 text-white font-medium">{d.name}</td>
                      <td className="p-4">
                        <span className="px-2 py-1 bg-sky-500/20 text-sky-400 rounded text-xs">
                          {d.trigger_type}
                        </span>
                      </td>
                      <td className="p-4 text-zinc-300">{d.step_count || 0}</td>
                      <td className="p-4">
                        <span
                          className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[d.status] || "bg-zinc-500/20 text-zinc-400"}`}
                        >
                          {d.status}
                        </span>
                      </td>
                      <td className="p-4 text-zinc-400">{d.run_count || 0}</td>
                      <td className="p-4">
                        <div className="flex gap-1">
                          <button
                            onClick={() => setSelectedItem(d)}
                            className="p-1.5 hover:bg-zinc-700 rounded-lg"
                          >
                            <Eye className="h-4 w-4 text-zinc-400" />
                          </button>
                          <button
                            onClick={() =>
                              triggerMutation.mutate({ definition_id: d.id })
                            }
                            className="p-1.5 hover:bg-sky-700/30 rounded-lg"
                            title="Trigger"
                          >
                            <Play className="h-4 w-4 text-sky-400" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "instances" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Workflow</th>
                <th className="text-left p-4 font-medium">Current Step</th>
                <th className="text-left p-4 font-medium">Status</th>
                <th className="text-left p-4 font-medium">Started</th>
                <th className="text-left p-4 font-medium">Duration</th>
                <th className="text-left p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {instancesQuery.isLoading
                ? Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-700/30">
                      <td colSpan={6} className="p-4">
                        <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                      </td>
                    </tr>
                    // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
                  ))
                : // @ts-ignore Sprint 85
                  (instancesQuery.data ?? []).map((inst: any) => (
                    <tr
                      key={inst.id}
                      className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                    >
                      <td className="p-4 text-white font-medium">
                        {inst.workflow_name || `WF-${inst.definition_id}`}
                      </td>
                      <td className="p-4 text-zinc-300">
                        {inst.current_step || "—"}
                      </td>
                      <td className="p-4">
                        <span
                          className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[inst.status] || "bg-zinc-500/20 text-zinc-400"}`}
                        >
                          {inst.status?.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="p-4 text-zinc-400 text-xs">
                        {inst.started_at
                          ? new Date(inst.started_at).toLocaleString()
                          : "—"}
                      </td>
                      <td className="p-4 text-zinc-400 text-xs">
                        {inst.duration || "—"}
                      </td>
                      <td className="p-4">
                        <button
                          onClick={() => setSelectedItem(inst)}
                          className="p-1.5 hover:bg-zinc-700 rounded-lg"
                        >
                          <Eye className="h-4 w-4 text-zinc-400" />
                        </button>
                      </td>
                    </tr>
                  ))}
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
              New Workflow Definition
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Workflow Name"
                value={form.name}
                onChange={(e: any) =>
                  setForm({ ...form, name: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <textarea
                placeholder="Description"
                value={form.description}
                onChange={(e: any) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={2}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white resize-none"
              />
              <select
                value={form.category}
                onChange={(e: any) =>
                  setForm({ ...form, category: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                {[
                  "general",
                  "billing",
                  "onboarding",
                  "compliance",
                  "approval",
                ].map((t: any) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => createMutation.mutate(form as any)}
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm"
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
              <h3 className="text-lg font-bold text-white">Details</h3>
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
                    {typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value ?? "—")}
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
