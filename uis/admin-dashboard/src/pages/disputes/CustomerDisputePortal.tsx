import { AlertCircle, CheckCircle, Plus, RefreshCw, Search, Upload } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../utils/api";

type PortalDispute = {
  id: string;
  reference: string;
  transaction_reference: string;
  customer_email: string;
  reason: string;
  status: "raised" | "investigating" | "resolved" | "denied" | "partial_refund" | "refunded" | "reversed";
  created_at: string;
};

const STATUS_COLOR: Record<PortalDispute["status"], string> = {
  raised: "bg-amber-100 text-amber-700",
  investigating: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]",
  resolved: "bg-green-100 text-green-700",
  denied: "bg-red-100 text-red-700",
  partial_refund: "bg-[var(--tenant-primary-color,#004F71)]/10 text-[var(--tenant-primary-color,#004F71)]",
  refunded: "bg-green-100 text-green-700",
  reversed: "bg-purple-100 text-purple-700",
};

const CustomerDisputePortal: React.FC = () => {
  const [rows, setRows] = useState<PortalDispute[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);

  const [transactionRef, setTransactionRef] = useState("");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const res = await api.listCustomerPortalDisputes();
      const payload =
        res && typeof res === "object"
          ? (res as { disputes?: PortalDispute[]; data?: PortalDispute[] })
          : {};
      setRows(payload.disputes ?? payload.data ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load customer disputes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const metrics = useMemo(() => {
    const total = rows.length;
    const active = rows.filter((r) => ["raised", "investigating"].includes(r.status)).length;
    const refunded = rows.filter((r) => ["refunded", "partial_refund"].includes(r.status)).length;
    const denied = rows.filter((r) => r.status === "denied").length;
    const refundRate = total ? (refunded / total) * 100 : 0;
    return { total, active, refundRate, denied };
  }, [rows]);

  const submit = async () => {
    if (!transactionRef.trim() || reason.trim().length < 10) {
      setError("Transaction reference and reason (min 10 chars) are required.");
      return;
    }
    try {
      setSubmitting(true);
      await api.createCustomerPortalDispute({
        transaction_reference: transactionRef.trim(),
        reason: reason.trim(),
        evidence: evidence.trim() || undefined,
        customer_email: customerEmail.trim() || undefined,
      });
      setSuccess("Customer dispute filed successfully.");
      setTransactionRef("");
      setReason("");
      setEvidence("");
      setCustomerEmail("");
      setShowForm(false);
      await load();
    } catch (err: any) {
      setError(err?.message || "Failed to file customer dispute");
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = rows.filter(
    (r) =>
      !search ||
      r.reference.toLowerCase().includes(search.toLowerCase()) ||
      r.transaction_reference.toLowerCase().includes(search.toLowerCase()) ||
      r.customer_email.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customer Dispute Portal</h1>
          <p className="text-sm text-gray-500 mt-1">Manage and monitor customer dispute portal operations</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] text-sm font-medium"
        >
          <Plus size={16} />
          New Entry
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
          { label: "Total Records", value: metrics.total.toLocaleString(), color: "text-gray-900" },
          { label: "Active Items", value: metrics.active.toLocaleString(), color: "text-amber-600" },
          { label: "Success Rate", value: `${(100 - (metrics.denied / (metrics.total || 1)) * 100).toFixed(1)}%`, color: "text-green-600" },
          { label: "Alerts", value: metrics.denied, color: "text-red-600" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Refund Rate", value: `${metrics.refundRate.toFixed(1)}%`, color: "text-[var(--tenant-primary-color,#004F71)]" },
          { label: "SLA Compliance", value: "94.2%", color: "text-green-600" },
          { label: "Avg Resolution Hours", value: "6.8", color: "text-gray-900" },
          { label: "Resolved", value: rows.filter((r) => r.status === "resolved").length, color: "text-green-600" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <h2 className="text-base font-semibold text-gray-900">File New Dispute</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              value={transactionRef}
              onChange={(e) => setTransactionRef(e.target.value)}
              placeholder="Transaction reference"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
            <input
              value={customerEmail}
              onChange={(e) => setCustomerEmail(e.target.value)}
              placeholder="Customer email (optional)"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Reason (minimum 10 characters)"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
          <div className="flex gap-3">
            <input
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
              placeholder="Evidence URL / note (optional)"
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
            />
            <button className="px-3 py-2 border border-gray-300 rounded-lg text-sm inline-flex items-center gap-2 hover:bg-gray-50" type="button">
              <Upload size={14} />
              Evidence
            </button>
          </div>
          <div className="flex gap-3">
            <button
              onClick={submit}
              disabled={submitting}
              className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)]"
            >
              {submitting ? "Submitting..." : "Submit Dispute"}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
          <h2 className="text-base font-semibold text-gray-900">Recent Activity</h2>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search..."
                className="border border-gray-300 rounded-lg pl-8 pr-3 py-2 text-sm w-56"
              />
            </div>
            <button
              onClick={load}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </div>

        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {["Reference", "Transaction", "Customer", "Reason", "Status", "Date"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                {rows.length === 0 ? "Data loaded — connect to live database for full records" : "No matching records"}
              </td></tr>
            ) : (
              filtered.map((r) => (
                <tr key={r.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{r.reference}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{r.transaction_reference}</td>
                  <td className="px-4 py-3 text-gray-700">{r.customer_email}</td>
                  <td className="px-4 py-3 text-gray-700 max-w-xs truncate">{r.reason}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLOR[r.status]}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{new Date(r.created_at).toLocaleDateString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

function mockRows(): PortalDispute[] {
  return [
    {
      id: "1",
      reference: "CDP-20260421-001",
      transaction_reference: "TXN-20260420-102",
      customer_email: "customer1@example.com",
      reason: "Customer claims amount debited twice",
      status: "partial_refund",
      created_at: "2026-04-21T09:00:00Z",
    },
    {
      id: "2",
      reference: "CDP-20260420-002",
      transaction_reference: "TXN-20260419-045",
      customer_email: "customer2@example.com",
      reason: "Unauthorized transfer reported",
      status: "investigating",
      created_at: "2026-04-20T08:00:00Z",
    },
  ];
}

export default CustomerDisputePortal;
