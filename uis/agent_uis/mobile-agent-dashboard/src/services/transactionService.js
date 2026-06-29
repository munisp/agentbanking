import * as SecureStore from "expo-secure-store";
import { accountApi, authHeaders, networkOperationsApi } from "./apiService";
import {
  isDeviceOnline,
  isTransientNetworkError,
  queueTransferForSync,
  startOfflineTransferSync,
} from "./offlineTransferQueue";

const PAYMENT_HUB_SWITCH_NAME = "mojaloop";
const PAYMENT_HUB_AMS_NAME = "core_banking";
const TRANSFER_ENDPOINT = "https://54agent.upi.dev/payment-hub/api/v1/transfers/initiate";

async function paymentHubHeaders() {
  const headers = await authHeaders();
  return {
    ...headers,
    "x-switch-name": PAYMENT_HUB_SWITCH_NAME,
    "x-ams-name": PAYMENT_HUB_AMS_NAME,
    "x-tenant-name":
      headers["x-tenant-id"] || headers["x-tenant-name"] || "default",
  };
}

class TransactionService {
  constructor() {
    this.syncStarted = false;
  }

  ensureSyncStarted() {
    if (this.syncStarted) {
      return;
    }

    this.syncStarted = true;
    startOfflineTransferSync(async (transferKind, payload) => {
      await this.sendTransferOnline(transferKind, payload);
    });
  }

  buildTransferPayload(transferKind, data, headers) {
    const commonPayload = {
      switch_name: PAYMENT_HUB_SWITCH_NAME,
      amount: Number(data.amount || 0).toFixed(2),
      currency: data.currency || "NGN",
      pin: data.pin,
    };

    if (transferKind === "external") {
      return {
        ...commonPayload,
        to: {
          idType: "ACCOUNT_ID",
          idValue: data.beneficiary_account_number || "",
          displayName: data.beneficiary_name || "Recipient",
        },
        from: {
          idType: "ACCOUNT_ID",
          idValue: data.from_account_number || data.from_account_id || "",
          displayName: data.sender_name || data.senderName || "Sender",
        },
        destination:
          data.destination ||
          data.beneficiary_bank_code ||
          data.beneficiary_bank ||
          headers["x-tenant-id"] ||
          headers["x-tenant-name"] ||
          "external-bank",
        note: data.narration || data.description || "Transfer",
      };
    }

    if (transferKind === "internal") {
      return {
        ...commonPayload,
        to: {
          idType: "ACCOUNT_ID",
          idValue: data.to_account_number || data.to_account_id || "",
          displayName: data.beneficiary_name || "Recipient",
        },
        from: {
          idType: "ACCOUNT_ID",
          idValue: data.from_account_number || data.from_account_id || "",
          displayName: data.sender_name || data.senderName || "Sender",
        },
        destination:
          headers["x-tenant-id"] || headers["x-tenant-name"] || "remittance",
        note: data.description || data.narration || "Transfer",
      };
    }

    return {
      ...commonPayload,
      to: {
        idType: "ACCOUNT_ID",
        idValue: data.to_account_number || data.to_account_id || data.payee || "",
        displayName: data.beneficiary_name || "Recipient",
      },
      from: {
        idType: "ACCOUNT_ID",
        idValue:
          data.from_account_number || data.from_account_id || data.payer || "",
        displayName: data.sender_name || data.senderName || "Sender",
      },
      destination:
        data.destination ||
        headers["x-tenant-id"] ||
        headers["x-tenant-name"] ||
        "remittance",
      note: data.narration || data.description || data.note || "Transfer",
    };
  }

  async sendTransferRequest(payload, headers) {
    const response = await fetch(TRANSFER_ENDPOINT, {
      method: "POST",
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(
        errorData.message ||
          errorData.error ||
          `Transfer failed with status ${response.status}`,
      );
      error.statusCode = response.status;
      throw error;
    }

    return response.json();
  }

  async sendTransferOnline(transferKind, data) {
    const headers = await paymentHubHeaders();
    const payload = this.buildTransferPayload(transferKind, data, headers);
    return this.sendTransferRequest(payload, headers);
  }

  async submitTransferWithOfflineFallback(transferKind, data) {
    this.ensureSyncStarted();

    const online = await isDeviceOnline();
    if (!online) {
      const queueId = await queueTransferForSync(transferKind, data);
      return {
        queued: true,
        queueId,
        message: "No internet. Transfer queued and will sync automatically.",
      };
    }

    try {
      const result = await this.sendTransferOnline(transferKind, data);
      return { queued: false, ...result };
    } catch (firstError) {
      if (firstError?.statusCode || !isTransientNetworkError(firstError)) {
        throw firstError;
      }

      // Network error on first attempt — wait briefly for SIM failover, then retry once
      await new Promise((resolve) => setTimeout(resolve, 2000));

      try {
        const result = await this.sendTransferOnline(transferKind, data);
        return { queued: false, ...result };
      } catch (retryError) {
        // Both attempts failed — queue for automatic sync when connectivity restores
        const queueId = await queueTransferForSync(transferKind, data);
        return {
          queued: true,
          queueId,
          message:
            "Network issue detected. Transfer queued and will sync automatically.",
        };
      }
    }
  }

  async getTransactions(filters = {}, page = 1, limit = 20) {
    try {
      // Get agent's keycloak ID
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Not authenticated");
      }

      // Get transactions from network operations API
      const response = await networkOperationsApi.listTransactions(
        keycloakId,
        filters,
        page,
        limit,
      );

      return response;
    } catch (error) {
      console.error("Error fetching transactions:", error);
      throw error;
    }
  }

  async getTransactionById(id) {
    try {
      const transaction = await networkOperationsApi.getTransaction(id);
      return transaction;
    } catch (error) {
      console.error("Error fetching transaction:", error);
      throw error;
    }
  }

  async getTransactionsByAccountNumber(accountNumber, page = 1, limit = 20) {
    try {
      const headers = await authHeaders();
      const baseUrl = "https://54agent.upi.dev";
      const url = `${baseUrl}/ledger/txn/account-number/${accountNumber}?limit=${limit}&page=${page}`;

      const response = await fetch(url, {
        method: "GET",
        headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Error fetching transactions by account:", error);
      throw error;
    }
  }

  async createTransaction(data) {
    try {
      return this.submitTransferWithOfflineFallback("generic", data);
    } catch (error) {
      console.error("Error creating transaction:", error);
      throw error;
    }
  }

  async createInternalTransfer(data) {
    try {
      return this.submitTransferWithOfflineFallback("internal", data);
    } catch (error) {
      console.error("Error creating internal transfer:", error);
      throw error;
    }
  }

  async createExternalTransfer(data) {
    try {
      return this.submitTransferWithOfflineFallback("external", data);
    } catch (error) {
      console.error("Error creating external transfer:", error);
      throw error;
    }
  }

  async getTransactionReceipt(id) {
    try {
      // Get the transaction details
      const transaction = await this.getTransactionById(id);

      // Format as a receipt
      return {
        transaction,
        formattedDate: new Date(
          transaction.created_at || transaction.timestamp,
        ).toLocaleString(),
        // Add any additional receipt formatting here
      };
    } catch (error) {
      console.error("Error fetching receipt:", error);
      throw error;
    }
  }

  async getAgentCashPosition() {
    try {
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("Not authenticated");
      }

      const cashPosition =
        await networkOperationsApi.getAgentCashPosition(keycloakId);
      return cashPosition;
    } catch (error) {
      console.error("Error fetching cash position:", error);
      throw error;
    }
  }
}

export const transactionService = new TransactionService();
export default transactionService;
