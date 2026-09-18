-- Float top-up race-safety (audit fix):
-- the submit handler's "one pending top-up per agent" guard was an
-- application-level SELECT-then-INSERT, which races under concurrent
-- submissions. This partial unique index makes the guard race-safe at the
-- database level: a second pending request for the same agent is rejected by
-- the unique constraint no matter how interleaved the requests are.
CREATE UNIQUE INDEX IF NOT EXISTS float_topup_requests_one_pending_per_agent
  ON float_topup_requests ("agentId")
  WHERE status = 'pending';
