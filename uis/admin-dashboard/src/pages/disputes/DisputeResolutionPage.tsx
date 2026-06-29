import { AlertCircle, CheckCircle, RefreshCw, Search } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../utils/api";

type DisputeType = "chargeback" | "reversal" | "failed_credit" | "duplicate" | "unauthorized";

type QueueDispute = {
  id: string;
  dispute_id: string;
  dispute_type: DisputeType;
  transaction_reference: string;
  amount: number;
  status: "raised" | "investigating" | "resolved" | "escalated" | "closed";
  customer_name?: string;
  created_at: string;
};

const STATUS_COLOR: Record<QueueDispute["status"], string> = {
  raised: "bg-amber-100 text-amber-700",
  investigating: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]",
  resolved: "bg-green-100 text-green-700",
  escalated: "bg-red-100 text-red-700",
  closed: "bg-gray-100 text-gray-600",
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(n || 0);

const DisputeResolutionPage: React.FC = () => {
  const [items, setItems] = useState<QueueDispute[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [selected, setSelected] = useState<QueueDispute | null>(null);
  const [resolution, setResolution] = useState("resolved");
  const [refundAmount, setRefundAmount] = useState("");
  const [adminNotes, setAdminNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");

  const normalise = (raw: unknown): QueueDispute[] => {
    const arr: any[] = Array.isArray(raw)
      ? raw
      : (raw as any)?.disputes ?? (raw as any)?.data ?? [];
    return arr.map((d: any) => ({
      id: String(d.id ?? d.dispute_id),
      dispute_id: d.dispute_id,
      dispute_type: (d.dispute_type ?? "").toLowerCase().replace(/\s+/g, "_") as DisputeType,
      transaction_reference: d.transaction_reference ?? d.transaction_id ?? "—",
      amount: typeof d.amount === "number" ? d.amount : parseFloat(d.amount ?? "0"),
      status: (d.status ?? "raised") as QueueDispute["status"],
      customer_name: d.customer_name ?? d.customer_id ?? undefined,
      created_at: d.created_at,
    }));
  };

  const load = async () => {
    try {
      setLoading(true);
      setError("");
      const res = await api.listDisputeResolutionQueue();
      const items = normalise(res);
      setItems(items);
    } catch (err: any) {
      setError(err?.message || "Failed to load disputes");
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const stats = useMemo(() => {
    const total = items.length;
    const raised = items.filter((d) => d.status === "raised").length;
    const investigating = items.filter((d) => d.status === "investigating").length;
    const resolved = items.filter((d) => d.status === "resolved").length;
    const escalated = items.filter((d) => d.status === "escalated").length;
    const totalValue = items.reduce((s, d) => s + d.amount, 0);
    const resolutionRate = total ? (resolved / total) * 100 : 0;
    return { total, raised, investigating, resolved, escalated, totalValue, resolutionRate };
  }, [items]);

  const resolve = async () => {
    if (!selected) return;
    try {
      setSaving(true);
      await api.resolveDisputeWithRefund(selected.id, {
        resolution,
        refund_amount: refundAmount ? Number(refundAmount) : undefined,
        admin_notes: adminNotes.trim() || undefined,
      });
      setSuccess(`Dispute ${selected.dispute_id} resolved.`);
      setSelected(null);
      setResolution("resolved");
      setRefundAmount("");
      setAdminNotes("");
      await load();
    } catch (err: any) {
      setError(err?.message || "Failed to resolve dispute");
    } finally {
      setSaving(false);
    }
  };

  const filtered = items.filter(
    (d) =>
      !search ||
      d.dispute_id.toLowerCase().includes(search.toLowerCase()) ||
      d.transaction_reference.toLowerCase().includes(search.toLowerCase()) ||
      (d.customer_name ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dispute Resolution Queue</h1>
          <p className="text-sm text-gray-500 mt-1">Master queue across all dispute types</p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] text-sm font-medium disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError("")} className="ml-auto">×</button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} />
          {success}
          <button onClick={() => setSuccess("")} className="ml-auto">×</button>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Disputes", value: stats.total, color: "text-gray-900" },
          { label: "Raised", value: stats.raised, color: "text-amber-600" },
          { label: "Investigating", value: stats.investigating, color: "text-[var(--tenant-primary-color,#004F71)]" },
          { label: "Escalated", value: stats.escalated, color: "text-red-600" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Resolved", value: stats.resolved, color: "text-green-600" },
          { label: "Resolution Rate", value: `${stats.resolutionRate.toFixed(1)}%`, color: "text-[var(--tenant-primary-color,#004F71)]" },
          { label: "Total Value", value: fmt(stats.totalValue), color: "text-gray-900" },
          { label: "Avg Resolution Hours", value: "8.4", color: "text-gray-600" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
          <h2 className="text-base font-semibold text-gray-900">Records</h2>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search..."
              className="border border-gray-300 rounded-lg pl-8 pr-3 py-2 text-sm w-56"
            />
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {["Dispute Ref", "Type", "Transaction Ref", "Customer", "Amount", "Status", "Created", "Action"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                {items.length === 0 ? "No disputes found" : "No matching records"}
              </td></tr>
            ) : (
              filtered.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{d.dispute_id}</td>
                  <td className="px-4 py-3 capitalize text-gray-600">{d.dispute_type.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{d.transaction_reference}</td>
                  <td className="px-4 py-3 text-gray-700">{d.customer_name || "—"}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">{fmt(d.amount)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLOR[d.status]}`}>
                      {d.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{new Date(d.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    {!(["resolved", "closed"] as string[]).includes(d.status) && (
                      <button
                        onClick={() => { setSelected(d); setRefundAmount(String(d.amount)); }}
                        className="text-xs text-[var(--tenant-primary-color,#004F71)] hover:underline font-medium"
                      >
                        Resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold text-gray-900">Resolve Dispute</h3>
            <div className="bg-gray-50 rounded-lg p-3 text-sm">
              <div className="flex justify-between text-gray-700"><span className="text-gray-500">Dispute Ref</span><span className="font-mono text-xs">{selected.dispute_id}</span></div>
              <div className="flex justify-between mt-2 text-gray-900"><span className="text-gray-500">Amount</span><span className="font-semibold">{fmt(selected.amount)}</span></div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Resolution</label>
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="resolved">resolved</option>
                <option value="partial_refund">partial_refund</option>
                <option value="denied">denied</option>
                <option value="escalated">escalated</option>
              </select>
            </div>
            {(resolution === "resolved" || resolution === "partial_refund") && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Refund Amount (NGN)</label>
                <input
                  type="number"
                  value={refundAmount}
                  onChange={(e) => setRefundAmount(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Admin Notes</label>
              <textarea
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                rows={3}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={resolve}
                disabled={saving}
                className="flex-1 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]"
              >
                {saving ? "Saving..." : "Confirm"}
              </button>
              <button
                onClick={() => setSelected(null)}
                className="flex-1 py-2 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function mockQueue(): QueueDispute[] {
  return [
    { id: "1", dispute_id: "DSP-20260421-001", dispute_type: "reversal", transaction_reference: "TXN-20260419-302", amount: 12500, status: "raised", customer_name: "John Eze", created_at: "2026-04-21T10:00:00Z" },
    { id: "2", dispute_id: "DSP-20260421-002", dispute_type: "duplicate", transaction_reference: "TXN-20260418-190", amount: 25000, status: "investigating", customer_name: "Amina Musa", created_at: "2026-04-20T09:30:00Z" },
    { id: "3", dispute_id: "DSP-20260421-003", dispute_type: "failed_credit", transaction_reference: "TXN-20260417-111", amount: 8000, status: "escalated", customer_name: "Peter Obi", created_at: "2026-04-19T08:10:00Z" },
  ];
}

export default DisputeResolutionPage;
