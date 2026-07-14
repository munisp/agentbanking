import axios, { AxiosInstance, isAxiosError } from "axios";
import util from "util";
import { readEnv } from "../config/readEnv.config";
import { CurrencyEnum, PartyIdTypeEnum } from "../utils/enums";
import createLogger from "../config/logger.config";
import { extract_name_form_path } from "../utils/helpers";
import { IPostTransfer } from "../types";

const logger = createLogger(extract_name_form_path(__filename));

export class MojaloopApiClient {
  private static instance: MojaloopApiClient | null = null;
  private readonly account_lookup_axios: AxiosInstance;
  private readonly quotes_axios: AxiosInstance;
  private readonly tranfers_axios: AxiosInstance;

  private constructor() {
    const accountLookupUrl = readEnv("ACCOUNT_LOOKUP_SERVICE") as string;
    const quotesUrl = readEnv("QUOTES_SERVICE") as string;
    const transfersUrl = readEnv("TRANSFERS_SERVICE") as string;

    // Validate that required service URLs are configured
    if (!accountLookupUrl) {
      throw new Error(
        "ACCOUNT_LOOKUP_SERVICE environment variable is not configured. Please set it to a valid Mojaloop ALS URL (e.g., http://mojaloop-als:3000)"
      );
    }
    if (!quotesUrl) {
      throw new Error(
        "QUOTES_SERVICE environment variable is not configured. Please set it to a valid Mojaloop quotes service URL (e.g., http://mojaloop-ml-api-adapter:3000)"
      );
    }
    if (!transfersUrl) {
      throw new Error(
        "TRANSFERS_SERVICE environment variable is not configured. Please set it to a valid Mojaloop transfers service URL (e.g., http://mojaloop-ml-api-adapter:3000)"
      );
    }

    this.account_lookup_axios = axios.create({
      baseURL: accountLookupUrl,
      headers: {
        "accept-encoding": "gzip, deflate",
        "cache-control": "no-cache",
      },
    });

    this.quotes_axios = axios.create({
      baseURL: quotesUrl,
      headers: {
        "accept-encoding": "gzip, deflate",
        "cache-control": "no-cache",
      },
    });

    this.tranfers_axios = axios.create({
      baseURL: transfersUrl,
      headers: {
        "accept-encoding": "gzip, deflate",
        "cache-control": "no-cache",
      },
    });
  }

  static getInstance(): MojaloopApiClient {
    if (!MojaloopApiClient.instance) {
      MojaloopApiClient.instance = new MojaloopApiClient();
    }
    return MojaloopApiClient.instance;
  }

  public async initiate_quote(
    fsp_id: string,
    destination: string,
    payload: any
  ) {
    const data = { ...payload };
    delete data.tag;
    delete data.note;
    delete data.reference;

    try {
      const headers = {
        "fspiop-source": fsp_id,
        "fspiop-destination": destination,
        "Content-Type":
          "application/vnd.interoperability.quotes+json;version=1.0",
        Accept: "application/vnd.interoperability.quotes+json;version=1.0",
        date: new Date().toUTCString(),
      };

      await this.quotes_axios.post("/quotes", data, {
        headers,
      });
    } catch (error) {
      if (isAxiosError(error)) {
        logger.info(
          `AXIOS ERROR ${error.status} ${error.response?.statusText}`
        );
        logger.info(util.inspect(error.response?.data || {}, false, 4));
      }

      throw error;
    }
  }

  public async register_participant(
    fsp_id: string,
    id_type: PartyIdTypeEnum,
    identifier: string,
    currency: string
  ) {
    logger.info(
      `registering participant with identifier ${identifier} fsp: ${fsp_id}`
    );

    const headers = {
      "fspiop-source": fsp_id,
      "Content-Type":
        "application/vnd.interoperability.participants+json;version=1.0",
      Accept: "application/vnd.interoperability.participants+json;version=1.0",
      date: new Date().toUTCString(),
    };

    const data = {
      fspId: fsp_id,
      currency,
    };

    await this.account_lookup_axios.post(
      `/participants/${id_type}/${identifier}`,
      data,
      { headers }
    );
  }

