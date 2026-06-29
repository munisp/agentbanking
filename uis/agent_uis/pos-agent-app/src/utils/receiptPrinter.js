import * as SecureStore from "expo-secure-store";
import {
    beep,
    getPrinterStatus,
    initPrinter,
    printReceipt,
} from "../lib/sunmi";

const getTenantName = async () => {
  try {
    const raw = await SecureStore.getItemAsync("tenant_config");
    if (raw) {
      const cfg = JSON.parse(raw);
      return cfg?.name || null;
    }
  } catch {}
  return null;
};

/**
 * Printer status codes from Nexgo SDK
 */
const PrinterStatus = {
  OK: 0, // Printer ready
  OUT_OF_PAPER: 1, // No paper
  OVERHEAT: 2, // Printer overheated
  OTHER_ERROR: 3, // Other error
};

/**
 * Check printer status and throw error if not ready
 * Note: Negative values are SDK errors, positive values are printer states
 */
const checkPrinterReady = async () => {
  try {
    const status = await getPrinterStatus();

    // Handle SDK errors (negative values)
    if (status < 0) {
      console.warn(
        `Printer status check returned SDK error: ${status}, attempting to print anyway`,
      );
      // Don't throw - printer might still work
      return true;
    }

    // Handle printer state codes
    switch (status) {
      case PrinterStatus.OK:
        return true;
      case PrinterStatus.OUT_OF_PAPER:
        throw new Error(
          "Printer is out of paper. Please load paper and try again.",
        );
      case PrinterStatus.OVERHEAT:
        throw new Error(
          "Printer is overheated. Please wait for it to cool down.",
        );
      case PrinterStatus.OTHER_ERROR:
        throw new Error(
          "Printer error. Please check the printer and try again.",
        );
      default:
        console.warn(
          `Unknown printer status: ${status}, attempting to print anyway`,
        );
        return true;
    }
  } catch (error) {
    // If status check itself fails, log but don't block printing
    console.warn("Printer status check failed:", error.message);
    return true;
  }
};

/**
 * Format and print transaction receipt
 * @param {object} transaction - Transaction data
 * @param {object} options - Print options (agentName, agentPhone, storeAddress, etc.)
 */
