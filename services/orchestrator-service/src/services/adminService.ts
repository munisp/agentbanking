import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import { IAdminProfilePayload } from "../types/admin";

// TLS certificate verification for service-to-service calls is ON by default.
// It may ONLY be disabled via the explicit opt-in env var
// SERVICE_TO_SERVICE_INSECURE_TLS=true (e.g. local dev stubs with self-signed
// certificates). In production this is a startup-fatal misconfiguration:
// disabling verification exposes inter-service traffic (KYC PII, credentials)
// to MITM. (Matches the ShieldApiClient pattern, escalated to fatal.)
const insecureTls = process.env.SERVICE_TO_SERVICE_INSECURE_TLS === "true";
if (insecureTls && (process.env.NODE_ENV === "production" || process.env.ENVIRONMENT === "production")) {
  throw new Error(
    "FATAL: SERVICE_TO_SERVICE_INSECURE_TLS=true is not allowed in production — TLS certificate verification must stay enabled."
  );
}

class AdminService {
  private _axiosInstance: AxiosInstance;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: readEnv("ADMIN_SVC_URL"),
      headers: {
        "content-type": "application/json",
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: !insecureTls,
      }),
    });
  }

  public async createAdminProfile(payload: IAdminProfilePayload) {
    try {
      await this._axiosInstance.post("/admin", payload, {
        headers: {
          "x-tenant-id": payload.tenant_id,
        },
      });
    } catch (error: any) {
      if (error.response) {
        throw new Error(
          error.response.data?.message ?? "Admin profile creation failed",
        );
      }
      throw new Error("Network error — admin service unreachable");
    }
  }

  public async saveAdminKycState(
    kyc_url: string,
    tenant_id: string,
    keycloak_id: string,
  ) {
    try {
      await this._axiosInstance.post(
        `/admin/kyc/save`,
        {
          kyc_url: kyc_url,
        },
        {
          headers: {
            "x-tenant-id": tenant_id,
            "x-keycloak-id": keycloak_id,
          },
        },
      );
    } catch (error: any) {
      // Fail gracefully.
    }
  }

  public async markKycComplete(tenant_id: string, keycloak_id: string) {
    try {
      await this._axiosInstance.post(
        `/admin/kyc/complete`,
        {},
        {
          headers: {
            "x-tenant-id": tenant_id,
            "x-keycloak-id": keycloak_id,
          },
        },
      );
    } catch (error: any) {
      // Fail gracefully.
    }
  }
}

export const adminService = new AdminService();
