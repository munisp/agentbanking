import axios, { AxiosInstance } from "axios";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { IRegisterParticipantInput } from "../types";
import { CurrencyEnum, PartyIdTypeEnum } from "../utils/enums";
import {
  TInitiateTransferSchemaMojaloop,
  TLookupPartySchemaMojaloop,
} from "../validations/v1";

const url = readEnv("MOJALOOP_CONNECTOR_URL") as string;

export class MojaloopConnectorApiClient {
  private static instance: MojaloopConnectorApiClient | null = null;
  private readonly clientAxios: AxiosInstance;

  private constructor() {
    this.clientAxios = axios.create({
      baseURL: url,
    });
  }

  static getInstance(): MojaloopConnectorApiClient {
    if (!MojaloopConnectorApiClient.instance) {
      MojaloopConnectorApiClient.instance = new MojaloopConnectorApiClient();
    }
    return MojaloopConnectorApiClient.instance;
  }

  public async initialize_transfer(
    body: TInitiateTransferSchemaMojaloop,
    headers?: Record<string, string>,
  ) {
    console.log("initialize transfer", body);
    console.log("with headers", headers);
    const { data } = await this.clientAxios.post("/transfers/initiate", body, {
      headers,
    });
    console.log("initialize transfer response", data);
    return data;
  }

  public async lookup_party(
    input: TLookupPartySchemaMojaloop,
    tenant_name: string,
  ) {
    const { data } = await this.clientAxios.post(
      "/parties/lookup",
      { ...input, tenant_name },
      {
        headers: { "fspiop-destination": input.destination },
      },
    );
    return data;
  }

  public async register_participant(input: IRegisterParticipantInput) {
    try {
      console.log("register_participant: init");

      const {
        currency = CurrencyEnum.NGN,
        identifier,
        identifier_type = PartyIdTypeEnum.MSISDN,
        tenant_name,
      } = input;

      const payload = {
        currency,
        identifier,
        identifier_type,
        tenant_name,
      };

      console.log("register_participant: payload", payload);

      const { data } = await this.clientAxios.post(
        "/participants/register",
        payload,
      );

      console.log("Response From Oracle", data);
    } catch (error) {
      logger.error("error registering participants", error);
    }
  }
}