export const printTransactionReceipt = async (transaction, options = {}) => {
  try {
    // Initialize printer first
    await initPrinter();

    // Check if printer has paper and is ready
    await checkPrinterReady();

    const lines = [];
    const now = new Date();
    const tenantName = await getTenantName();

    // Header
    lines.push({
      text: options.storeName || (tenantName ? `${tenantName} Agent Banking` : "Agent Banking"),
      fontSize: 24,
      align: "CENTER",
      isBold: true,
    });

    if (options.storeAddress) {
      lines.push({
        text: options.storeAddress,
        fontSize: 16,
        align: "CENTER",
      });
    }

    if (options.agentPhone) {
      lines.push({
        text: `Tel: ${options.agentPhone}`,
        fontSize: 16,
        align: "CENTER",
      });
    }

    lines.push({
      text: "================================",
      fontSize: 16,
      align: "CENTER",
    });

    // Receipt type
    const transactionType = getTransactionTypeLabel(transaction);
    lines.push({
      text: transactionType.toUpperCase(),
      fontSize: 20,
      align: "CENTER",
      isBold: true,
    });

    lines.push({
      text: "================================",
      fontSize: 16,
      align: "CENTER",
    });

    // Transaction details
    const transactionDate =
      transaction.date ||
      transaction.created_at ||
      transaction.timestamp ||
      now.toISOString();

    lines.push({
      text: `Date: ${new Date(transactionDate).toLocaleString()}`,
      fontSize: 16,
      align: "LEFT",
    });

    if (transaction.reference || transaction.transaction_id) {
      lines.push({
        text: `Ref: ${transaction.reference || transaction.transaction_id}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    lines.push({
      text: " ",
      fontSize: 16,
    });

    // Amount (large and prominent)
    lines.push({
      text: "AMOUNT",
      fontSize: 16,
      align: "LEFT",
    });

    const amount = parseFloat(transaction.amount || 0);
    const isCredit = transaction.type === "credit";

    lines.push({
      text: `${isCredit ? "+" : "-"}NGN ${amount.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
      fontSize: 32,
      align: "CENTER",
      isBold: true,
    });

    lines.push({
      text: " ",
      fontSize: 16,
    });

    // Transaction-specific details
    if (transaction.recipient || transaction.payer || transaction.payee) {
      const counterparty =
        transaction.recipient ||
        (isCredit ? transaction.payer : transaction.payee) ||
        "N/A";
      lines.push({
        text: `${isCredit ? "From" : "To"}: ${counterparty}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    // Account details
    if (transaction.payer_account_number) {
      lines.push({
        text: `Payer Account: ${transaction.payer_account_number}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    if (transaction.payee_account_number) {
      lines.push({
        text: `Payee Account: ${transaction.payee_account_number}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    // Card details (if card transaction)
    if (transaction.card_number) {
      lines.push({
        text: `Card: ****${transaction.card_number}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    if (transaction.card_slot_name) {
      lines.push({
        text: `Method: ${transaction.card_slot_name}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    if (transaction.account_type) {
      lines.push({
        text: `Account Type: ${transaction.account_type.toUpperCase()}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    // Note/Description
    if (transaction.note || transaction.description) {
      lines.push({
        text: " ",
        fontSize: 16,
      });
      lines.push({
        text: `Note: ${transaction.note || transaction.description}`,
        fontSize: 16,
        align: "LEFT",
      });
    }

    lines.push({
      text: " ",
      fontSize: 16,
    });

    // Status
    const status = transaction.status || "COMPLETED";
    lines.push({
      text: `Status: ${status.toUpperCase()}`,
      fontSize: 20,
      align: "CENTER",
      isBold: true,
    });

    lines.push({
      text: "================================",
      fontSize: 16,
      align: "CENTER",
    });

    // Footer
    if (options.agentName) {
      lines.push({
        text: `Agent: ${options.agentName}`,
        fontSize: 16,
        align: "CENTER",
      });
    }

    if (options.agentId) {
      lines.push({
        text: `Agent ID: ${options.agentId}`,
        fontSize: 16,
        align: "CENTER",
      });
    }

    lines.push({
      text: " ",
      fontSize: 16,
    });

    lines.push({
      text: "Thank you for your business!",
      fontSize: 16,
      align: "CENTER",
    });

    lines.push({
      text: `Powered by ${tenantName || "54agent"}`,
      fontSize: 16,
      align: "CENTER",
      isBold: true,
    });

    lines.push({
      text: " ",
      fontSize: 16,
    });

    // Print the receipt
    await printReceipt(lines, 60);

    // Success beep
    await beep(200);

    return { success: true };
  } catch (error) {
    console.error("Print receipt error:", error);
    throw error;
  }
};

/**
 * Get human-readable transaction type label
 */
const getTransactionTypeLabel = (transaction) => {
  if (transaction.transaction_type) {
    return transaction.transaction_type;
  }

  if (transaction.payment_method === "card") {
    return transaction.type === "credit" ? "Card Deposit" : "Card Withdrawal";
  }

  if (transaction.type === "credit") {
    return "Credit";
  }

  if (transaction.type === "debit") {
    return "Debit";
  }

  return "Transaction";
};

/**
 * Print cash out receipt specifically
 */
export const printCashOutReceipt = async (
  transactionData,
  cardData,
  options = {},
) => {
  const receipt = {
    type: "debit",
    amount: transactionData.amount,
    date: new Date().toISOString(),
    reference: transactionData.reference,
    description: transactionData.description,
    card_number: cardData.cardLast4,
    card_slot_name: cardData.cardSlotName,
    account_type: transactionData.account_type,
    status: "COMPLETED",
    transaction_type: "Card Withdrawal",
  };

  return printTransactionReceipt(receipt, options);
};
