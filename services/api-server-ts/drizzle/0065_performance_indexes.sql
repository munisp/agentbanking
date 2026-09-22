-- Round-8 performance indexes (Wave B1 audit).
--
-- Checked against 0000-0064 before authoring; only GAPS are added here:
--   - tx_agentId_createdAt_idx / tx_status_createdAt_idx exist (0016), but the
--     composite (agentId, status, createdAt) used by agent-scoped
--     status-filtered lists did not.
--   - audit_action_idx (0016) and idx_audit_log_created_brin (0048, BRIN)
--     exist, but there was no (action, createdAt) composite and no BTREE on
--     createdAt (BRIN cannot serve ORDER BY createdAt DESC LIMIT n used by
--     dashboard activity feeds / restBridge).
--   - disputes had no index covering the SLA-overdue scan
--     (slaDeadlineAt IS NOT NULL AND status NOT IN ('resolved','rejected')).
--   - float_topup_requests had the unique one-pending-per-agent index (0054)
--     but no pending-queue listing index.
--
-- NOTE: CONCURRENTLY is intentionally NOT used — drizzle-kit runs migrations
-- inside a transaction where CREATE INDEX CONCURRENTLY is illegal in
-- Postgres. All statements are IF NOT EXISTS so re-application is safe.

CREATE INDEX IF NOT EXISTS "tx_agentId_status_createdAt_idx"
  ON "transactions" USING btree ("agentId", "status", "createdAt");--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "audit_action_createdAt_idx"
  ON "audit_log" USING btree ("action", "createdAt");--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "audit_createdAt_btree_idx"
  ON "audit_log" USING btree ("createdAt");--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "disputes_slaDeadlineAt_active_idx"
  ON "disputes" USING btree ("slaDeadlineAt")
  WHERE "slaDeadlineAt" IS NOT NULL AND "status" NOT IN ('resolved', 'rejected');--> statement-breakpoint

CREATE INDEX IF NOT EXISTS "topup_pending_createdAt_idx"
  ON "float_topup_requests" USING btree ("createdAt")
  WHERE "status" = 'pending';
