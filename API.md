# 54Link POS Shell — tRPC API Reference

**Version:** Phase 136  
**Transport:** HTTP Batch (POST `/api/trpc`)  
**Auth:** Session cookie (`session=<jwt>`) for agent procedures; Manus OAuth for admin SSO

All procedures use [tRPC v11](https://trpc.io) with [Superjson](https://github.com/blitz-js/superjson) serialization.

---

## Authentication Procedures

### `auth.me` — Get current user (Manus OAuth)

**Type:** Query | **Auth:** Public  
Returns the currently authenticated Manus OAuth user or null.

### `auth.logout` — Logout (Manus OAuth)

**Type:** Mutation | **Auth:** Protected  
Clears the Manus OAuth session cookie.

---

## Agent Authentication Procedures

### `agent.login` — Agent login

**Type:** Mutation | **Auth:** Public  
**Input:** `{ agentCode: string, pin: string }`  
**Returns:** `{ success: true, agentCode: string, name: string, role: string }`  
Sets a `session` HttpOnly cookie with a 12-hour JWT.

### `agent.logout` — Agent logout

**Type:** Mutation | **Auth:** Agent  
Clears the agent session cookie.

### `agent.me` — Get agent profile

**Type:** Query | **Auth:** Agent  
**Returns:** `{ agentCode, name, floatBalance, commissionBalance, loyaltyPoints, tier, role, isActive, location }`

### `agent.register` — Register new agent (dev/demo)

**Type:** Mutation | **Auth:** Public  
**Input:** `{ agentCode, name, pin, phone, location? }`

---

## Transaction Procedures

### `transactions.create` — Create transaction

**Type:** Mutation | **Auth:** Agent  
**Input:**

```ts
{
  type: "cash_in" | "cash_out" | "transfer" | "airtime" | "bills" | "card" | "qr" | "nfc",
  amount: number,          // in kobo (₦1 = 100 kobo)
  customerPhone?: string,
  customerName?: string,
  recipientAccount?: string,
  recipientBank?: string,
  billProvider?: string,
  billAccountNumber?: string,
  channel?: string,
  metadata?: Record<string, unknown>
}
```

**Returns:** `{ txRef, type, amount, fee, commission, loyaltyPoints, status, timestamp }`

**Side effects:**

- Deducts/credits float balance
- Accrues commission
- Awards loyalty points
- Publishes `tx.created` to Kafka
- Publishes to Fluvio fraud stream
- Tries TigerBeetle sidecar first, falls back to PostgreSQL

### `transactions.list` — List transactions (paginated)

**Type:** Query | **Auth:** Agent  
**Input:** `{ page?: number, limit?: number, type?: string, status?: string }`  
**Returns:** `{ transactions: Transaction[], total: number, page: number }`

### `transactions.getByRef` — Get transaction by reference

**Type:** Query | **Auth:** Agent  
**Input:** `{ txRef: string }`  
**Returns:** `Transaction | null`

### `transactions.reverse` — Reverse transaction

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ txRef: string, reason: string }`  
**Returns:** `{ success: true, reversalRef: string }`

---

## Fraud Procedures

### `fraud.list` — List fraud alerts

**Type:** Query | **Auth:** Agent  
**Input:** `{ page?: number, limit?: number, status?: string, severity?: string }`

### `fraud.create` — Create fraud alert

**Type:** Mutation | **Auth:** Agent  
**Input:** `{ txRef, severity, type, customerPhone, amount, reason }`

### `fraud.updateStatus` — Update fraud alert status

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ alertId: number, status: "open" | "investigating" | "resolved" | "dismissed" }`

---

## Loyalty Procedures

### `loyalty.profile` — Get loyalty profile

**Type:** Query | **Auth:** Agent  
**Returns:** `{ points, tier, nextTier, pointsToNextTier, history: LoyaltyEvent[] }`

### `loyalty.claimChallenge` — Claim a loyalty challenge

**Type:** Mutation | **Auth:** Agent  
**Input:** `{ challengeId: string }`

### `loyalty.redeemReward` — Redeem loyalty reward

**Type:** Mutation | **Auth:** Agent  
**Input:** `{ rewardId: string, pointsCost: number }`

---

## Chat Procedures

### `chat.startSession` — Start chat session

**Type:** Mutation | **Auth:** Agent  
**Returns:** `{ sessionId: string }`

### `chat.sendMessage` — Send chat message

**Type:** Mutation | **Auth:** Agent  
**Input:** `{ sessionId: string, content: string, role: "agent" | "support" }`

### `chat.getMessages` — Get chat messages

**Type:** Query | **Auth:** Agent  
**Input:** `{ sessionId: string }`  
**Returns:** `ChatMessage[]`

---

## Admin Management Procedures

### `agentManagement.listAll` — List all agents

**Type:** Query | **Auth:** Admin  
**Input:** `{ page?: number, limit?: number, search?: string, role?: string, isActive?: boolean }`

### `agentManagement.setRole` — Set agent role

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ agentCode: string, role: "admin" | "agent" | "supervisor" }`

### `agentManagement.setActive` — Suspend/activate agent

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ agentCode: string, isActive: boolean }`

