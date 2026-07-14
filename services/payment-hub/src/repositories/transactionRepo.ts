import { MainRepository } from "./mainRepository";
import {
  IQuoteInitiatedEvent,
  ITransactionCompletedEvent,
  ITransactionFailedEvent,
  ITransactionInitiatedEvent,
  IUpdateLocalTxnIdEvent,
} from "../types/events";
import { Transaction } from "../models/Transaction";
import {
  PhEventTypeEnum,
  PubSubTopics,
  TransactionDirectionEnum,
  TransactionQuoteStatusEnum,
  TransactionStatusEnum,
} from "../utils/enums";
import logger from "../config/logger.config";
import { publishGeneralEvent } from "../events/publishers/general";
import { CoreBankingApiClient } from "../lib/CoreBankingApiClient";
import { daprClient } from "../services";
import { uuid } from "uuidv4";
import { EXTERNAL_DAPR_EVENT_PUBSUB_NAME } from "../utils/constants";

export class TransactionRepository extends MainRepository<Transaction> {
  constructor() {
    super(Transaction);
  }

  async fetch_txn_records_by_txn_id(transaction_id: string, tenant: string) {
    return await this.repo.find({ where: { transaction_id, tenant } });
  }

  async fetch_txn_record_by_txn_id(transaction_id: string) {
    return await this.repo.findOne({
      where: { transaction_id: transaction_id },
    });
  }

  async fetch_txn_record_by_local_id(id: string) {
    return await this.repo.findOne({
      where: { local_transaction_id: id },
    });
  }

  async update_local_txn_id(payload: IUpdateLocalTxnIdEvent) {
    await this.repo.update(
      { transaction_id: payload.transaction_id },
      { local_transaction_id: payload.local_transaction_id }
    );

    const transactions = await this.find({
      where: {
        transaction_id: payload.transaction_id,
      },
    });

    logger.info(
      "update_local_txn_id transaction_id:",
      payload.transaction_id,
      "local_transaction_id:",
      payload.local_transaction_id
    );

    for (const transaction of transactions) {
      if (transaction.local_transaction_id && transaction.status == TransactionStatusEnum.success) {
        publishGeneralEvent(
          {
            transaction_id: transaction.id,
            operation_date: transaction.completed_at || new Date().toISOString(),
            local_transaction_id: transaction.local_transaction_id,
            reason: transaction.reason || undefined,
          },
          PhEventTypeEnum.TransactionSuccessful,
          transaction.transaction_id
        ).catch(console.error);
      }
    }
  }

  async failed_transaction(payload: ITransactionFailedEvent) {
    await this.repo.update(
      { transaction_id: payload.transaction_id },
      { reason: payload.reason, status: TransactionStatusEnum.failed }
    );

    const transactions = await this.repo.find({
      where: {
        transaction_id: payload.transaction_id,
      },
    });

    transactions.forEach(async (transaction) => {
      // If transaction is a reversal, update balance_after_transaction to the pre-transaction state
      if (payload.reason.toLowerCase() == "reversal" && transaction.balance_after_transaction) {
        const currentBalance = Number(transaction.balance_after_transaction ?? "0.0");
        const amount = Number(transaction.amount ?? "0.0");

        const newBalance =
          transaction.transaction_direction === TransactionDirectionEnum.outgoing
            ? currentBalance + amount
            : currentBalance - amount;

        await this.repo.update(
          {
            transaction_id: transaction.transaction_id,
            transaction_direction: transaction.transaction_direction,
          },
          {
            balance_after_transaction: newBalance.toString(),
          }
        );
      }

      // Refresh own hold_id if exists
      if (transaction.hold_id) {
        // Release funds, incase not already released
        await CoreBankingApiClient.getInstance().release_reserved_funds(
          transaction.payer.idValue,
          transaction.hold_id
        );

        logger.info(`Reason for transaction failure: ${payload.reason.toLowerCase()}`);

        // Re-reserve funds for retry only if not a reversal
        if (payload.reason.toLowerCase() != "reversal") {
          logger.info(`Re-reserving funds for failed transaction: ${transaction.transaction_id}`);
          const reserve_funds_response = await CoreBankingApiClient.getInstance().reserve_funds(
            transaction.payer.idValue,
            transaction.amount,
            "Retryable Transaction"
          );
          transaction.hold_id = reserve_funds_response?.resourceId || transaction.hold_id;
        } else {
          transaction.hold_id = null;
        }

        await this.repo.save(transaction);
      }

      // Refresh parent hold_id if exists
      if (transaction?.reference) {
        const parentTransaction = await this.repo.findOne({
          where: {
            transaction_id: transaction.reference,
          },
        });

        if (parentTransaction && parentTransaction.hold_id) {
          await CoreBankingApiClient.getInstance().release_reserved_funds(
            parentTransaction.payer.idValue,
            parentTransaction.hold_id
          );

          // Re-reserve funds for retry only if not a reversal
          if (payload.reason.toLowerCase() != "reversal") {
            const reserve_funds_response = await CoreBankingApiClient.getInstance().reserve_funds(
              parentTransaction.payer.idValue,
              parentTransaction.amount,
              "Failed Retriable Transaction"
            );
            parentTransaction.hold_id = reserve_funds_response?.resourceId || parentTransaction.hold_id;
          } else {
            parentTransaction.hold_id = null;
          }

          await this.repo.save(parentTransaction);
        }
      }

      publishGeneralEvent(
        {
          transaction_id: transaction.id,
          operation_date: transaction.failed_at || new Date().toISOString(),
          reason: transaction.reason || undefined,
        },
        PhEventTypeEnum.TransactionFailed,
        transaction.transaction_id
      ).catch(console.error);
    });
  }

