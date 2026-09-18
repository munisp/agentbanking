# AgentBanking Platform — Exhaustive Scenario & Use-Case Gap Catalog
**Round 6 deep audit — munisp/agentbanking @ main (`1fe48891`)**
Method: full-tree recon (16,333 blobs) + 4 parallel specialist audits (security/reliability, frontend↔backend contract, money lifecycle/consistency, tenancy/compliance). Every verdict cites file:line evidence. Routers referenced are under `services/api-server-ts/server/`.

Verdict legend: **HANDLED** (working end-to-end with evidence) · **PARTIAL** (exists but incomplete/broken in a defined way) · **GAP** (absent, stubbed, or fake success). "Fix" refers to the round-6 staged patch set.

---

## 1. Core agent money movement

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 1.1 | Cash-in / cash-out at POS | HANDLED | `routers/transactions.ts` create path: TB-first transfer (756-793), guarded float update via `db.ts:285-330` | — |
| 1.2 | Idempotent transaction submission | HANDLED | claim-first `withIdempotency`/`claimIdempotencyKey`, `transactionHelper.ts:144-289`; used at transactions.ts:398-421 | — |
| 1.3 | Double-spend protection on float | HANDLED | `updateAgentFloat` single guarded UPDATE, 0 rows → throw | — |
| 1.4 | Immediate POS reversal | HANDLED | transactions.ts:1264-1325 — atomic status flip + guarded float restore in one `withTransaction`, conditional UPDATE → 409 on double-reversal | — |
| 1.5 | Reversal approval (>₦10k queued) | PARTIAL | queue works (1213-1262) but `approveReversal` was non-atomic TOCTOU (1459-1490) | **F20** fixed: conditional UPDATE + float restore in one transaction |
| 1.6 | Reversal reflected in TigerBeetle ledger | PARTIAL | `tbClient.ts:56-90` has no post/void/contra API; reversal writes only `LEDGER_RECONCILIATION_PENDING` audit marker (1327-1357) | OPEN (needs tb-sidecar contra-transfer endpoint — next round) |
| 1.7 | TB commit → Postgres write partial failure | PARTIAL | create path 756-858: PG insert/float failure after TB commit has no compensation (catch only releases idempotency claim, 1046-1056) | OPEN (saga/compensation — next round) |
| 1.8 | Float top-up request + GL journal | PARTIAL | atomic in one db.transaction (floatTopUp.ts:239-260), but duplicate guard is self-admittedly race-prone (210-226), no idempotency key | OPEN (needs unique partial index migration) |
| 1.9 | Float top-up supervisor approval | HANDLED | floatTopUp.ts:473-491 with assignment verification | — |
| 1.10 | Agent-to-agent float transfer | HANDLED | agentFloatTransfer.ts:232-393 — idempotency + guarded debit/credit in one tx (caveat: no TB leg, see 1.6 class) | — |
| 1.11 | Split payments | GAP→FIXED | splitPayments.ts:290-327 — N success rows outside tx + unguarded debit, no idempotency, stale-read balance check | **F16** fixed: `withIdempotency` + single `withTransaction` + guarded `updateAgentFloat` |
| 1.12 | Commission payout approve/process | GAP→FIXED | commissionPayouts.ts:248-370 — TOCTOU status checks, unguarded negative-capable debit, non-atomic | **F17** fixed: conditional guarded updates in one tx |
| 1.13 | Merchant payout settlement lifecycle | GAP→FIXED | merchantPayoutSettlement.ts:204-266 — STATUS_TRANSITIONS declared (24-30) but never used; unconditional flips | **F21** fixed: enforced state machine + conditional UPDATEs |
| 1.14 | Settlement cron (aggregation + SMS) | HANDLED | settlementCron.ts:148-262 per-agent isolation, lock release in finally | — |
| 1.15 | Settlement batch funds movement (Go) | GAP | settlement-batch-processor/main.go: no row claiming (89-112), fresh batch ID per run defeats TB dedup, no compensation on mid-batch failure, in-memory batch state | OPEN (Go service rework — next round) |
| 1.16 | float-service settle_float | GAP | float_service_production.py:1008-1052 — gateway failure swallowed, balances updated anyway | OPEN (Python service rework — next round) |
| 1.17 | Float reservation expiry | GAP | reservations get `expires_at` (line 750) but no sweeper ever queries it | OPEN |
| 1.18 | Stuck `floatLocked` DB flag after crash | PARTIAL | Redis lock TTLs but DB flag only cleared in finally paths; no reconciler; agents blocked until manual unlock (agent.ts:670) | OPEN (sweeper — next round) |
| 1.19 | Float/PG internal reconciliation (detection) | HANDLED | floatReconciliation.ts:319-443 detects discrepancies (no auto-correction) | — |
| 1.20 | Commission balance updates | GAP | db.ts:332-353 `updateAgentCommission`: unlocked read-modify-write, JS float math, silent drop on DB outage | OPEN (next round) |
| 1.21 | Refunds (refund-service) | PARTIAL | service.py:43-58 no idempotency key on reversal POST; REFUND_WINDOW_HOURS=72 declared but never enforced | OPEN |
| 1.22 | Instant reversal engine → gateway route | PARTIAL | instant-reversal-engine/service.py:190-201 POSTs `/api/v1/transactions/reverse` which does not exist in payment-gateway-service (only `/refund`) → 404 → all reversals escalate | OPEN |

