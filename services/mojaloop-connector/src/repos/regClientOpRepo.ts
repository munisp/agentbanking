import { v4 } from "uuid";
import createLogger from "../config/logger.config";
import { RegisterClientOperation } from "../models/RegisterClientOperation";
import { IPutParticipantResponse } from "../types/workflow";
import { extract_name_form_path } from "../utils/helpers";
import { MainRepository } from "./mainRepository";

const logger = createLogger(extract_name_form_path(__filename));

export class RegisterClientOperationRepository extends MainRepository<RegisterClientOperation> {
  constructor() {
    super(RegisterClientOperation);
  }

  async getByPutResponse(
    data: IPutParticipantResponse
  ): Promise<RegisterClientOperation | null> {
    if (!data.fspId) {
      const message = "fspId is required";
      logger.info(message);
      throw new Error(message);
    }
    return await this.repo.findOneBy({
      identifier: data.identifier,
      identifier_type: data.identifier_type,
      fsp_id: data.fspId,
    });
  }

  async createRecord(
    workflow_id: string,
    data: IPutParticipantResponse
  ): Promise<RegisterClientOperation> {
    if (!data.fspId) {
      const message = "fspId is required";
      logger.info(message);
      throw new Error(message);
    }
    await this.deleteIfExist({
      fsp_id: data.fspId,
      identifier: data.identifier,
      identifier_type: data.identifier_type,
    });
    const id = v4();
    const op = this.repo.create({
      id,
      fsp_id: data.fspId,
      workflow_id,
      ...data,
    });
    return this.saveEntity(op);
  }
}

export const regClientOpRepo = new RegisterClientOperationRepository();
