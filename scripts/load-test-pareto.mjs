#!/usr/bin/env node
/**
 * Pareto-Aware Load Testing Script
 * P2-2: 80% of load on top 20% of agents (zipf distribution)
 *
 * From the 1B Payments article:
 * "Real payment traffic follows a Pareto distribution — 20% of merchants
 *  generate 80% of transactions. Load tests with uniform distribution
 *  miss hot-path contention that causes production incidents."
 *
 * Usage:
 *   node scripts/load-test-pareto.mjs [options]
 *
 * Options:
 *   --target-rps    Target requests per second (default: 100)
 *   --duration      Test duration in seconds (default: 30)
 *   --agents        Number of simulated agents (default: 100)
 *   --base-url      API base URL (default: http://localhost:3000)
 *   --zipf-s        Zipf skewness parameter (default: 1.07, higher = more skewed)
 */

import http from "http";

// ── Configuration ────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
function getArg(name, defaultVal) {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 && args[idx + 1] ? args[idx + 1] : defaultVal;
}

const TARGET_RPS = parseInt(getArg("target-rps", "100"), 10);
const DURATION_S = parseInt(getArg("duration", "30"), 10);
const NUM_AGENTS = parseInt(getArg("agents", "100"), 10);
const BASE_URL = getArg("base-url", "http://localhost:3000");
const ZIPF_S = parseFloat(getArg("zipf-s", "1.07"));

// ── Zipf Distribution ────────────────────────────────────────────────────────

/**
 * Generate a Zipf-distributed random integer in [0, n).
 * P(k) ∝ 1/k^s where s is the skewness parameter.
 * s=1.07 gives approximately 80/20 Pareto distribution.
 */
class ZipfDistribution {
  constructor(n, s = 1.07) {
    this.n = n;
    this.s = s;
    // Pre-compute CDF for fast sampling
    this.cdf = new Float64Array(n);
    let sum = 0;
    for (let k = 1; k <= n; k++) {
      sum += 1.0 / Math.pow(k, s);
    }
    let cumulative = 0;
    for (let k = 0; k < n; k++) {
      cumulative += (1.0 / Math.pow(k + 1, s)) / sum;
      this.cdf[k] = cumulative;
    }
  }

  /** Sample a random index following zipf distribution */
  sample() {
    const u = Math.random();
    // Binary search in CDF
    let lo = 0, hi = this.n - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (this.cdf[mid] < u) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }
}

// ── Agent Pool ───────────────────────────────────────────────────────────────

function generateAgents(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    code: `AGT-${String(i + 1).padStart(5, "0")}`,
    name: `Agent ${i + 1}`,
    merchantId: 1000 + i,
  }));
}

// ── Request Generators ───────────────────────────────────────────────────────

const REQUEST_TYPES = [
  {
    name: "settlement.getStats",
    weight: 30,
    generate: (agent) => ({
      method: "GET",
      path: "/api/trpc/settlementBatchProcessor.getStats",
    }),
  },
  {
    name: "settlement.listBatches",
    weight: 25,
    generate: (agent) => ({
      method: "GET",
      path: `/api/trpc/settlementBatchProcessor.listBatches?input=${encodeURIComponent(JSON.stringify({ json: { limit: 20 } }))}`,
    }),
  },
  {
    name: "settlement.listSettlements",
    weight: 20,
    generate: (agent) => ({
      method: "GET",
      path: `/api/trpc/settlementBatchProcessor.listSettlements?input=${encodeURIComponent(JSON.stringify({ json: { cursor: null, limit: 50 } }))}`,
    }),
  },
  {
    name: "commission.getStats",
    weight: 15,
    generate: (agent) => ({
      method: "GET",
      path: "/api/trpc/commissionEngine.getStats",
    }),
  },
  {
    name: "health",
    weight: 10,
    generate: () => ({
      method: "GET",
      path: "/api/health",
    }),
  },
];

function selectRequestType() {
  const totalWeight = REQUEST_TYPES.reduce((sum, rt) => sum + rt.weight, 0);
  let r = Math.random() * totalWeight;
  for (const rt of REQUEST_TYPES) {
    r -= rt.weight;
    if (r <= 0) return rt;
  }
  return REQUEST_TYPES[0];
}

// ── HTTP Client ──────────────────────────────────────────────────────────────

function makeRequest(method, path) {
  return new Promise((resolve) => {
    const url = new URL(path, BASE_URL);
    const startTime = performance.now();

    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port || 3000,
        path: url.pathname + url.search,
        method,
        timeout: 10000,
        headers: {
          "Content-Type": "application/json",
          "User-Agent": "54Link-LoadTest/1.0",
        },
      },
      (res) => {
        let body = "";
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          resolve({
            status: res.statusCode,
            latency: performance.now() - startTime,
            success: res.statusCode >= 200 && res.statusCode < 400,
          });
        });
      }
    );

    req.on("error", () => {
      resolve({
        status: 0,
        latency: performance.now() - startTime,
        success: false,
      });
    });

    req.on("timeout", () => {
      req.destroy();
      resolve({
        status: 0,
        latency: performance.now() - startTime,
        success: false,
      });
    });

    req.end();
  });
}

// ── Metrics Collector ────────────────────────────────────────────────────────

class MetricsCollector {
  constructor() {
    this.latencies = [];
    this.statusCodes = {};
    this.requestsByAgent = {};
    this.requestsByType = {};
    this.errors = 0;
    this.successes = 0;
    this.startTime = null;
  }