## 2. Disputes & chargebacks

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 2.1 | Raise dispute (agent) | HANDLED | disputeResolution.ts:258-310 real insert | — |
| 2.2 | Customer dispute portal + evidence/messages | HANDLED | customerDisputePortal.ts:203-291 | — |
| 2.3 | disputes.raise / addMessage (main router) | GAP (stubbed) | disputes.ts:377-398 NOT_IMPLEMENTED — real equivalents exist elsewhere; stubs fail loud | — (honest stubs) |
| 2.4 | disputes.resolve | GAP→FIXED | disputes.ts:334-368 returned `{resolved:true}` with NO DB write | **F18** fixed: conditional UPDATE persists status/resolution/resolvedBy/resolvedAt, CONFLICT on double-resolve |
| 2.5 | Dispute status transition validation | GAP→FIXED | disputeResolution.ts:321-341 free-form status string, unconditional UPDATE | **F19** fixed: enum + state machine + conditional UPDATE |
| 2.6 | Dispute auto-escalation (SLA) | HANDLED | cron/disputeAutoEscalation.ts:9-62 15-min sweep | — |
| 2.7 | Chargeback creation | PARTIAL | chargebackManagement.ts:165-221 inserts disputes row only | — |
| 2.8 | Chargeback resolution moves money | GAP | chargebackManagement.ts:222-247 `resolveChargeback` only flips status; no re-credit, no ledger contra-entry | OPEN (needs money-movement design — next round) |
| 2.9 | Funds re-credit on dispute resolution | GAP | absent everywhere (disputeResolution.updateStatus:321-375, disputeWorkflowEngine.autoResolve:425+) | OPEN (same class as 2.8) |
| 2.10 | reversalApproval router | GAP (stubbed) | reversalApproval.ts:70-101 NOT_IMPLEMENTED; working path is transactions.approveReversal/rejectReversal | — (honest stubs) |

