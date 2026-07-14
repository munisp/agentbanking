import axios, { AxiosInstance } from "axios";
import { readEnv } from "../config/readEnv.config";
import * as z from "zod";
import { ProcessCardPaymentSchema } from "../validations/v1/card_payment";
import { EMVStandardResponse } from "../types/card_payment";
import logger from "../config/logger.config";

const url = readEnv("LUX_CONNECTOR_URL") as string;

export class LuxConnectorApiClient {
  private static instance: LuxConnectorApiClient | null = null;
  private readonly clientAxios: AxiosInstance;

  private constructor() {
    this.clientAxios = axios.create({
      baseURL: url,
    });
  }

  static getInstance(): LuxConnectorApiClient {
    if (!LuxConnectorApiClient.instance) {
      LuxConnectorApiClient.instance = new LuxConnectorApiClient();
    }
    return LuxConnectorApiClient.instance;
  }

  public async process_card_payment(
    payload: z.infer<typeof ProcessCardPaymentSchema>
  ): Promise<EMVStandardResponse> {
    try {
      const response = await this.clientAxios.post<EMVStandardResponse>(`/process-card-payment`, payload);
      return response.data;
    } catch (error) {
      logger.error("Failed to process payment: ", error);
      throw error;
    }
  }

  public async get_notifications(query: any, tenant: string) {
    try {
      const response = await this.clientAxios.get(`/transactions`, {
        params: { ...query, tenant },
      });
      return response.data;
    } catch (error) {
      logger.error("Failed to fetch notifications: ", error);
      throw error;
    }
  }
}
