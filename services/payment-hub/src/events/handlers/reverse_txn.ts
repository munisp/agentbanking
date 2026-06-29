import logger from "../../config/logger.config";
import { CoreBankingApiClient } from "../../lib/CoreBankingApiClient";
import { IReverseTransactionEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { ReverseTransferEventSchema } from "../../validations/v1/events";

export const reverse_txn = async (data: IReverseTransactionEvent) => {
  try {
    logger.info(`reverse_txn event: ${JSON.stringify(data)}`);

    const payload = validateRequest(ReverseTransferEventSchema, data);

    const response = await CoreBankingApiClient.getInstance().fund_account(
      {
        payee: {
          partyIdType: payload.id_type,
          partyIdentifier: payload.id_value,
        },
        amount: {
          currency: payload.currency,
          amount: payload.amount,
        },
        source: "reverse_transfer",
        note: `Reversal for ${payload.local_transaction_id}`,
        transaction_id: payload.local_transaction_id,
      },
      payload.tenant,
    );

    logger.info(`reverse_txn completed: ${JSON.stringify(response)}`);
  } catch (error) {
    logger.error("reverse_txn failed:", error);
    throw error;
  }
};
