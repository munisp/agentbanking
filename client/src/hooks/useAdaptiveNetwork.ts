// bandwidth: estimated available bandwidth in kbps
// adaptive: dynamically adjust behavior based on network conditions
// carrier: detected mobile carrier name (e.g. Safaricom, MTN, Airtel)
/**
 * useAdaptiveNetwork — Adaptive Network Manager
 *
 * Monitors network quality in real-time, detects tier changes,
 * and provides feature flags for progressive degradation.
 * Uses Navigator.connection API + latency probing.
 */

import { useState, useEffect, useCallback, useRef } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

export type NetworkTier =
  | "2g_gprs"
  | "2g_edge"
  | "3g"
  | "4g_lte"
  | "5g_wifi"
  | "offline";
export type ConnectionState = "online" | "degraded" | "offline";

export interface NetworkStatus {
  tier: NetworkTier;
  state: ConnectionState;
  effectiveType: string;
  downlinkMbps: number;
  rttMs: number;
  saveData: boolean;
  isOnline: boolean;
  lastProbeMs: number;
  probeLatencyMs: number;
  packetLossPct: number;
  signalStrength: number; // 0-4 bars
  jitterMs: number;
  stableFor: number; // ms since last tier change
}

export interface AdaptiveFeatures {
  useWebSocket: boolean;
  usePolling: boolean;
  pollingIntervalMs: number;
  loadImages: boolean;
  loadCharts: boolean;
  enableAnimations: boolean;
  maxListPageSize: number;
  textOnlyMode: boolean;
  enableOfflineQueue: boolean;
  compressionHint: string;
  syncIntervalMs: number;
  requestTimeoutMs: number;
  maxRetries: number;
  useSmssFallback: boolean;
  useUssdFallback: boolean;
}

// ── Feature Matrix ───────────────────────────────────────────────────────────

const FEATURE_MATRIX: Record<NetworkTier, AdaptiveFeatures> = {
  "5g_wifi": {
    useWebSocket: true,
    usePolling: false,
    pollingIntervalMs: 0,
    loadImages: true,
    loadCharts: true,
    enableAnimations: true,
    maxListPageSize: 100,
    textOnlyMode: false,
    enableOfflineQueue: true,
    compressionHint: "none",
    syncIntervalMs: 5000,
    requestTimeoutMs: 10000,
    maxRetries: 3,
    useSmssFallback: false,
    useUssdFallback: false,
  },
  "4g_lte": {
    useWebSocket: true,
    usePolling: false,
    pollingIntervalMs: 0,
    loadImages: true,
    loadCharts: true,
    enableAnimations: true,
    maxListPageSize: 50,
    textOnlyMode: false,
    enableOfflineQueue: true,
    compressionHint: "gzip",
    syncIntervalMs: 10000,
    requestTimeoutMs: 15000,
    maxRetries: 3,
    useSmssFallback: false,
    useUssdFallback: false,
  },
  "3g": {
    useWebSocket: false,
    usePolling: true,
    pollingIntervalMs: 30000,
    loadImages: false,
    loadCharts: false,
    enableAnimations: false,
    maxListPageSize: 25,
    textOnlyMode: false,
    enableOfflineQueue: true,
    compressionHint: "gzip",
    syncIntervalMs: 30000,
    requestTimeoutMs: 30000,
    maxRetries: 5,
    useSmssFallback: false,
    useUssdFallback: false,
  },
  "2g_edge": {
    useWebSocket: false,
    usePolling: true,
    pollingIntervalMs: 60000,
    loadImages: false,
    loadCharts: false,
    enableAnimations: false,
    maxListPageSize: 10,
    textOnlyMode: true,
    enableOfflineQueue: true,
    compressionHint: "deflate",
    syncIntervalMs: 60000,
    requestTimeoutMs: 60000,
    maxRetries: 10,
    useSmssFallback: true,
    useUssdFallback: false,
  },
  "2g_gprs": {
    useWebSocket: false,
    usePolling: true,
    pollingIntervalMs: 120000,
    loadImages: false,
    loadCharts: false,
    enableAnimations: false,
    maxListPageSize: 5,
    textOnlyMode: true,
    enableOfflineQueue: true,
    compressionHint: "deflate",
    syncIntervalMs: 120000,
    requestTimeoutMs: 120000,
    maxRetries: 15,
    useSmssFallback: true,
    useUssdFallback: true,
  },
  offline: {
    useWebSocket: false,
    usePolling: false,
    pollingIntervalMs: 0,
    loadImages: false,
    loadCharts: false,
    enableAnimations: false,
    maxListPageSize: 5,
    textOnlyMode: true,
    enableOfflineQueue: true,
    compressionHint: "none",
    syncIntervalMs: 0,
    requestTimeoutMs: 0,
    maxRetries: 0,
    useSmssFallback: true,
    useUssdFallback: true,
  },
};

// ── Tier Detection ───────────────────────────────────────────────────────────

function detectTier(
  effectiveType: string,
  downlinkMbps: number,
  rttMs: number,
  packetLoss: number,
  isOnline: boolean
): NetworkTier {
  if (!isOnline) return "offline";
  if (packetLoss > 30) return "offline";

  // Use RTT + downlink for more accurate detection
  if (rttMs > 1000 || downlinkMbps < 0.05) return "2g_gprs";
  if (rttMs > 500 || downlinkMbps < 0.2) return "2g_edge";
  if (rttMs > 100 || downlinkMbps < 2) return "3g";
  if (rttMs > 50 || downlinkMbps < 50) return "4g_lte";
  return "5g_wifi";
}

