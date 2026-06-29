import fs from "fs";
import path from "path";
import logger from "../../../config/logger.config";
import { MojaloopConnectorApiClient } from "../../../lib/MojaloopConnectorApiClient";
import { asyncHandler } from "../../../middlewares/async";
import { tenantRepository } from "../../../repositories/tenantRepo";
import { CurrencyEnum, PartyIdTypeEnum } from "../../../utils/enums";

export const register_participants = asyncHandler(async (req, res) => {
  let tenants: Array<{ name: string; dfsp_id: string }> | undefined =
    req.body?.tenants;

  if (!tenants) {
    const tenantsPath = path.resolve(
      process.cwd(),
      "services/payment-hub/tenants.json",
    );
    const content = fs.readFileSync(tenantsPath, "utf8");
    tenants = JSON.parse(content) as Array<{ name: string; dfsp_id: string }>;
  }

  const results: Array<any> = [];

  for (const t of tenants) {
    try {
      const input = {
        tenant_name: t.name,
        identifier: t.dfsp_id,
        identifier_type: PartyIdTypeEnum.ACCOUNT_ID,
        currency: CurrencyEnum.NGN,
      };

      await MojaloopConnectorApiClient.getInstance().register_participant(
        input,
      );

      // persist tenant if not exists
      const existing = await tenantRepository.getByName(t.name);
      if (!existing) {
        // saveEntity accepts a plain object for now
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const tenant = tenantRepository.create({
          name: t.name,
          dfsp_id: t.dfsp_id,
        });
        await tenantRepository.saveEntity(tenant);
      }

      results.push({ tenant: t.name, status: "registered" });
    } catch (error) {
      logger.error("error registering tenant", error);
      results.push({ tenant: t.name, status: "error", error: String(error) });
    }
  }

  return res.json({ results });
});

export default register_participants;
