import axios, { AxiosInstance } from "axios";
import { readEnv } from "../config/readEnv.config";
import { ICreateVfdSubWalletInput, ICreateVfdWalletInput, ICreateVfdWalletResponse } from "../types";
import logger from "../config/logger.config";

const url = readEnv("PROVIDER_PROXY_URL") as string;

export class ProviderProxyApiClient {
  private static __instance: ProviderProxyApiClient | null = null;
  private readonly clientAxios: AxiosInstance;

  private constructor() {
    this.clientAxios = axios.create({
      baseURL: url,
    });
  }

  static instance(): ProviderProxyApiClient {
    if (!ProviderProxyApiClient.__instance) {
      ProviderProxyApiClient.__instance = new ProviderProxyApiClient();
    }
    return ProviderProxyApiClient.__instance;
  }

  public async create_vfd_wallet(data: ICreateVfdWalletInput): Promise<ICreateVfdWalletResponse> {
    try {
      const response = await this.clientAxios.post("/open-account", data);
      return response.data;
    } catch (error: any) {
      console.error("Error creating VFD wallet:", error.response?.data);
      if (error.response?.data?.status == "929") {
        throw new Error("VFD_ERROR_929");
      }
      throw new Error(error.response.data.message || "Failed to create VFD wallet");
    }
  }

  public async create_vfd_sub_wallet(data: ICreateVfdSubWalletInput): Promise<ICreateVfdWalletResponse> {
    try {
      const response = await this.clientAxios.post("/open-sub-account", data);
      return response.data;
    } catch (error: any) {
      console.error("Error creating VFD sub-wallet:", error.response?.data);
      throw new Error(error.response.data.message || "Failed to create VFD wallet");
    }
  }
}
