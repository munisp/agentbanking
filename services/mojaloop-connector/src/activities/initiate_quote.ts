import { readEnv } from "../config/readEnv.config";
import { MojaloopApiClient } from "../lib/MojaloopApiClient";
import { daprClient } from "../services";
import { IAmount, IQuotePayload } from "../types";
import { IQuoteInitiatedEvent } from "../types/events";
import { PubSubTopics, TransactionDirectionEnum } from "../utils/enums";

const tenant = readEnv("TENANT_NAME", "ucard") as string;

export const initiate_quote = async (
  fsp_id: string,
  destination: string,
  payload: IQuotePayload,
  fees: IAmount,
  hold_id?: string
) => {
  await MojaloopApiClient.getInstance().initiate_quote(fsp_id, destination, payload);

  await daprClient.publishTxnNotification<IQuoteInitiatedEvent>(PubSubTopics.quote_initiated, {
    tenant,
    amount: payload.amount,
    destinationFsp: destination,
    sourceFsp: fsp_id,
    quote_id: payload.quoteId,
    transaction_id: payload.transactionId,
    transaction_type: payload.transactionType.scenario,
    amount_type: payload.amountType,
    fees,
    payee: {
      idType: payload.payee.partyIdInfo.partyIdType,
      idValue: payload.payee.partyIdInfo.partyIdentifier,
    },
    payer: {
      idType: payload.payer.partyIdInfo.partyIdType,
      idValue: payload.payer.partyIdInfo.partyIdentifier,
    },
    tag: payload.tag,
    reference: payload.reference,
    note: payload.note,
    transaction_direction: TransactionDirectionEnum.outgoing,
    hold_id,
  });
};
