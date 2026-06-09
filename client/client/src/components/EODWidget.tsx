/**
 * EODWidget — End-of-day floating banner shown before closing time (P3).
 */
import { useState, useEffect } from "react";
import { haptic } from "@/lib/haptics";

interface EODWidgetProps {
  txCount: number;
  floatBalance: number;
  closingHour?: number;
  onReconcile: () => void;
  onPrintSummary: () => void;
}

export function EODWidget({
  txCount,
  floatBalance,
  closingHour = 18,
  onReconcile,
  onPrintSummary,
}: EODWidgetProps) {
  const [dismissed, setDismissed] = useState(false);
  const [show, setShow] = useState(false);

  useEffect(() => {
    const check = () => {
      const now = new Date();
      const minutesBefore =
        closingHour * 60 - (now.getHours() * 60 + now.getMinutes());
      setShow(minutesBefore > 0 && minutesBefore <= 30);
    };
    check();
    const iv = setInterval(check, 60_000);
    return () => clearInterval(iv);
  }, [closingHour]);

  if (!show || dismissed) return null;

  const fmt = (n: number) =>
    "₦" + n.toLocaleString("en-NG", { minimumFractionDigits: 0 });

  return (
    <div
      className="mx-3 mb-2 rounded-xl p-3 flex flex-col gap-2"
      style={{
        background: "oklch(0.15 0.04 80 / 0.95)",
        border: "1px solid oklch(0.50 0.15 80)",
        backdropFilter: "blur(8px)",
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">🕐</span>
          <div>
            <div
              className="text-xs font-bold"
              style={{
                color: "oklch(0.90 0.10 80)",
                fontFamily: "'Space Grotesk', sans-serif",
              }}
            >
              EOD Approaching
            </div>
            <div
              className="text-xs"
              style={{
                color: "oklch(0.70 0.06 80)",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {txCount} transactions today · {fmt(floatBalance)} float
            </div>
          </div>
        </div>
        <button
          onClick={() => {
            setDismissed(true);
            haptic("micro");
          }}
          className="text-sm px-2"
          style={{ color: "oklch(0.60 0.04 80)" }}
          aria-label="Dismiss EOD reminder"
        >
          ×
        </button>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => {
            haptic("tap");
            onReconcile();
          }}
          className="flex-1 py-2 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{
            background: "oklch(0.78 0.18 80 / 0.25)",
            color: "oklch(0.90 0.10 80)",
            border: "1px solid oklch(0.60 0.15 80)",
          }}
        >
          Start Reconciliation
        </button>
        <button
          onClick={() => {
            haptic("tap");
            onPrintSummary();
          }}
          className="flex-1 py-2 rounded-lg text-xs font-semibold transition-all active:scale-95"
          style={{
            background: "oklch(0.14 0.012 240)",
            color: "oklch(0.70 0.04 240)",
            border: "1px solid oklch(0.25 0.015 240)",
          }}
        >
          Print Summary
        </button>
      </div>
    </div>
  );
}
