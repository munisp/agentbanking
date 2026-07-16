/**
 * Push Notifications via Firebase Cloud Messaging (FCM)
 * Handles PWA push subscription, token management, and notification display.
 * Integrates with server-side push router for delivery.
 */

const VAPID_KEY = "YOUR_VAPID_PUBLIC_KEY"; // Set in env

interface PushSubscription {
  token: string;
  platform: "web" | "ios" | "android";
  deviceId: string;
  subscribedTopics: string[];
}

let registration: ServiceWorkerRegistration | null = null;

export async function initPushNotifications(): Promise<string | null> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return null;
  }

  try {
    registration = await navigator.serviceWorker.ready;

    const permission = await Notification.requestPermission();
    if (permission !== "granted") return null;

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(
        VAPID_KEY
      ) as unknown as ArrayBuffer,
    });

    const token = btoa(JSON.stringify(subscription.toJSON()));

    // Register token with server
    await fetch("/api/push/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        platform: "web",
        deviceId: getDeviceId(),
        topics: ["transactions", "float_alerts", "promotions"],
      }),
    }).catch(() => {});

    return token;
  } catch {
    return null;
  }
}

export async function subscribeTopic(topic: string): Promise<void> {
  await fetch("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, deviceId: getDeviceId() }),
  }).catch(() => {});
}

export async function unsubscribeTopic(topic: string): Promise<void> {
  await fetch("/api/push/unsubscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, deviceId: getDeviceId() }),
  }).catch(() => {});
}

export function showLocalNotification(
  title: string,
  body: string,
  data?: Record<string, string>
): void {
  if (!registration || Notification.permission !== "granted") return;
  registration.showNotification(title, {
    body,
    icon: "/icons/icon-192x192.png",
    badge: "/icons/badge-72x72.png",
    data,
    tag: data?.tag || "default",
    renotify: true,
  } as NotificationOptions);
}

// ── Float alert notifications ───────────────────────────────────────────────

export function notifyFloatWarning(balance: number, threshold: number): void {
  showLocalNotification(
    "⚠️ Low Float Balance",
    `Your float is at ${threshold}% (₦${(balance / 100).toLocaleString()}). Top up soon.`,
    { tag: "float_warning", action: "/float-topup" }
  );
}

export function notifyFloatCritical(balance: number): void {
  showLocalNotification(
    "🚨 Critical Float Balance",
    `Float critically low at ₦${(balance / 100).toLocaleString()}. Top up immediately to avoid service disruption.`,
    { tag: "float_critical", action: "/float-topup" }
  );
}

export function notifyTransactionSuccess(
  type: string,
  amount: number,
  ref: string
): void {
  showLocalNotification(
    `${type} Successful`,
    `₦${(amount / 100).toLocaleString()} — Ref: ${ref}`,
    { tag: `tx_${ref}`, action: `/transactions/${ref}` }
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function getDeviceId(): string {
  let id = localStorage.getItem("54link_device_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("54link_device_id", id);
  }
  return id;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}
