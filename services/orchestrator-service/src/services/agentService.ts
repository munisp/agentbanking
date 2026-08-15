import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import { IAgentProfilePayload } from "../types/agent";

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

class AgentService {
  private _axiosInstance: AxiosInstance;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: readEnv("AGENT_SVC_URL"),
      headers: {
        "content-type": "application/json",
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: !insecureTls,
      }),
    });
  }

  public async createAgentProfile(payload: IAgentProfilePayload) {
    try {
      await this._axiosInstance.post("/agent", payload, {
        headers: {
          "x-tenant-id": payload.tenant_id,
          "x-keycloak-id": payload.keycloak_id,
        },
      });
    } catch (error: unknown) {
      if (error instanceof Error && "response" in error) {
        const axiosError = error as {
          response?: { data?: { message?: string } };
        };
        throw new Error(
          axiosError.response?.data?.message ?? "Agent profile creation failed",
        );
      }
      throw new Error("Network error — agent service unreachable");
    }
  }

  public async saveAgentKycState(
    kyc_url: string,
    tenant_id: string,
    keycloak_id: string,
  ) {
    try {
      await this._axiosInstance.post(
        `/agent/kyc/save`,
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
    } catch {
      // Fail gracefully.
    }
  }

  public async markKycComplete(tenant_id: string, keycloak_id: string) {
    try {
      await this._axiosInstance.post(
        `/agent/kyc/complete`,
        {},
        {
          headers: {
            "x-tenant-id": tenant_id,
            "x-keycloak-id": keycloak_id,
          },
        },
      );
    } catch {
      // Fail gracefully.
    }
  }
}

export const agentService = new AgentService();