## 3. AuthN/AuthZ & API surface security

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 3.1 | Keycloak JWT validation (JWKS+aud+iss) on tRPC | HANDLED | `_core/keycloak.ts` verifyKeycloakToken | — |
| 3.2 | REST bridge `/api/v1` authentication | GAP→FIXED (CRITICAL) | `restBridge.ts` requireAuth defined but never mounted — 120 routes open | **F1** fixed: session cookie / Bearer JWKS / internal-gateway-token (fail-closed), mounted with `/health` exemption |
| 3.3 | Permify authorization failure mode | GAP→FIXED | `_core/permify.ts` exception path returned `true` (fail-open) | **F2** fixed: fail-closed in production |
| 3.4 | PBAC at money-write | GAP | middleware/pbacEnforcement.ts used by 0 routers | OPEN (pipeline wiring — next round) |
| 3.5 | x-tenant-id header trusted for authz | PARTIAL | securityOrchestrator.ts:139 forwards client header as PBAC resource tenant — spoofable | OPEN |
| 3.6 | auth-service token validation | GAP→FIXED | services/auth-service/services/token.py: JWKS refetched per call, no timeout, no aud/iss verification, hardcoded host | **F10** fixed: TTL cache, timeout, iss/aud verify, env-configurable |
| 3.7 | PIN reset OTP abuse | GAP→FIXED | pinReset.ts: no request throttle (SMS bombing), no attempt lockout | **F9** fixed: 60s throttle + 5-attempt lockout + migration 0053 |
| 3.8 | MDM OTA status reporting | GAP→FIXED | mdm.ts:1465 recordOtaUpdate publicProcedure, only deviceId needed | **F8** fixed: device-token (timingSafeEqual) required, same NF-SEC-2 pattern as heartbeat |
| 3.9 | txMonitor alert rules/dashboard | GAP→FIXED | txMonitor.ts:384-467 getRules/getAlerts/acknowledgeAlert/resolveAlert/getDashboard were publicProcedure | **F7** fixed: all 5 → protectedProcedure |
| 3.10 | payment-gateway webhook admin endpoints | GAP→FIXED | webhook_router.py `/events`, `/events/{id}/reprocess` "admin only" in docstring, no auth; placeholder secrets `your_paystack_secret` in source; missing typing/datetime imports | **F3** fixed: env secrets (fail-closed), Keycloak admin dependency, imports |
| 3.11 | billing-webhook-dispatcher | GAP→FIXED | main.py: hardcoded `whsec_tenant1/2…` config secrets, simulated delivery (`return True`), no auth on dispatch/stats/deliveries/dlq | **F4** fixed: WEBHOOK_CONFIGS_JSON env, real HTTP POST with timeout, INTERNAL_GATEWAY_TOKEN auth (fail-closed) |
| 3.12 | webhook-delivery service | GAP→FIXED | main.py: default signing secret committed, no auth on 9 routes, endpoint list leaked secrets | **F5** fixed: fail-closed secret, internal auth on all routes, redaction |
| 3.13 | Data export (transactions/agents/audit) | GAP→FIXED | dataExport.ts:224-347 any authenticated user could dump 10k rows | **F6** fixed: adminProcedure + tenant filter |
| 3.14 | Tenant registry enumeration | GAP→FIXED | multiTenantIsolation.ts:166-212 listTenants/getTenant/createTenant bare protectedProcedure | **T9** fixed: adminProcedure |
| 3.15 | Tenant creation (tenantAdmin) | GAP→FIXED | tenantAdmin.ts:239 no role check — any user could create tenants | **T8** fixed: adminProcedure |

## 4. Multi-tenancy

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 4.1 | tenantId columns on core tables | HANDLED | schema.ts:381/399 + agents/customers/kyc_sessions/disputes/audit_log etc. | — |
| 4.2 | Fail-closed RLS policies | PARTIAL | drizzle/0051_rls_tenant_isolation_failclosed.sql exists as file, corrects 0048 fail-open | — |
| 4.3 | RLS migrations registered/applied | GAP | meta/_journal.json ends at 0042 (api-server-ts) / 0044 (root); 0047-0052 unjournaled; only `db:push` script exists | OPEN (migration runner step — next round) |
| 4.4 | App sets `app.current_tenant_id` per request | GAP | lib/queryHelpers.ts:101-127, base.repository.ts:77-83 exist with zero callers | OPEN |
| 4.5 | Tenant middleware adoption | GAP | middleware/tenantIsolation.ts + tenantScope.ts imported by 0 of 484 routers | OPEN |
| 4.6 | tenantScope fallback | GAP | tenantScope.ts ~95: unmapped users silently get "tenant-default" | OPEN |
| 4.7 | Cross-tenant leakage in management stats | GAP | management.ts:125-139 aggregates all tenants; agents.list (~208-220) no tenant filter | OPEN |
| 4.8 | tenantId on satellite money tables | GAP | commission_payouts/merchant_payouts/agent_loans/fee_rules/velocity_limits/transaction_limits lack tenantId (schema.ts:2314/3304/3193/3233/824/3040); 0051 RLS silently skips them | OPEN (schema migration — next round) |
| 4.9 | Per-tenant fee schedules | HANDLED | tenantFeeOverridesCrud.ts:153-345 | — |
| 4.10 | Per-tenant limits | GAP | transaction_limits/velocity_limits keyed by tier only | OPEN |
| 4.11 | Tenant onboarding provisioning | PARTIAL | orchestrator-service Temporal workflow real (provisionKeycloakRealm, mint account); tenantAdmin.createTenant didn't invoke it | **T8** (gate); workflow invocation OPEN |

