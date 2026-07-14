import { v4 } from "uuid";
// import createLogger from "../config/logger.config";
// import { extract_name_form_path } from "../utils/helpers";
import { MainRepository } from "./mainRepository";
import { InitiateTransactionOperation } from "../models/InitiateTransactionOperation";

// const logger = createLogger(extract_name_form_path(__filename));

export class InitiateTransferOperationRepository extends MainRepository<InitiateTransactionOperation> {
  constructor() {
    super(InitiateTransactionOperation);
  }

  async createRecord(
    workflow_id: string,
    sender: string,
    receiver: string,
    amount: number
  ): Promise<InitiateTransactionOperation> {
    const id = v4();
    const op = this.repo.create({
      id,
      sender,
      receiver,
      workflow_id,
      amount,
    });
    return this.saveEntity(op);
  }
}

export const initTrsOpRepo = new InitiateTransferOperationRepository();
