import { Camera, CheckCircle, QrCode, Upload, X } from "lucide-react";
import React, { useRef, useState } from "react";
import { authHeaders } from "../utils/api";

// Use Core Banking URL for QR code functionality
const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const QRScanner = () => {
  const [scanResult, setScanResult] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [recentScans, setRecentScans] = useState([]);
  const [isGeneratingQR, setIsGeneratingQR] = useState(false);
  const [qrAmount, setQrAmount] = useState("");
  const [qrNote, setQrNote] = useState("");
  const [generatedQR, setGeneratedQR] = useState(null);
  const fileInputRef = useRef(null);

  // Fetch recent transactions as recent scans
  React.useEffect(() => {
    const fetchRecentScans = async () => {
      try {
        const res = await fetch(
          `${CORE_BANKING_URL}/ledger/txn/?page=1&limit=5`,
          {
            headers: authHeaders(),
          },
        );
        if (res.ok) {
          const data = await res.json();
          const transactions = data.transactions || [];
          setRecentScans(
            transactions.slice(0, 3).map((txn) => ({
              id: txn.id,
              type: txn.payer === "MINT_ACCOUNT" ? "Receipt" : "Payment",
              customer: txn.payee || txn.payer,
              amount: parseFloat(txn.amount || 0),
              date: new Date(
                txn.created_at?.replace(" ", "T"),
              ).toLocaleDateString(),
              time: new Date(
                txn.created_at?.replace(" ", "T"),
              ).toLocaleTimeString(),
              status:
                txn.status?.toLowerCase() === "success"
                  ? "completed"
                  : txn.status,
            })),
          );
        }
      } catch (err) {
        console.error("Failed to fetch recent scans:", err);
      }
    };

    fetchRecentScans();
  }, []);

  const handleGenerateQR = async () => {
    if (!qrAmount || parseFloat(qrAmount) <= 0) {
      alert("Please enter a valid amount");
      return;
    }

    setIsGeneratingQR(true);
    try {
      // Get user's account info
      const keycloakId = localStorage.getItem("keycloakId");
      if (!keycloakId) {
        alert("No keycloak ID found. Please login again.");
        setIsGeneratingQR(false);
        return;
      }

      const accountRes = await fetch(
        `${CORE_BANKING_URL}/account/account/keycloak/${keycloakId}`,
        {
          headers: authHeaders(),
        },
      );
      const accountData = await accountRes.json();
      // The endpoint returns a single account object or an array
      const accounts = Array.isArray(accountData)
        ? accountData
        : accountData.account
          ? [accountData.account]
          : accountData.accounts || [];
      const primaryAccount = accounts[0];

      if (!primaryAccount) {
        alert("No account found");
        return;
      }

      // Get mint account id from tenant config
      let mintAccountId = null;
      try {
        const configStr = localStorage.getItem("tenant_config");
        if (configStr) {
          const tenant = JSON.parse(configStr);
          const featureFlags = Array.isArray(tenant.feature_flags)
            ? tenant.feature_flags
            : [];
          const accountsFeature = featureFlags.find(
            (flag) =>
              flag.name === "accounts" && flag.config && flag.config.account,
          );
          if (
            accountsFeature &&
            accountsFeature.config.account &&
            accountsFeature.config.account.id
          ) {
            mintAccountId = String(accountsFeature.config.account.id);
          }
        }
      } catch (err) {
        console.warn("Could not parse tenant config for mint account id", err);
      }

      const headers = {
        ...authHeaders(),
        "Content-Type": "application/json",
      };
      if (mintAccountId) {
        headers["x-mint-account-id"] = mintAccountId;
      }

      const res = await fetch(
        `${CORE_BANKING_URL}/payment-processing/qr/generate`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({
            recipient: primaryAccount.account_number,
            amount: String(qrAmount),
            currency: "NGN",
            note: qrNote,
          }),
        },
      );

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
      setIsGeneratingQR(false);
    }
  };

  const handleScanClick = () => {
    setIsScanning(true);
    // In a real implementation, this would open the camera
    // For demo purposes, we'll simulate a scan after 2 seconds
    setTimeout(() => {
      setScanResult({
        type: "Payment Request",
        customer: "John Doe",
        amount: 50000,
        reference:
          "QR-" + Math.random().toString(36).substr(2, 9).toUpperCase(),
      });
      setIsScanning(false);
    }, 2000);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      // In a real implementation, this would process the QR code from the image
      setScanResult({
        type: "Receipt Verification",
        customer: "Jane Smith",
        amount: 30000,
        reference:
          "QR-" + Math.random().toString(36).substr(2, 9).toUpperCase(),
      });
    }
  };

  const handleProcessPayment = () => {
    console.log("Processing payment:", scanResult);
    // Add to recent scans and reset
    setScanResult(null);
  };

  const handleCancelScan = () => {
    setScanResult(null);
    setIsScanning(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">QR Code Scanner</h1>
        <p className="text-gray-600 mt-1">
          Scan QR codes for payments and receipts
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scanner Section */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">
              Scanner
            </h2>

            {!scanResult && !isScanning && (
              <div className="space-y-4">
                {/* Generate QR Code Section */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                  <h3 className="font-medium text-blue-900 mb-3 flex items-center">
                    <QrCode className="h-5 w-5 mr-2" />
                    Generate QR Code for Payment
                  </h3>
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Amount (₦)
                      </label>
                      <input
                        type="number"
                        value={qrAmount}
                        onChange={(e) => setQrAmount(e.target.value)}
                        placeholder="Enter amount"
                        min="1"
                        step="0.01"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Note (Optional)
                      </label>
                      <input
                        type="text"
                        value={qrNote}
                        onChange={(e) => setQrNote(e.target.value)}
                        placeholder="Payment note"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                      />
                    </div>
                    <button
                      onClick={handleGenerateQR}
                      disabled={isGeneratingQR}
                      className="w-full px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:bg-gray-400"
                    >
                      {isGeneratingQR ? "Generating..." : "Generate QR Code"}
                    </button>
                  </div>

                  {generatedQR && (
                    <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200">
                      <p className="text-sm font-medium text-gray-700 mb-2">
                        Your QR Code:
                      </p>
                      <div className="flex justify-center">
                        <img
                          src={`data:image/png;base64,${generatedQR}`}
                          alt="Generated QR Code"
                          className="max-w-xs"
                        />
                      </div>
                      <button
                        onClick={() => setGeneratedQR(null)}
                        className="mt-3 w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                      >
                        Close
                      </button>
                    </div>
                  )}
                </div>

                {/* Scan Options */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <button
                    onClick={handleScanClick}
                    className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-gray-300 rounded-lg hover:border-[var(--tenant-primary-color,#004F71)] transition-all"
                    style={{ backgroundColor: "transparent" }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.backgroundColor =
                        "rgba(0,79,113,0.05)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.backgroundColor = "transparent")
                    }
                  >
                    <div
                      className="p-4 rounded-full mb-4"
                      style={{ backgroundColor: "rgba(0,79,113,0.1)" }}
                    >
                      <Camera
                        className="h-8 w-8"
                        style={{ color: "var(--tenant-primary-color,#004F71)" }}
                      />
                    </div>
                    <span className="text-lg font-medium text-gray-900">
                      Scan with Camera
                    </span>
                    <span className="text-sm text-gray-500 mt-2">
                      Open camera to scan QR code
                    </span>
                  </button>

                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-gray-300 rounded-lg hover:border-[var(--tenant-primary-color,#004F71)] transition-all"
                    style={{ backgroundColor: "transparent" }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.backgroundColor =
                        "rgba(0,79,113,0.05)")
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.backgroundColor = "transparent")
                    }
                  >
                    <div className="p-4 bg-green-100 rounded-full mb-4">
                      <Upload className="h-8 w-8 text-green-600" />
                    </div>
                    <span className="text-lg font-medium text-gray-900">
                      Upload QR Image
                    </span>
                    <span className="text-sm text-gray-500 mt-2">
                      Select image from device
                    </span>
                  </button>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileUpload}
                  className="hidden"
                />

                {/* Info Section */}
                <div
                  className="rounded-lg p-4 mt-6"
                  style={{
                    backgroundColor: "rgba(0,79,113,0.05)",
                    borderColor: "rgba(0,79,113,0.2)",
                    borderWidth: "1px",
                  }}
                >
                  <div className="flex items-start">
                    <QrCode
                      className="h-5 w-5 mt-0.5 mr-3 shrink-0"
                      style={{ color: "var(--tenant-primary-color,#004F71)" }}
                    />
                    <div>
                      <h3
                        className="font-medium mb-1"
                        style={{ color: "var(--tenant-primary-color,#003047)" }}
                      >
                        How to use QR Scanner
                      </h3>
                      <ul className="text-sm text-blue-700 space-y-1">
                        <li>• Point your camera at the customer's QR code</li>
                        <li>• Wait for automatic detection and scanning</li>
                        <li>• Review payment details before confirming</li>
                        <li>• Or upload a QR code image from your device</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Scanning State */}
            {isScanning && (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="relative">
                  <div
                    className="w-64 h-64 border-4 rounded-lg relative"
                    style={{ borderColor: "var(--tenant-primary-color,#004F71)" }}
                  >
                    <div
                      className="absolute top-0 left-0 w-16 h-16 border-t-4 border-l-4"
                      style={{ borderColor: "var(--tenant-primary-color,#004F71)" }}
                    ></div>
                    <div
                      className="absolute top-0 right-0 w-16 h-16 border-t-4 border-r-4"
                      style={{ borderColor: "var(--tenant-primary-color,#004F71)" }}
                    ></div>
                    <div
                      className="absolute bottom-0 left-0 w-16 h-16 border-b-4 border-l-4"
                      style={{ borderColor: "var(--tenant-primary-color,#004F71)" }}
                    ></div>
                    <div
                      className="absolute bottom-0 right-0 w-16 h-16 border-b-4 border-r-4"
                      style={{ borderColor: "var(--tenant-primary-color,#004F71)" }}
                    ></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Camera
                        className="h-12 w-12 animate-pulse"
                        style={{ color: "var(--tenant-primary-color,#004F71)" }}
                      />
                    </div>
                  </div>
                </div>
                <p className="text-lg font-medium text-gray-900 mt-6">
                  Scanning QR Code...
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  Position the QR code within the frame
                </p>
                <button
                  onClick={handleCancelScan}
                  className="mt-6 px-6 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Scan Result */}
            {scanResult && (
              <div className="space-y-6">
                <div className="flex items-center justify-center py-4">
                  <div className="p-3 bg-green-100 rounded-full">
                    <CheckCircle className="h-12 w-12 text-green-600" />
                  </div>
                </div>

                <div className="text-center">
                  <h3 className="text-xl font-semibold text-gray-900">
                    QR Code Scanned Successfully!
                  </h3>
                  <p className="text-gray-600 mt-1">Review the details below</p>
                </div>

                <div className="bg-gray-50 rounded-lg p-6 space-y-4">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Type:</span>
                    <span className="font-semibold text-gray-900">
                      {scanResult.type}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Customer:</span>
                    <span className="font-semibold text-gray-900">
                      {scanResult.customer}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Amount:</span>
                    <span className="font-semibold text-green-600 text-xl">
                      ₦{scanResult.amount.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Reference:</span>
                    <span className="font-mono text-sm text-gray-900">
                      {scanResult.reference}
                    </span>
                  </div>
                </div>

                <div className="flex gap-4">
                  <button
                    onClick={handleProcessPayment}
                    className="flex-1 px-6 py-3 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors font-medium"
                  >
                    Process Payment
                  </button>
                  <button
                    onClick={handleCancelScan}
                    className="px-6 py-3 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors font-medium"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Recent Scans */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Recent Scans
          </h2>
          <div className="space-y-4">
            {recentScans.map((scan) => (
              <div key={scan.id} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-medium text-gray-900 text-sm">
                      {scan.type}
                    </p>
                    <p className="text-xs text-gray-500">{scan.customer}</p>
                  </div>
                  <QrCode className="h-4 w-4 text-gray-400" />
                </div>
                <div className="flex justify-between items-center mt-2">
                  <span className="text-sm font-semibold text-gray-900">
                    ₦{scan.amount.toLocaleString()}
                  </span>
                  <span className="text-xs text-gray-500">{scan.time}</span>
                </div>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mt-2">
                  {scan.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default QRScanner;