### `agentManagement.updateFloat` — Update agent float

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ agentCode: string, amount: number, operation: "credit" | "debit" }`

### `agentManagement.listTopUpRequests` — List float top-up requests

**Type:** Query | **Auth:** Admin  
**Input:** `{ status?: "pending" | "approved" | "rejected" }`

### `agentManagement.approveTopUp` — Approve float top-up

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ requestId: number }`

### `agentManagement.rejectTopUp` — Reject float top-up

**Type:** Mutation | **Auth:** Admin  
**Input:** `{ requestId: number, reason: string }`

---

## Audit Log Procedures

### `auditLog.list` — List audit log (agent-scoped)

**Type:** Query | **Auth:** Agent  
**Input:** `{ page?: number, limit?: number }`

### `auditLog.listAll` — List all audit log

**Type:** Query | **Auth:** Admin  
**Input:** `{ page?: number, limit?: number, actor?: string, action?: string }`

---

## Settlement Procedures

### `settlement.runNow` — Trigger manual settlement

**Type:** Mutation | **Auth:** Admin  
**Returns:** `{ agentsProcessed, totalVolume, totalCommission, smsCount, errors }`

### `settlement.getLastRun` — Get last settlement run

**Type:** Query | **Auth:** Admin  
**Returns:** `{ timestamp, agentsProcessed, totalVolume, errors } | null`

---

## Export Procedures

### `export.transactionsCsv` — Export transactions as CSV

**Type:** Query | **Auth:** Admin  
**Input:** `{ startDate?: string, endDate?: string, agentCode?: string }`  
**Returns:** CSV string (download via Blob in browser)

---

## PIN Reset Procedures

### `pinReset.requestOtp` — Request PIN reset OTP

**Type:** Mutation | **Auth:** Public  
**Input:** `{ agentCode: string, phone: string }`

### `pinReset.resetPin` — Reset PIN with OTP

**Type:** Mutation | **Auth:** Public  
**Input:** `{ agentCode: string, otp: string, newPin: string }`

---

## SMS Receipt Procedures

### `smsReceipt.send` — Send SMS receipt

**Type:** Mutation | **Auth:** Agent  
**Input:** `{ phone: string, txRef: string, amount: number, type: string, timestamp: string }`

---

## SIM Orchestrator Procedures

### `simOrchestrator.ingestProbe` — Ingest connectivity probe

**Type:** Mutation | **Auth:** Public (API key)  
**Input:** `{ terminalId, carrier, rssi, latency, packetLoss, latE6?, lonE6?, txRef? }`

### `simOrchestrator.getProbes` — Get probe history

**Type:** Query | **Auth:** Admin  
**Input:** `{ terminalId?: string, limit?: number }`

### `simOrchestrator.getProbeGeoData` — Get geo-tagged probe data for coverage map

**Type:** Query | **Auth:** Admin  
**Input:** `{ hours?: number, carrier?: string }`  
**Returns:** `ProbeGeoPoint[]` with latE6, lonE6, rssi, carrier, terminalId

### `simOrchestrator.reportFailover` — Report SIM failover event

**Type:** Mutation | **Auth:** Public (API key)  
**Input:** `{ terminalId, fromSlot, toSlot, reason, latencyMs, lossX10, txRef? }`

### `simOrchestrator.getFailoverHistory` — Get failover history

**Type:** Query | **Auth:** Admin  
**Input:** `{ terminalId?: string, limit?: number }`

---

## System Procedures

### `system.notifyOwner` — Send notification to platform owner

**Type:** Mutation | **Auth:** Protected  
**Input:** `{ title: string, content: string }`

---

## Error Codes

| Code                    | Message                                     | Description                  |
| ----------------------- | ------------------------------------------- | ---------------------------- |
| `UNAUTHORIZED`          | Please login (10001)                        | No valid session cookie      |
| `FORBIDDEN`             | You do not have required permission (10002) | Insufficient role            |
| `BAD_REQUEST`           | Validation error                            | Zod schema validation failed |
| `NOT_FOUND`             | Resource not found                          | Entity does not exist        |
| `INTERNAL_SERVER_ERROR` | Internal error                              | Unexpected server error      |

---

## Rate Limits (APISix)

| Endpoint                        | Limit       | Window    |
| ------------------------------- | ----------- | --------- |
| `/api/trpc/transactions.create` | 30 req/min  | per agent |
| `/api/trpc/agent.login`         | 10 req/min  | per IP    |
| `/api/trpc/pinReset.*`          | 5 req/min   | per IP    |
| All other `/api/trpc/*`         | 100 req/min | per agent |

---

## WebSocket Events (Socket.IO)

### `/fraud` namespace

- `fraud:new` — new fraud alert `{ id, severity, type, amount, agentCode, timestamp }`
- `fraud:updated` — status update `{ id, status }`

### `/chat` namespace

- `chat:message` — new message `{ sessionId, content, role, timestamp }`
- `chat:typing` — typing indicator `{ sessionId, isTyping }`

### `/terminal` namespace

- `terminal:heartbeat` — terminal online `{ terminalId, timestamp }`
- `terminal:offline` — terminal offline `{ terminalId, lastSeen }`