  async reserve_transaction(transaction_id: string) {
    await this.repo.update({ transaction_id }, { status: TransactionStatusEnum.reserved });
  }

  async update_from_quote_agreed_event(quote_id: string) {
    const transaction = await this.repo.findOneBy({ quote_id });

    if (transaction) {
      transaction.quote_status = TransactionQuoteStatusEnum.agreed;
      await this.saveEntity(transaction);
    }
  }

  async update_from_quote_failed_event(quote_id: string, reason: string) {
    const transaction = await this.repo.findOneBy({ quote_id });

    if (transaction) {
      transaction.quote_status = TransactionQuoteStatusEnum.failed;
      transaction.failed_at = new Date().toISOString();
      transaction.reason = reason;
      transaction.status = TransactionStatusEnum.failed;
      await this.saveEntity(transaction);

      publishGeneralEvent(
        {
          transaction_id: transaction.id,
          operation_date: transaction.failed_at || new Date().toISOString(),
          reason: transaction.reason || undefined,
        },
        PhEventTypeEnum.TransactionFailed,
        transaction.transaction_id
      ).catch(console.error);
    }
  }

  async complete_txn(data: ITransactionCompletedEvent) {
    const transaction = await this.repo.findOne({
      where: {
        transaction_id: data.transaction_id,
        transaction_direction: data.direction,
      },
    });

    if (!transaction) return;

    // Safely fetch and store the user's account balance after transaction completion
    try {
      const affected_account =
        data.direction === TransactionDirectionEnum.outgoing
          ? transaction.payer.idValue
          : transaction.payee.idValue;

      logger.info(
        `Fetching account balance for ${affected_account} on transaction completion: ${transaction.transaction_id}`
      );

      const core_account = await CoreBankingApiClient.getInstance().get_account(affected_account, transaction.tenant);

      logger.info(`Core account: ${JSON.stringify(core_account)}`);

      if (core_account.summary?.availableBalance) {
        await this.repo.update(
          {
            transaction_id: data.transaction_id,
            transaction_direction: data.direction,
          },
          {
            balance_after_transaction: core_account.summary?.availableBalance.toString(),
          }
        );
      }
    } catch {}

    await this.repo.update(
      {
        transaction_id: data.transaction_id,
        transaction_direction: data.direction,
      },
      {
        note: data.note,
        fulfillment: data.fulfilment || "",
        status: TransactionStatusEnum.success,
        completed_at: data.completed_at || new Date().toISOString(),
        local_transaction_id: data.local_transaction_id,
      }
    );

    // Remove hold_id regardless of direction
    await this.repo.update(
      {
        transaction_id: data.transaction_id,
      },
      {
        hold_id: null,
      }
    );

    // Remove parent hold_id on current transaction success
    if (transaction?.reference) {
      await this.repo.update(
        {
          transaction_id: transaction?.reference,
        },
        {
          hold_id: null,
        }
      );
    }

    // Update missing fields in incoming transaction
    if (transaction.transaction_direction == TransactionDirectionEnum.incoming) {
      const transaction_outgoing = await this.repo.findOne({
        where: {
          transaction_id: data.transaction_id,
          transaction_direction: TransactionDirectionEnum.outgoing,
        },
      });

      if (transaction_outgoing) {
        await this.repo.update(
          {
            transaction_id: data.transaction_id,
            transaction_direction: TransactionDirectionEnum.incoming,
          },
          {
            tag: transaction_outgoing.tag || "",
            note: transaction_outgoing.note || data.note || "",
            reference: transaction_outgoing.reference || "",
            quote_status: TransactionQuoteStatusEnum.agreed,
          }
        );
      }
    }

    if (data.local_transaction_id) {
      // General Event
      await publishGeneralEvent(
        {
          transaction_id: transaction.id,
          operation_date: transaction.completed_at || new Date().toISOString(),
          local_transaction_id: data.local_transaction_id,
          reason: transaction.reason || undefined,
        },
        PhEventTypeEnum.TransactionSuccessful,
        transaction.transaction_id
      ).catch(console.error);
    }

    // This external event can be consumed by the middleware for
    // extra processing, say to debit a charge
    await daprClient.publishExternalEvent(
      PubSubTopics.payment_completed,
      {
        event_id: uuid(),
        event_type: PubSubTopics.payment_completed,
        timestamp: transaction.completed_at,
        version: 1,
        source: "paymenthub",
        payload: {
          ...transaction,
          ...data,
        },
        tenant: transaction.tenant,
      },
      EXTERNAL_DAPR_EVENT_PUBSUB_NAME
    );
  }

