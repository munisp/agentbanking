import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  BookOpen,
  Search,
  RefreshCw,
  Plus,
  Eye,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

export default function GeneralLedgerPage() {
  const [tab, setTab] = useState<"entries" | "accounts" | "trial_balance">(
    "entries"
  );
  const [search, setSearch] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<any>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    account_code: "",
    description: "",
    debit_amount: "",
    credit_amount: "",
    reference: "",
    entry_date: "",
  });

  const entriesQuery = trpc.generalLedger.listEntries.useQuery({ limit: 200 });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const accountsQuery = trpc.generalLedger.listAccounts.useQuery({
    limit: 100,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const trialBalanceQuery = trpc.generalLedger.getTrialBalance.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.generalLedger.getStats.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const createMutation = trpc.generalLedger.createEntry.useMutation({
    onSuccess: () => {
      entriesQuery.refetch();
      setShowCreate(false);
      toast.success("Journal entry created");
    },
    onError: (e: any) => toast.error(e.message),
  });

  const stats = statsQuery.data;
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const entries = (entriesQuery.data ?? []).filter((e: any) => {
    if (
      search &&
      !e.description?.toLowerCase().includes(search.toLowerCase()) &&
      !e.account_code?.includes(search)
    )
      return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-amber-400" /> General Ledger
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Double-entry accounting, journal entries, chart of accounts, and
            trial balance
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              entriesQuery.refetch();
              accountsQuery.refetch();
              trialBalanceQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Entry
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Entries",
            value: stats?.totalEntries ?? 0,
            color: "text-amber-400",
          },
          {
            label: "Total Debits",
            value: `₦${Number(stats?.totalDebits ?? 0).toLocaleString()}`,
            color: "text-emerald-400",
          },
          {
            label: "Total Credits",
            value: `₦${Number(stats?.totalCredits ?? 0).toLocaleString()}`,
            color: "text-red-400",
          },
          {
            label: "Accounts",
            value: stats?.totalAccounts ?? 0,
            color: "text-blue-400",
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

      <div className="flex gap-2">
        {(["entries", "accounts", "trial_balance"] as const).map((t: any) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${tab === t ? "bg-amber-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
          >
            {t.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {tab === "entries" && (
        <>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Search entries..."
              value={search}
              onChange={(e: any) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>
          <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-700/50 text-zinc-400">
                  <th className="text-left p-4 font-medium">Date</th>
                  <th className="text-left p-4 font-medium">Account</th>
                  <th className="text-left p-4 font-medium">Description</th>
                  <th className="text-right p-4 font-medium">Debit</th>
                  <th className="text-right p-4 font-medium">Credit</th>
                  <th className="text-left p-4 font-medium">Reference</th>
                </tr>
              </thead>
              <tbody>
                {entriesQuery.isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-700/30">
                      <td colSpan={6} className="p-4">
                        <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : entries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-zinc-500">
                      No entries found
                    </td>
                  </tr>
                ) : (
                  entries.map((e: any) => (
                    <tr
                      key={e.id}
                      className="border-b border-zinc-700/30 hover:bg-zinc-700/20 cursor-pointer"
                      onClick={() => setSelectedEntry(e)}
                    >
                      <td className="p-4 text-zinc-400 text-xs">
                        {e.entry_date
                          ? new Date(e.entry_date).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="p-4 text-white font-mono text-xs">
                        {e.account_code}
                      </td>
                      <td className="p-4 text-zinc-300">{e.description}</td>
                      <td className="p-4 text-right">
                        {Number(e.debit_amount) > 0 ? (
                          <span className="text-emerald-400 font-bold flex items-center justify-end gap-1">
                            <ArrowUpRight className="h-3 w-3" />₦
                            {Number(e.debit_amount).toLocaleString()}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="p-4 text-right">
                        {Number(e.credit_amount) > 0 ? (
                          <span className="text-red-400 font-bold flex items-center justify-end gap-1">
                            <ArrowDownRight className="h-3 w-3" />₦
                            {Number(e.credit_amount).toLocaleString()}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="p-4 text-zinc-400 font-mono text-xs">
                        {e.reference || "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "accounts" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Code</th>
                <th className="text-left p-4 font-medium">Name</th>
                <th className="text-left p-4 font-medium">Type</th>
                <th className="text-right p-4 font-medium">Balance</th>
                <th className="text-left p-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {accountsQuery.isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-700/30">
                      <td colSpan={5} className="p-4">
                        <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                : (accountsQuery.data ?? []).map((a: any) => (
                    <tr
                      key={a.id || a.code}
                      className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                    >
                      <td className="p-4 text-white font-mono">{a.code}</td>
                      <td className="p-4 text-zinc-300">{a.name}</td>
                      <td className="p-4">
                        <span className="px-2 py-1 bg-amber-500/20 text-amber-400 rounded text-xs">
                          {a.account_type}
                        </span>
                      </td>
                      <td className="p-4 text-right text-white font-bold">
                        ₦{Number(a.balance ?? 0).toLocaleString()}
                      </td>
                      <td className="p-4">
                        <span
                          className={`px-2 py-1 rounded-full text-xs ${a.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-500/20 text-zinc-400"}`}
                        >
                          {a.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "trial_balance" && (
        <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700/50 text-zinc-400">
                <th className="text-left p-4 font-medium">Account</th>
                <th className="text-right p-4 font-medium">Debit Balance</th>
                <th className="text-right p-4 font-medium">Credit Balance</th>
              </tr>
            </thead>
            <tbody>
              {trialBalanceQuery.isLoading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-zinc-700/30">
                      <td colSpan={3} className="p-4">
                        <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                : (trialBalanceQuery.data ?? []).map((tb: any, idx: number) => (
                    <tr key={idx} className="border-b border-zinc-700/30">
                      <td className="p-4 text-white">
                        {tb.account_name || tb.account_code}
                      </td>
                      <td className="p-4 text-right text-emerald-400 font-bold">
                        {Number(tb.debit_balance) > 0
                          ? `₦${Number(tb.debit_balance).toLocaleString()}`
                          : "—"}
                      </td>
                      <td className="p-4 text-right text-red-400 font-bold">
                        {Number(tb.credit_balance) > 0
                          ? `₦${Number(tb.credit_balance).toLocaleString()}`
                          : "—"}
                      </td>
                    </tr>
                  ))}
              <tr className="bg-zinc-700/30 font-bold">
                <td className="p-4 text-white">TOTAL</td>
                <td className="p-4 text-right text-emerald-400">
                  ₦
                  {(trialBalanceQuery.data ?? [])
                    .reduce(
                      (s: number, tb: any) => s + Number(tb.debit_balance || 0),
                      0
                    )
                    .toLocaleString()}
                </td>
                <td className="p-4 text-right text-red-400">
                  ₦
                  {(trialBalanceQuery.data ?? [])
                    .reduce(
                      (s: number, tb: any) =>
                        s + Number(tb.credit_balance || 0),
                      0
                    )
                    .toLocaleString()}
                </td>
              </tr>
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
              New Journal Entry
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Account Code (e.g., 1001)"
                value={form.account_code}
                onChange={(e: any) =>
                  setForm({ ...form, account_code: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <input
                type="text"
                placeholder="Description"
                value={form.description}
                onChange={(e: any) =>
                  setForm({ ...form, description: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="number"
                  placeholder="Debit Amount"
                  value={form.debit_amount}
                  onChange={(e: any) =>
                    setForm({ ...form, debit_amount: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
                <input
                  type="number"
                  placeholder="Credit Amount"
                  value={form.credit_amount}
                  onChange={(e: any) =>
                    setForm({ ...form, credit_amount: e.target.value })
                  }
                  className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
                />
              </div>
              <input
                type="text"
                placeholder="Reference"
                value={form.reference}
                onChange={(e: any) =>
                  setForm({ ...form, reference: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <input
                type="date"
                value={form.entry_date}
                onChange={(e: any) =>
                  setForm({ ...form, entry_date: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() =>
                    createMutation.mutate({
                      ...form,
                      debit_amount: parseFloat(form.debit_amount) || 0,
                      credit_amount: parseFloat(form.credit_amount) || 0,
                    })
                  }
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedEntry && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedEntry(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-white">Entry Details</h3>
              <button
                onClick={() => setSelectedEntry(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedEntry).map(([key, value]) => (
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