function signalBars(tier: NetworkTier): number {
  const bars: Record<NetworkTier, number> = {
    "5g_wifi": 4,
    "4g_lte": 3,
    "3g": 2,
    "2g_edge": 1,
    "2g_gprs": 1,
    offline: 0,
  };
  return bars[tier];
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useAdaptiveNetwork(probeIntervalMs = 15000) {
  const [status, setStatus] = useState<NetworkStatus>({
    tier: "4g_lte",
    state: "online",
    effectiveType: "4g",
    downlinkMbps: 10,
    rttMs: 50,
    saveData: false,
    isOnline: navigator.onLine,
    lastProbeMs: 0,
    probeLatencyMs: 0,
    packetLossPct: 0,
    signalStrength: 3,
    jitterMs: 0,
    stableFor: 0,
  });

  const [features, setFeatures] = useState<AdaptiveFeatures>(
    FEATURE_MATRIX["4g_lte"]
  );
  const lastTierChange = useRef(Date.now());
  const probeHistory = useRef<number[]>([]);

  // Probe server latency
  const probeLatency = useCallback(async (): Promise<{
    latencyMs: number;
    success: boolean;
  }> => {
    try {
      const start = performance.now();
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);

      await fetch("/api/health", {
        method: "HEAD",
        signal: controller.signal,
        cache: "no-store",
      });

      clearTimeout(timeout);
      const latencyMs = Math.round(performance.now() - start);
      return { latencyMs, success: true };
    } catch {
      return { latencyMs: 99999, success: false };
    }
  }, []);

  // Update network status
  const updateStatus = useCallback(async () => {
    const conn = (navigator as any).connection;
    const isOnline = navigator.onLine;

    let effectiveType = "4g";
    let downlinkMbps = 10;
    let rttMs = 50;
    let saveData = false;

    if (conn) {
      effectiveType = conn.effectiveType || "4g";
      downlinkMbps = conn.downlink || 10;
      rttMs = conn.rtt || 50;
      saveData = conn.saveData || false;
    }

    // Probe actual latency
    const probe = await probeLatency();
    const probeLatencyMs = probe.success ? probe.latencyMs : 99999;

    // Track probe history for jitter calculation
    probeHistory.current.push(probeLatencyMs);
    if (probeHistory.current.length > 10) probeHistory.current.shift();

    // Calculate jitter (standard deviation of recent probes)
    const avg =
      probeHistory.current.reduce((a, b) => a + b, 0) /
      probeHistory.current.length;
    const jitterMs = Math.round(
      Math.sqrt(
        probeHistory.current.reduce((sum, v) => sum + (v - avg) ** 2, 0) /
          probeHistory.current.length
      )
    );

    // Estimate packet loss from failed probes
    const recentProbes = probeHistory.current.slice(-5);
    const failedProbes = recentProbes.filter(p => p >= 99999).length;
    const packetLossPct = (failedProbes / recentProbes.length) * 100;

    // Use actual probe latency for tier detection (more accurate than API)
    const actualRtt = probe.success ? probeLatencyMs : rttMs;
    const tier = detectTier(
      effectiveType,
      downlinkMbps,
      actualRtt,
      packetLossPct,
      isOnline
    );

    const state: ConnectionState =
      !isOnline || tier === "offline"
        ? "offline"
        : packetLossPct > 10 || probeLatencyMs > 2000
          ? "degraded"
          : "online";

    const newStatus: NetworkStatus = {
      tier,
      state,
      effectiveType,
      downlinkMbps,
      rttMs: actualRtt,
      saveData,
      isOnline,
      lastProbeMs: Date.now(),
      probeLatencyMs,
      packetLossPct,
      signalStrength: signalBars(tier),
      jitterMs,
      stableFor: Date.now() - lastTierChange.current,
    };

    setStatus(prev => {
      if (prev.tier !== tier) {
        lastTierChange.current = Date.now();
        console.log(`[Network] Tier changed: ${prev.tier} → ${tier}`);
      }
      return newStatus;
    });

    setFeatures(FEATURE_MATRIX[tier]);
  }, [probeLatency]);

  // Listen for online/offline events
  useEffect(() => {
    const handleOnline = () => updateStatus();
    const handleOffline = () => {
      setStatus(prev => ({
        ...prev,
        isOnline: false,
        tier: "offline",
        state: "offline",
        signalStrength: 0,
      }));
      setFeatures(FEATURE_MATRIX["offline"]);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Listen for connection change events
    const conn = (navigator as any).connection;
    if (conn) {
      conn.addEventListener("change", updateStatus);
    }

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      if (conn) conn.removeEventListener("change", updateStatus);
    };
  }, [updateStatus]);

  // Periodic probing
  useEffect(() => {
    updateStatus(); // Initial probe
    const interval = setInterval(updateStatus, probeIntervalMs);
    return () => clearInterval(interval);
  }, [updateStatus, probeIntervalMs]);

  return {
    status,
    features,
    probeLatency,
    forceUpdate: updateStatus,
  };
}
