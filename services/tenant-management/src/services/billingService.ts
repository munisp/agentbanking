import { HttpMethod } from "@dapr/dapr";
import { readEnv } from "../config/readEnv.config";
import { daprClient } from "../lib/daprClient";
import { IGetBillingInfoResponse, IBillingProfile } from "../types/billing";

class BillingService {
  // cast the key to any to satisfy the typed readEnv signature for custom env keys
  private APP_ID: string = readEnv(("BILLING_SERVICE_APP_ID" as any)) as string;

  async createBillingProfile(tenantId: string, plan: string) {
    const { billing_profile } = (await daprClient.invoke(
      this.APP_ID,
      "billing",
      HttpMethod.PUT,
      {plan: plan},
      {
        "x-tenant-id": tenantId,
      }
    )) as { billing_profile: IBillingProfile };

    return billing_profile;
  }

  async getBillingInfo(tenantId: string) {
    const { billing_info } = (await daprClient.invoke(
      this.APP_ID,
      "billing/info",
      HttpMethod.GET,
      {},
      {
        "x-tenant-id": tenantId,
      }
    )) as { billing_info: IGetBillingInfoResponse };

    return billing_info;
  }
}

export const billingService = new BillingService();