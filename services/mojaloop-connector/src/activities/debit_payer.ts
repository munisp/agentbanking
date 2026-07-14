import { HttpMethod } from "@dapr/dapr";
import { readEnv } from "../config/readEnv.config";
import { daprClient } from "../services";
import { IPartyIdInfo, IPostTransfer } from "../types";
import { IFineractWithdrawResponse } from "../types/api.response";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";
import { IUpdateLocalTxnId } from "../types/events";
import { PubSubTopics } from "../utils/enums";

const logger = createLogger(extract_name_form_path(__filename));

export const debit_payer = async (
  payer: IPartyIdInfo,
  data: IPostTransfer
): Promise<IFineractWithdrawResponse> => {
  const result = (await daprClient.invoke(
    readEnv("CORE_BANKING_CONNECT_DAPR_ID", "core-banking") as string,
    "transfers/withdraw",
    HttpMethod.POST,
    {
      payer,
      amount: data.amount,
      transferId: data.transferId,
      holdId: data.holdId,
      bank: data.payeeFsp,
    }
  )) as IFineractWithdrawResponse;

  logger.info(`Debit Result ${JSON.stringify(result)}`);

  daprClient.publishTxnNotification<IUpdateLocalTxnId>(PubSubTopics.update_local_transaction_id, {
    transaction_id: data.transferId,
    local_transaction_id: (result.resourceId ?? result.transactionId).toString(),
  });

  return result;
};
