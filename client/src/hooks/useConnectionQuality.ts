/**
 * useConnectionQuality
 *
 * Probes the server every 5 seconds with a lightweight HEAD request and
 * classifies the connection quality based on round-trip latency:
 *
 *   Excellent  < 300ms   (strong 4G / WiFi)
 *   Good       300–800ms (normal 3G/4G)
 *   Poor       800–2000ms (edge / congested cell)
 *   Offline    > 2000ms or error
 *
 * Also reads navigator.connection (Network Information API) where available
 * to surface the effective connection type (4g, 3g, 2g, slow-2g).
 */
import { useState, useEffect, useRef, useCallback } from "react";

export type SignalQuality = "Excellent" | "Good" | "Poor" | "Offline";

export interface ConnectionState {
  quality: SignalQuality;
  latencyMs: number | null;
  effectiveType: string | null; // "4g" | "3g" | "2g" | "slow-2g" | null
  downlink: number | null; // Mbps, if available
  isOnline: boolean;
}

const PROBE_URL =
  "/api/trpc/agent.me?batch=1&input=%7B%220%22%3A%7B%22json%22%3Anull%7D%7D";
const PROBE_INTERVAL_MS = 5_000;

function classify(latencyMs: number): SignalQuality {
  if (latencyMs < 300) return "Excellent";
  if (latencyMs < 800) return "Good";
  if (latencyMs < 2000) return "Poor";
  return "Offline";
}

export function useConnectionQuality(): ConnectionState {
  const [state, setState] = useState<ConnectionState>({
    quality: "Good",
    latencyMs: null,
    effectiveType: null,
    downlink: null,
    isOnline: navigator.onLine,
  });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const probe = useCallback(async () => {
    if (!navigator.onLine) {
      setState(s => ({
        ...s,
        quality: "Offline",
        latencyMs: null,
        isOnline: false,
      }));
      return;
    }

    const start = performance.now();
    try {
      await fetch(PROBE_URL, {
        method: "GET",
        cache: "no-store",
        signal: AbortSignal.timeout(2500),
      });
      const latencyMs = Math.round(performance.now() - start);
      const quality = classify(latencyMs);

      // Read Network Information API if available
      const conn =
        (navigator as any).connection ??
        (navigator as any).mozConnection ??
        (navigator as any).webkitConnection;
      const effectiveType: string | null = conn?.effectiveType ?? null;
      const downlink: number | null = conn?.downlink ?? null;

      setState({ quality, latencyMs, effectiveType, downlink, isOnline: true });
    } catch {
      setState(s => ({
        ...s,
        quality: "Offline",
        latencyMs: null,
        isOnline: false,
      }));
    }
  }, []);

  useEffect(() => {
    probe();
    timerRef.current = setInterval(probe, PROBE_INTERVAL_MS);
    window.addEventListener("online", probe);
    window.addEventListener("offline", probe);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      window.removeEventListener("online", probe);
      window.removeEventListener("offline", probe);
    };
  }, [probe]);

  return state;
}
