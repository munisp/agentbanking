const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");
const crypto = require("crypto");

const app = express();
const PORT = process.env.PORT || 3022;

app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json());

app.get("/health", (req, res) => res.json({ status: "ok", service: "webhook-service" }));

// In-memory store (replace with DB in production)
const endpoints = new Map();
const deliveries = new Map();

app.get("/developer/api/v1/webhooks", (req, res) => {
  res.json({ endpoints: Array.from(endpoints.values()) });
});

app.post("/developer/api/v1/webhooks", (req, res) => {
  const id = `wh-${Date.now()}`;
  const secret = crypto.randomBytes(32).toString("hex");
  const endpoint = {
    id,
    url: req.body.url,
    events: req.body.events || [],
    status: "active",
    secret,
    success_rate: 100,
    total_deliveries: 0,
    created_at: new Date().toISOString(),
  };
  endpoints.set(id, endpoint);
  res.status(201).json({ endpoint, secret });
});

app.patch("/developer/api/v1/webhooks/:id/status", (req, res) => {
  const ep = endpoints.get(req.params.id);
  if (!ep) return res.status(404).json({ error: "Not found" });
  ep.status = req.body.status;
  res.json({ success: true });
});

app.delete("/developer/api/v1/webhooks/:id", (req, res) => {
  endpoints.delete(req.params.id);
  res.status(204).send();
});

app.post("/developer/api/v1/webhooks/:id/test", async (req, res) => {
  const ep = endpoints.get(req.params.id);
  if (!ep) return res.status(404).json({ error: "Not found" });
  // In production: dispatch test event to ep.url with HMAC signature
  res.json({ success: true, message: "Test event dispatched" });
});

// Internal endpoint: receive Kafka events and fan out to registered endpoints
app.post("/internal/dispatch", async (req, res) => {
  const { event, payload } = req.body;
  const targets = Array.from(endpoints.values()).filter(ep =>
    ep.status === "active" && ep.events.includes(event)
  );
  // In production: push to delivery queue (Redis / BullMQ)
  res.json({ dispatched: targets.length });
});

// ── Webhook Retry Engine ───────────────────────────────────────────────────────

const retryQueue = new Map(); // retryId → retryEntry
const RETRY_TTL_MS = 24 * 60 * 60 * 1000; // 24h

function scheduleRetry(webhookId, payload, maxAttempts = 5) {
  const retryId = `retry-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  retryQueue.set(retryId, {
    retryId,
    webhookId,
    payload,
    attempts: 0,
    maxAttempts,
    nextRetryAt: Date.now() + 5000, // first retry in 5s
    status: "pending",
    createdAt: Date.now(),
    lastError: null,
  });
  return retryId;
}

function getRetryQueue(webhookId) {
  const entries = Array.from(retryQueue.values());
  return webhookId ? entries.filter(e => e.webhookId === webhookId) : entries;
}

async function processRetryQueue() {
  const now = Date.now();
  const processed = [];
  for (const [retryId, entry] of retryQueue.entries()) {
    if (entry.status !== "pending" || entry.nextRetryAt > now) continue;
    const ep = endpoints.get(entry.webhookId);
    if (!ep || ep.status !== "active") {
      entry.status = "abandoned";
      continue;
    }
    entry.attempts += 1;
    try {
      const axios = require("axios");
      const sig = crypto
        .createHmac("sha256", ep.secret)
        .update(JSON.stringify(entry.payload))
        .digest("hex");
      await axios.post(ep.url, entry.payload, {
        timeout: 10000,
        headers: { "X-Webhook-Signature": `sha256=${sig}`, "X-Retry-Attempt": entry.attempts },
      });
      entry.status = "delivered";
      ep.total_deliveries += 1;
      processed.push({ retryId, status: "delivered", attempts: entry.attempts });
    } catch (err) {
      entry.lastError = err.message;
      if (entry.attempts >= entry.maxAttempts) {
        entry.status = "failed";
        processed.push({ retryId, status: "failed", attempts: entry.attempts });
      } else {
        // Exponential backoff: 5s, 25s, 125s, 625s, …
        entry.nextRetryAt = Date.now() + Math.pow(5, entry.attempts) * 1000;
        processed.push({ retryId, status: "retrying", nextRetryAt: entry.nextRetryAt });
      }
    }
  }
  return processed;
}

function getRetryStats() {
  const entries = Array.from(retryQueue.values());
  return {
    total: entries.length,
    pending: entries.filter(e => e.status === "pending").length,
    delivered: entries.filter(e => e.status === "delivered").length,
    failed: entries.filter(e => e.status === "failed").length,
    abandoned: entries.filter(e => e.status === "abandoned").length,
  };
}

function clearExpiredRetries() {
  const cutoff = Date.now() - RETRY_TTL_MS;
  let cleared = 0;
  for (const [id, entry] of retryQueue.entries()) {
    if (entry.createdAt < cutoff || entry.status === "delivered") {
      retryQueue.delete(id);
      cleared++;
    }
  }
  return cleared;
}

// Retry REST endpoints
app.post("/internal/retry/schedule", (req, res) => {
  const { webhookId, payload, maxAttempts } = req.body;
  if (!webhookId || !payload) return res.status(400).json({ error: "webhookId and payload required" });
  const retryId = scheduleRetry(webhookId, payload, maxAttempts);
  res.status(201).json({ retryId });
});

app.get("/internal/retry/queue", (req, res) => {
  res.json({ queue: getRetryQueue(req.query.webhookId) });
});

app.post("/internal/retry/process", async (req, res) => {
  const results = await processRetryQueue();
  res.json({ processed: results.length, results });
});

app.get("/internal/retry/stats", (req, res) => {
  res.json(getRetryStats());
});

app.delete("/internal/retry/expired", (req, res) => {
  const cleared = clearExpiredRetries();
  res.json({ cleared });
});

// Run retry processor every 30 seconds
setInterval(async () => {
  try { await processRetryQueue(); } catch (e) { /* silent */ }
  clearExpiredRetries();
}, 30000);

app.listen(PORT, () => console.log(`webhook-service running on port ${PORT}`));
