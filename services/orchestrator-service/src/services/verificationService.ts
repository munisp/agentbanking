import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import { IKycVerificationPayload, IKycVerificationResponse } from "../types/verification";

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

class VerificationService {
  private _axiosInstance: AxiosInstance;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: readEnv("VERIFICATION_SVC_URL"),
      headers: {
        "content-type": "application/json",
        "x-client-id": readEnv("VERIFICATION_SVC_CLIENT_ID"),
        "x-client-secret": readEnv("VERIFICATION_SVC_CLIENT_SECRET"),
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: !insecureTls,
      }),
    });
  }

  public async initializeKycVerification(
    payload: IKycVerificationPayload
  ): Promise<IKycVerificationResponse> {
    try {
      const response = await this._axiosInstance.post("/kyc/initialize-verification", {
        ...payload,
        identityProvider: payload.identityProvider || readEnv("VERIFICATION_SVC_IDP"),
      });
      return response.data;
    } catch (error: any) {
      if (error.response) {
        throw new Error(error.response.data?.message ?? "Kyc initialization failed");
      }
      throw new Error("Network error — verification service unreachable");
    }
  }
}

export const verificationService = new VerificationService();
