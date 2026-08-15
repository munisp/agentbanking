import axios, { AxiosInstance } from "axios";
import { readEnv } from "../config/readEnv.config";
import logger from "../config/logger.config";
import * as https from "https";
import { InitVerification, IVerifyFace, IVerifyFaceResult } from "../types/verification";
import { ShieldConfig } from "../types/config";

class ShieldApiClient {
  private _axiosInstance: AxiosInstance;
  private _baseUrl = readEnv("SHIELD_VERIFICATION_BASE_URL");
  private _apiKey = readEnv("SHIELD_VERIFICATION_API_KEY");
  private _logger = logger;

  constructor() {
    // TLS certificate verification is ON by default. It may ONLY be disabled
    // via the explicit opt-in env var SHIELD_API_INSECURE_TLS=true (e.g. for a
    // local dev stub with a self-signed cert). Never enable this in production:
    // disabling verification exposes identity-verification traffic to MITM.
    const insecureTls = readEnv("SHIELD_API_INSECURE_TLS") === "true";
    if (insecureTls) {
      // SEC-12 hardening: escalate from warn to startup-fatal in production.
      if (process.env.NODE_ENV === "production" || process.env.ENVIRONMENT === "production") {
        throw new Error(
          "FATAL: SHIELD_API_INSECURE_TLS=true is not allowed in production — TLS certificate verification must stay enabled."
        );
      }
      this._logger.warn(
        "WARNING: SHIELD_API_INSECURE_TLS=true — TLS certificate verification is DISABLED for the Shield identity client. Do not use in production."
      );
    }
    this._axiosInstance = axios.create({
      baseURL: this._baseUrl,
      headers: {
        "Content-Type": "application/json",
        "x-api-key": this._apiKey,
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: !insecureTls,
      }),
    });
  }

  async setupInternalClient(): Promise<ShieldConfig> {
    this._logger.info("Setting up shield internal client..");
    const response = await this._axiosInstance.post<ShieldConfig>(
      "/verification/register-verification-client",
      {
        clientName: "Newwave Verification Portal",
        redirectUrl: "",
        callbackUrl: `${readEnv("SHIELD_API_URL")}/notifications/shield`,
      }
    );
    this._logger.info(`setup_shield_internal_client_response: ${JSON.stringify(response.data)}`);
    return response.data;
  }

  async initVerification(payload: InitVerification) {
    const response = await this._axiosInstance.post(
      "/verification/verify-client-verification-session",
      payload
    );
    this._logger.info(`init_shield_verification_response: ${JSON.stringify(response.data)}`);
  }

  async verifyFace(payload: IVerifyFace): Promise<IVerifyFaceResult> {
    const response = await this._axiosInstance.post<IVerifyFaceResult>(
      "/verification/face-verification",
      payload
    );
    this._logger.info(`shield_face_verification_response: ${JSON.stringify(response.data)}`);
    return response.data;
  }
}

export const shieldApiClient = new ShieldApiClient();
