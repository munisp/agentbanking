import axios, { AxiosError, AxiosInstance } from "axios";
import { randomUUID } from "crypto";
import logger from "../config/logger.config";
import { readEnv } from "../config/readEnv.config";
import { CurrencyEnum, PartyIdTypeEnum } from "../utils/enums";

interface ICoreBankingAccountCreateInput {
  fullname: string;
  externalId?: string;
  keycloakId?: string;
  accountExternalId?: string;
}

interface ICoreBankingManualFundInput {
  accountId: string;
  amount: {
    currency: CurrencyEnum;
    amount: string;
  };
  source: string;
  note?: string;
  reference: string;
  transaction_date: string;
}

interface ICoreBankingFundInput {
  payee: {
    partyIdType: PartyIdTypeEnum;
    partyIdentifier: string;
  };
  amount: {
    currency: CurrencyEnum;
    amount: string;
  };
  source: string;
  note?: string;
  transaction_id: string;
}

const accountServiceUrl = readEnv("ACCOUNT_SERVICE_URL") as string;
const paymentProcessingServiceUrl = readEnv(
  "PAYMENT_PROCESSING_SERVICE_URL",
) as string;
const defaultTenantName =
  (readEnv("TENANT_NAME", "54agent") as string) || "54agent";
const defaultLedgerId =
  (readEnv("CORE_BANKING_LEDGER_ID", "1") as string) || "1";
const defaultSystemKeycloakId =
  (readEnv("CORE_BANKING_SYSTEM_KEYCLOAK_ID", "payment-hub") as string) ||
  "payment-hub";

export class CoreBankingApiClient {
  private static instance: CoreBankingApiClient | null = null;
  private readonly accountAxios: AxiosInstance;
  private readonly paymentAxios: AxiosInstance;
  private readonly mintAccountCache = new Map<string, string>();

  private constructor() {
    this.accountAxios = axios.create({
      baseURL: accountServiceUrl,
    });

    this.paymentAxios = axios.create({
      baseURL: paymentProcessingServiceUrl,
    });
  }

  static getInstance(): CoreBankingApiClient {
    if (!CoreBankingApiClient.instance) {
      CoreBankingApiClient.instance = new CoreBankingApiClient();
    }

    return CoreBankingApiClient.instance;
  }

  private buildCoreHeaders(
    tenantName = defaultTenantName,
    keycloakId = defaultSystemKeycloakId,
  ) {
    return {
      "Content-Type": "application/json",
      "x-tenant-id": tenantName,
      "x-keycloak-id": keycloakId,
      "x-ledger-id": defaultLedgerId,
    };
  }

  private async ensureMintAccountId(tenantName = defaultTenantName) {
    const cachedMintId = this.mintAccountCache.get(tenantName);

    if (cachedMintId) {
      return cachedMintId;
    }

    const headers = this.buildCoreHeaders(tenantName);

    try {
      const response = await this.accountAxios.get("/system/get-mint-account", {
        headers,
      });
      const mintAccountId = response.data?.id?.toString();

      if (mintAccountId) {
        this.mintAccountCache.set(tenantName, mintAccountId);
        return mintAccountId;
      }
    } catch (error) {
      logger.warn(
        `Mint account fetch failed for tenant ${tenantName}: ${this.resolveErrorMessage(error)}`,
      );
    }

    const response = await this.accountAxios.post(
      "/system/create-mint-account",
      undefined,
      { headers },
    );
    const mintAccountId = response.data?.account?.id?.toString();

    if (!mintAccountId) {
      throw new Error("Failed to resolve mint account");
    }

    this.mintAccountCache.set(tenantName, mintAccountId);
    return mintAccountId;
  }

  private extractAccount(payload: any) {
    return payload?.account ?? payload;
  }

  private normalizeAccount(account: any) {
    const balance =
      account?.balance?.toString?.() ?? `${account?.balance ?? 0}`;

    return {
      ...account,
      savingsId: account?.id,
      clientId: account?.id,
      officeId: Number(defaultLedgerId),
      summary: {
        availableBalance: balance,
        accountNumber: account?.account_number,
      },
    };
  }

  private resolveAccountNumberOverride(input: ICoreBankingAccountCreateInput) {
    if (!input.accountExternalId) {
      return undefined;
    }

    if (input.accountExternalId.startsWith("vfd_")) {
      return input.accountExternalId.replace(/^vfd_/, "");
    }

    return input.accountExternalId;
  }

  private resolveErrorMessage(error: unknown) {
    if (axios.isAxiosError(error)) {
      return (
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.response?.data?.error ||
        error.message
      );
    }

    return error instanceof Error ? error.message : "Unknown error";
  }

  private async resolveAccountByIdentifier(
    identifier: string,
    tenantName = defaultTenantName,
  ) {
    const headers = this.buildCoreHeaders(tenantName);

    try {
      const response = await this.accountAxios.get(
        `/account/account-number/${identifier}`,
        { headers },
      );
      return this.normalizeAccount(this.extractAccount(response.data));
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError.response?.status && axiosError.response.status !== 404) {
        throw error;
      }
    }

