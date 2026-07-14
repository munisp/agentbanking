import { Tenant } from "../models/Tenant";
import { MainRepository } from "./mainRepository";

export class TenantRepository extends MainRepository<Tenant> {
  constructor() {
    super(Tenant);
  }

  async getByName(name: string): Promise<Tenant | null> {
    return await this.repo.findOneBy({ name });
  }
}

export const tenantRepository = new TenantRepository();
