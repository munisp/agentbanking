import { RotateCcw, XCircle, Eye, RefreshCw, Clock, AlertCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

type OperationType = "payment" | "notification" | "webhook" | "settlement";

interface RetryItem {
  id: string;
  operationType: OperationType;
  payloadSummary: string;
  attemptCount: number;
  nextRetryTime: string;
  originalError: string;
}

interface InspectModal {
  item: RetryItem | null;
}

const MOCK_ITEMS: RetryItem[] = [
  { id: "RQ-001", operationType: "payment", payloadSummary: "NGN 5,000 → AGT-012", attemptCount: 2, nextRetryTime: "2026-05-02 10:15", originalError: "Connection timeout to core banking" },
  { id: "RQ-002", operationType: "webhook", payloadSummary: "POST https://partner.example.com/hook", attemptCount: 4, nextRetryTime: "2026-05-02 10:30", originalError: "HTTP 503 from upstream" },
  { id: "RQ-003", operationType: "notification", payloadSummary: "SMS to +2348012345678", attemptCount: 1, nextRetryTime: "2026-05-02 10:10", originalError: "SMS gateway rate limit exceeded" },
  { id: "RQ-004", operationType: "settlement", payloadSummary: "Batch settle 312 txns", attemptCount: 3, nextRetryTime: "2026-05-02 11:00", originalError: "Insufficient settlement float" },
  { id: "RQ-005", operationType: "payment", payloadSummary: "GHS 200 → AGT-088", attemptCount: 1, nextRetryTime: "2026-05-02 10:05", originalError: "Invalid account number" },
];

const OP_STYLES: Record<OperationType, string> = {
  payment: "bg-blue-100 text-blue-700",
  notification: "bg-purple-100 text-purple-700",
  webhook: "bg-amber-100 text-amber-700",
  settlement: "bg-emerald-100 text-emerald-700",
};

const RetryQueueViewer: React.FC = () => {
  const [items, setItems] = useState<RetryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<InspectModal>({ item: null });
  const [toast, setToast] = useState<string | null>(null);

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/retry-queue`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setItems(Array.isArray(d.items) ? d.items : MOCK_ITEMS); }
    } catch { }
    finally { setLoading(false); }
  };

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const handleRetry = async (id: string) => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/retry-queue/${id}/retry`, {
        method: "POST",
        headers: getTenantHeadersFromStorage(),
      });
      showToast(`Retry triggered for ${id}`);
      fetchData();
    } catch { showToast(`Retry triggered for ${id} (demo)`); }
  };

  const handleCancel = async (id: string) => {
    try {
      await fetch(`${CORE_URL}/ops/api/v1/retry-queue/${id}`, {
        method: "DELETE",
        headers: getTenantHeadersFromStorage(),
      });
      showToast(`${id} cancelled`);
      fetchData();
    } catch { setItems(prev => prev.filter(i => i.id !== id)); showToast(`${id} cancelled (demo)`); }
  };

  const totalQueued = items.length;
  const avgAttempts = items.length > 0 ? (items.reduce((s, i) => s + i.attemptCount, 0) / items.length).toFixed(1) : "0";
  const maxAttempts = items.length > 0 ? Math.max(...items.map(i => i.attemptCount)) : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <RotateCcw className="w-7 h-7 text-indigo-600" /> Retry Queue Viewer
          </h1>
          <p className="text-gray-500 text-sm mt-1">Failed operations pending automatic or manual retry</p>
        </div>
        <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {toast && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-sm text-blue-700">{toast}</div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Queued", value: totalQueued, color: "text-gray-800" },
          { label: "Avg Attempts", value: avgAttempts, color: "text-amber-600" },
          { label: "Max Attempts", value: maxAttempts, color: "text-red-600" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl shadow-sm p-6">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["ID", "Type", "Payload", "Attempts", "Next Retry", "Error", "Actions"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono text-gray-700 text-xs">{item.id}</td>
                  <td className="py-2 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full capitalize font-medium ${OP_STYLES[item.operationType]}`}>{item.operationType}</span>
                  </td>
                  <td className="py-2 px-3 text-gray-600 max-w-[160px] truncate">{item.payloadSummary}</td>
                  <td className="py-2 px-3">
                    <span className={`font-semibold ${item.attemptCount >= 4 ? "text-red-600" : item.attemptCount >= 2 ? "text-amber-600" : "text-gray-700"}`}>{item.attemptCount}</span>
                  </td>
                  <td className="py-2 px-3 text-gray-500 flex items-center gap-1 text-xs"><Clock className="w-3 h-3" />{item.nextRetryTime}</td>
                  <td className="py-2 px-3 text-gray-500 max-w-[160px] truncate text-xs">{item.originalError}</td>
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleRetry(item.id)} className="p-1 text-indigo-600 hover:bg-indigo-50 rounded" title="Retry Now"><RotateCcw className="w-3.5 h-3.5" /></button>
                      <button onClick={() => handleCancel(item.id)} className="p-1 text-red-500 hover:bg-red-50 rounded" title="Cancel"><XCircle className="w-3.5 h-3.5" /></button>
                      <button onClick={() => setModal({ item })} className="p-1 text-gray-500 hover:bg-gray-100 rounded" title="Inspect"><Eye className="w-3.5 h-3.5" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {modal.item && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2"><AlertCircle className="w-4 h-4 text-indigo-500" /> Inspect {modal.item.id}</h3>
              <button onClick={() => setModal({ item: null })} className="text-gray-400 hover:text-gray-600"><XCircle className="w-5 h-5" /></button>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Type</span><span className="font-medium capitalize">{modal.item.operationType}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Payload</span><span className="font-medium text-right max-w-[200px]">{modal.item.payloadSummary}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Attempts</span><span className="font-medium">{modal.item.attemptCount}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Next Retry</span><span className="font-medium">{modal.item.nextRetryTime}</span></div>
              <div className="pt-2 border-t border-gray-100">
                <p className="text-gray-500 text-xs mb-1">Original Error</p>
                <p className="text-red-600 text-xs bg-red-50 rounded p-2">{modal.item.originalError}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RetryQueueViewer;
