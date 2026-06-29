import { useEffect, useRef, useState } from "react";
import { billingApi } from "@/utils/api";
import {
  AlertTriangle, CheckCircle, CreditCard, FileText,
  MessageSquare, RefreshCw, TrendingUp, Wallet,
} from "lucide-react";

function fmtNGN(n: number): string {
  return new Intl.NumberFormat("en-NG", {
    style: "currency", currency: "NGN", maximumFractionDigits: 0,
  }).format(n || 0);
}

const STATUS_COLORS: Record<string, string> = {
  paid: "bg-green-100 text-green-700",
  pending: "bg-amber-100 text-amber-700",
  overdue: "bg-red-100 text-red-700",
  draft: "bg-gray-100 text-gray-600",
};

// ─── inline gateway launcher ──────────────────────────────────────────────────
// Dynamically loads the gateway SDK script once and calls the appropriate popup.
function launchGateway(
  result: { gateway: string; authorization_url: string; access_code?: string; public_key?: string },
  onSuccess: (ref: string) => void,
  onClose: () => void,
) {
  if (result.gateway === "paystack" && result.access_code && result.public_key) {
    loadScript("https://js.paystack.co/v1/inline.js", () => {
      const handler = (window as any).PaystackPop.setup({
        key: result.public_key,
        access_code: result.access_code,
        onSuccess: (txn: any) => onSuccess(txn.reference),
        onCancel: onClose,
      });
      handler.openIframe();
    });
    return;
  }

  if (result.gateway === "flutterwave" && result.public_key) {
    loadScript("https://checkout.flutterwave.com/v3.js", () => {
      (window as any).FlutterwaveCheckout({
        public_key: result.public_key,
        tx_ref: result.reference,
        authorization_url: result.authorization_url,
        onSuccess: (txn: any) => onSuccess(txn.tx_ref ?? txn.transaction_id),
        onClose,
      });
    });
    return;
  }

  // Stripe Checkout: full redirect — the success_url carries ?session_id=cs_xxx
  // which is read from the URL on mount and passed to verifyPayment.
  if (result.gateway === "stripe") {
    window.location.href = result.authorization_url;
    return;
  }

  // Fallback: open gateway's hosted page in a new tab
  window.open(result.authorization_url, "_blank");
  onClose();
}

function loadScript(src: string, onLoad: () => void) {
  if (document.querySelector(`script[src="${src}"]`)) { onLoad(); return; }
  const s = document.createElement("script");
  s.src = src; s.async = true;
  s.onload = onLoad;
  document.head.appendChild(s);
}
// ─────────────────────────────────────────────────────────────────────────────

