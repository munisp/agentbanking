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
    this._axiosInstance = axios.create({
      baseURL: this._baseUrl,
      headers: {
        "Content-Type": "application/json",
        "x-api-key": this._apiKey,
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: false,
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
