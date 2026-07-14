/**
 * Mojaloop Callback Handlers & Quoting Flow — 54agent Platform
 *
 * Implements the FSPIOP callback patterns:
 * - Party resolution callbacks (PUT /parties/{Type}/{ID})
 * - Quote callbacks (PUT /quotes/{ID})
 * - Transfer callbacks (PUT /transfers/{ID})
 * - Settlement notifications
 * - Error callbacks
 */

const MOJALOOP_HUB_URL =
  process.env.MOJALOOP_HUB_URL ?? "http://localhost:4000";
const DFSP_ID = process.env.MOJALOOP_DFSP_ID ?? "pos-shell-dfsp";

export interface MojaloopQuote {
  quoteId: string;
  transactionId: string;
  payee: {
    partyIdInfo: {
      partyIdType: string;
      partyIdentifier: string;
      fspId: string;
    };
  };
  payer: {
    partyIdInfo: {
      partyIdType: string;
      partyIdentifier: string;
      fspId: string;
    };
  };
  amountType: "SEND" | "RECEIVE";
  amount: { amount: string; currency: string };
}

export interface MojaloopTransferCallback {
  transferId: string;
  transferState: "COMMITTED" | "RESERVED" | "ABORTED";
  completedTimestamp?: string;
  fulfilment?: string;
}

export interface MojaloopSettlement {
  id: number;
  state:
    | "PENDING_SETTLEMENT"
    | "PS_TRANSFERS_RECORDED"
    | "PS_TRANSFERS_COMMITTED"
    | "SETTLED";
  participants: Array<{
    id: number;
    accounts: Array<{
      id: number;
      netSettlementAmount: { amount: number; currency: string };
    }>;
  }>;
}

const pendingQuotes = new Map<
  string,
  { resolve: (v: any) => void; timer: ReturnType<typeof setTimeout> }
>();
const pendingTransfers = new Map<
  string,
  { resolve: (v: any) => void; timer: ReturnType<typeof setTimeout> }
>();

export async function requestQuote(quote: MojaloopQuote): Promise<any> {
  const headers: Record<string, string> = {
    "Content-Type": "application/vnd.interoperability.quotes+json;version=1.1",
    "FSPIOP-Source": DFSP_ID,
    "FSPIOP-Destination": quote.payee.partyIdInfo.fspId,
    Date: new Date().toUTCString(),
    Accept: "application/vnd.interoperability.quotes+json;version=1.1",
  };

  try {
    const res = await fetch(`${MOJALOOP_HUB_URL}/quotes`, {
      method: "POST",
      headers,
      body: JSON.stringify(quote),
      signal: AbortSignal.timeout(30000),
    });

    if (res.status === 202) {
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          pendingQuotes.delete(quote.quoteId);
          reject(new Error(`Quote ${quote.quoteId} timed out after 30s`));
        }, 30000);
        pendingQuotes.set(quote.quoteId, { resolve, timer });
      });
    }
    return null;
  } catch (err) {
    console.error("[Mojaloop] Quote request failed:", (err as Error).message);
    return null;
  }
}

export function handleQuoteCallback(quoteId: string, data: any): void {
  const pending = pendingQuotes.get(quoteId);
  if (pending) {
    clearTimeout(pending.timer);
    pending.resolve(data);
    pendingQuotes.delete(quoteId);
    console.log(`[Mojaloop] Quote ${quoteId} resolved`);
  }
}

export function handleTransferCallback(
  callback: MojaloopTransferCallback
): void {
  const pending = pendingTransfers.get(callback.transferId);
  if (pending) {
    clearTimeout(pending.timer);
    pending.resolve(callback);
    pendingTransfers.delete(callback.transferId);
    console.log(
      `[Mojaloop] Transfer ${callback.transferId} → ${callback.transferState}`
    );
  }
}

export async function handleSettlementNotification(
  settlement: MojaloopSettlement
): Promise<void> {
  console.log(
    `[Mojaloop] Settlement ${settlement.id} → ${settlement.state} (${settlement.participants.length} participants)`
  );
  for (const participant of settlement.participants) {
    for (const account of participant.accounts) {
      console.log(
        `  Participant ${participant.id}: ${account.netSettlementAmount.amount} ${account.netSettlementAmount.currency}`
      );
    }
  }
}

export function handleError(
  resourceType: string,
  resourceId: string,
  error: { errorCode: string; errorDescription: string }
): void {
  console.error(
    `[Mojaloop] Error on ${resourceType}/${resourceId}: ${error.errorCode} — ${error.errorDescription}`
  );
  if (resourceType === "quotes") {
    const pending = pendingQuotes.get(resourceId);
    if (pending) {
      clearTimeout(pending.timer);
      pending.resolve({ error });
      pendingQuotes.delete(resourceId);
    }
  }
  if (resourceType === "transfers") {
    const pending = pendingTransfers.get(resourceId);
    if (pending) {
      clearTimeout(pending.timer);
      pending.resolve({ error });
      pendingTransfers.delete(resourceId);
    }
  }
}

export function getStats() {
  return {
    pendingQuotes: pendingQuotes.size,
    pendingTransfers: pendingTransfers.size,
  };
}
