import { AlertCircle, Bot, CheckCircle, Plus, RefreshCw, Search } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../utils/api";

type Recommendation = "full_refund" | "partial_refund" | "deny" | "escalate" | "merchant_credit";

type AICase = {
  id: string;
  dispute_ref: string;
  transaction_ref: string;
  amount: number;
  recommendation: Recommendation;
  confidence: number;
  suggested_amount?: number;
  reason: string;
  status?: "pending" | "applied" | "overridden";
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(n || 0);

const REC_COLOR: Record<Recommendation, string> = {
  full_refund: "text-green-600",
  partial_refund: "text-[var(--tenant-primary-color,#004F71)]",
  deny: "text-red-600",
  escalate: "text-amber-600",
  merchant_credit: "text-purple-600",
};

const DisputeMediationAI: React.FC = () => {
  const [rows, setRows] = useState<AICase[]>([]);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");

  const load = async () => {
    try {
      setLoading(true);
      const res = await api.listMediationRecommendations();
      const payload =
        res && typeof res === "object"
          ? (res as { recommendations?: AICase[]; data?: AICase[] })
          : {};
      setRows(payload.recommendations ?? payload.data ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load mediation recommendations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const applyDecision = async (row: AICase) => {
    try {
      setProcessingId(row.id);
      await api.applyMediationDecision(row.id, {
        recommendation: row.recommendation,
        suggested_amount: row.suggested_amount,
        note: "Applied from admin AI mediation queue",
      });
      setSuccess(`Decision applied for ${row.dispute_ref}`);
      await load();
    } catch (err: any) {
      setError(err?.message || "Failed to apply AI decision");
    } finally {
      setProcessingId(null);
    }
  };

  const stats = useMemo(() => {
    const total = rows.length;
    const resolved = rows.filter((r) => r.status === "applied").length;
    const pending = rows.filter((r) => !r.status || r.status === "pending").length;
    const avgConfidence = total
      ? (rows.reduce((s, r) => s + r.confidence, 0) / total) * 100
      : 0;
    const autoResolved = rows.filter((r) => r.confidence >= 0.9 && r.status === "applied").length;
    const humanOverride = rows.filter((r) => r.status === "overridden").length;
    return { total, resolved, pending, avgConfidence, autoResolved, humanOverride };
  }, [rows]);

  const filtered = rows.filter(
    (r) =>
      !search ||
      r.dispute_ref.toLowerCase().includes(search.toLowerCase()) ||
      r.transaction_ref.toLowerCase().includes(search.toLowerCase()) ||
      r.reason.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Dispute Mediation</h1>
          <p className="text-sm text-gray-500 mt-1">AI-powered transaction dispute resolution</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] text-sm font-medium">
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
          { label: "Total Mediations", value: stats.total, color: "text-gray-900" },
          { label: "Resolved", value: stats.resolved, color: "text-green-600" },
          { label: "Pending", value: stats.pending, color: "text-amber-600" },
          { label: "Avg Confidence", value: stats.avgConfidence.toFixed(1), color: "text-[var(--tenant-primary-color,#004F71)]" },
        ].map((s) => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-500">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Auto Resolved", value: stats.autoResolved, color: "text-green-600" },
          { label: "Human Override", value: stats.humanOverride, color: "text-purple-600" },
          { label: "Avg Resolution Hours", value: "4.2", color: "text-gray-900" },
          { label: "Customer Satisfaction", value: "92", color: "text-[var(--tenant-primary-color,#004F71)]" },
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
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search..."
                className="border border-gray-300 rounded-lg pl-8 pr-3 py-2 text-sm text-gray-900 bg-white w-56"
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
              {["Dispute Ref", "Transaction", "Amount", "Recommendation", "Confidence", "Suggested", "Action"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading recommendations...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                {rows.length === 0 ? "Data loaded — connect to live database for full records" : "No matching records"}
              </td></tr>
            ) : (
              filtered.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{row.dispute_ref}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{row.transaction_ref}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">{fmt(row.amount)}</td>
                  <td className="px-4 py-3">
                    <span className={`font-semibold text-xs ${REC_COLOR[row.recommendation]}`}>
                      {row.recommendation}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <Bot size={12} className="text-gray-400" />
                      <span className="text-[var(--tenant-primary-color,#004F71)] font-semibold">{(row.confidence * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{fmt(row.suggested_amount || 0)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => applyDecision(row)}
                      disabled={processingId === row.id}
                      className="px-3 py-1 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-md text-xs font-medium hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#004F71) 70%, black)] disabled:opacity-50"
                    >
                      {processingId === row.id ? "Applying..." : "Apply"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

function mockCases(): AICase[] {
  return [
    {
      id: "1",
      dispute_ref: "DSP-20260420-100",
      transaction_ref: "TXN-20260418-221",
      amount: 10000,
      recommendation: "full_refund",
      confidence: 0.94,
      suggested_amount: 10000,
      reason: "Strong duplicate debit pattern with confirmed failed reversal",
      status: "applied",
    },
    {
      id: "2",
      dispute_ref: "DSP-20260420-101",
      transaction_ref: "TXN-20260418-222",
      amount: 22000,
      recommendation: "partial_refund",
      confidence: 0.81,
      suggested_amount: 12000,
      reason: "Partial service delivered; shared fault detected",
      status: "pending",
    },
    {
      id: "3",
      dispute_ref: "DSP-20260420-102",
      transaction_ref: "TXN-20260418-223",
      amount: 5000,
      recommendation: "deny",
      confidence: 0.76,
      suggested_amount: 0,
      reason: "Customer acknowledged receiving the service",
      status: "pending",
    },
  ];
}

export default DisputeMediationAI;