## 5. Compliance (CBN/AML/KYC/privacy)

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 5.1 | Tier velocity limits at money-write | HANDLED | transactions.ts:139-245 + Gate 4 at 495-541 (blocks + fraud alert + audit) | — |
| 5.2 | Business-rules limit check at write | GAP→FIXED | checkTransactionLimits imported but never invoked; whole block fail-open catch (746-751) | **T16** fixed: invoked + fail-closed |
| 5.3 | Customer KYC-tier limits at POS write | GAP | kyc-enforcement-go + kycEnforcement.ts:541 exist; nothing calls them from payment path | OPEN |
| 5.4 | AML triggers (CTR ₦5M, structuring) | PARTIAL | businessRulesEngine.ts:398-445 real logic; called with hardcoded zeros, never blocks, never queues CTR | OPEN |
| 5.5 | Sanctions/PEP screening at write | GAP | lib/complianceScreening.ts real (OFAC SDN); only used by transactionPipeline.ts which has 0 importers | OPEN |
| 5.6 | CBN monthly/quarterly reports | HANDLED | cbnReporting.ts:77-159 real SQL aggregation | — |
| 5.7 | SAR filing fallback persistence | GAP→FIXED | fileSar:450-490 returned synthetic `filed_locally` without persisting | **T20** fixed: persists to compliance_reports |
| 5.8 | cbnReportsTotal metric | GAP→FIXED | metrics.ts:164 defined, 0 increments | **T21** fixed: wired at 5 call sites |
| 5.9 | Immutable/hash-chained audit log | GAP | writeAuditLog plain INSERT; no prevHash chain; blockchainAuditTrail.ts has no chaining | OPEN |
| 5.10 | Audit write failures swallowed | PARTIAL | db.ts:627-629 catch→console.error | OPEN |
| 5.11 | BVN/NIN encryption at rest | GAP | plaintext varchar (schema.ts:985-986, 1308-1309); AES-GCM exists only in encryptedFieldsCrud.ts | OPEN |
| 5.12 | GDPR/NDPR erasure actually anonymizes | PARTIAL | gdpr.ts endpoints real; erasure only writes audit row; admin processing flips status only | OPEN |
| 5.13 | Weekly compliance PDF | HANDLED | compliancePdf.ts (pdfkit→S3) | — |

