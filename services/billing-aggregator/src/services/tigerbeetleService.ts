import { type Transfer } from "tigerbeetle-node";
import { getTigerBeetleClient } from "../config/tigerbeetle.config";
import logger from "../config/logger.config";

// Ledger IDs map to ISO 4217 currency codes
const LEDGER: Record<string, number> = {
  NGN: 566,
  USD: 840,
  GBP: 826,
  EUR: 978,
};

// Account codes
const CODE_TENANT = 1;
const CODE_PLATFORM = 2;

// The platform clearing account debits tenant credit transfers.
// Its ID is configurable so it matches whatever account was created in the TB cluster.
const PLATFORM_ACCOUNT_ID = BigInt(process.env.TIGERBEETLE_PLATFORM_ACCOUNT_ID ?? "1");

function ledgerFor(currency: string): number {
  return LEDGER[currency.toUpperCase()] ?? LEDGER.NGN;
}

/**
 * Derive a stable 128-bit account ID from the billing record's DB id.
 * Offset by 1000 to avoid collision with reserved system accounts (1, 2, etc.).
 */
function tenantAccountId(billingDbId: number): bigint {
  return BigInt(billingDbId) + 1000n;
}

/**
 * Ensure a TigerBeetle account exists for a tenant billing record.
 * Idempotent — safe to call on every provisioning update.
 * Returns the account ID string to persist on TenantBillingEntity, or null on failure.
 */
export async function ensureTenantAccount(
  billingDbId: number,
  currency = "NGN"
): Promise<string | null> {
  const client = getTigerBeetleClient();
  if (!client) return null;

  const accountId = tenantAccountId(billingDbId);
  const ledger = ledgerFor(currency);

  const errors = await client.createAccounts([
    {
      id: accountId,
      debits_pending: 0n,
      debits_posted: 0n,
      credits_pending: 0n,
      credits_posted: 0n,
      user_data_128: 0n,
      user_data_64: BigInt(billingDbId),
      user_data_32: 0,
      reserved: 0,
      ledger,
      code: CODE_TENANT,
      flags: 0,
      timestamp: 0n,
    },
  ]);

  for (const e of errors) {
    // "exists_with_same_flags" means the account already exists with matching config — that's fine.
    if (!String(e.result).includes("exists")) {
      logger.error("[TigerBeetle] createAccount error", { billingDbId, result: e.result });
      return null;
    }
  }

  return accountId.toString();
}

/**
 * Post the client_revenue portion of a billing split as a TigerBeetle transfer.
 * Debit: platform clearing account  →  Credit: tenant account.
 * Returns the transfer ID string to persist on BillingLedgerEntity, or null on failure.
 */
export async function postBillingTransfer(params: {
  ledger_entry_id: number;
  tigerbeetle_account_id: string;
  client_revenue: number;
  currency: string;
}): Promise<string | null> {
  const client = getTigerBeetleClient();
  if (!client) return null;

  const amount = BigInt(Math.round(params.client_revenue * 100)); // smallest unit (kobo / cents)
  if (amount <= 0n) return null;

  // Unique transfer ID: timestamp (ms) shifted left + entry id as low bits
  const transferId =
    BigInt(Date.now()) * 1_000_000n + BigInt(params.ledger_entry_id % 1_000_000);

  const transfer: Transfer = {
    id: transferId,
    debit_account_id: PLATFORM_ACCOUNT_ID,
    credit_account_id: BigInt(params.tigerbeetle_account_id),
    amount,
    pending_id: 0n,
    user_data_128: 0n,
    user_data_64: BigInt(params.ledger_entry_id),
    user_data_32: 0,
    timeout: 0,
    ledger: ledgerFor(params.currency),
    code: CODE_TENANT,
    flags: 0,
    timestamp: 0n,
  };

  const errors = await client.createTransfers([transfer]);

  if (errors.length > 0) {
    logger.error("[TigerBeetle] createTransfer error", {
      ledger_entry_id: params.ledger_entry_id,
      result: errors[0].result,
    });
    return null;
  }

  return transferId.toString();
}
