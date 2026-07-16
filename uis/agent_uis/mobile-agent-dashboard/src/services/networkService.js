const PING_URL = "https://54agent.upi.dev";
const PING_TIMEOUT_MS = 5000;
const POLL_INTERVAL_MS = 30_000;

let isOnlineState = true;
let pollTimer = null;
const listeners = new Set();

async function pingConnectivity() {
  try {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), PING_TIMEOUT_MS);
    await fetch(PING_URL, {
      method: "HEAD",
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(tid);
    return true;
  } catch {
    return false;
  }
}

async function checkAndNotify() {
  const wasOnline = isOnlineState;
  const nowOnline = await pingConnectivity();
  isOnlineState = nowOnline;

  if (wasOnline !== nowOnline) {
    for (const listener of listeners) {
      try {
        listener({ isOnline: nowOnline, wasOnline });
      } catch {}
    }
  }
}

export function addNetworkListener(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function startNetworkMonitor() {
  if (pollTimer) return;
  checkAndNotify();
  pollTimer = setInterval(checkAndNotify, POLL_INTERVAL_MS);
}

export function stopNetworkMonitor() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

export async function isDeviceOnline() {
  isOnlineState = await pingConnectivity();
  return isOnlineState;
}

export function getCachedNetworkState() {
  return { isOnline: isOnlineState };
}
