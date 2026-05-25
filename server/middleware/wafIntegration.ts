/**
 * OpenAppSec WAF Integration — 54Link Platform
 *
 * Provides application-level WAF integration:
 * - Health monitoring of the OpenAppSec agent
 * - Dynamic rule updates via management API
 * - Request/response logging for WAF learning mode
 * - Incident reporting and alerting
 * - IP reputation checking
 */

const WAF_MGMT_URL = process.env.OPENAPPSEC_MGMT_URL ?? "http://localhost:8085";
const WAF_AGENT_URL =
  process.env.OPENAPPSEC_AGENT_URL ?? "http://localhost:8080";

interface WAFHealthStatus {
  agent: "healthy" | "degraded" | "down";
  mode: "prevent" | "detect" | "prevent-learn" | "inactive";
  lastPolicyUpdate: string | null;
  rulesLoaded: number;
  requestsProcessed: number;
  threatsBlocked: number;
}

interface WAFIncident {
  id: string;
  timestamp: string;
  sourceIp: string;
  method: string;
  url: string;
  threatType: string;
  severity: "critical" | "high" | "medium" | "low";
  action: "blocked" | "detected" | "learned";
  details: string;
}

export class WAFIntegration {
  private mgmtUrl: string;
  private agentUrl: string;
  private incidentBuffer: WAFIncident[] = [];
  private stats = {
    totalRequests: 0,
    blockedRequests: 0,
    detectedThreats: 0,
    lastCheck: 0,
  };

  constructor(mgmtUrl?: string, agentUrl?: string) {
    this.mgmtUrl = mgmtUrl ?? WAF_MGMT_URL;
    this.agentUrl = agentUrl ?? WAF_AGENT_URL;
  }

  async getHealth(): Promise<WAFHealthStatus> {
    try {
      const res = await fetch(`${this.mgmtUrl}/api/v1/health`, {
        signal: AbortSignal.timeout(3000),
      });
      if (res.ok) {
        const data = (await res.json()) as any;
        return {
          agent: "healthy",
          mode: data.mode ?? "prevent-learn",
          lastPolicyUpdate: data.lastPolicyUpdate ?? null,
          rulesLoaded: data.rulesLoaded ?? 0,
          requestsProcessed: this.stats.totalRequests,
          threatsBlocked: this.stats.blockedRequests,
        };
      }
      return this.degradedStatus();
    } catch {
      return this.degradedStatus();
    }
  }

  private degradedStatus(): WAFHealthStatus {
    return {
      agent: "down",
      mode: "inactive",
      lastPolicyUpdate: null,
      rulesLoaded: 0,
      requestsProcessed: this.stats.totalRequests,
      threatsBlocked: this.stats.blockedRequests,
    };
  }

  async checkIpReputation(
    ip: string
  ): Promise<{ allowed: boolean; score: number; reason?: string }> {
    try {
      const res = await fetch(`${this.mgmtUrl}/api/v1/reputation/${ip}`, {
        signal: AbortSignal.timeout(2000),
      });
      if (res.ok) {
        const data = (await res.json()) as any;
        return {
          allowed: data.score < 80,
          score: data.score ?? 0,
          reason: data.reason,
        };
      }
    } catch {
      // Fall through — allow by default if WAF unreachable
    }
    return { allowed: true, score: 0 };
  }

  async reportIncident(incident: Omit<WAFIncident, "id">): Promise<void> {
    const fullIncident: WAFIncident = {
      ...incident,
      id: `waf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    };
    this.incidentBuffer.push(fullIncident);
    this.stats.totalRequests++;
    if (incident.action === "blocked") this.stats.blockedRequests++;
    if (incident.action === "detected") this.stats.detectedThreats++;

    if (this.incidentBuffer.length >= 50) {
      await this.flushIncidents();
    }
  }

  async flushIncidents(): Promise<void> {
    if (this.incidentBuffer.length === 0) return;
    const batch = [...this.incidentBuffer];
    this.incidentBuffer = [];
    try {
      await fetch(`${this.mgmtUrl}/api/v1/incidents/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incidents: batch }),
        signal: AbortSignal.timeout(5000),
      });
    } catch {
      // Re-buffer on failure
      this.incidentBuffer = [...batch, ...this.incidentBuffer].slice(-500);
    }
  }

  async updatePolicy(policyPatch: Record<string, unknown>): Promise<boolean> {
    try {
      const res = await fetch(`${this.mgmtUrl}/api/v1/policy`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(policyPatch),
        signal: AbortSignal.timeout(5000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  async addIpToBlocklist(ip: string, reason: string): Promise<boolean> {
    try {
      const res = await fetch(`${this.mgmtUrl}/api/v1/blocklist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip, reason, expiresIn: "24h" }),
        signal: AbortSignal.timeout(3000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  async getRecentIncidents(limit: number = 100): Promise<WAFIncident[]> {
    try {
      const res = await fetch(
        `${this.mgmtUrl}/api/v1/incidents?limit=${limit}`,
        { signal: AbortSignal.timeout(5000) }
      );
      if (res.ok) {
        const data = (await res.json()) as any;
        return data.incidents ?? [];
      }
    } catch {
      // Return buffered incidents as fallback
    }
    return this.incidentBuffer.slice(-limit);
  }

  getStats() {
    return { ...this.stats, bufferedIncidents: this.incidentBuffer.length };
  }
}

export const wafIntegration = new WAFIntegration();