  public async lookup_party(
    fsp_id: string,
    id_type: PartyIdTypeEnum,
    identifier: string,
    destination?: string
  ) {
    const headers: { [x: string]: string } = {
      "fspiop-source": fsp_id,
      "Content-Type":
        "application/vnd.interoperability.parties+json;version=1.0",
      Accept: "application/vnd.interoperability.parties+json;version=1.0",
      date: new Date().toUTCString(),
    };

    if (destination) {
      headers["fspiop-destination"] = destination;
    }

    await this.account_lookup_axios.get(`/parties/${id_type}/${identifier}`, {
      headers,
    });
  }

  public async lookup_participants(
    fsp_id: string,
    id_type: PartyIdTypeEnum,
    identifier: string
  ) {
    const headers: { [x: string]: string } = {
      "fspiop-source": fsp_id,
      "Content-Type":
        "application/vnd.interoperability.participants+json;version=1.0",
      Accept: "application/vnd.interoperability.participants+json;version=1.0",
      date: new Date().toUTCString(),
    };

    await this.account_lookup_axios.get(
      `/participants/${id_type}/${identifier}`,
      {
        headers,
      }
    );
  }

  public async send_transfer_error(
    id: string,
    message: string,
    fsp_id: string,
    destination: string
  ) {
    const headers = {
      Accept: undefined,
      "fspiop-source": fsp_id,
      "fspiop-destination": destination,
      date: new Date().toUTCString(),
      "Content-Type":
        "application/vnd.interoperability.transfers+json;version=1.1",
    };

    await this.tranfers_axios.put(
      `/transfers/${id}/error`,
      { errorInformation: { errorDescription: message, errorCode: "5100" } },
      {
        headers,
      }
    );
  }

  public async send_transfer_res(
    fsp_id: string,
    destination: string,
    id: string,
    data: object
  ) {
    logger.info(`send_transfer_res ${JSON.stringify(data)}`);
    const headers = {
      Accept: undefined,
      "fspiop-source": fsp_id,
      "fspiop-destination": destination,
      date: new Date().toUTCString(),
      "Content-Type":
        "application/vnd.interoperability.transfers+json;version=1.1",
    };

    await this.tranfers_axios.put(`/transfers/${id}`, data, {
      headers,
    });
  }

  public async send_quote_error(
    id: string,
    message: string,
    fsp_id: string,
    destination: string
  ) {
    const headers = {
      Accept: undefined,
      "fspiop-source": fsp_id,
      "fspiop-destination": destination,
      date: new Date().toUTCString(),
      "Content-Type":
        "application/vnd.interoperability.quotes+json;version=1.1",
    };

    await this.tranfers_axios.put(
      `/quotes/${id}/error`,
      { errorInformation: { errorDescription: message, errorCode: "5100" } },
      {
        headers,
      }
    );
  }

  public async prepare_transfer(data: IPostTransfer) {
    const headers: { [x: string]: string } = {
      "fspiop-source": data.payerFsp,
      "fspiop-destination": data.payeeFsp,
      "Content-Type":
        "application/vnd.interoperability.transfers+json;version=1.1",
      Accept: "application/vnd.interoperability.transfers+json;version=1.1",
      date: new Date().toUTCString(),
    };

    await this.tranfers_axios.post("/transfers", data, {
      headers,
    });
  }

  public async send_party_res(
    res: any,
    fsp_id: string,
    identifier: string,
    id_type: string,
    destination: string
  ) {
    const headers = {
      "fspiop-source": fsp_id,
      "fspiop-destination": destination,
      "Content-Type":
        "application/vnd.interoperability.parties+json;version=1.0",
      Accept: "application/vnd.interoperability.parties+json;version=1.0",
      date: new Date().toUTCString(),
    };

    logger.info(`send res ${JSON.stringify(res)}`);

    await this.account_lookup_axios.put(
      `/parties/${id_type}/${identifier}`,
      JSON.stringify(res),
      {
        headers,
      }
    );
  }

  public async send_quote_res(
    quoteId: string,
    fsp_id: string,
    destination: string,
    response: {
      ilpPacket: string;
      condition: string;
      transferAmount: {
        amount: string;
        currency: CurrencyEnum;
      };
      expiration: string;
    }
  ) {
    const headers = {
      "fspiop-source": fsp_id,
      "fspiop-destination": destination,
      "Content-Type":
        "application/vnd.interoperability.quotes+json;version=1.0",
      Accept: undefined,
      date: new Date().toUTCString(),
    };

    logger.info(`send_quote_res ${JSON.stringify(response)}`);

    await this.quotes_axios.put(
      `/quotes/${quoteId}`,
      JSON.stringify(response),
      {
        headers,
      }
    );
  }
}
