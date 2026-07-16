import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import { IAgentProfilePayload } from "../types/agent";

class AgentService {
  private _axiosInstance: AxiosInstance;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: readEnv("AGENT_SVC_URL"),
      headers: {
        "content-type": "application/json",
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: false,
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
