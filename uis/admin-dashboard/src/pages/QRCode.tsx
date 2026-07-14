import { Camera, QrCode, Upload } from "lucide-react";
import React, { useRef, useState } from "react";

const CORE_BANKING_URL =
  import.meta.env.VITE_API_URL || "https://54agent.upi.dev";

const QRCodePage: React.FC = () => {
  const [qrAmount, setQrAmount] = useState("");
  const [qrNote, setQrNote] = useState("");
  const [generatedQR, setGeneratedQR] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleGenerateQR = async () => {
    if (!qrAmount || parseFloat(qrAmount) <= 0) {
      alert("Please enter a valid amount");
      return;
    }

    setIsGenerating(true);
    try {
      const token = localStorage.getItem("auth_token");

      // Get account info
      const accountRes = await fetch(`${CORE_BANKING_URL}/account/accounts`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });
      const accountData = await accountRes.json();
      const accounts = Array.isArray(accountData)
        ? accountData
        : accountData.accounts || [];
      const primaryAccount = accounts[0];

      if (!primaryAccount) {
        alert("No account found");
        return;
      }

      const res = await fetch(`${CORE_BANKING_URL}/payment/qr/generate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          recipient: primaryAccount.account_number,
          amount: parseFloat(qrAmount),
          currency: "NGN",
          note: qrNote,
        }),
      });

      const data = await res.json();
      if (res.ok && data.qr_code_data) {
        setGeneratedQR(data.qr_code_data);
      } else {
        alert(data.message || "Failed to generate QR code");
      }
    } catch (err) {
      console.error("QR generation error:", err);
      alert("Failed to generate QR code");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">QR Code Management</h1>
        <p className="text-gray-600 mt-1">
          Generate and manage QR codes for payments
        </p>
      </div>

      <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center">
          <QrCode className="h-5 w-5 mr-2" />
          Generate QR Code for Payment
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Amount (₦)
            </label>
            <input
              type="number"
              value={qrAmount}
              onChange={(e) => setQrAmount(e.target.value)}
              placeholder="Enter amount"
              min="1"
              step="0.01"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Note (Optional)
            </label>
            <input
              type="text"
              value={qrNote}
              onChange={(e) => setQrNote(e.target.value)}
              placeholder="Payment note"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <button
            onClick={handleGenerateQR}
            disabled={isGenerating}
            className="w-full px-4 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:bg-gray-400 font-medium"
          >
            {isGenerating ? "Generating..." : "Generate QR Code"}
          </button>
        </div>

        {generatedQR && (
          <div className="mt-6 p-6 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-sm font-medium text-gray-700 mb-4 text-center">
              Your QR Code:
            </p>
            <div className="flex justify-center">
              <img
                src={`data:image/png;base64,${generatedQR}`}
                alt="Generated QR Code"
                className="max-w-xs border-4 border-white shadow-lg"
              />
            </div>
            <button
              onClick={() => setGeneratedQR(null)}
              className="mt-4 w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
            >
              Close
            </button>
          </div>
        )}
      </div>

      <div
        className="rounded-lg p-4 max-w-2xl"
        style={{
          backgroundColor: "rgba(0,79,113,0.05)",
          borderColor: "rgba(0,79,113,0.2)",
          borderWidth: "1px",
        }}
      >
        <div className="flex items-start">
          <QrCode
            className="h-5 w-5 mt-0.5 mr-3 flex-shrink-0"
            style={{ color: "var(--tenant-primary-color,#002082)" }}
          />
          <div>
            <h3 className="font-medium mb-1" style={{ color: "color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)" }}>
              How to use QR Codes
            </h3>
            <ul className="text-sm text-blue-700 space-y-1">
              <li>• Generate a QR code with the payment amount</li>
              <li>• Share the QR code with customers for payment</li>
              <li>• Customers can scan to make instant payments</li>
              <li>• Track all payments through the transactions page</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QRCodePage;
