import util from "util";
import { v4 } from "uuid";
import { uuid } from "uuidv4";
import logger from "../../config/logger.config";
import { readEnv } from "../../config/readEnv.config";
import { AppDataSource } from "../../database/dataSource";
import { CoreBankingApiClient } from "../../lib/CoreBankingApiClient";
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
import { InflowSchema, TInflowSchema } from "../../validations/v1";

export const process_inflow = async (data: TInflowSchema) => {
  try {
    logger.info(`process_inflow: ${util.inspect(data)}`);

    const parsed_data = validateRequest(InflowSchema, data);

    let updated_balance: string | null = null;

    try {
      const affected_account = parsed_data.payee_account_number;

      logger.info(
        `Fetching account balance for ${affected_account} on transaction completion: ${parsed_data.reference}`,
      );

      const core_account =
        await CoreBankingApiClient.getInstance().get_account(affected_account);

      logger.info(`Core account: ${JSON.stringify(core_account)}`);

      updated_balance = core_account.summary?.availableBalance;
    } catch {}

    await AppDataSource.manager.transaction(async (manager) => {
      const transaction = new Transaction();

      transaction.amount = parsed_data.amount;
      transaction.amount_type = AmountTypeEnum.RECEIVE;
      transaction.completed_at = parsed_data.timestamp;
      transaction.currency = parsed_data.currency || CurrencyEnum.NGN;
      transaction.fees = parsed_data.fees || "0";
      transaction.local_transaction_id = parsed_data.reference;
      transaction.note = `INFLOW_FROM_${parsed_data.payer_account_number}`;
      transaction.payee = {
        idType: PartyIdTypeEnum.ACCOUNT_ID,
        idValue: parsed_data.payee_account_number,
      };
      transaction.payeeFsp = readEnv("TENANT_NAME", "54agent") as string;
      transaction.payer = {
        idType: PartyIdTypeEnum.ALIAS,
        idValue: parsed_data.payer_account_number,
      };
      transaction.payerFsp = parsed_data.payer_fsp;
      transaction.quote_id = v4();
      transaction.quote_status = TransactionQuoteStatusEnum.agreed;
      transaction.status = TransactionStatusEnum.success;
      transaction.switch_name = parsed_data.switch_name;
      transaction.tenant = readEnv("TENANT_NAME", "54agent") as string;
      transaction.transaction_direction = TransactionDirectionEnum.incoming;
      transaction.transaction_id = v4();
      transaction.transaction_type = TransactionTypeEnum.TRANSFER;
      transaction.tag = parsed_data.tag || TransactionTypeEnum.TRANSFER;
      transaction.note = parsed_data.note || null;
      transaction.balance_after_transaction = (
        Number(updated_balance) + Number(parsed_data.amount)
      ).toString();

      await manager.save(transaction);

      // fund account
      await CoreBankingApiClient.getInstance().fund_account(
        {
          payee: {
            partyIdentifier: parsed_data.payee_account_number,
            partyIdType: PartyIdTypeEnum.ACCOUNT_ID,
          },
          amount: {
            amount: parsed_data.amount,
            currency: parsed_data.currency || CurrencyEnum.NGN,
          },
          source: parsed_data.payer_account_number,
          transaction_id: transaction.transaction_id,
          note:
            parsed_data.note ||
            `INFLOW_FROM_${parsed_data.payer_account_number}`,
        },
        transaction.tenant,
      );

      // emit inflow received event
      await daprClient.publishExternalEvent(PubSubTopics.inflow_received, {
        event_id: uuid(),
        event_type: PubSubTopics.inflow_received,
        timestamp: transaction.completed_at,
        version: 1,
        source: "paymenthub",
        payload: {
          ...transaction,
          processor: parsed_data.processor,
          metadata: parsed_data.metadata,
        },
        tenant: transaction.tenant,
      });
    });
  } catch (error) {
    logger.error(error);
    throw error;
  }
};
