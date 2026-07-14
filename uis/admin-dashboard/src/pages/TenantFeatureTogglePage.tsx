import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  ToggleLeft,
  Search,
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  ToggleRight,
} from "lucide-react";

export default function TenantFeatureTogglePage() {
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editToggle, setEditToggle] = useState<any>(null);
  const [form, setForm] = useState({
    feature_key: "",
    feature_name: "",
    description: "",
    is_enabled: true,
    tenant_id: "",
    rollout_percentage: "100",
  });

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const togglesQuery = trpc.tenantFeatureToggle.listToggles.useQuery({
    limit: 100,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.tenantFeatureToggle.getStats.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const createMutation = trpc.tenantFeatureToggle.createToggle.useMutation({
    onSuccess: () => {
      togglesQuery.refetch();
      setShowCreate(false);
      toast.success("Feature toggle created");
    },
    onError: (e: any) => toast.error(e.message),
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const updateMutation = trpc.tenantFeatureToggle.updateToggle.useMutation({
    onSuccess: () => {
      togglesQuery.refetch();
      setEditToggle(null);
      toast.success("Toggle updated");
    },
    onError: (e: any) => toast.error(e.message),
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const deleteMutation = trpc.tenantFeatureToggle.deleteToggle.useMutation({
    onSuccess: () => {
      togglesQuery.refetch();
      toast.success("Toggle deleted");
    },
    onError: (e: any) => toast.error(e.message),
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const flipMutation = trpc.tenantFeatureToggle.flipToggle.useMutation({
    onSuccess: () => {
      togglesQuery.refetch();
      toast.success("Toggle flipped");
    },
    onError: (e: any) => toast.error(e.message),
  });

  const toggles = (togglesQuery.data ?? []).filter((t: any) => {
    if (
      search &&
      !t.feature_key?.toLowerCase().includes(search.toLowerCase()) &&
      !t.feature_name?.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    return true;
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <ToggleLeft className="h-6 w-6 text-cyan-400" /> Feature Toggles
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Multi-tenant feature flags, rollout percentages, and A/B testing
            controls
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              togglesQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              setForm({
                feature_key: "",
                feature_name: "",
                description: "",
                is_enabled: true,
                tenant_id: "",
                rollout_percentage: "100",
              });
              setShowCreate(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Toggle
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[
          {
            label: "Total Toggles",
            value: stats?.totalToggles ?? 0,
            color: "text-cyan-400",
          },
          {
            label: "Enabled",
            value: stats?.enabled ?? 0,
            color: "text-emerald-400",
          },
          {
            label: "Disabled",
            value: stats?.disabled ?? 0,
            color: "text-red-400",
          },
        ].map((s: any) => (
          <div
            key={s.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
          >
            <p className="text-xs text-zinc-400 uppercase">{s.label}</p>
            <p className={`text-2xl font-bold mt-2 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
        <input
          type="text"
          placeholder="Search feature toggles..."
          value={search}
          onChange={(e: any) => setSearch(e.target.value)}
          className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
        />
      </div>

      <div className="space-y-3">
        {togglesQuery.isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
            >
              <div className="h-12 bg-zinc-700/50 rounded animate-pulse" />
            </div>
          ))
        ) : toggles.length === 0 ? (
          <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-8 text-center text-zinc-500">
            No feature toggles found
          </div>
        ) : (
          toggles.map((t: any) => (
            <div
              key={t.id}
              className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4 hover:border-cyan-600/30 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h4 className="text-white font-medium">
                      {t.feature_name || t.feature_key}
                    </h4>
                    <code className="text-xs text-zinc-500 bg-zinc-900 px-2 py-0.5 rounded">
                      {t.feature_key}
                    </code>
                  </div>
                  <p className="text-zinc-400 text-xs mt-1">
                    {t.description || "No description"}
                  </p>
                  <div className="flex items-center gap-4 mt-2">
                    {t.tenant_id && (
                      <span className="text-xs text-zinc-500">
                        Tenant: {t.tenant_id}
                      </span>
                    )}
                    <span className="text-xs text-zinc-500">
                      Rollout: {t.rollout_percentage ?? 100}%
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => flipMutation.mutate({ id: t.id })}
                    className={`p-2 rounded-lg transition-colors ${t.is_enabled ? "bg-emerald-600/20 hover:bg-emerald-600/30" : "bg-zinc-700/50 hover:bg-zinc-700"}`}
                  >
                    {t.is_enabled ? (
                      <ToggleRight className="h-6 w-6 text-emerald-400" />
                    ) : (
                      <ToggleLeft className="h-6 w-6 text-zinc-500" />
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setEditToggle(t);
                      setForm({
                        feature_key: t.feature_key,
                        feature_name: t.feature_name || "",
                        description: t.description || "",
                        is_enabled: t.is_enabled,
                        tenant_id: t.tenant_id || "",
                        rollout_percentage: String(t.rollout_percentage ?? 100),
                      });
                    }}
                    className="p-1.5 hover:bg-zinc-700 rounded-lg"
                  >
                    <Edit className="h-4 w-4 text-zinc-400" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm("Delete this toggle?"))
                        deleteMutation.mutate({ id: t.id });
                    }}
                    className="p-1.5 hover:bg-red-700/30 rounded-lg"
                  >
                    <Trash2 className="h-4 w-4 text-red-400" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {(showCreate || editToggle) && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => {
            setShowCreate(false);
            setEditToggle(null);
          }}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-md w-full mx-4"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-4">
              {editToggle ? "Edit Toggle" : "New Feature Toggle"}
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Feature Key (e.g., enable_nfc_payments)"
                value={form.feature_key}
                onChange={(e: any) =>
                  setForm({ ...form, feature_key: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                disabled={!!editToggle}
              />
              <input
                type="text"
                placeholder="Feature Name"
                value={form.feature_name}
                onChange={(e: any) =>
                  setForm({ ...form, feature_name: e.target.value })
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
              <input
                type="number"
                placeholder="Rollout %"
                min="0"
                max="100"
                value={form.rollout_percentage}
                onChange={(e: any) =>
                  setForm({ ...form, rollout_percentage: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    setShowCreate(false);
                    setEditToggle(null);
                  }}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    const data = {
                      ...form,
                      rollout_percentage:
                        parseInt(form.rollout_percentage) || 100,
                    };
                    if (editToggle)
                      updateMutation.mutate({ id: editToggle.id, ...data });
                    else createMutation.mutate(data);
                  }}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg text-sm"
                >
                  {editToggle ? "Update" : "Create"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