    const response = await this.accountAxios.get(`/account/${identifier}`, {
      headers,
    });
    return this.normalizeAccount(this.extractAccount(response.data));
  }

  public async get_account(account: string, tenantName = defaultTenantName) {
    try {
      return await this.resolveAccountByIdentifier(account, tenantName);
    } catch (error) {
      throw new Error(
        this.resolveErrorMessage(error) || "Failed to get account",
      );
    }
  }

  public async create_account(
    input: ICoreBankingAccountCreateInput,
    tenantName = defaultTenantName,
  ) {
    try {
      const headers = this.buildCoreHeaders(
        tenantName,
        input.externalId || input.keycloakId || defaultSystemKeycloakId,
      );
      const accountNumber = this.resolveAccountNumberOverride(input);

      const response = await this.accountAxios.post(
        "/account",
        {
          name: input.fullname,
          account_number: accountNumber,
        },
        { headers },
      );

      const account = this.extractAccount(response.data);

      return {
        savingsId: account.id,
        resourceId: account.id,
        clientId: account.id,
        officeId: Number(defaultLedgerId),
        vfd_account_number: accountNumber || null,
        vfd_account_name: accountNumber ? input.fullname : null,
      };
    } catch (error) {
      throw new Error(
        this.resolveErrorMessage(error) || "Failed to create account",
      );
    }
  }

  public async create_sub_account(
    input: ICoreBankingAccountCreateInput,
    tenantName = defaultTenantName,
  ) {
    try {
      const headers = this.buildCoreHeaders(
        tenantName,
        input.externalId || input.keycloakId || defaultSystemKeycloakId,
      );
      const accountNumber = this.resolveAccountNumberOverride(input);

      const response = await this.accountAxios.post(
        "/account",
        {
          name: input.fullname,
          account_type: "savings",
          account_number: accountNumber,
        },
        { headers },
      );

      const account = this.extractAccount(response.data);

      return {
        savingsId: account.id,
        vfd_account_number: accountNumber || null,
        vfd_account_name: accountNumber ? input.fullname : null,
      };
    } catch (error) {
      throw new Error(
        this.resolveErrorMessage(error) || "Failed to create sub account",
      );
    }
  }

  public async fund_account(
    payload: ICoreBankingFundInput,
    tenantName = defaultTenantName,
  ) {
    try {
      const payeeAccount = await this.resolveAccountByIdentifier(
        payload.payee.partyIdentifier,
        tenantName,
      );
      const mintAccountId = await this.ensureMintAccountId(tenantName);

      return (
        await this.paymentAxios.post(
          "/payment/deposit",
          {
            recipient: Number(payeeAccount.id),
            amount: Number(payload.amount.amount),
            note: payload.note || payload.transaction_id,
          },
          {
            headers: {
              ...this.buildCoreHeaders(tenantName),
              "x-mint-account-id": mintAccountId,
            },
          },
        )
      ).data;
    } catch (error) {
      throw new Error(
        this.resolveErrorMessage(error) || "Failed to fund account",
      );
    }
  }

  public async manual_fund_account(
    payload: ICoreBankingManualFundInput,
    tenantName = defaultTenantName,
  ) {
    try {
      const mintAccountId = await this.ensureMintAccountId(tenantName);

      const response = await this.paymentAxios.post(
        "/payment/deposit",
        {
          recipient: Number(payload.accountId),
          amount: Number(payload.amount.amount),
          note: payload.note || payload.reference,
        },
        {
          headers: {
            ...this.buildCoreHeaders(tenantName),
            "x-mint-account-id": mintAccountId,
          },
        },
      );

      return {
        resourceId: response.data?.reference,
      };
    } catch (error) {
      throw new Error(
        this.resolveErrorMessage(error) || "Failed to fund account",
      );
    }
  }

  public async fund_account_with_external_id(
    externalId: string,
    data: Omit<ICoreBankingFundInput, "payee">,
    tenantName = defaultTenantName,
  ) {
    const accountNumber = externalId.replace(/^vfd_/, "");

    return this.fund_account(
      {
        ...data,
        payee: {
          partyIdType: PartyIdTypeEnum.ACCOUNT_ID,
          partyIdentifier: accountNumber,
        },
      },
      tenantName,
    );
  }

  public async reserve_funds(
    account_id: string,
    amount: string,
    reason: string,
  ) {
    const resourceId = randomUUID();

    logger.warn(
      `Soft-reserving funds for account ${account_id}, amount ${amount}. Reason: ${reason}. Token: ${resourceId}`,
    );

    return { resourceId };
  }

  public async release_reserved_funds(
    account_id: string,
    transaction_id: string,
  ) {
    logger.warn(
      `Soft-releasing funds for account ${account_id}, token ${transaction_id}`,
    );
    return { success: true };
  }
}
