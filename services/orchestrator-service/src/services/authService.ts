import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import {
  IAuthProfilePayload,
  IAuthProfileResponse,
  ISetupPassword,
} from "../types/auth";

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

class AuthService {
  private _axiosInstance: AxiosInstance;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: readEnv("AUTH_SVC_URL"),
      headers: {
        "content-type": "application/json",
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: !insecureTls,
      }),
    });
  }

  public async createAuthProfile(
    payload: IAuthProfilePayload,
  ): Promise<IAuthProfileResponse> {
    try {
      const response = await this._axiosInstance.post(
        "/auth",
        {
          email: payload.email,
          user_role: payload.user_role,
          platform_role: payload.platform_role, // v2.perm platform entity role
          tenant_role: payload.tenant_role, // v2.perm tenants entity role
        },
        {
          headers: {
            "x-tenant-id": payload.tenant_id,
            "x-keycloak-realm": payload.keycloak_realm,
            "x-keycloak-pub-key": payload.keycloak_pub_key,
          },
        },
      );
      return response.data;
    } catch (error: any) {
      if (error.response) {
        const errorMessage = error.response.data?.message ?? "Authentication profile creation failed";
        const errorCode = error.response.data?.code ?? "UNKNOWN";
        const statusCode = error.response.status;
        
        // Log detailed error information for debugging
        console.error("Auth profile creation error:", {
          email: payload.email,
          tenant_id: payload.tenant_id,
          status: statusCode,
          code: errorCode,
          message: errorMessage,
          fullError: JSON.stringify(error.response.data),
        });
        
        throw new Error(`${errorMessage} (Status: ${statusCode}, Code: ${errorCode})`);
      }
      console.error("Network error creating auth profile:", error.message);
      throw new Error("Network error — authentication service unreachable");
    }
  }

  public async setupPassword(payload: ISetupPassword): Promise<void> {
    try {
      const response = await this._axiosInstance.post(
        "/auth/setup-password",
        {
          keycloak_id: payload.keycloak_id,
          password: payload.password,
          confirm_password: payload.confirm_password,
        },
        {
          headers: {
            "x-tenant-id": payload.tenant_id,
            "x-keycloak-realm": payload.keycloak_realm,
            "x-keycloak-pub-key": payload.keycloak_pub_key,
          },
        },
      );
      return;
    } catch (error: any) {
      if (error.response) {
        const errorMessage = error.response.data?.message ?? "Password setup failed";
        const errorCode = error.response.data?.code ?? "UNKNOWN";
        const statusCode = error.response.status;
        
        console.error("Password setup error:", {
          keycloak_id: payload.keycloak_id,
          tenant_id: payload.tenant_id,
          status: statusCode,
          code: errorCode,
          message: errorMessage,
        });
        
        throw new Error(`${errorMessage} (Status: ${statusCode}, Code: ${errorCode})`);
      }
      console.error("Network error setting up password:", error.message);
      throw new Error("Network error — authentication service unreachable");
    }
  }
}

export const authService = new AuthService();
