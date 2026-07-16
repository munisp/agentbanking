import { Nfc, CheckCircle, XCircle, RefreshCw, Wifi, WifiOff, AlertTriangle, ArrowRight } from "lucide-react";
import React, { useState, useEffect } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const STATUS = { IDLE: "idle", SCANNING: "scanning", PROCESSING: "processing", SUCCESS: "success", ERROR: "error" };

const NFCPayment = () => {
  const [status, setStatus] = useState(STATUS.IDLE);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [nfcSupported, setNfcSupported] = useState(null);
  const [recentTx, setRecentTx] = useState([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [successTx, setSuccessTx] = useState(null);

  useEffect(() => {
    setNfcSupported("NDEFReader" in window);
    fetchRecentNfcTx();
  }, []);

  const fetchRecentNfcTx = async () => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/payment-processing/api/v1/transactions?channel=nfc&limit=10`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setRecentTx(Array.isArray(data.transactions) ? data.transactions : Array.isArray(data) ? data : []);
      }
    } catch {
      setRecentTx([]);
    }
  };

  const startNfcScan = async () => {
    if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
      setErrorMsg("Enter a valid amount before scanning.");
      return;
    }
    setErrorMsg("");
    setStatus(STATUS.SCANNING);

    try {
      if ("NDEFReader" in window) {
        const ndef = new window.NDEFReader();
        await ndef.scan();
        ndef.onreading = async (event) => {
          const cardId = event.serialNumber;
          await processNfcPayment(cardId);
        };
        ndef.onreadingerror = () => {
          setStatus(STATUS.ERROR);
          setErrorMsg("Could not read NFC tag. Try again.");
        };
      } else {
        // Simulate for non-NFC browsers (dev/testing)
        setTimeout(() => processNfcPayment("SIM-" + Date.now()), 2000);
      }
    } catch (err) {
      setStatus(STATUS.ERROR);
      setErrorMsg(err.message || "NFC scan failed.");
    }
  };

  const processNfcPayment = async (cardId) => {
    setStatus(STATUS.PROCESSING);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/payment-processing/api/v1/transactions`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: parseFloat(amount),
          channel: "nfc",
          card_token: cardId,
          description: description || "NFC payment",
          currency: "NGN",
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || "Payment failed");
      setSuccessTx(data);
      setStatus(STATUS.SUCCESS);
      setAmount("");
      setDescription("");
      fetchRecentNfcTx();
    } catch (err) {
      setStatus(STATUS.ERROR);
      setErrorMsg(err.message || "Payment processing failed.");
    }
  };

  const reset = () => { setStatus(STATUS.IDLE); setErrorMsg(""); setSuccessTx(null); };

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 rounded-lg">
            <Nfc className="w-7 h-7 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">NFC Payment</h1>
            <p className="text-gray-400 text-sm">Accept contactless card & device payments</p>
          </div>
          <div className="ml-auto flex items-center gap-2 text-xs">
            {nfcSupported === null ? null : nfcSupported ? (
              <span className="flex items-center gap-1 text-emerald-400"><Wifi className="w-4 h-4" /> NFC Ready</span>
            ) : (
              <span className="flex items-center gap-1 text-amber-400"><WifiOff className="w-4 h-4" /> NFC Simulated</span>
            )}
          </div>
        </div>

        {/* Success State */}
        {status === STATUS.SUCCESS && successTx && (
          <div className="bg-emerald-900/30 border border-emerald-700 rounded-xl p-6 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <h2 className="text-xl font-bold text-emerald-300">Payment Successful</h2>
            <p className="text-gray-600 mt-1">₦{parseFloat(successTx.amount || 0).toLocaleString()}</p>
            <p className="text-gray-500 text-sm mt-1">Ref: {successTx.reference || successTx.id}</p>
            <button onClick={reset} className="mt-4 px-6 py-2 bg-emerald-600 hover:bg-emerald-700 rounded-lg text-sm font-medium transition-colors">
              New Payment
            </button>
          </div>
        )}

        {/* Error State */}
        {status === STATUS.ERROR && (
          <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-400 shrink-0" />
            <p className="text-red-300 text-sm flex-1">{errorMsg}</p>
            <button onClick={reset} className="text-xs text-red-400 underline">Try again</button>
          </div>
        )}

        {/* Payment Form */}
        {(status === STATUS.IDLE || status === STATUS.ERROR) && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-6 space-y-4">
            <h2 className="font-semibold text-gray-200">Payment Details</h2>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Amount (₦)</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full bg-white border border-gray-300 rounded-lg px-4 py-3 text-white text-lg font-semibold placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Description (optional)</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Payment description"
                className="w-full bg-white border border-gray-300 rounded-lg px-4 py-2 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={startNfcScan}
              disabled={!amount}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-semibold flex items-center justify-center gap-2 transition-colors"
            >
              <Nfc className="w-5 h-5" /> Start NFC Scan
            </button>
          </div>
        )}

        {/* Scanning Animation */}
        {status === STATUS.SCANNING && (
          <div className="bg-blue-900/20 border border-blue-700 rounded-xl p-10 text-center">
            <div className="relative inline-block">
              <Nfc className="w-16 h-16 text-blue-400 mx-auto animate-pulse" />
              <span className="absolute inset-0 rounded-full border-4 border-blue-400/30 animate-ping" />
            </div>
            <p className="mt-4 text-blue-300 font-medium">Waiting for NFC tap...</p>
            <p className="text-gray-500 text-sm mt-1">Hold card or device near reader</p>
            <button onClick={reset} className="mt-4 text-gray-400 text-sm underline">Cancel</button>
          </div>
        )}

        {/* Processing Animation */}
        {status === STATUS.PROCESSING && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-10 text-center">
            <RefreshCw className="w-10 h-10 text-blue-400 mx-auto animate-spin" />
            <p className="mt-4 text-gray-600">Processing payment...</p>
          </div>
        )}

        {/* Recent NFC Transactions */}
        <div className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h3 className="font-medium text-gray-200">Recent NFC Transactions</h3>
            <button onClick={fetchRecentNfcTx} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
          {recentTx.length === 0 ? (
            <div className="p-8 text-center text-gray-500 text-sm">No NFC transactions yet</div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {recentTx.slice(0, 8).map((tx, i) => (
                <li key={tx.id || i} className="flex items-center justify-between px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Nfc className="w-4 h-4 text-blue-400" />
                    <div>
                      <p className="text-sm font-medium">{tx.description || "NFC Payment"}</p>
                      <p className="text-xs text-gray-500">{tx.reference || tx.id}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-emerald-400">₦{parseFloat(tx.amount || 0).toLocaleString()}</p>
                    <p className="text-xs text-gray-500">{tx.status || "completed"}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default NFCPayment;
