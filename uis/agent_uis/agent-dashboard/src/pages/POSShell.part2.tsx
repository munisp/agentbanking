// @ts-nocheck
import { useTransactionCreate } from "../hooks/useTransactionCreate";
import { trpc } from "../lib/trpc";
import { QRCodeCanvas } from "qrcode.react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { AmountDisplay, NumPad, ScreenHeader, SuccessScreen } from "./POSShell.part10";
import { fmt } from "./POSShell.part5";
import { ReceiptModal } from "./POSShell.part6";
import { BORDER, CARD, DISP, GOLD, GREEN, MONO, QR_TTL_MS, RED, TERMINAL } from "./POSShell.shared";

function QRPaymentScreen({ onBack }: { onBack: () => void }) {
  const [mode, setMode] = useState<"scan" | "generate" | "batch" | "success">(
    "scan"
  );
  // Batch QR state
  const DEFAULT_PRESET_AMOUNTS = [
    500, 1000, 2000, 5000, 10000, 20000, 50000, 100000,
  ];
  const LS_PRESETS_KEY = "54link-qr-preset-amounts";
  const [batchPresetAmounts, setBatchPresetAmounts] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem(LS_PRESETS_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as number[];
        if (Array.isArray(parsed) && parsed.length > 0)
          return parsed.sort((a: any, b: any) => a - b);
      }
    } catch {}
    return DEFAULT_PRESET_AMOUNTS;
  });
  const [showAddPreset, setShowAddPreset] = useState(false);
  const [newPresetInput, setNewPresetInput] = useState("");
  const savePresets = (presets: number[]) => {
    const sorted = Array.from(new Set(presets)).sort((a: any, b: any) => a - b);
    setBatchPresetAmounts(sorted);
    localStorage.setItem(LS_PRESETS_KEY, JSON.stringify(sorted));
  };
  const [batchQRList, setBatchQRList] = useState<
    Array<{
      id: string;
      amount: number;
      payload: string;
      expiresAt: number;
      label: string;
      synced: boolean;
    }>
  >([]);
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [selectedBatchAmounts, setSelectedBatchAmounts] = useState<Set<number>>(
    new Set([500, 1000, 2000, 5000])
  );
  const [amount, setAmount] = useState("");
  const [receipt, setReceipt] = useState(false);
  const [txRef, setTxRef] = useState(`TXN-${Date.now().toString().slice(-9)}`);
  const [showUssdFallback, setShowUssdFallback] = useState(false);
  const [scanResult, setScanResult] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [qrPayload, setQrPayload] = useState<string>("");
  const [qrExpiresAt, setQrExpiresAt] = useState<number | null>(null);
  const [qrSecondsLeft, setQrSecondsLeft] = useState<number | null>(null);
  const [qrExpired, setQrExpired] = useState(false);
  const [offlineQRList, setOfflineQRList] = useState<
    Array<{
      id: string;
      payload: string;
      amount: number;
      label: string;
      synced: boolean;
    }>
  >([]);
  const num = parseFloat(amount || "0");
  const { submit } = useTransactionCreate();
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const agentData = trpc.agentBanking.profile.get.useQuery(
    { agentId: 1 },
    { retry: false }
  );
  const agentCode = (agentData.data as any)?.agentCode ?? "AGENT";

  // Track online state
  useEffect(() => {
    const on = () => setIsOnline(true);
    const off = () => setIsOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  // Build QR payload with TTL whenever amount or agentCode changes
  useEffect(() => {
    if (num > 0) {
      const ref = `QR-${agentCode}-${Date.now().toString(36).toUpperCase()}`;
      const expiresAt = Date.now() + QR_TTL_MS;
      // Format: 54LINK:{ref}:{amount}:{agentCode}:{expiresAt_unix_sec}
      setQrPayload(
        `54LINK:${ref}:${num}:${agentCode}:${Math.floor(expiresAt / 1000)}`
      );
      setQrExpiresAt(expiresAt);
      setQrExpired(false);
    } else {
      setQrPayload("");
      setQrExpiresAt(null);
      setQrSecondsLeft(null);
      setQrExpired(false);
    }
  }, [num, agentCode]);
  // Countdown timer
  useEffect(() => {
    if (!qrExpiresAt) return;
    const tick = () => {
      const left = Math.max(0, Math.floor((qrExpiresAt - Date.now()) / 1000));
      setQrSecondsLeft(left);
      if (left === 0) setQrExpired(true);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [qrExpiresAt]);
  // Regenerate expired QR
  const regenerateQR = useCallback(() => {
    if (num > 0) {
      const ref = `QR-${agentCode}-${Date.now().toString(36).toUpperCase()}`;
      const expiresAt = Date.now() + QR_TTL_MS;
      setQrPayload(
        `54LINK:${ref}:${num}:${agentCode}:${Math.floor(expiresAt / 1000)}`
      );
      setQrExpiresAt(expiresAt);
      setQrExpired(false);
    }
  }, [num, agentCode]);

  // Load offline QR codes from IndexedDB
  useEffect(() => {
    const IDB_NAME = "54link-qr-store";
    const IDB_STORE = "offline_qr_codes";
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = e => {
      const db = (e.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(IDB_STORE))
        db.createObjectStore(IDB_STORE, { keyPath: "id" });
    };
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction(IDB_STORE, "readonly");
      const all = tx.objectStore(IDB_STORE).getAll();
      all.onsuccess = () =>
        setOfflineQRList(
          (all.result as any[]).filter(r => r.agentCode === agentCode)
        );
      db.close();
    };
  }, [agentCode]);

  // Camera scanner refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number | null>(null);
  const [cameraActive, setCameraActive] = useState(false);

  const stopCamera = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
  }, []);

  const startCamera = useCallback(async () => {
    setScanError(null);
    setScanResult(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setScanError("Camera not available");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraActive(true);
        const { default: jsQR } = await import("jsqr");
        const tick = () => {
          const v = videoRef.current;
          const c = canvasRef.current;
          if (!v || !c || v.readyState !== v.HAVE_ENOUGH_DATA) {
            rafRef.current = requestAnimationFrame(tick);
            return;
          }
          c.width = v.videoWidth;
          c.height = v.videoHeight;
          const ctx = c.getContext("2d");
          if (!ctx) {
            rafRef.current = requestAnimationFrame(tick);
            return;
          }
          ctx.drawImage(v, 0, 0);
          const img = ctx.getImageData(0, 0, c.width, c.height);
          const code = jsQR(img.data, img.width, img.height, {
            inversionAttempts: "dontInvert",
          });
          if (code?.data) {
            stopCamera();
            setScanResult(code.data);
            // If it's a 54Link QR, validate TTL and auto-process the payment
            if (code.data.startsWith("54LINK:")) {
              const parts = code.data.split(":");
              // parts: ["54LINK", ref, amount, agentCode, expiresAt_sec?]
              const scannedAmount = parseFloat(parts[2] ?? "0");
              const expiresAtSec = parts[4] ? parseInt(parts[4], 10) : null;
              // Validate expiry if present
              if (expiresAtSec && Date.now() / 1000 > expiresAtSec) {
                toast.error(
                  "⚠️ QR code has expired. Ask the agent to regenerate."
                );
                setScanResult(null);
                // Restart camera for retry
                startCamera();
                return;
              }
              if (scannedAmount > 0) {
                setAmount(String(scannedAmount));
                submit({
                  type: "QR Payment",
                  amount: scannedAmount,
                  customerName: "QR Customer",
                  channel: "QR",
                })
                  .then(result => {
                    if (result) {
                      setTxRef(result.ref);
                      setMode("success");
                    }
                  })
                  .catch(() => toast.error("QR payment failed"));
              }
            } else {
              toast.success(`QR scanned: ${code.data.slice(0, 40)}...`);
            }
            return;
          }
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      }
    } catch (e: unknown) {
      setScanError(e instanceof Error ? e.message : "Camera access denied");
    }
  }, [submit, stopCamera]);

  useEffect(() => () => stopCamera(), [stopCamera]);

  // USSD fallback
  const encodeUssd = trpc.resilience.encodeUssd.useMutation();
  const [ussdResult, setUssdResult] = useState<{
    ussd_string: string;
    instructions: string;
    carrier_hint: string | null;
  } | null>(null);
  const handleUssdFallback = async () => {
    if (num < 1) {
      toast.error("Enter an amount first");
      return;
    }
    try {
      const result = await encodeUssd.mutateAsync({
        txType: "Transfer",
        amount: num,
      });
      setUssdResult(result as any);
      setShowUssdFallback(true);
    } catch {
      toast.error("USSD encoder unavailable");
    }
  };

  // Save QR to IndexedDB for offline persistence
  const saveQROffline = useCallback(async () => {
    if (num < 1) {
      toast.error("Enter an amount first");
      return;
    }
    const IDB_NAME = "54link-qr-store";
    const IDB_STORE = "offline_qr_codes";
    const record = {
      id: qrPayload,
      code: qrPayload,
      amount: num,
      agentCode,
      label: `₦${num.toLocaleString()} QR`,
      payload: qrPayload,
      createdAt: new Date().toISOString(),
      synced: false,
    };
    const req = indexedDB.open(IDB_NAME, 1);
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction(IDB_STORE, "readwrite");
      tx.objectStore(IDB_STORE).put(record);
      tx.oncomplete = () => {
        db.close();
        setOfflineQRList(prev => [
          record,
          ...prev.filter(r => r.id !== record.id),
        ]);
        toast.success("QR saved offline");
      };
    };
  }, [num, agentCode, qrPayload]);

  if (mode === "success")
    return (
      <>
        <SuccessScreen
          title="QR Payment Complete"
          amount={num}
          ref={txRef}
          customer="QR Customer"
          onDone={onBack}
          onPrint={() => setReceipt(true)}
        />
        {receipt && (
          <ReceiptModal
            tx={{
              type: "QR Payment",
              amount: num,
              customer: "QR Customer",
              ref: txRef,
              time: new Date().toLocaleTimeString("en-NG", {
                hour: "2-digit",
                minute: "2-digit",
              }),
            }}
            onClose={() => setReceipt(false)}
          />
        )}
      </>
    );

  return (
    <div className="flex flex-col h-full">
      <ScreenHeader title="QR Payment" onBack={onBack} />

      {/* Online/Offline indicator */}
      {!isOnline && (
        <div
          className="flex items-center gap-2 px-4 py-1.5 text-xs font-semibold"
          style={{ background: "oklch(0.78 0.18 80 / 0.15)", color: GOLD }}
        >
          <span>📵</span> Offline mode — QR generation works · Scanner requires
          camera · USSD available
        </div>
      )}

      {/* Tab bar */}
      <div
        className="flex gap-2 px-4 py-2 border-b"
        style={{ borderColor: BORDER }}
      >
        {(["scan", "generate", "batch"] as const).map(m => (
          <button
            key={m}
            onClick={() => {
              setMode(m);
              stopCamera();
            }}
            className="flex-1 py-2 rounded-xl text-sm font-semibold capitalize transition-all"
            style={{
              background: mode === m ? "oklch(0.65 0.18 200 / 0.3)" : CARD,
              color: mode === m ? "#06b6d4" : "oklch(0.55 0.015 230)",
              fontFamily: DISP,
            }}
          >
            {m === "scan"
              ? "📷 Scan QR"
              : m === "generate"
                ? "⬛ Generate QR"
                : "📦 Batch QR"}
          </button>
        ))}
      </div>

      {/* ── SCAN mode ── */}
      {mode === "scan" && (
        <div className="flex flex-col items-center flex-1 gap-4 p-4 overflow-y-auto">
          {/* Camera viewfinder */}
          <div
            className="relative w-full max-w-xs aspect-square rounded-2xl overflow-hidden"
            style={{
              background: "oklch(0.08 0.01 240)",
              border: `2px solid ${cameraActive ? "#22c55e" : "#06b6d4"}`,
            }}
          >
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              playsInline
              muted
            />
            <canvas ref={canvasRef} className="hidden" />
            {!cameraActive && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                <span className="text-6xl">📷</span>
                <span
                  className="text-xs text-gray-400"
                  style={{ fontFamily: DISP }}
                >
                  Camera not active
                </span>
              </div>
            )}
            {cameraActive && (
              <div className="absolute inset-0 pointer-events-none">
                {/* Scanning crosshair */}
                <div className="absolute inset-8 border-2 border-cyan-400 rounded-lg opacity-60" />
                <div className="absolute top-8 left-8 w-6 h-6 border-t-4 border-l-4 border-cyan-400 rounded-tl" />
                <div className="absolute top-8 right-8 w-6 h-6 border-t-4 border-r-4 border-cyan-400 rounded-tr" />
                <div className="absolute bottom-8 left-8 w-6 h-6 border-b-4 border-l-4 border-cyan-400 rounded-bl" />
                <div className="absolute bottom-8 right-8 w-6 h-6 border-b-4 border-r-4 border-cyan-400 rounded-br" />
              </div>
            )}
          </div>

          {scanError && (
            <div className="text-xs text-red-400 text-center">{scanError}</div>
          )}
          {scanResult && !scanResult.startsWith("54LINK:") && (
            <div
              className="w-full p-3 rounded-xl text-xs"
              style={{
                background: CARD,
                border: `1px solid #22c55e`,
                color: "#22c55e",
                fontFamily: MONO,
              }}
            >
              Scanned: {scanResult.slice(0, 60)}
              {scanResult.length > 60 ? "..." : ""}
            </div>
          )}

          <div className="flex gap-2 w-full">
            {!cameraActive ? (
              <button
                onClick={startCamera}
                className="flex-1 py-3 rounded-xl font-bold text-white"
                style={{ background: "#06b6d4", fontFamily: DISP }}
              >
                📷 Start Camera
              </button>
            ) : (
              <button
                onClick={stopCamera}
                className="flex-1 py-3 rounded-xl font-bold"
                style={{
                  background: "#374151",
                  color: "white",
                  fontFamily: DISP,
                }}
              >
                ⏹ Stop
              </button>
            )}
          </div>

          <div
            className="text-xs text-gray-500 text-center"
            style={{ fontFamily: DISP }}
          >
            Supports NIP QR · NIBSS QR · Masterpass · Visa QR · 54Link QR
          </div>

          {/* USSD Offline Fallback */}
          <div
            className="w-full p-3 rounded-xl"
            style={{
              background: "oklch(0.78 0.18 80 / 0.08)",
              border: `1px solid ${GOLD}44`,
            }}
          >
            <div
              className="text-xs font-bold mb-2"
              style={{ color: GOLD, fontFamily: DISP }}
            >
              📱 USSD Fallback {isOnline ? "(optional)" : "(offline mode)"}
            </div>
            <AmountDisplay value={amount} label="Amount" />
            <NumPad value={amount} onChange={setAmount} />
            {num > 0 && (
              <button
                onClick={handleUssdFallback}
                disabled={encodeUssd.isPending}
                className="w-full py-3 rounded-xl font-bold mt-2"
                style={{ background: GOLD, color: "#000", fontFamily: DISP }}
              >
                {encodeUssd.isPending
                  ? "Generating..."
                  : "Generate USSD Code →"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── GENERATE mode ── */}
      {mode === "generate" && (
        <div className="flex flex-col gap-4 p-4 overflow-y-auto">
          <AmountDisplay value={amount} label="Amount to Collect" />
          <NumPad value={amount} onChange={setAmount} />

          {num > 0 && qrPayload && (
            <div
              className="flex flex-col items-center gap-3 p-4 rounded-2xl"
              style={{
                background: CARD,
                border: `1px solid ${qrExpired ? RED : BORDER}`,
              }}
            >
              {/* Real QR code — works fully offline */}
              <div className="relative">
                <div
                  className="p-3 rounded-xl"
                  style={{ background: "white", opacity: qrExpired ? 0.25 : 1 }}
                >
                  <QRCodeCanvas
                    value={qrPayload}
                    size={180}
                    bgColor="#ffffff"
                    fgColor="#0a0e1a"
                    level="M"
                    includeMargin={false}
                  />
                </div>
                {qrExpired && (
                  <div
                    className="absolute inset-0 flex flex-col items-center justify-center rounded-xl"
                    style={{ background: "rgba(10,14,26,0.85)" }}
                  >
                    <div
                      className="text-2xl font-black"
                      style={{ color: RED, fontFamily: MONO }}
                    >
                      EXPIRED
                    </div>
                    <div
                      className="text-xs text-gray-400 mt-1"
                      style={{ fontFamily: DISP }}
                    >
                      QR code has expired
                    </div>
                    <button
                      onClick={regenerateQR}
                      className="mt-3 px-4 py-2 rounded-xl text-xs font-bold text-white"
                      style={{ background: RED, fontFamily: DISP }}
                    >
                      🔄 Regenerate QR
                    </button>
                  </div>
                )}
              </div>
              {/* TTL countdown */}
              {!qrExpired && qrSecondsLeft !== null && (
                <div
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                  style={{
                    background: qrSecondsLeft < 60 ? `${RED}22` : `${GREEN}11`,
                    border: `1px solid ${qrSecondsLeft < 60 ? RED : GREEN}44`,
                  }}
                >
                  <span
                    className="text-xs font-bold"
                    style={{
                      color: qrSecondsLeft < 60 ? RED : GREEN,
                      fontFamily: MONO,
                    }}
                  >
                    ⏱ {Math.floor(qrSecondsLeft / 60)}:
                    {String(qrSecondsLeft % 60).padStart(2, "0")}
                  </span>
                  <span
                    className="text-xs text-gray-500"
                    style={{ fontFamily: DISP }}
                  >
                    until expiry
                  </span>
                </div>
              )}
              <div
                className="text-xs text-gray-400 text-center"
                style={{ fontFamily: MONO }}
              >
                54Link QR · {fmt(num)}
              </div>
              <div
                className="text-xs text-gray-600 text-center break-all px-2"
                style={{ fontFamily: MONO }}
              >
                {qrPayload.slice(0, 50)}...
              </div>
              <div className="flex gap-2 w-full">
                <button
                  onClick={saveQROffline}
                  className="flex-1 py-2 rounded-xl text-xs font-bold"
                  style={{
                    background: "oklch(0.65 0.18 200 / 0.2)",
                    color: "#06b6d4",
                    fontFamily: DISP,
                  }}
                >
                  💾 Save Offline
                </button>
                {isOnline && (
                  <button
                    onClick={async () => {
                      const result = await submit({
                        type: "QR Payment",
                        amount: num,
                        customerName: "QR Customer",
                        channel: "QR",
                      });
                      if (result) {
                        setTxRef(result.ref);
                        setMode("success");
                      }
                    }}
                    className="flex-1 py-2 rounded-xl text-xs font-bold text-white"
                    style={{ background: "#06b6d4", fontFamily: DISP }}
                  >
                    ✓ Confirm Payment
                  </button>
                )}
              </div>
              {!isOnline && (
                <div
                  className="w-full text-xs text-center py-2 rounded-xl"
                  style={{
                    background: "oklch(0.78 0.18 80 / 0.1)",
                    color: GOLD,
                    fontFamily: DISP,
                  }}
                >
                  📵 Offline — QR saved locally, will sync when connected
                </div>
              )}
            </div>
          )}

          {/* Offline QR library */}
          {offlineQRList.length > 0 && (
            <div
              className="rounded-2xl overflow-hidden"
              style={{ border: `1px solid ${BORDER}` }}
            >
              <div
                className="px-4 py-2 text-xs font-bold"
                style={{ background: CARD, color: GOLD, fontFamily: DISP }}
              >
                💾 Saved Offline QR Codes ({offlineQRList.length})
              </div>
              {offlineQRList.slice(0, 5).map(qr => (
                <div
                  key={qr.id}
                  className="flex items-center gap-3 px-4 py-2 border-t"
                  style={{ borderColor: BORDER }}
                >
                  <div className="p-1 rounded" style={{ background: "white" }}>
                    <QRCodeCanvas
                      value={qr.payload}
                      size={40}
                      bgColor="#fff"
                      fgColor="#0a0e1a"
                      level="L"
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-xs font-semibold text-white truncate"
                      style={{ fontFamily: DISP }}
                    >
                      {qr.label}
                    </div>
                    <div
                      className="text-xs"
                      style={{
                        color: qr.synced ? "#22c55e" : GOLD,
                        fontFamily: MONO,
                      }}
                    >
                      {qr.synced ? "✓ Synced" : "⏳ Pending sync"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── BATCH mode ── */}
      {mode === "batch" && (
        <div className="flex flex-col gap-4 p-4 overflow-y-auto">
          {/* Header */}
          <div className="flex flex-col gap-1">
            <div
              className="text-sm font-bold text-white"
              style={{ fontFamily: DISP }}
            >
              📦 Batch QR Generation
            </div>
            <div
              className="text-xs"
              style={{ color: "oklch(0.55 0.015 230)", fontFamily: DISP }}
            >
              Pre-generate QR codes for common amounts. Saved to device — works
              offline all day.
            </div>
          </div>
          {/* Amount selector */}
          <div
            className="rounded-2xl p-4"
            style={{ background: CARD, border: `1px solid ${BORDER}` }}
          >
            <div
              className="text-xs font-bold mb-3"
              style={{ color: GOLD, fontFamily: DISP }}
            >
              Select Amounts
            </div>
            <div className="grid grid-cols-4 gap-2">
              {batchPresetAmounts.map(amt => {
                const selected = selectedBatchAmounts.has(amt);
                return (
                  <button
                    key={amt}
                    onClick={() => {
                      setSelectedBatchAmounts(prev => {
                        const next = new Set(prev);
                        if (next.has(amt)) next.delete(amt);
                        else next.add(amt);
                        return next;
                      });
                    }}
                    className="py-2 rounded-xl text-xs font-bold transition-all"
                    style={{
                      background: selected
                        ? "oklch(0.65 0.18 200 / 0.3)"
                        : "oklch(0.12 0.01 240)",
                      border: `1px solid ${selected ? "#06b6d4" : BORDER}`,
                      color: selected ? "#06b6d4" : "oklch(0.55 0.015 230)",
                      fontFamily: MONO,
                    }}
                  >
                    {amt >= 1000 ? `₦${amt / 1000}K` : `₦${amt}`}
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={() =>
                  setSelectedBatchAmounts(new Set(batchPresetAmounts))
                }
                className="text-xs px-3 py-1.5 rounded-lg font-bold"
                style={{
                  background: "oklch(0.65 0.18 160 / 0.2)",
                  color: "#10b981",
                  fontFamily: DISP,
                }}
              >
                Select All
              </button>
              <button
                onClick={() => setSelectedBatchAmounts(new Set())}
                className="text-xs px-3 py-1.5 rounded-lg font-bold"
                style={{
                  background: "oklch(0.60 0.22 25 / 0.2)",
                  color: "#ef4444",
                  fontFamily: DISP,
                }}
              >
                Clear
              </button>
              <button
                onClick={() => setShowAddPreset(v => !v)}
                className="text-xs px-3 py-1.5 rounded-lg font-bold ml-1"
                style={{
                  background: "oklch(0.60 0.22 260 / 0.2)",
                  color: "#60a5fa",
                  fontFamily: DISP,
                }}
              >
                + Custom
              </button>
              <button
                onClick={() => {
                  savePresets(DEFAULT_PRESET_AMOUNTS);
                  setSelectedBatchAmounts(new Set([500, 1000, 2000, 5000]));
                }}
                className="text-xs px-3 py-1.5 rounded-lg font-bold"
                style={{
                  background: "oklch(0.78 0.18 80 / 0.15)",
                  color: "#f59e0b",
                  fontFamily: DISP,
                }}
                title="Reset to default preset amounts"
              >
                ↺ Reset
              </button>
              <span
                className="text-xs ml-auto"
                style={{ color: "oklch(0.55 0.015 230)", fontFamily: MONO }}
              >
                {selectedBatchAmounts.size} selected
              </span>
            </div>
            {/* Custom preset management panel */}
            {showAddPreset && (
              <div
                className="mt-3 p-3 rounded-xl"
                style={{
                  background: "oklch(0.10 0.01 240)",
                  border: `1px solid ${BORDER}`,
                }}
              >
                <div
                  className="text-xs font-bold mb-2"
                  style={{ color: "#60a5fa", fontFamily: DISP }}
                >
                  Manage Custom Presets
                </div>
                <div className="flex gap-2 mb-3">
                  <input
                    type="number"
                    min={1}
                    max={1000000}
                    placeholder="Enter amount (e.g. 7500)"
                    value={newPresetInput}
                    onChange={e => setNewPresetInput(e.target.value)}
                    className="flex-1 px-3 py-1.5 rounded-lg text-xs bg-transparent text-white"
                    style={{
                      border: `1px solid ${BORDER}`,
                      fontFamily: MONO,
                      outline: "none",
                    }}
                    onKeyDown={e => {
                      if (e.key === "Enter") {
                        const v = parseInt(newPresetInput, 10);
                        if (
                          !isNaN(v) &&
                          v > 0 &&
                          v <= 1_000_000 &&
                          !batchPresetAmounts.includes(v)
                        ) {
                          savePresets([...batchPresetAmounts, v]);
                          setNewPresetInput("");
                          toast.success(
                            `₦${v.toLocaleString()} added to presets`
                          );
                        } else if (batchPresetAmounts.includes(v)) {
                          toast.error("Amount already in presets");
                        }
                      }
                    }}
                  />
                  <button
                    onClick={() => {
                      const v = parseInt(newPresetInput, 10);
                      if (
                        !isNaN(v) &&
                        v > 0 &&
                        v <= 1_000_000 &&
                        !batchPresetAmounts.includes(v)
                      ) {
                        savePresets([...batchPresetAmounts, v]);
                        setNewPresetInput("");
                        toast.success(
                          `₦${v.toLocaleString()} added to presets`
                        );
                      } else if (batchPresetAmounts.includes(v)) {
                        toast.error("Amount already in presets");
                      }
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold"
                    style={{
                      background: "#06b6d4",
                      color: "#fff",
                      fontFamily: DISP,
                    }}
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {batchPresetAmounts.map(amt => (
                    <div
                      key={amt}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs"
                      style={{
                        background: "oklch(0.14 0.02 240)",
                        border: `1px solid ${BORDER}`,
                        fontFamily: MONO,
                      }}
                    >
                      <span style={{ color: "#e2e8f0" }}>
                        {amt >= 1000 ? `₦${amt / 1000}K` : `₦${amt}`}
                      </span>
                      {!DEFAULT_PRESET_AMOUNTS.includes(amt) && (
                        <button
                          onClick={() => {
                            savePresets(
                              batchPresetAmounts.filter(a => a !== amt)
                            );
                            setSelectedBatchAmounts(prev => {
                              const n = new Set(prev);
                              n.delete(amt);
                              return n;
                            });
                            toast.success(`₦${amt.toLocaleString()} removed`);
                          }}
                          className="ml-0.5 text-red-400 hover:text-red-300 font-bold"
                          title="Remove this preset"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <div
                  className="text-xs mt-2"
                  style={{ color: "oklch(0.45 0.01 230)", fontFamily: DISP }}
                >
                  Default amounts cannot be removed. Custom amounts are saved to
                  your device.
                </div>
              </div>
            )}
          </div>
          {/* Generate button */}
          <button
            disabled={selectedBatchAmounts.size === 0 || batchGenerating}
            onClick={async () => {
              if (selectedBatchAmounts.size === 0) return;
              setBatchGenerating(true);
              const IDB_NAME = "54link-qr-store";
              const IDB_STORE = "offline_qr_codes";
              const newItems: typeof batchQRList = [];
              const expiresAt = Date.now() + QR_TTL_MS;
              for (const amt of Array.from(selectedBatchAmounts).sort(
                (a: any, b: any) => a - b
              )) {
                const ref = `QR-${agentCode}-${Date.now().toString(36).toUpperCase()}-${amt}`;
                const payload = `54LINK:${ref}:${amt}:${agentCode}:${Math.floor(expiresAt / 1000)}`;
                const item = {
                  id: ref,
                  amount: amt,
                  payload,
                  expiresAt,
                  label: `₦${amt.toLocaleString("en-NG")}`,
                  synced: false,
                };
                newItems.push(item);
                // Persist to IndexedDB
                try {
                  await new Promise<void>((resolve, reject) => {
                    const req = indexedDB.open(IDB_NAME, 1);
                    req.onupgradeneeded = e => {
                      (e.target as IDBOpenDBRequest).result.createObjectStore(
                        IDB_STORE,
                        { keyPath: "id" }
                      );
                    };
                    req.onsuccess = () => {
                      const tx = req.result.transaction(IDB_STORE, "readwrite");
                      tx.objectStore(IDB_STORE).put({
                        ...item,
                        createdAt: Date.now(),
                      });
                      tx.oncomplete = () => resolve();
                      tx.onerror = () => reject(tx.error);
                    };
                    req.onerror = () => reject(req.error);
                  });
                } catch {
                  /* ignore IDB errors */
                }
              }
              setBatchQRList(prev => {
                const existingIds = new Set(prev.map(p => p.id));
                return [
                  ...prev,
                  ...newItems.filter(n => !existingIds.has(n.id)),
                ];
              });
              setBatchGenerating(false);
              toast.success(
                `Generated ${newItems.length} QR codes — saved to device`
              );
            }}
            className="w-full py-3 rounded-xl font-bold text-white"
            style={{
              background:
                batchGenerating || selectedBatchAmounts.size === 0
                  ? "#374151"
                  : "#06b6d4",
              fontFamily: DISP,
            }}
          >
            {batchGenerating
              ? "Generating..."
              : `⚡ Generate ${selectedBatchAmounts.size} QR Code${selectedBatchAmounts.size !== 1 ? "s" : ""}`}
          </button>
          {/* Batch QR grid */}
          {batchQRList.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div
                  className="text-xs font-bold"
                  style={{ color: GOLD, fontFamily: DISP }}
                >
                  Generated QR Codes ({batchQRList.length})
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const now = Date.now();
                      const activeQRs = batchQRList.filter(
                        q => q.expiresAt > now
                      );
                      if (activeQRs.length === 0) {
                        toast.error("No active QR codes to print");
                        return;
                      }
                      const printWin = window.open(
                        "",
                        "_blank",
                        "width=794,height=1123"
                      );
                      if (!printWin) {
                        toast.error(
                          "Pop-up blocked — allow pop-ups and try again"
                        );
                        return;
                      }
                      const canvases =
                        document.querySelectorAll<HTMLCanvasElement>(
                          ".batch-qr-canvas"
                        );
                      const canvasMap: Record<string, string> = {};
                      canvases.forEach(c => {
                        const id = c.dataset.qrid;
                        if (id) canvasMap[id] = c.toDataURL("image/png");
                      });
                      const rows = activeQRs
                        .map(qr => {
                          const img = canvasMap[qr.id]
                            ? `<img src="${canvasMap[qr.id]}" width="120" height="120" />`
                            : "";
                          const mins = Math.floor(
                            Math.max(0, qr.expiresAt - now) / 60000
                          );
                          return `<div class="qr-cell"><div class="amount">&#8358;${qr.amount.toLocaleString("en-NG")}</div>${img}<div class="label">${qr.label}</div><div class="ttl">Valid ~${mins} min</div></div>`;
                        })
                        .join("");
                      const _agentName = TERMINAL.agentName;
                      const _agentCode = TERMINAL.agentCode;
                      const _serialNo = TERMINAL.serialNo;
                      const _printDate = new Date().toLocaleString("en-NG");
                      printWin.document.write(
                        `<!DOCTYPE html><html><head><title>54Link Batch QR — ${_agentCode}</title><style>@page{size:A4;margin:12mm}body{font-family:'Courier New',monospace;background:#fff;color:#000}h1{font-size:13px;margin:0 0 4px;font-weight:bold}.meta{font-size:9px;color:#555;margin-bottom:10px;line-height:1.6}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.qr-cell{border:1px solid #bbb;border-radius:6px;padding:8px;text-align:center;page-break-inside:avoid}.amount{font-size:13px;font-weight:bold;margin-bottom:4px;color:#000}.label{font-size:8px;color:#666;margin-top:3px;word-break:break-all}.ttl{font-size:8px;color:#999;margin-top:2px}.agent-footer{font-size:8px;color:#aaa;margin-top:3px;border-top:1px dashed #ddd;padding-top:3px}img{display:block;margin:0 auto}.watermark{position:fixed;bottom:8mm;right:10mm;font-size:8px;color:#ccc;text-align:right}@media print{.watermark{position:fixed}}</style></head><body><h1>54Link Agent Banking — QR Payment Sheet</h1><div class="meta">Agent: <strong>${_agentName}</strong> &nbsp;|&nbsp; Code: <strong>${_agentCode}</strong> &nbsp;|&nbsp; Terminal: <strong>${_serialNo}</strong><br/>Printed: ${_printDate} &nbsp;|&nbsp; ${activeQRs.length} code(s) &nbsp;|&nbsp; Codes expire 15 min after generation</div><div class="grid">${rows}</div><div class="watermark">54Link Agent Banking<br/>${_agentCode} | ${_serialNo}<br/>Printed ${_printDate}</div></body></html>`
                      );
                      printWin.document.close();
                      printWin.focus();
                      setTimeout(() => {
                        printWin.print();
                      }, 500);
                    }}
                    className="text-xs px-3 py-1 rounded-lg font-bold"
                    style={{
                      background: "oklch(0.60 0.22 260 / 0.2)",
                      color: "#3b82f6",
                      fontFamily: DISP,
                    }}
                  >
                    🖨 Print All
                  </button>
                  <button
                    onClick={() => {
                      setBatchQRList([]);
                      toast.success("Batch cleared");
                    }}
                    className="text-xs px-3 py-1 rounded-lg font-bold"
                    style={{
                      background: "oklch(0.60 0.22 25 / 0.2)",
                      color: "#ef4444",
                      fontFamily: DISP,
                    }}
                  >
                    Clear All
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {batchQRList.map(qr => {
                  const now = Date.now();
                  const expired = qr.expiresAt < now;
                  const secsLeft = Math.max(
                    0,
                    Math.floor((qr.expiresAt - now) / 1000)
                  );
                  const mins = Math.floor(secsLeft / 60);
                  const secs = secsLeft % 60;
                  return (
                    <div
                      key={qr.id}
                      className="flex flex-col items-center gap-2 p-3 rounded-2xl"
                      style={{
                        background: CARD,
                        border: `1px solid ${expired ? "#ef4444" : BORDER}`,
                      }}
                    >
                      <div
                        className="text-sm font-black"
                        style={{ color: GOLD, fontFamily: MONO }}
                      >
                        ₦{qr.amount.toLocaleString("en-NG")}
                      </div>
                      <div className="relative">
                        <QRCodeCanvas
                          value={qr.payload}
                          size={120}
                          bgColor="#111827"
                          fgColor={expired ? "#6b7280" : "#ffffff"}
                          level="M"
                          className="batch-qr-canvas"
                          data-qrid={qr.id}
                        />
                        {expired && (
                          <div
                            className="absolute inset-0 flex items-center justify-center rounded"
                            style={{ background: "rgba(0,0,0,0.75)" }}
                          >
                            <span
                              className="text-xs font-bold text-red-400"
                              style={{ fontFamily: DISP }}
                            >
                              EXPIRED
                            </span>
                          </div>
                        )}
                      </div>
                      {!expired ? (
                        <div
                          className="text-xs font-bold"
                          style={{
                            color: secsLeft < 120 ? "#ef4444" : "#10b981",
                            fontFamily: MONO,
                          }}
                        >
                          ⏱ {mins}:{secs.toString().padStart(2, "0")}
                        </div>
                      ) : (
                        <div
                          className="text-xs font-bold text-red-400"
                          style={{ fontFamily: DISP }}
                        >
                          Expired
                        </div>
                      )}
                      <div
                        className="text-xs"
                        style={{
                          color: qr.synced ? "#10b981" : GOLD,
                          fontFamily: MONO,
                        }}
                      >
                        {qr.synced ? "✓ Synced" : "⏳ Offline"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {batchQRList.length === 0 && (
            <div
              className="text-center py-8"
              style={{ color: "oklch(0.40 0.01 240)", fontFamily: DISP }}
            >
              <div className="text-3xl mb-2">📦</div>
              <div className="text-sm">No batch QR codes yet</div>
              <div className="text-xs mt-1">
                Select amounts above and tap Generate
              </div>
            </div>
          )}
        </div>
      )}

      {/* USSD Result Modal */}
      {showUssdFallback && ussdResult && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.85)" }}
        >
          <div
            className="w-full max-w-sm rounded-2xl p-6"
            style={{ background: CARD, border: `1px solid ${GOLD}` }}
          >
            <div className="text-center mb-4">
              <div className="text-2xl mb-2">📱</div>
              <div
                className="text-base font-bold text-white"
                style={{ fontFamily: DISP }}
              >
                USSD Fallback Code
              </div>
              {ussdResult.carrier_hint && (
                <div className="text-xs text-gray-400">
                  {ussdResult.carrier_hint}
                </div>
              )}
            </div>
            <div
              className="text-center p-4 rounded-xl mb-4"
              style={{
                background: "oklch(0.07 0.01 240)",
                border: `2px solid ${GOLD}`,
              }}
            >
              <div
                className="text-2xl font-bold tracking-widest"
                style={{ color: GOLD, fontFamily: MONO }}
              >
                {ussdResult.ussd_string}
              </div>
            </div>
            <div
              className="text-xs text-gray-400 text-center mb-4"
              style={{ fontFamily: DISP }}
            >
              {ussdResult.instructions}
            </div>
            <button
              onClick={() => setShowUssdFallback(false)}
              className="w-full py-3 rounded-xl font-bold text-white"
              style={{ background: "#374151", fontFamily: DISP }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// 6. NFC Payment ──────────────────────────────────────────────────────────────
