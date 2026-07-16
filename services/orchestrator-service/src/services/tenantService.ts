import { HttpMethod } from "@dapr/dapr";
import { readEnv } from "../config/readEnv.config";
import { daprClient } from "../lib/daprClient";
import { ICreateTenantPayload, ITenant } from "../types/tenant";

class TenantService {
  private APP_ID: string = readEnv("TENANT_SERVICE_APP_ID") as string;

  async getTenant(tenant_id: string) {
    const { tenant } = (await daprClient.invoke(this.APP_ID, `tenant/${tenant_id}`, HttpMethod.GET, {})) as {
      message: string;
      tenant: ITenant | null;
    };

    return tenant;
  }

  async createTenant(payload: ICreateTenantPayload) {
    const { tenant } = (await daprClient.invoke(
      this.APP_ID,
      "system/create-tenant",
      HttpMethod.POST,
      payload,
      {
        "x-tenant-id": payload.tenantId,
      }
    )) as { message: string; tenant: ITenant };

    return tenant;
  }

  async getKeycloakPublicKey(tenantId: string) {
    const { public_rsa_key } = (await daprClient.invoke(
      this.APP_ID,
      `tenant/keycloak-public-key/${tenantId}`,
      HttpMethod.GET,
      {}
    )) as { public_rsa_key: string };

    return public_rsa_key;
  }
}

export const tenantService = new TenantService();