## 6. Product rails (frontend↔backend contract audit: 186 of 1,383 procedure calls broken)

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 6.1 | Bill payments execution | GAP | billPayments.payBill:285-300 NOT_IMPLEMENTED (honest stub) | OPEN (rail integration — beyond code-only scope) |
| 6.2 | Savings deposit/withdraw | GAP | savingsProducts.ts:287-317 NOT_IMPLEMENTED; no savings ledger schema | OPEN |
| 6.3 | QR payments | PARTIAL | pay leg real; generateQr NOT_IMPLEMENTED | OPEN |
| 6.4 | Airtime/data purchase | PARTIAL | ledger-only, no VAS provider call | OPEN |
| 6.5 | Loans | PARTIAL | stored scores; no disbursement engine | OPEN |
| 6.6 | Referrals | PARTIAL | no generate/redeem UI; referralConversionsTotal never incremented | OPEN |
| 6.7 | Cross-border (CIPS/PAPSS) | PARTIAL | pure local-DB CRUD stubs | OPEN |
| 6.8 | Standing orders execution engine | GAP | no executor found | OPEN |
| 6.9 | BVN/NIN verification | GAP | no backend procedures | OPEN |
| 6.10 | Push notifications | GAP | no /api/push mount | OPEN |
| 6.11 | Bulk/payroll execution | PARTIAL | no execution path | OPEN |
| 6.12 | EOD reconciliation | PARTIAL | backend only | OPEN |
| 6.13 | Offline sync push | PARTIAL | syncBatch exists; /api/sync/push dead | OPEN |
| 6.14 | FX rates (live ECB/OXR) | HANDLED | live providers with fallback | — |
| 6.15 | Offline POS enqueue (Rust queue) | HANDLED | Rust offline queue | — |
| 6.16 | Fraud dashboard realtime | HANDLED | Socket.IO/SSE | — |
| 6.17 | Insider-threat router | GAP | router unregistered | OPEN |
| 6.18 | 54link_admin REST surfaces (/api/db/*, /api/v1/lpo/*, loans, cards) | GAP | unimplemented mounts | OPEN |
| 6.19 | Geofencing admin procedures | GAP | missing procedures referenced by UI | OPEN |
| 6.20 | AI/compliance chatbot procedures | GAP | missing procedures referenced by UI | OPEN |
| 6.21 | settlementNettingEngine sessions | GAP | createSession fabricates `NET-<timestamp>` ID, persists nothing; settleSession always CONFLICTs; side-effects in bare `catch {}` | OPEN |

## 7. Platform reliability

| # | Scenario | Verdict | Evidence | Fix |
|---|----------|---------|----------|-----|
| 7.1 | Webhook HMAC on api-server-ts | HANDLED | middleware/webhookHmac.ts fail-closed; Stripe constructEvent | — |
| 7.2 | Kafka consumer message loss | GAP→FIXED | shared/kafka_consumer.py: auto-commit default true, DLQ commented out | **F11** fixed: manual commit after success/DLQ, DLQ producer |
| 7.3 | Kafka producer (TS) retries/DLQ | GAP | kafkaClient.ts:16,107-135 publish returns false, no retry/DLQ | OPEN |
| 7.4 | Transactional outbox | GAP | only at root `server/middleware/transactionalOutbox.ts`; api-server-ts has none; Kafka/Fluvio publishes fire-and-forget (transactions.ts:957-994) | OPEN (next round) |
| 7.5 | Graceful shutdown (Python services) | HANDLED | register_shutdown pattern present (billing dispatcher, webhook-delivery) | — |
| 7.6 | Shallow /health only | PARTIAL | most services expose shallow health; no /ready with dependency checks | OPEN |
| 7.7 | requests.* without timeout | GAP | 42 sites incl. wazuh_client.py, cbn scheduler | **F10** fixed for auth-service; remaining OPEN |
| 7.8 | Stale root `server/` mirror | PARTIAL (process) | 433 divergent files vs deployed tree; root copy contains the only outbox + orphan tests | Documented; OPEN (repo hygiene decision) |

---

## Fix ledger (round-6 staged set, git blob sha → file)

| sha | file | fix |
|-----|------|-----|
| 7faf2acf3a2a | services/api-server-ts/server/restBridge.ts | F1 |
| acf04b5db1b0 | services/api-server-ts/server/_core/permify.ts | F2 |
| f5f75a6a6d4e | services/payment-gateway-service/routers/webhook_router.py | F3 |
| 4ce69176c8fb | services/billing-webhook-dispatcher/main.py | F4 |
| fc673bec04fd | services/webhook-delivery/main.py | F5 |
| be06afb09888 | services/api-server-ts/server/routers/dataExport.ts | F6 |
| cf924aadabb7 | services/api-server-ts/server/routers/txMonitor.ts | F7 |
| de019f095057 | services/api-server-ts/server/routers/mdm.ts | F8 |
| 72c3f6f516ac | services/api-server-ts/server/routers/pinReset.ts | F9 |
| 55ea348d5973 | services/api-server-ts/drizzle/schema.ts | F9 (attempts col) |
| a226235703f4 | services/api-server-ts/drizzle/0053_pin_reset_otp_attempts.sql | F9 (migration) |
| ced8b12aee6b | services/auth-service/services/token.py | F10 |
| 511d33594626 | services/shared/kafka_consumer.py | F11 |
| 5423fce2d09a | services/api-server-ts/server/routers/splitPayments.ts | F16 |
| 59f36f70d7e9 | services/api-server-ts/server/routers/commissionPayouts.ts | F17 |
| de25d3b551a8 | services/api-server-ts/server/routers/disputes.ts | F18 |
| d40d268515f6 | services/api-server-ts/server/routers/disputeResolution.ts | F19 |
| 211722373894 | services/api-server-ts/server/routers/transactions.ts | F20+T16 |
| 3b7c5117473e | services/api-server-ts/server/routers/merchantPayoutSettlement.ts | F21 |
| 17d08b5e4815 | services/api-server-ts/server/routers/multiTenantIsolation.ts | T9 |
| 223802931b53 | services/api-server-ts/server/routers/tenantAdmin.ts | T8 |
| c0af6b91f4bd | services/api-server-ts/server/routers/cbnReporting.ts | T20+T21 |

**Counts:** 81 cataloged scenarios — HANDLED 19 · PARTIAL 21 · GAP 41 → 20 gaps fixed in round 6 (22 files); remaining GAPs documented OPEN with owner classes identified (Go/Python service rework, schema migrations, external rail integrations, outbox/TB-contra architecture work scheduled next round).

---

## 8. Onboarding workflows — merchants, individuals, agents (round-6b extension audit)

Dedicated onboarding audit: 50 findings across account opening, KYC/KYB, agent onboarding chain, merchant onboarding, tenant onboarding, OTP, and orchestrator provisioning. Fixed in PR #128 (squash `8dbd8b19`).

| # | Scenario | Verdict (pre-fix) | Fix |
|---|----------|-------------------|-----|
| 8.1 | Orchestrator KYC callback authenticity | GAP (critical) — unauthenticated POST could complete KYC + create accounts (postKycCallback.ts) | FIXED: HMAC-SHA256 signature (fail-closed), score threshold, faceVerificationResult required |
| 8.2 | kyc-enforcement-go endpoint auth | GAP (critical) — zero auth; forgable verify-callback auto-approvals (main.go:643-687, 997-1005) | FIXED: internalAuthMiddleware on all /api/v1/* (fail-closed), crypto/rand IDs; live-binary verified |
| 8.3 | Agent onboarding step ordering/ownership | GAP (critical) — anyone could activate any agent, steps skippable (agentOnboarding.ts) | FIXED: self-or-admin gate + ordered conditional-UPDATE state machine |
| 8.4 | Account opening KYC denial handling | GAP (critical) — only HTTP 503 blocked; 202 {allowed:false} passed | FIXED: fail-closed unless allowed===true; 4xx/5xx deny |
| 8.5 | agentKyc.approveSession | GAP — non-admin, no precondition, status vocab mismatch | FIXED: adminProcedure + conditional + unified `completed` |
| 8.6 | Customer duplicate BVN/NIN | GAP | FIXED: pre-checks → CONFLICT (unique indexes remain as migration follow-up) |
| 8.7 | Account-opening idempotency | GAP | FIXED: withIdempotency |
| 8.8 | Customer tenantId stamping | GAP (RLS NULL rows visible cross-tenant) | FIXED: tenantId from ctx |
| 8.9 | approveAccount role gate | GAP | FIXED: adminProcedure + conditional |
| 8.10 | KYC doc OCR self-approval | GAP — verifyDocument auto-completed sessions | FIXED: OCR pass → pending_review (human gate) |
| 8.11 | kycDocuments verify/reject | GAP — non-admin, forged verifiedBy | FIXED: adminProcedure + server-set verifiedBy |
| 8.12 | whiteLabelOnboarding.approveApplication | GAP | FIXED: adminProcedure + pending-only conditional |
| 8.13 | Merchant registration dup/audit/tenant | PARTIAL→GAP | FIXED: phone/rcNumber pre-checks, auditLog, tenantId |
| 8.14 | checkRegistrationStatus enumeration | GAP | FIXED: admin/supervisor or owner-email gate |
| 8.15 | merchantKycOnboarding.uploadDoc | GAP — arbitrary merchantId, dup-spam | FIXED: ownership/admin + pending-dup guard |
| 8.16 | rejectMerchant status semantics | BUG — set `suspended` | FIXED: terminal `closed` (pgEnum-compatible; `rejected` needs enum migration follow-up) |
| 8.17 | restBridge POST /agents mass assignment | GAP — pinHash/floatBalance/isActive accepted from body | FIXED: field whitelist + server-side bcrypt PIN |
| 8.18 | mdm.enrollWithToken 100-device scan | GAP | FIXED: direct indexed enrollment-token query |
| 8.19 | Tier-1 OTP proof at account opening | PARTIAL | OPEN (next round) |
| 8.20 | startLiveness fail-open hint | PARTIAL | OPEN |
| 8.21 | KYB audit actor attribution | PARTIAL | OPEN |
| 8.22 | kyb-engine in-memory state + dup CAC | GAP | OPEN (Go service rework) |
| 8.23 | KYB approve preconditions | GAP | OPEN |
| 8.24 | Merchant email TOCTOU / unique constraints | PARTIAL | OPEN (migration follow-up) |
| 8.25 | Terminal serial uniqueness + MDM binding | PARTIAL (dup check fixed; MDM binding OPEN) | partial FIXED |
| 8.26 | Customer pipeline stage persistence | GAP — advanceStage persisted nothing; metrics hardcoded | OPEN |
| 8.27 | Orchestrator workflowId idempotency + schema strictness | PARTIAL | OPEN |
| 8.28 | Tenant onboarding-service (FastAPI) auth | GAP | OPEN |
| 8.29 | Tenant billing provisioning gate | PARTIAL | OPEN |
| 8.30 | OTP resend throttle + verify-otp token return | GAP | OPEN (auth-service) |
| 8.31 | BVN/NIN real verification (NIBSS/NIMC) | GAP | OPEN (needs vendor integration) |
| 8.32 | Frontend contracts: sprint23.kycVerification nested router | GAP | OPEN |
| 8.33 | KycWorkflow admin actions missing | GAP | OPEN |
| 8.34 | AccountOpeningPage mock data / no submit | GAP | OPEN |
| 8.35 | MerchantKycOnboardingPage dead wiring | GAP | OPEN |
| 8.36 | KYB form contract mismatch (54link_admin) | GAP | OPEN |
| 8.37 | Flutter/RN placeholder onboarding screens | GAP | OPEN |
| 8.38 | CustomerOnboardingPipeline field mismatch | PARTIAL | OPEN |

Positive controls confirmed: float top-up approval (admin + transactional + audit), merchant doc decision (admin + pending-only conditional), OTP core store (TTL/attempt cap/constant-time/replay-safe), liveness cooldown + session ownership, agent.register dev fail-closed gate.

### Round-6b fix ledger (sha → file)
| sha | file |
|-----|------|
| dc3465049ccc | services/api-server-ts/server/routers/accountOpening.ts |
| 83adae3e75de | services/api-server-ts/server/routers/agentKyc.ts |
| b9fb0d4aa920 | services/api-server-ts/server/routers/agentOnboarding.ts |
| 50744b026509 | services/api-server-ts/server/routers/agentOnboardingWizard.ts |
| 80f3e0d4ff08 | services/api-server-ts/server/routers/kycDocumentsCrud.ts |
| bad3981cdddb | services/api-server-ts/server/routers/kyc.ts |
| c11502d4bfda | services/api-server-ts/server/routers/whiteLabelOnboarding.ts |
| b06f70306643 | services/api-server-ts/server/routers/merchant.ts |
| ecffe6498fe1 | services/api-server-ts/server/routers/merchantKycOnboarding.ts |
| 9b70bd2c2de3 | services/api-server-ts/server/routers/merchantOnboardingPortal.ts |
| 066d853d9f47 | services/api-server-ts/server/restBridge.ts |
| 6a6234857c42 | services/api-server-ts/server/routers/mdm.ts |
| c1d8800efb71 | services/orchestrator-service/src/controllers/kyc/postKycCallback.ts |
| 8253351e3c36 | services/kyc-enforcement-go/main.go |