  record(agentId, requestType, result) {
    this.latencies.push(result.latency);
    this.statusCodes[result.status] = (this.statusCodes[result.status] || 0) + 1;
    this.requestsByAgent[agentId] = (this.requestsByAgent[agentId] || 0) + 1;
    this.requestsByType[requestType] = (this.requestsByType[requestType] || 0) + 1;
    if (result.success) this.successes++;
    else this.errors++;
  }

  percentile(p) {
    if (this.latencies.length === 0) return 0;
    const sorted = [...this.latencies].sort((a, b) => a - b);
    const idx = Math.ceil((p / 100) * sorted.length) - 1;
    return sorted[Math.max(0, idx)];
  }

  report() {
    const totalRequests = this.successes + this.errors;
    const elapsed = (performance.now() - this.startTime) / 1000;
    const actualRps = totalRequests / elapsed;

    // Pareto analysis: verify 80/20 distribution
    const agentEntries = Object.entries(this.requestsByAgent).sort((a, b) => b[1] - a[1]);
    const top20Count = Math.ceil(agentEntries.length * 0.2);
    const top20Requests = agentEntries.slice(0, top20Count).reduce((sum, [, cnt]) => sum + cnt, 0);
    const top20Pct = ((top20Requests / totalRequests) * 100).toFixed(1);

    console.log("\n" + "═".repeat(70));
    console.log("  54Link POS — Pareto Load Test Results");
    console.log("═".repeat(70));
    console.log(`  Duration:          ${elapsed.toFixed(1)}s`);
    console.log(`  Total Requests:    ${totalRequests}`);
    console.log(`  Actual RPS:        ${actualRps.toFixed(1)}`);
    console.log(`  Target RPS:        ${TARGET_RPS}`);
    console.log(`  Success Rate:      ${((this.successes / totalRequests) * 100).toFixed(1)}%`);
    console.log(`  Errors:            ${this.errors}`);
    console.log("─".repeat(70));
    console.log("  Latency Percentiles:");
    console.log(`    P50:  ${this.percentile(50).toFixed(1)}ms`);
    console.log(`    P90:  ${this.percentile(90).toFixed(1)}ms`);
    console.log(`    P95:  ${this.percentile(95).toFixed(1)}ms`);
    console.log(`    P99:  ${this.percentile(99).toFixed(1)}ms`);
    console.log(`    Max:  ${this.percentile(100).toFixed(1)}ms`);
    console.log("─".repeat(70));
    console.log("  Pareto Distribution Verification:");
    console.log(`    Agents:          ${agentEntries.length}`);
    console.log(`    Top 20% agents:  ${top20Count} agents → ${top20Pct}% of requests`);
    console.log(`    Zipf skewness:   s=${ZIPF_S}`);
    console.log(`    Target:          80% (Pareto optimal)`);
    console.log("─".repeat(70));
    console.log("  Request Type Distribution:");
    for (const [type, cnt] of Object.entries(this.requestsByType).sort((a, b) => b[1] - a[1])) {
      console.log(`    ${type.padEnd(35)} ${cnt} (${((cnt / totalRequests) * 100).toFixed(1)}%)`);
    }
    console.log("─".repeat(70));
    console.log("  Status Code Distribution:");
    for (const [code, cnt] of Object.entries(this.statusCodes).sort((a, b) => b[1] - a[1])) {
      console.log(`    HTTP ${code}:  ${cnt}`);
    }
    console.log("═".repeat(70));

    return {
      totalRequests,
      actualRps,
      successRate: (this.successes / totalRequests) * 100,
      p50: this.percentile(50),
      p95: this.percentile(95),
      p99: this.percentile(99),
      paretoTop20Pct: parseFloat(top20Pct),
    };
  }
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  console.log("54Link POS — Pareto-Aware Load Test");
  console.log(`  Target: ${TARGET_RPS} RPS for ${DURATION_S}s`);
  console.log(`  Agents: ${NUM_AGENTS} (Zipf s=${ZIPF_S})`);
  console.log(`  URL:    ${BASE_URL}`);
  console.log();

  const agents = generateAgents(NUM_AGENTS);
  const zipf = new ZipfDistribution(NUM_AGENTS, ZIPF_S);
  const metrics = new MetricsCollector();
  metrics.startTime = performance.now();

  const intervalMs = 1000 / TARGET_RPS;
  const totalRequests = TARGET_RPS * DURATION_S;
  let sent = 0;

  console.log(`  Sending ${totalRequests} requests...`);

  const promises = [];

  for (let i = 0; i < totalRequests; i++) {
    const agentIdx = zipf.sample();
    const agent = agents[agentIdx];
    const reqType = selectRequestType();
    const req = reqType.generate(agent);

    const promise = makeRequest(req.method, req.path).then((result) => {
      metrics.record(agent.id, reqType.name, result);
    });
    promises.push(promise);

    sent++;
    if (sent % (TARGET_RPS * 5) === 0) {
      console.log(`  Progress: ${sent}/${totalRequests} requests sent (${((sent / totalRequests) * 100).toFixed(0)}%)`);
    }

    // Rate limiting: sleep to maintain target RPS
    if (i % 10 === 0) {
      await new Promise((r) => setTimeout(r, intervalMs * 10));
    }
  }

  // Wait for all in-flight requests
  console.log("  Waiting for in-flight requests...");
  await Promise.allSettled(promises);

  return metrics.report();
}

main().catch(console.error);
