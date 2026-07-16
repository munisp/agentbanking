import {
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  RefreshCw,
  Upload,
  XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { api } from "../../utils/api";

interface Chargeback {
  id: string;
  chargeback_ref: string;
  transaction_ref: string;
  agent_name: string;
  amount: number;
  reason_code: string;
  reason_label: string;
  card_network: "visa" | "mastercard" | "verve";
  status: "received" | "under_review" | "responded" | "won" | "lost" | "split";
  response_deadline: string;
  evidence_submitted: boolean;
  refund_amount?: number;
  created_at: string;
}

interface ChargebackStats {
  total: number;
  pending_response: number;
  won: number;
  lost: number;
  win_rate: number;
  total_exposure: number;
  total_refunded: number;
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  received: { label: "Received", color: "bg-yellow-100 text-yellow-700" },
  under_review: { label: "Under Review", color: "bg-blue-50 text-[var(--tenant-primary-color,#004F71)]" },
  responded: { label: "Responded", color: "bg-purple-100 text-purple-700" },
  won: { label: "Won", color: "bg-green-100 text-green-700" },
  lost: { label: "Lost", color: "bg-red-100 text-red-700" },
  split: { label: "Split", color: "bg-orange-100 text-orange-700" },
};

const REASON_CODES: Record<string, string> = {
  "4853": "Cardholder Dispute",
  "4855": "Non-receipt of Merchandise",
  "4863": "Cardholder Does Not Recognize",
  "4837": "No Cardholder Authorization",
  "4842": "Late Presentment",
  "12.1": "EMV Liability Shift",
  "37": "No Cardholder Authorization",
  "4808": "Authorization-Related",
};

const NETWORK_DEADLINES: Record<string, number> = {
  visa: 30,
  mastercard: 45,
  verve: 30,
};

const fmt = (n: number) =>
  new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(n || 0);

const ChargebackManagement: React.FC = () => {
  const [chargebacks, setChargebacks] = useState<Chargeback[]>([]);
  const [stats, setStats] = useState<ChargebackStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedCb, setSelectedCb] = useState<Chargeback | null>(null);
  const [outcome, setOutcome] = useState<"won" | "lost" | "split">("won");
  const [refundAmt, setRefundAmt] = useState("");
  const [evidenceNote, setEvidenceNote] = useState("");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    load();
  }, [statusFilter]);

  const load = async () => {
    try {
      setLoading(true);
      const res = await api.listChargebacks(statusFilter !== "all" ? statusFilter : undefined);
      const payload =
        res && typeof res === "object"
          ? (res as { chargebacks?: Chargeback[]; data?: Chargeback[] })
          : {};
      const data: Chargeback[] =
        payload.chargebacks ?? payload.data ?? generateMockChargebacks();
      setChargebacks(data);

      setStats({
        total: data.length,
        pending_response: data.filter((c) => ["received", "under_review"].includes(c.status)).length,
        won: data.filter((c) => c.status === "won").length,
        lost: data.filter((c) => c.status === "lost").length,
        win_rate: data.length ? (data.filter((c) => c.status === "won").length / data.filter((c) => ["won", "lost"].includes(c.status)).length) * 100 || 0 : 0,
        total_exposure: data.filter((c) => ["received", "under_review", "responded"].includes(c.status)).reduce((s, c) => s + c.amount, 0),
        total_refunded: data.filter((c) => ["lost", "split"].includes(c.status)).reduce((s, c) => s + (c.refund_amount || c.amount), 0),
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load chargebacks");
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedCb) return;
    try {
      setProcessing(true);
      await api.resolveChargeback(selectedCb.id, {
        outcome,
        refund_amount: refundAmt ? parseFloat(refundAmt) : undefined,
      });
      setSuccess(`Chargeback ${selectedCb.chargeback_ref} marked as ${outcome}`);
      setSelectedCb(null);
      load();
    } catch (err: any) {
      setError(err.message || "Failed to resolve chargeback");
    } finally {
      setProcessing(false);
    }
  };

  const getDaysLeft = (deadline: string) => {
    const diff = Math.ceil((new Date(deadline).getTime() - Date.now()) / 86400000);
    return diff;
  };

  const filtered = chargebacks.filter(
    (c) => statusFilter === "all" || c.status === statusFilter,
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chargeback Management</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage bank-initiated chargebacks, submit evidence, and track win/loss rates
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Pending Response", value: stats.pending_response, color: "text-yellow-600", sub: "Requires action" },
            { label: "Win Rate", value: `${stats.win_rate.toFixed(1)}%`, color: "text-green-600", sub: `${stats.won} won / ${stats.lost} lost` },
            { label: "Total Exposure", value: fmt(stats.total_exposure), color: "text-red-600", sub: "Open chargebacks" },
            { label: "Total Refunded", value: fmt(stats.total_refunded), color: "text-orange-600", sub: "Lost + Split" },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-lg p-4 border border-gray-200">
              <p className="text-xs text-gray-500">{s.label}</p>
              <p className={`text-xl font-bold mt-1 ${s.color}`}>{s.value}</p>
              <p className="text-xs text-gray-400 mt-1">{s.sub}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {["all", "received", "under_review", "responded", "won", "lost", "split"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
              statusFilter === s
                ? "bg-[var(--tenant-primary-color,#004F71)] text-white border-[var(--tenant-primary-color,#004F71)]"
                : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
            }`}
          >
            {s === "all" ? "All" : STATUS_CONFIG[s]?.label || s}
          </button>
        ))}
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError("")} className="ml-auto text-lg">×</button>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 flex items-center gap-2 text-green-700 text-sm">
          <CheckCircle size={16} />
          {success}
          <button onClick={() => setSuccess("")} className="ml-auto text-lg">×</button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {["Ref", "Transaction", "Agent", "Amount", "Reason", "Network", "Deadline", "Evidence", "Status", "Actions"].map((h) => (
                <th key={h} className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={10} className="px-4 py-8 text-center text-gray-400">No chargebacks found</td></tr>
            ) : (
              filtered.map((c) => {
                const cfg = STATUS_CONFIG[c.status] || STATUS_CONFIG.received;
                const daysLeft = getDaysLeft(c.response_deadline);
                const isUrgent = daysLeft <= 5 && ["received", "under_review"].includes(c.status);
                return (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-3 py-3 font-mono text-xs">{c.chargeback_ref}</td>
                    <td className="px-3 py-3 font-mono text-xs text-gray-500">{c.transaction_ref}</td>
                    <td className="px-3 py-3 text-sm">{c.agent_name}</td>
                    <td className="px-3 py-3 font-semibold">{fmt(c.amount)}</td>
                    <td className="px-3 py-3">
                      <span className="text-xs text-gray-500">
                        {c.reason_code} — {c.reason_label}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <span className={`text-xs font-semibold uppercase ${
                        c.card_network === "visa" ? "text-blue-600" : c.card_network === "mastercard" ? "text-red-600" : "text-green-600"
                      }`}>
                        {c.card_network}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className={`text-xs font-medium ${isUrgent ? "text-red-600" : "text-gray-600"}`}>
                        {daysLeft > 0 ? `${daysLeft}d left` : "Overdue"}
                      </div>
                      <div className="text-xs text-gray-400">
                        {new Date(c.response_deadline).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      {c.evidence_submitted ? (
                        <CheckCircle size={14} className="text-green-500" />
                      ) : (
                        <XCircle size={14} className="text-red-400" />
                      )}
                    </td>
                    <td className="px-3 py-3">
                      <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
                        {cfg.label}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      {["received", "under_review", "responded"].includes(c.status) && (
                        <button
                          onClick={() => { setSelectedCb(c); setRefundAmt(c.amount.toString()); }}
                          className="text-xs text-[var(--tenant-primary-color,#004F71)] hover:underline font-medium"
                        >
                          Resolve
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Resolve Modal */}
      {selectedCb && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold">Resolve Chargeback</h3>
            <div className="bg-gray-50 rounded-lg p-3 text-sm space-y-2">
              <div className="flex justify-between">
                <span className="text-gray-500">Reference</span>
                <span className="font-mono text-xs">{selectedCb.chargeback_ref}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Amount</span>
                <span className="font-bold">{fmt(selectedCb.amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Network Deadline</span>
                <span className={getDaysLeft(selectedCb.response_deadline) <= 5 ? "text-red-600 font-semibold" : ""}>
                  {new Date(selectedCb.response_deadline).toLocaleDateString()} ({getDaysLeft(selectedCb.response_deadline)}d)
                </span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Outcome</label>
              <div className="flex gap-2">
                {(["won", "lost", "split"] as const).map((o) => (
                  <button
                    key={o}
                    onClick={() => setOutcome(o)}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium border-2 transition-colors capitalize ${
                      outcome === o
                        ? o === "won" ? "bg-green-600 text-white border-green-600"
                          : o === "lost" ? "bg-red-600 text-white border-red-600"
                          : "bg-orange-500 text-white border-orange-500"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {o}
                  </button>
                ))}
              </div>
            </div>

            {(outcome === "lost" || outcome === "split") && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Refund Amount (₦)
                </label>
                <input
                  type="number"
                  value={refundAmt}
                  onChange={(e) => setRefundAmt(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="0.00"
                />
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleResolve}
                disabled={processing}
                className="flex-1 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >
                {processing ? "Saving…" : "Confirm Outcome"}
              </button>
              <button
                onClick={() => setSelectedCb(null)}
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

function generateMockChargebacks(): Chargeback[] {
  return [
    { id: "1", chargeback_ref: "CB-20250421-001", transaction_ref: "TXN-20250415-334", agent_name: "Emeka Obi", amount: 15000, reason_code: "4853", reason_label: "Cardholder Dispute", card_network: "visa", status: "received", response_deadline: "2025-05-21", evidence_submitted: false, created_at: "2025-04-21T10:00:00Z" },
    { id: "2", chargeback_ref: "CB-20250419-002", transaction_ref: "TXN-20250410-228", agent_name: "Fatima Sule", amount: 8500, reason_code: "4837", reason_label: "No Cardholder Authorization", card_network: "mastercard", status: "responded", response_deadline: "2025-05-04", evidence_submitted: true, created_at: "2025-04-19T14:30:00Z" },
    { id: "3", chargeback_ref: "CB-20250418-003", transaction_ref: "TXN-20250405-112", agent_name: "Chidi Nwosu", amount: 25000, reason_code: "4855", reason_label: "Non-receipt of Merchandise", card_network: "verve", status: "won", response_deadline: "2025-05-18", evidence_submitted: true, created_at: "2025-04-18T09:00:00Z" },
    { id: "4", chargeback_ref: "CB-20250416-004", transaction_ref: "TXN-20250401-089", agent_name: "Aisha Bello", amount: 5000, reason_code: "4863", reason_label: "Cardholder Does Not Recognize", card_network: "visa", status: "lost", response_deadline: "2025-05-16", evidence_submitted: false, refund_amount: 5000, created_at: "2025-04-16T11:00:00Z" },
    { id: "5", chargeback_ref: "CB-20250414-005", transaction_ref: "TXN-20250399-067", agent_name: "Tunde Adeyemi", amount: 32000, reason_code: "12.1", reason_label: "EMV Liability Shift", card_network: "mastercard", status: "split", response_deadline: "2025-05-29", evidence_submitted: true, refund_amount: 16000, created_at: "2025-04-14T15:00:00Z" },
  ];
}

export default ChargebackManagement;
