import { v4 } from "uuid";
import { MainRepository } from "./mainRepository";
import { LookupOperation } from "../models/LookupOperation";
import { LookupResourceEnum, PartyIdTypeEnum } from "../utils/enums";

export class LookupOperationRepository extends MainRepository<LookupOperation> {
  constructor() {
    super(LookupOperation);
  }

  async getBySignature(
    identifier: string,
    identifier_type: PartyIdTypeEnum,
    resource: LookupResourceEnum
  ): Promise<LookupOperation | null> {
    return await this.repo.findOneBy({
      identifier,
      identifier_type,
      resource,
    });
  }

  async createRecord(
    workflow_id: string,
    identifier: string,
    identifier_type: PartyIdTypeEnum,
    resource: LookupResourceEnum
  ): Promise<LookupOperation> {
    await this.deleteIfExist({ identifier, identifier_type, resource });

    const id = v4();
    const op = this.repo.create({
      id,
      identifier,
      identifier_type,
      resource,
      workflow_id,
    });
    return this.saveEntity(op);
  }
}

export const lookupOpRepo = new LookupOperationRepository();
