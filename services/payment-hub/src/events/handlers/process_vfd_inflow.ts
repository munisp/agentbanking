import util from "util";
import { v4 } from "uuid";
import logger from "../../config/logger.config";
import { readEnv } from "../../config/readEnv.config";
import { AppDataSource } from "../../database/dataSource";
import { CoreBankingApiClient } from "../../lib/CoreBankingApiClient";
import { VfdConnectorApiClient } from "../../lib/VfdConnectorApiClient";
import { Transaction } from "../../models/Transaction";
import { daprClient } from "../../services";
import {
    AmountTypeEnum,
    CurrencyEnum,
    PartyIdTypeEnum,
    PubSubTopics,
    TransactionDirectionEnum,
    TransactionQuoteStatusEnum,
    TransactionStatusEnum,
    TransactionTypeEnum,
} from "../../utils/enums";
import { validateRequest } from "../../validations";
import { TVfdInflowSchema, VfdInflowSchema } from "../../validations/v1";

export const process_vfd_inflow = async (data: object | string) => {
  try {
    if (typeof data === "string") {
      data = JSON.parse(data);
    }

    logger.info(`process_vfd_inflow: ${util.inspect(data)}`);

    const parsed_data = validateRequest(VfdInflowSchema, data);

    let updated_balance: string | null = null;

    try {
      logger.info(
        `Fetching account balance for ${parsed_data.account_number} on transaction completion: ${parsed_data.reference}`,
      );

      const core_account = await CoreBankingApiClient.getInstance().get_account(
        parsed_data.account_number,
      );

      logger.info(`Core account: ${JSON.stringify(core_account)}`);

      updated_balance = core_account.summary?.availableBalance;
    } catch {}

    await AppDataSource.manager.transaction(async (manager) => {
      const transaction = new Transaction();

      transaction.amount = parsed_data.amount;
      transaction.amount_type = AmountTypeEnum.RECEIVE;
      transaction.completed_at = parsed_data.timestamp;
      transaction.currency = CurrencyEnum.NGN;
      transaction.fees = "0";
      transaction.local_transaction_id = parsed_data.reference;
      transaction.note = parsed_data.originator_narration || null;
      transaction.payee = {
        idType: PartyIdTypeEnum.ACCOUNT_ID,
        idValue: parsed_data.account_number,
      };
      transaction.payeeFsp = readEnv("TENANT_NAME", "54agent") as string;
      transaction.payer = {
        idType: PartyIdTypeEnum.ACCOUNT_ID,
        idValue: parsed_data.originator_account_number,
      };
      transaction.payerFsp = parsed_data.originator_bank;
      transaction.quote_id = v4();
      transaction.quote_status = TransactionQuoteStatusEnum.agreed;
      transaction.status = TransactionStatusEnum.success;
      transaction.switch_name = parsed_data.switch_name!;
      transaction.tenant = readEnv("TENANT_NAME", "54agent") as string;
      transaction.transaction_direction = TransactionDirectionEnum.incoming;
      transaction.transaction_id = v4();
      transaction.transaction_type = TransactionTypeEnum.TRANSFER;
      transaction.tag = "INWARD TRANSFER";
      transaction.balance_after_transaction = (
        Number(updated_balance) + Number(parsed_data.amount)
      ).toString();

      await manager.save(transaction);

      await VfdConnectorApiClient.instance().create_notification(
        parsed_data as TVfdInflowSchema,
        "54agent",
      );

      await CoreBankingApiClient.getInstance().fund_account_with_external_id(
        `vfd_${parsed_data.account_number}`,
        {
          amount: {
            currency: CurrencyEnum.NGN,
            amount: parsed_data.amount,
          },
          source: parsed_data.originator_bank,
          note: parsed_data.originator_narration,
          transaction_id: transaction.transaction_id,
        },
        transaction.tenant,
      );

      await daprClient.publishExternalEvent(PubSubTopics.inflow_received, {
        event_id: v4(),
        event_type: PubSubTopics.inflow_received,
        timestamp: transaction.completed_at,
        version: 1,
        source: "paymenthub",
        payload: {
          ...transaction,
          processor: "vfd",
          metadata: {},
        },
        tenant: transaction.tenant,
      });
    });
  } catch (error) {
    logger.error(error);
    throw error;
  }
};
