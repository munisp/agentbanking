import { DataSource } from "typeorm";
import { Tenant } from "../../models/Tenant";
import * as path from "path";
import logger from "../../config/logger.config";
import { ISeeder } from "../../types";

// Load JSON data
const tenantData = require(path.resolve("./tenants.json"));

export class TenantSeeder implements ISeeder {
  tenantData: any;

  constructor() {
    this.tenantData = require(path.resolve("./tenants.json"));
  }

  async seed(dataSource: DataSource, forceSeed: boolean) {
    const tenantRepository = dataSource.getRepository(Tenant);

    if ((await tenantRepository.count()) > 0) {
      if (forceSeed) {
        logger.info("Clearing table...");
        await tenantRepository.clear();
      } else {
        logger.info("Ignore, seed Table already has data!");
        return;
      }
    }

    // Save JSON data to the database
    await tenantRepository.save(tenantData);

    logger.info("Database seeded successfully with tenants from JSON!");
  }
}
