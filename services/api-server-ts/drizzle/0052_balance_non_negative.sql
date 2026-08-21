-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 0052: money CHECK constraints (funds-flow integrity)
--
-- Adds database-level CHECK constraints so negative stored balances and
-- non-positive transaction amounts are rejected by PostgreSQL itself,
-- independent of application-layer validation:
--
--   agents."floatBalance"        >= 0   (agent float cannot go negative)
--   agents."commissionBalance"   >= 0
--   customers."walletBalance"    >= 0
--   merchants."walletBalance"    >= 0
--   transactions."amount"        >  0   (ledger rows are always positive;
--                                        direction is carried by "type")
--
-- DEFENSIVE ROLLOUT — READ BEFORE APPLYING:
-- Every constraint below is added NOT VALID. NOT VALID constraints are
-- enforced immediately for all NEW/UPDATED rows, but PostgreSQL does NOT scan
-- existing rows, so this migration cannot fail on dirty historical data.
--
-- After deploying, operators MUST verify existing data is clean and then
-- validate the constraints to gain the full table-scan guarantee:
--
--   -- 1. Find offending rows (must all return 0 rows):
--   SELECT id FROM agents       WHERE "floatBalance" < 0
--      OR "commissionBalance" < 0;
--   SELECT id FROM customers    WHERE "walletBalance" < 0;
--   SELECT id FROM merchants    WHERE "walletBalance" < 0;
--   SELECT id FROM transactions WHERE "amount" <= 0;
--
--   -- 2. Remediate any offenders, then:
--   ALTER TABLE agents       VALIDATE CONSTRAINT "agents_float_balance_non_negative";
--   ALTER TABLE agents       VALIDATE CONSTRAINT "agents_commission_balance_non_negative";
--   ALTER TABLE customers    VALIDATE CONSTRAINT "customers_wallet_balance_non_negative";
--   ALTER TABLE merchants    VALIDATE CONSTRAINT "merchants_wallet_balance_non_negative";
--   ALTER TABLE transactions VALIDATE CONSTRAINT "transactions_amount_positive";
--
-- NOTE: "Reversal" ledger rows must also store a positive "amount"; the
-- reversal semantics come from type='Reversal', not from a negative amount.
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
  -- agents.floatBalance >= 0
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'agents' AND column_name = 'floatBalance'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'agents'
      AND constraint_name = 'agents_float_balance_non_negative'
  ) THEN
    ALTER TABLE "agents"
      ADD CONSTRAINT "agents_float_balance_non_negative"
      CHECK ("floatBalance" >= 0) NOT VALID;
  END IF;

  -- agents.commissionBalance >= 0
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'agents' AND column_name = 'commissionBalance'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'agents'
      AND constraint_name = 'agents_commission_balance_non_negative'
  ) THEN
    ALTER TABLE "agents"
      ADD CONSTRAINT "agents_commission_balance_non_negative"
      CHECK ("commissionBalance" >= 0) NOT VALID;
  END IF;

  -- customers.walletBalance >= 0
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'customers' AND column_name = 'walletBalance'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'customers'
      AND constraint_name = 'customers_wallet_balance_non_negative'
  ) THEN
    ALTER TABLE "customers"
      ADD CONSTRAINT "customers_wallet_balance_non_negative"
      CHECK ("walletBalance" >= 0) NOT VALID;
  END IF;

  -- merchants.walletBalance >= 0
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'merchants' AND column_name = 'walletBalance'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'merchants'
      AND constraint_name = 'merchants_wallet_balance_non_negative'
  ) THEN
    ALTER TABLE "merchants"
      ADD CONSTRAINT "merchants_wallet_balance_non_negative"
      CHECK ("walletBalance" >= 0) NOT VALID;
  END IF;

  -- transactions.amount > 0
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'transactions' AND column_name = 'amount'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_name = 'transactions'
      AND constraint_name = 'transactions_amount_positive'
  ) THEN
    ALTER TABLE "transactions"
      ADD CONSTRAINT "transactions_amount_positive"
      CHECK ("amount" > 0) NOT VALID;
  END IF;
END $$;