  async create_from_generic_initiate_event(
    data: ITransactionInitiatedEvent,
    status: TransactionStatusEnum = TransactionStatusEnum.pending
  ): Promise<Transaction> {
    const transaction = await this.saveEntity(
      this.repo.create({
        amount: data.amount.amount,
        quote_id: data.transaction_id,
        transaction_id: data.transaction_id,
        amount_type: data.amount_type,
        payeeFsp: data.destinationFsp,
        payerFsp: data.sourceFsp,
        fees: data.fees?.amount ?? "0.0",
        currency: data.amount.currency,
        payee: data.payee,
        payer: data.payer,
        transaction_direction: data.transaction_direction,
        tenant: data.tenant,
        transaction_type: data.transaction_type,
        tag: data.tag,
        note: data.note,
        local_transaction_id: data.local_transaction_id,
        status,
        hold_id: data.hold_id,
      })
    );

    publishGeneralEvent(transaction, PhEventTypeEnum.TransactionCreated, transaction.transaction_id).catch(
      console.error
    );

    return transaction;
  }

  async create_from_quote_initiated_event(data: IQuoteInitiatedEvent): Promise<Transaction> {
    const transaction = await this.saveEntity(
      this.repo.create({
        amount: data.amount.amount,
        quote_id: data.quote_id,
        transaction_id: data.transaction_id,
        transaction_type: data.transaction_type,
        amount_type: data.amount_type,
        payeeFsp: data.destinationFsp,
        payerFsp: data.sourceFsp,
        fees: data.fees?.amount ?? "0.0",
        currency: data.amount.currency,
        payee: data.payee,
        payer: data.payer,
        fulfillment: data.fulfillment,
        fulfillment_secret: data.fulfilment_secret,
        transaction_direction: data.transaction_direction,
        tenant: data.tenant,
        tag: data.tag || "",
        note: data.note || "",
        reference: data.reference || "",
        hold_id: data.hold_id,
      })
    );

    publishGeneralEvent(transaction, PhEventTypeEnum.TransactionCreated, transaction.transaction_id).catch(
      console.error
    );

    return transaction;
  }
}

export const transactionRepository = new TransactionRepository();
