import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import { IKycVerificationPayload, IKycVerificationResponse } from "../types/verification";

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
        rejectUnauthorized: false,
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
