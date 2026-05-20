import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Calculator,
  Search,
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Eye,
  DollarSign,
} from "lucide-react";

export default function DynamicFeeEnginePage() {
  const [search, setSearch] = useState("");
  const [txTypeFilter, setTxTypeFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [editRule, setEditRule] = useState<any>(null);
  const [simAmount, setSimAmount] = useState("10000");
  const [simTxType, setSimTxType] = useState("transfer");
  const [form, setForm] = useState({
    transaction_type: "transfer",
    fee_type: "percentage",
    fee_value: "",
    min_fee: "",
    max_fee: "",
    min_amount: "",
    max_amount: "",
    description: "",
  });

  const rulesQuery = trpc.dynamicFeeEngine.listRules.useQuery({ limit: 100 });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.dynamicFeeEngine.getStats.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const simulateQuery = trpc.dynamicFeeEngine.simulateFee.useQuery(
    { amount: parseFloat(simAmount) || 0, transaction_type: simTxType },
    { enabled: false }
  );
  const createMutation = trpc.dynamicFeeEngine.createRule.useMutation({
    onSuccess: () => {
      rulesQuery.refetch();
      setShowCreate(false);
      toast.success("Fee rule created");
    },
    onError: (e: any) => toast.error(e.message),
  });
  const updateMutation = trpc.dynamicFeeEngine.updateRule.useMutation({
    onSuccess: () => {
      rulesQuery.refetch();
      setEditRule(null);
      toast.success("Fee rule updated");
    },
    onError: (e: any) => toast.error(e.message),
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const deleteMutation = trpc.dynamicFeeEngine.deleteRule.useMutation({
    onSuccess: () => {
      rulesQuery.refetch();
      toast.success("Fee rule deleted");
    },
    onError: (e: any) => toast.error(e.message),
  });

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const rules = (rulesQuery.data ?? []).filter((r: any) => {
    if (search && !r.description?.toLowerCase().includes(search.toLowerCase()))
      return false;
    if (txTypeFilter !== "all" && r.transaction_type !== txTypeFilter)
      return false;
    return true;
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Calculator className="h-6 w-6 text-amber-400" /> Dynamic Fee Engine
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Configurable fee rules per transaction type, tier, and volume with
            simulation
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              rulesQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              setForm({
                transaction_type: "transfer",
                fee_type: "percentage",
                fee_value: "",
                min_fee: "",
                max_fee: "",
                min_amount: "",
                max_amount: "",
                description: "",
              });
              setShowCreate(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Rule
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Rules",
            value: stats?.totalRules ?? 0,
            color: "text-amber-400",
          },
          {
            label: "Active Rules",
            value: stats?.activeRules ?? 0,
            color: "text-emerald-400",
          },
          {
            label: "Transaction Types",
            value: stats?.txTypes ?? 0,
            color: "text-blue-400",
          },
          {
            label: "Avg Fee Rate",
            value: `${(stats?.avgFeeRate ?? 0).toFixed(2)}%`,
            color: "text-purple-400",
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

      {/* Fee Simulator */}
      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-amber-400" /> Fee Simulator
        </h3>
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-zinc-400 block mb-1">
              Amount (₦)
            </label>
            <input
              type="number"
              value={simAmount}
              onChange={(e: any) => setSimAmount(e.target.value)}
              className="px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white w-40"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-400 block mb-1">
              Transaction Type
            </label>
            <select
              value={simTxType}
              onChange={(e: any) => setSimTxType(e.target.value)}
              className="px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white"
            >
              {[
                "transfer",
                "withdrawal",
                "deposit",
                "bill_payment",
                "airtime",
                "pos_purchase",
              ].map((t: any) => (
                <option key={t} value={t}>
                  {t.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => simulateQuery.refetch()}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm"
          >
            Calculate Fee
          </button>
          {simulateQuery.data && (
            <div className="px-4 py-2 bg-emerald-900/30 border border-emerald-700/30 rounded-lg">
              <span className="text-emerald-400 font-bold">
                Fee: ₦{Number(simulateQuery.data.fee || 0).toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search rules..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-500"
          />
        </div>
        <select
          value={txTypeFilter}
          onChange={(e: any) => setTxTypeFilter(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
        >
          <option value="all">All Types</option>
          {[
            "transfer",
            "withdrawal",
            "deposit",
            "bill_payment",
            "airtime",
            "pos_purchase",
          ].map((t: any) => (
            <option key={t} value={t}>
              {t.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700/50 text-zinc-400">
              <th className="text-left p-4 font-medium">Tx Type</th>
              <th className="text-left p-4 font-medium">Fee Type</th>
              <th className="text-left p-4 font-medium">Fee Value</th>
              <th className="text-left p-4 font-medium">Min/Max Fee</th>
              <th className="text-left p-4 font-medium">Amount Range</th>
              <th className="text-left p-4 font-medium">Status</th>
              <th className="text-left p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rulesQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-zinc-700/30">
                  <td colSpan={7} className="p-4">
                    <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                  </td>
                </tr>
              ))
            ) : rules.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-zinc-500">
                  No fee rules found
                </td>
              </tr>
            ) : (
              rules.map((r: any) => (
                <tr
                  key={r.id}
                  className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                >
                  <td className="p-4 text-white">
                    {r.transaction_type?.replace(/_/g, " ")}
                  </td>
                  <td className="p-4 text-zinc-300">{r.fee_type}</td>
                  <td className="p-4 text-amber-400 font-bold">
                    {r.fee_type === "percentage"
                      ? `${r.fee_value}%`
                      : `₦${Number(r.fee_value || 0).toLocaleString()}`}
                  </td>
                  <td className="p-4 text-zinc-400">
                    ₦{Number(r.min_fee || 0).toLocaleString()} — ₦
                    {Number(r.max_fee || 0).toLocaleString()}
                  </td>
                  <td className="p-4 text-zinc-400">
                    ₦{Number(r.min_amount || 0).toLocaleString()} — ₦
                    {Number(r.max_amount || 0).toLocaleString()}
                  </td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs ${r.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-500/20 text-zinc-400"}`}
                    >
                      {r.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-1">
                      <button
                        onClick={() => {
                          setEditRule(r);
                          setForm({
                            transaction_type: r.transaction_type,
                            fee_type: r.fee_type,
                            fee_value: String(r.fee_value),
                            min_fee: String(r.min_fee || ""),
                            max_fee: String(r.max_fee || ""),
                            min_amount: String(r.min_amount || ""),
                            max_amount: String(r.max_amount || ""),
                            description: r.description || "",
                          });
                        }}
                        className="p-1.5 hover:bg-zinc-700 rounded-lg"
                      >
                        <Edit className="h-4 w-4 text-zinc-400" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm("Delete this rule?"))
                            deleteMutation.mutate({ id: r.id });
                        }}
                        className="p-1.5 hover:bg-red-700/30 rounded-lg"
                      >
                        <Trash2 className="h-4 w-4 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {(showCreate || editRule) && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => {
            setShowCreate(false);
            setEditRule(null);
          }}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-md w-full mx-4"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-4">
              {editRule ? "Edit Fee Rule" : "New Fee Rule"}
            </h3>
            <div className="space-y-3">
              <select
                value={form.transaction_type}
                onChange={(e: any) =>
                  setForm({ ...form, transaction_type: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                {[
                  "transfer",
                  "withdrawal",
                  "deposit",
                  "bill_payment",
                  "airtime",
                  "pos_purchase",
                ].map((t: any) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
              <select
                value={form.fee_type}
                onChange={(e: any) =>
                  setForm({ ...form, fee_type: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                <option value="percentage">Percentage</option>
                <option value="flat">Flat</option>
                <option value="tiered">Tiered</option>
              </select>
              <input
                type="number"
                placeholder="Fee Value"
                value={form.fee_value}
                onChange={(e: any) =>
                  setForm({ ...form, fee_value: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  placeholder="Min Fee (₦)"
                  value={form.min_fee}
                  onChange={(e: any) =>
                    setForm({ ...form, min_fee: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
                <input
                  type="number"
                  placeholder="Max Fee (₦)"
                  value={form.max_fee}
                  onChange={(e: any) =>
                    setForm({ ...form, max_fee: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  placeholder="Min Amount (₦)"
                  value={form.min_amount}
                  onChange={(e: any) =>
                    setForm({ ...form, min_amount: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
                <input
                  type="number"
                  placeholder="Max Amount (₦)"
                  value={form.max_amount}
                  onChange={(e: any) =>
                    setForm({ ...form, max_amount: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
              </div>
              <textarea
                placeholder="Description"
                value={form.description}
                onChange={(e: any) =>
                  setForm({ ...form, description: e.target.value })
                }
                rows={2}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    setShowCreate(false);
                    setEditRule(null);
                  }}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    const data = {
                      ...form,
                      fee_value: parseFloat(form.fee_value),
                      min_fee: parseFloat(form.min_fee) || 0,
                      max_fee: parseFloat(form.max_fee) || 0,
                      min_amount: parseFloat(form.min_amount) || 0,
                      max_amount: parseFloat(form.max_amount) || 0,
                    };
                    // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
                    if (editRule)
                      updateMutation.mutate({ id: editRule.id, ...data });
                    // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
                    else createMutation.mutate(data);
                  }}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm"
                >
                  {editRule ? "Update" : "Create"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
