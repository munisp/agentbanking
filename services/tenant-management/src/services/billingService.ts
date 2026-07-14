import { HttpMethod } from "@dapr/dapr";
import { readEnv } from "../config/readEnv.config";
import { daprClient } from "../lib/daprClient";
import { IGetBillingInfoResponse, IBillingProfile } from "../types/billing";
import logger from "../config/logger.config";

class BillingService {
  private APP_ID: string = readEnv("BILLING_SERVICE_APP_ID", "billing-aggregator");

  async createBillingProfile(tenantId: string, plan: string, billingPeriod: string) {
    try {
      logger.info("[BillingService] Creating billing profile", {
        tenantId,
        plan,
        billingPeriod,
        appId: this.APP_ID,
      });

      const { billing_profile } = (await daprClient.invoke(
        this.APP_ID,
        "billing",
        HttpMethod.PUT,
        { plan, billingPeriod },
        {
          "x-tenant-id": tenantId,
        }
      )) as { billing_profile: IBillingProfile };

      logger.info("[BillingService] Billing profile created successfully", {
        tenantId,
      });

      return billing_profile;
    } catch (error: any) {
      logger.error("[BillingService] Failed to create billing profile", {
        tenantId,
        plan,
        appId: this.APP_ID,
        errorMessage: error?.message,
        stack: error?.stack,
      });
      throw error;
    }
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