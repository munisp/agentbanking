import axios, { AxiosInstance } from "axios";
import * as https from "https";
import { readEnv } from "../config/readEnv.config";
import {
  ICreateAccountPayload,
  ICreateAccountResponse,
  ICreateBankPayload,
} from "../types/account";

class AccountService {
  private _axiosInstance: AxiosInstance;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: readEnv("ACCOUNT_SVC_URL"),
      headers: {
        "content-type": "application/json",
      },
      httpsAgent: new https.Agent({
        rejectUnauthorized: false,
      }),
    });
  }

  public async createAccount(
    payload: ICreateAccountPayload,
  ): Promise<ICreateAccountResponse> {
    try {
      const response = await this._axiosInstance.post("/account", payload, {
        headers: {
          "x-tenant-id": payload.tenant_id,
          "x-keycloak-id": payload.keycloak_id,
          "x-ledger-id": payload.ledger_id,
        },
      });
      return response.data;
    } catch (error: any) {
      if (error.response) {
        const detail =
          error.response.data?.message ?? error.response.data?.detail;
        const suffix = detail ? `: ${detail}` : "";
        throw new Error(
          `Account creation failed (status ${error.response.status})${suffix}`,
        );
      }
      throw new Error("Network error — account service unreachable");
    }
  }

  public async createBank(payload: ICreateBankPayload) {
    try {
      const response = await this._axiosInstance.post(`/bank`, payload, {
        headers: {
          "x-tenant-id": payload.tenant_id,
          "x-keycloak-id": payload.keycloak_id,
          "x-ledger-id": payload.ledger_id,
        },
      });
      return response.data;
    } catch (error: any) {
      if (error.response) {
        throw new Error(error.response.data?.message ?? "Bank creation failed");
      }
      throw new Error("Network error — account service unreachable");
    }
  }

  public async createMintAccount(
    payload: ICreateAccountPayload,
  ): Promise<ICreateAccountResponse> {
    try {
      const response = await this._axiosInstance.post(
        `/system/create-mint-account`,
        { ...payload, bank: null },
        {
          headers: {
            "x-tenant-id": payload.tenant_id,
            "x-keycloak-id": payload.keycloak_id,
            "x-ledger-id": payload.ledger_id,
          },
        },
      );
      return response.data;
    } catch (error: any) {
      if (error.response) {
        throw new Error(
          error.response.data?.message ?? "Account creation failed",
        );
      }
      throw new Error("Network error — account service unreachable");
    }
  }
}

export const accountService = new AccountService();