export default function CreditsPaymentsPage() {
  const [credits, setCredits] = useState<any>(null);
  const [forecast, setForecast] = useState<any>(null);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [disputes, setDisputes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Payment form
  const [amount, setAmount] = useState("");
  const [email, setEmail] = useState("");
  const [paying, setPaying] = useState(false);
  const [payError, setPayError] = useState("");
  const [paySuccess, setPaySuccess] = useState<{ reference: string; amount: number } | null>(null);
  const pendingRef = useRef<string | null>(null);

  // Dispute form
  const [disputeInvoiceId, setDisputeInvoiceId] = useState("");
  const [disputeAmount, setDisputeAmount] = useState("");
  const [disputeReason, setDisputeReason] = useState("");
  const [filingDispute, setFilingDispute] = useState(false);
  const [disputeMsg, setDisputeMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [c, f, inv, d] = await Promise.allSettled([
        billingApi.getCreditBalance(),
        billingApi.getRevenueForecast(),
        billingApi.listInvoices({ page: 1, page_size: 20 }),
        billingApi.listDisputes(),
      ]);
      if (c.status === "fulfilled") setCredits(c.value);
      if (f.status === "fulfilled") setForecast(f.value);
      if (inv.status === "fulfilled") {
        const d = inv.value ?? {};
        const all: any[] = Array.isArray(d) ? d : d?.invoices ?? d?.data ?? [];
        setInvoices(all.filter((i: any) => i.status === "pending" || i.status === "overdue"));
      }
      if (d.status === "fulfilled") setDisputes(d.value?.disputes ?? d.value?.data ?? []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Check URL for a returning gateway redirect (ref=...)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    // Prefer Stripe's session_id for verification; fall back to our own ref
    const ref = params.get("session_id") ?? params.get("ref");
    if (ref) {
      pendingRef.current = ref;
      handleVerify(ref);
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  const handleVerify = async (reference: string) => {
    try {
      const result = await billingApi.verifyPayment(reference);
      if (result.status === "success") {
        setPaySuccess({ reference: result.reference, amount: result.amount });
        load();
      }
    } catch { /* silently ignore — user can retry */ }
  };

  const handlePay = async () => {
    const amt = Number(amount);
    if (!amt || amt < 100000) { setPayError("Minimum top-up is ₦100,000"); return; }
    if (!email) { setPayError("Email is required for payment"); return; }
    setPayError("");
    setPaying(true);
    try {
      const result = await billingApi.initializePayment({ amount: amt, email });
      launchGateway(
        result,
        async (ref) => {
          setPaying(false);
          const verification = await billingApi.verifyPayment(ref);
          if (verification.status === "success") {
            setPaySuccess({ reference: ref, amount: amt });
            setAmount(""); setEmail("");
            load();
          } else {
            setPayError("Payment could not be confirmed. Contact support if funds were deducted.");
          }
        },
        () => setPaying(false),
      );
    } catch (e: any) {
      setPayError(e?.message ?? "Could not initialize payment");
      setPaying(false);
    }
  };

  const handleFileDispute = async () => {
    if (!disputeInvoiceId || !disputeReason) return;
    setFilingDispute(true);
    try {
      await billingApi.fileDispute({
        invoice_id: disputeInvoiceId,
        amount: Number(disputeAmount) || 0,
        reason: disputeReason,
      });
      setDisputeMsg("Dispute filed successfully");
      setDisputeInvoiceId(""); setDisputeAmount(""); setDisputeReason("");
      load();
    } catch {
      setDisputeMsg("Failed to file dispute");
    } finally {
      setFilingDispute(false);
    }
  };

  const balance = credits?.balance ?? credits?.credit_balance ?? 0;
  const nextCharge = forecast?.forecast?.[0];

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Credits & Payments</h1>
          <p className="text-sm text-gray-500 mt-1">Top up your credit balance and manage outstanding invoices</p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1 text-sm px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-50">
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      {/* Balance + forecast */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 md:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <Wallet size={18} className="text-blue-600" />
            <span className="text-sm font-medium text-gray-600">Credit Balance</span>
          </div>
          {loading ? <div className="h-10 w-40 bg-gray-100 rounded animate-pulse" /> : (
            <>
              <p className={`text-4xl font-bold ${balance > 0 ? "text-gray-900" : "text-red-600"}`}>{fmtNGN(balance)}</p>
              {balance <= 0 && (
                <p className="text-sm text-red-500 mt-1 flex items-center gap-1">
                  <AlertTriangle size={14} /> Top up now to avoid service interruption
                </p>
              )}
            </>
          )}
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp size={18} className="text-green-600" />
            <span className="text-sm font-medium text-gray-600">Next Month Forecast</span>
          </div>
          {loading ? <div className="h-8 w-28 bg-gray-100 rounded animate-pulse" /> : nextCharge ? (
            <>
              <p className="text-2xl font-bold text-gray-900">{fmtNGN(nextCharge.projected_revenue)}</p>
              <p className="text-xs text-gray-400 mt-1">{nextCharge.month} · {Math.round(nextCharge.confidence * 100)}% confidence</p>
            </>
          ) : <p className="text-sm text-gray-400">No forecast available</p>}
        </div>
      </div>

      {/* Outstanding invoices */}
      {invoices.length > 0 && (
        <div className="bg-white rounded-xl border border-amber-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-amber-200 bg-amber-50 flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-600" />
            <h2 className="text-sm font-semibold text-amber-800">Outstanding Invoices ({invoices.length})</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left text-xs text-gray-500">
                <th className="px-5 py-3 font-medium">Invoice #</th>
                <th className="px-5 py-3 font-medium">Period</th>
                <th className="px-5 py-3 font-medium text-right">Amount Due</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Due Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {invoices.map((inv: any, i: number) => (
                <tr key={inv.id ?? i} className="hover:bg-gray-50">
                  <td className="px-5 py-3 font-mono text-xs text-blue-600">{inv.invoice_number ?? inv.id}</td>
                  <td className="px-5 py-3 text-xs text-gray-500">{inv.period_start?.slice(0, 10)} → {inv.period_end?.slice(0, 10)}</td>
                  <td className="px-5 py-3 text-right font-semibold">{fmtNGN(inv.total ?? inv.total_amount ?? 0)}</td>
                  <td className="px-5 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_COLORS[inv.status] ?? "bg-gray-100 text-gray-600"}`}>{inv.status}</span>
                  </td>
                  <td className="px-5 py-3 text-xs text-gray-500">{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Top-up / payment */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <CreditCard size={18} className="text-blue-600" />
          <h2 className="text-base font-semibold text-gray-900">Buy Credits</h2>
        </div>

        {paySuccess ? (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg space-y-1">
            <div className="flex items-center gap-2">
              <CheckCircle size={16} className="text-green-600" />
              <p className="text-sm font-semibold text-green-800">Payment confirmed — {fmtNGN(paySuccess.amount)} credited</p>
            </div>
            <p className="text-xs text-green-700 font-mono">Ref: {paySuccess.reference}</p>
            <button onClick={() => setPaySuccess(null)} className="text-xs text-green-700 underline">Make another payment</button>
          </div>
        ) : (
          <>
            <p className="text-sm text-gray-500">Enter an amount and your email. You'll be taken through a secure payment flow — card, bank transfer, or USSD.</p>
            <div className="flex flex-wrap gap-4 items-end">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Amount (₦)</label>
                <input
                  type="number"
                  min="100000"
                  step="50000"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 500000"
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-44"
                />
                <p className="text-xs text-gray-400 mt-1">Min ₦100,000</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-56"
                />
              </div>
              <button
                onClick={handlePay}
                disabled={paying || !amount || !email}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                <CreditCard size={14} />
                {paying ? "Opening payment..." : "Pay Now"}
              </button>
            </div>
            {payError && <p className="text-sm text-red-500">{payError}</p>}
          </>
        )}
      </div>

      {/* Revenue forecast */}
      {forecast?.forecast?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200 flex items-center gap-2">
            <TrendingUp size={16} className="text-blue-600" />
            <h2 className="text-sm font-semibold text-gray-700">Revenue Forecast (next 6 months)</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left text-xs text-gray-500">
                <th className="px-5 py-3 font-medium">Month</th>
                <th className="px-5 py-3 font-medium text-right">Projected Revenue</th>
                <th className="px-5 py-3 font-medium text-right">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {forecast.forecast.map((row: any, i: number) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-5 py-3 font-mono text-xs">{row.month}</td>
                  <td className="px-5 py-3 text-right font-medium">{fmtNGN(row.projected_revenue)}</td>
                  <td className="px-5 py-3 text-right text-gray-500">{Math.round(row.confidence * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Dispute */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center gap-2">
          <MessageSquare size={18} className="text-orange-500" />
          <h2 className="text-base font-semibold text-gray-900">Dispute an Invoice</h2>
        </div>

        {disputeMsg ? (
          <div className={`flex items-center gap-2 p-3 rounded-lg border ${disputeMsg.includes("success") ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"}`}>
            <CheckCircle size={16} className={disputeMsg.includes("success") ? "text-green-600" : "text-red-500"} />
            <p className={`text-sm ${disputeMsg.includes("success") ? "text-green-800" : "text-red-700"}`}>{disputeMsg}</p>
            <button onClick={() => setDisputeMsg("")} className="ml-auto text-xs underline opacity-70">Dismiss</button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Invoice ID</label>
              <input type="text" value={disputeInvoiceId} onChange={(e) => setDisputeInvoiceId(e.target.value)} placeholder="invoice-id..." className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-44" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Disputed Amount (₦)</label>
              <input type="number" value={disputeAmount} onChange={(e) => setDisputeAmount(e.target.value)} placeholder="Optional" className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-40" />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-gray-600 mb-1">Reason</label>
              <input type="text" value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} placeholder="Describe the issue..." className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <button onClick={handleFileDispute} disabled={filingDispute || !disputeInvoiceId || !disputeReason} className="flex items-center gap-2 px-4 py-2 bg-orange-500 text-white rounded-lg text-sm font-medium hover:bg-orange-600 disabled:opacity-50">
              <FileText size={14} />
              {filingDispute ? "Filing..." : "File Dispute"}
            </button>
          </div>
        )}

        {disputes.length > 0 && (
          <div className="border-t border-gray-100 pt-4 space-y-2">
            <p className="text-xs font-medium text-gray-500">Your Disputes</p>
            {disputes.map((d: any, i: number) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-orange-50 border border-orange-100">
                <AlertTriangle size={14} className="text-orange-500 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-gray-800">{d.invoice_id ?? d.id}</p>
                  <p className="text-xs text-gray-500">{d.reason}</p>
                  {d.amount > 0 && <p className="text-xs text-orange-600">{fmtNGN(d.amount)}</p>}
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${d.status === "resolved" ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700"}`}>
                  {d.status ?? "open"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
