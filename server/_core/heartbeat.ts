/**
 * heartbeat.ts — Self-hosted cron/heartbeat management.
 * No external platform dependency.
 *
 * Cron jobs are managed via the platform-heartbeat CLI or directly in
 * docker-compose / Kubernetes CronJob manifests.
 *
 * This module provides a no-op shim so existing callers compile without error.
 * Replace with your preferred scheduler (node-cron, pg_cron, Temporal, etc.)
 * for production use.
 */

export type HeartbeatConfig = {
  name: string;
  cronExpression: string;
  path: string;
  description?: string;
};

export type HeartbeatEntry = HeartbeatConfig & {
  uid: string;
  createdAt: string;
  status: "active" | "paused";
};

/**
 * Register a scheduled cron job.
 * In production, implement this using your scheduler of choice.
 * Returns a task UID for future management.
 */
export async function createHeartbeat(
  config: HeartbeatConfig
): Promise<{ uid: string }> {
  console.info(
    `[Heartbeat] Cron registered (no-op): ${config.name} — ${config.cronExpression} → ${config.path}`
  );
  return { uid: `local-${Date.now()}` };
}

export async function listHeartbeats(): Promise<HeartbeatEntry[]> {
  return [];
}

export async function pauseHeartbeat(_uid: string): Promise<void> {
  // no-op
}

export async function deleteHeartbeat(_uid: string): Promise<void> {
  // no-op
}
