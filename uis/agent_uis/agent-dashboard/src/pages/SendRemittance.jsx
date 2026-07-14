import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Building2,
  CheckCircle2,
  Clock,
  DollarSign,
  Globe,
  Loader2,
  Lock,
  Mail,
  Phone,
  RefreshCw,
  Send,
  TrendingUp,
  Unlock,
} from "lucide-react";
import React, { useCallback, useEffect, useMemo, useState } from "react";

// Constants
const SUPPORTED_CURRENCIES = {
  source: ["GBP", "USD", "EUR", "NGN", "GHS", "JPY", "AUD"],
  destination: ["NGN", "GHS", "USD", "GBP", "EUR", "JPY", "AUD"],
};

const CURRENCY_FLAGS = {
  GBP: "🇬🇧",
  USD: "🇺🇸",
  EUR: "🇪🇺",
  NGN: "🇳🇬",
  GHS: "🇬🇭",
  JPY: "🇯🇵",
  AUD: "🇦🇺",
  KES: "🇰🇪",
  ZAR: "🇿🇦",
};

const CURRENCY_SYMBOLS = {
  GBP: "£",
  USD: "$",
  EUR: "€",
  NGN: "₦",
  GHS: "₵",
  JPY: "¥",
  AUD: "A$",
  KES: "KSh",
  ZAR: "R",
};

const FEE_STRUCTURE = {
  "GBP-NGN": { fixed: 0.99, percentage: 0.5, margin: 0.3 },
  "USD-NGN": { fixed: 2.99, percentage: 0.5, margin: 0.4 },
  "EUR-NGN": { fixed: 1.99, percentage: 0.5, margin: 0.35 },
  "NGN-GHS": { fixed: 100, percentage: 1.0, margin: 0.5 },
  "NGN-KES": { fixed: 150, percentage: 1.0, margin: 0.5 },
  default: { fixed: 50, percentage: 1.5, margin: 0.5 },
};

const DELIVERY_METHODS = {
  NGN: [
    {
      value: "bank_transfer",
      label: "Bank Transfer",
      icon: "🏦",
      time: "Instant - 30 mins",
    },
    {
      value: "mobile_money",
      label: "Mobile Money",
      icon: "📱",
      time: "Instant",
    },
    {
      value: "cash_pickup",
      label: "Cash Pickup",
      icon: "💵",
      time: "1 - 4 hours",
    },
  ],
  GHS: [
    {
      value: "bank_transfer",
      label: "Bank Transfer",
      icon: "🏦",
      time: "1 - 2 hours",
    },
    {
      value: "mobile_money",
      label: "Mobile Money",
      icon: "📱",
      time: "Instant - 30 mins",
    },
    {
      value: "cash_pickup",
      label: "Cash Pickup",
      icon: "💵",
      time: "2 - 6 hours",
    },
  ],
  KES: [
    {
      value: "bank_transfer",
      label: "Bank Transfer",
      icon: "🏦",
      time: "1 - 3 hours",
    },
    {
      value: "mobile_money",
      label: "Mobile Money",
      icon: "📱",
      time: "Instant",
    },
  ],
  default: [
    {
      value: "bank_transfer",
      label: "Bank Transfer",
      icon: "🏦",
      time: "1 - 2 business days",
    },
  ],
};

const BPMGD_BANK = {
  code: "999999",
  name: "bpmgd",
};

const ensureBpmgdBank = (bankList) => {
  const exists = bankList.some(
    (bank) =>
      String(bank?.name || "").toLowerCase() === "bpmgd" ||
      String(bank?.tenant_id || "").toLowerCase() === "bpmgd",
  );

  if (exists) {
    return bankList;
  }

  return [...bankList, BPMGD_BANK];
};

const normalizeBankList = (data) => {
  const candidates = [
    data?.banks,
    data?.data?.banks,
    data?.data,
    data?.result?.banks,
    data?.result,
    data,
  ];

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return candidate;
    }
  }

  return [];
};

// Utility function to get authentication headers
const authHeaders = () => {
  const tenantConfig = JSON.parse(
    localStorage.getItem("tenant_config") || "{}",
  );
  const tenantId = tenantConfig.tenantId || tenantConfig.tenant_id || "";
  const ledgerId =
    tenantConfig.ledgerId ||
    tenantConfig.ledger_id ||
    localStorage.getItem("ledgerId") ||
    localStorage.getItem("ledger_id") ||
    "1";
  return {
    "Content-Type": "application/json",
    "x-tenant-id": tenantId,
    "x-tenant-name": tenantId,
    "x-keycloak-id": localStorage.getItem("keycloakId") || "",
    "x-ledger-id": ledgerId,
    "x-mint-id": tenantConfig.mintId || tenantConfig.mint_id || "1",
    "x-mint-account-id":
      tenantConfig.mintAccountId ||
      tenantConfig.mint_account_id ||
      "MINT_ACCOUNT",
    "x-keycloak-realm":
      tenantConfig.keycloakRealm || tenantConfig.keycloak_realm || "master",
    "x-keycloak-pub-key":
      tenantConfig.keycloakPubKey || tenantConfig.keycloak_pub_key || "",
    Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
  };
};

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";
const PAYMENT_HUB_SWITCH_NAME = "mojaloop";
const PAYMENT_HUB_AMS_NAME = "core_banking";
const SUPPORTED_PAYMENT_HUB_CURRENCIES = new Set([
  "NGN",
  "USD",
  "EUR",
  "GBP",
  "JPY",
  "AUD",
  "GHS",
]);

const normalizePaymentHubCurrency = (...candidates) => {
  for (const candidate of candidates) {
    if (typeof candidate !== "string") {
      continue;
    }

    const normalized = candidate.trim().toUpperCase();
    if (SUPPORTED_PAYMENT_HUB_CURRENCIES.has(normalized)) {
      return normalized;
    }
  }

  return "NGN";
};

const getTenantName = () => {
  try {
    const tenantConfig = JSON.parse(
      localStorage.getItem("tenant_config") || "{}",
    );
    return (
      tenantConfig.tenantId ||
      tenantConfig.tenant_id ||
      tenantConfig.name ||
      "default"
    );
  } catch {
    return "default";
  }
};

const resolveSourceAccountNumber = async (headerValues) => {
  try {
    const cachedAccounts = JSON.parse(
      localStorage.getItem("agentAccounts") || "[]",
    );
    if (Array.isArray(cachedAccounts) && cachedAccounts[0]?.account_number) {
      return cachedAccounts[0].account_number;
    }
  } catch {
    // Fallback to API lookup
  }

  const keycloakId = localStorage.getItem("keycloakId");
  if (!keycloakId) {
    return "";
  }

  try {
    const response = await fetch(
      `${CORE_BANKING_URL}/account/account/keycloak/${keycloakId}`,
      {
        headers: headerValues,
      },
    );

    if (!response.ok) {
      return "";
    }

    const data = await response.json();
    const accountsData = Array.isArray(data)
      ? data
      : data.account
        ? [data.account]
        : data.accounts || data.data || [];

    return accountsData[0]?.account_number || "";
  } catch {
    return "";
  }
};

const SendRemittance = () => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    recipientType: "bank",
    recipientName: "",
    recipient: "",
    bankCode: "",
    amount: "",
    currency: "GBP",
    destinationCurrency: "NGN",
    note: "",
    deliveryMethod: "bank_transfer",
  });

  const [exchangeRate, setExchangeRate] = useState(null);
  const [rateLock, setRateLock] = useState(null);
  const [rateRefreshCountdown, setRateRefreshCountdown] = useState(30);
  const [sourceAccounts, setSourceAccounts] = useState([]);
  const [selectedSourceAccountId, setSelectedSourceAccountId] = useState("");
  const [isLoadingSourceAccounts, setIsLoadingSourceAccounts] = useState(false);
  const [sourceAccountLoadError, setSourceAccountLoadError] = useState(null);
  const [banks, setBanks] = useState([]);
  const [isLoadingBanks, setIsLoadingBanks] = useState(false);
  const [bankLoadError, setBankLoadError] = useState(null);
  const [isRecipientValidated, setIsRecipientValidated] = useState(false);
  const [isValidatingRecipient, setIsValidatingRecipient] = useState(false);
  const [isLoadingRate, setIsLoadingRate] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [transactionReference, setTransactionReference] = useState(null);

  useEffect(() => {
    const loadBanks = async () => {
      setIsLoadingBanks(true);
      setBankLoadError(null);

      try {
        const response = await fetch(`${CORE_BANKING_URL}/account/bank`, {
          method: "GET",
          headers: authHeaders(),
        });

        if (!response.ok) {
          throw new Error("Failed to load banks");
        }

        const data = await response.json();
        const bankList = normalizeBankList(data);
        setBanks(ensureBpmgdBank(bankList));
      } catch {
        setBankLoadError("Failed to load banks");
        setBanks(ensureBpmgdBank([]));
      } finally {
        setIsLoadingBanks(false);
      }
    };

    loadBanks();
  }, []);

  useEffect(() => {
    const loadSourceAccounts = async () => {
      setIsLoadingSourceAccounts(true);
      setSourceAccountLoadError(null);

      try {
        const response = await fetch(
          `${CORE_BANKING_URL}/account/account/user/all`,
          {
            method: "GET",
            headers: authHeaders(),
          },
        );

        if (!response.ok) {
          throw new Error("Failed to load source accounts");
        }

        const data = await response.json();
        const accountCandidates = [
          data?.account,
          data?.accounts,
          data?.data?.account,
          data?.data?.accounts,
          data?.data,
          data,
        ];

        const accounts = accountCandidates.find(Array.isArray) || [];

        const eligible = accounts.filter(
          (account) =>
            String(account?.status || "").toLowerCase() === "active" &&
            ["primary", "savings", "current", "mint"].includes(
              String(account?.account_type || "").toLowerCase(),
            ) &&
            account?.account_number,
        );

        setSourceAccounts(eligible);

        if (eligible.length > 0) {
          const preferred =
            eligible.find(
              (account) =>
                String(account?.account_type || "").toLowerCase() === "primary",
            ) || eligible[0];

          setSelectedSourceAccountId(preferred.account_number);
          setFormData((prev) => ({
            ...prev,
            currency: preferred.account_currency || prev.currency,
          }));
        } else {
          setSourceAccountLoadError("No active source accounts available.");
        }
      } catch {
        setSourceAccountLoadError("Failed to load source accounts");
      } finally {
        setIsLoadingSourceAccounts(false);
      }
    };

    loadSourceAccounts();
  }, []);

  // Calculate fee breakdown
  const feeBreakdown = useMemo(() => {
    const amount = parseFloat(formData.amount) || 0;
    if (amount <= 0) return null;

    const corridor = `${formData.currency}-${formData.destinationCurrency}`;
    const fees = FEE_STRUCTURE[corridor] || FEE_STRUCTURE.default;
    const transferFee = fees.fixed + (amount * fees.percentage) / 100;
    const exchangeMargin = (amount * fees.margin) / 100;
    const networkFee = formData.deliveryMethod === "cash_pickup" ? 2.0 : 0;
    const totalFees = transferFee + networkFee;

    return {
      transferFee: parseFloat(transferFee.toFixed(2)),
      exchangeMargin: parseFloat(exchangeMargin.toFixed(2)),
      networkFee: parseFloat(networkFee.toFixed(2)),
      totalFees: parseFloat(totalFees.toFixed(2)),
      feePercentage: parseFloat(((totalFees / amount) * 100).toFixed(2)),
    };
  }, [
    formData.amount,
    formData.currency,
    formData.destinationCurrency,
    formData.deliveryMethod,
  ]);

  // Calculate received amount
  const receivedAmount = useMemo(() => {
    const amount = parseFloat(formData.amount) || 0;
    const rate = rateLock?.rate || exchangeRate?.rate || 0;
    return (amount * rate).toFixed(2);
  }, [formData.amount, rateLock, exchangeRate]);

  const selectedSourceAccount = useMemo(
    () =>
      sourceAccounts.find(
        (account) => account.account_number === selectedSourceAccountId,
      ) || null,
    [sourceAccounts, selectedSourceAccountId],
  );

  // Fetch exchange rate
  const fetchExchangeRate = useCallback(async () => {
    if (rateLock) return;
    setIsLoadingRate(true);
    setError(null);

    try {
      const response = await fetch(
        `${CORE_BANKING_URL}/cross-border/api/v1/fx-rates/latest?base_currency=${formData.currency}&target_currency=${formData.destinationCurrency}`,
        {
          method: "GET",
          headers: authHeaders(),
        },
      );

      if (!response.ok) throw new Error("Failed to fetch exchange rate");

      const data = await response.json();
      const rateRecord = Array.isArray(data)
        ? data[0]
        : data?.data?.[0] || data?.data || data;
      const rateValue =
        Number(
          rateRecord?.rate ||
            rateRecord?.exchange_rate ||
            rateRecord?.value ||
            0,
        ) || 0;
      setExchangeRate({
        from: formData.currency,
        to: formData.destinationCurrency,
        rate: rateValue || 1,
        lastUpdated: new Date().toISOString(),
      });
    } catch (err) {
      setError("Could not fetch exchange rate. Please try again.");
      setExchangeRate(null);
    } finally {
      setIsLoadingRate(false);
      setRateRefreshCountdown(30);
    }
  }, [formData.currency, formData.destinationCurrency, rateLock]);

  // Lock rate
  const handleLockRate = () => {
    if (!exchangeRate) return;
    const lockDuration = 600; // 10 minutes
    setRateLock({
      id: `lock_${Date.now()}`,
      from: formData.currency,
      to: formData.destinationCurrency,
      rate: exchangeRate.rate,
      amount: parseFloat(formData.amount) || 0,
      lockedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + lockDuration * 1000).toISOString(),
    });
  };

  // Unlock rate
  const handleUnlockRate = () => {
    setRateLock(null);
    fetchExchangeRate();
  };

  const handleSourceAccountChange = (accountNumber) => {
    setSelectedSourceAccountId(accountNumber);

    const selectedAccount = sourceAccounts.find(
      (account) => account.account_number === accountNumber,
    );

    if (selectedAccount) {
      setFormData((prev) => ({
        ...prev,
        currency: selectedAccount.account_currency || prev.currency,
      }));

      if (rateLock) {
        handleUnlockRate();
      }
    }
  };

  // Handle form input changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    if (
      name === "recipient" ||
      name === "bankCode" ||
      name === "recipientType"
    ) {
      setIsRecipientValidated(false);
    }

    if ((name === "currency" || name === "destinationCurrency") && rateLock) {
      handleUnlockRate();
    }
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (step === 1) {
      if (!isRecipientValidated) {
        if (formData.recipientType === "bank") {
          if (!formData.bankCode) {
            setError("Please select a bank for the recipient account.");
            return;
          }

          const selectedBank = banks.find(
            (bank) => String(bank.code) === String(formData.bankCode),
          );

          if (!selectedBank) {
            setError(
              "Selected bank is invalid. Please choose a different bank.",
            );
            return;
          }

          try {
            setIsValidatingRecipient(true);
            setError(null);

            const response = await fetch(
              `${CORE_BANKING_URL}/account/account/account-number/${formData.recipient}`,
              {
                method: "GET",
                headers: {
                  ...authHeaders(),
                  "x-tenant-id": selectedBank.name,
                },
              },
            );

            const result = await response.json();
            if (!response.ok) {
              throw new Error(
                result?.message || "Could not validate recipient account.",
              );
            }

            const account =
              result?.account || result?.data?.account || result?.data || {};

            setFormData((prev) => ({
              ...prev,
              recipientName: account?.name || prev.recipientName,
              destinationCurrency: account?.account_currency || prev.currency,
            }));
            setIsRecipientValidated(true);
          } catch (err) {
            setError(
              err?.message ||
                "Could not validate recipient account. Please check the account number and try again.",
            );
            return;
          } finally {
            setIsValidatingRecipient(false);
          }
        } else {
          setFormData((prev) => ({
            ...prev,
            destinationCurrency: prev.currency,
          }));
          setIsRecipientValidated(true);
        }

        return;
      }

      setStep(step + 1);
      setIsRecipientValidated(false);
      return;
    }

    if (step === 2) {
      setStep(3);
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const headerValues = authHeaders();
      const tenantName = getTenantName();
      const sourceAccountNumber =
        selectedSourceAccountId ||
        (await resolveSourceAccountNumber(headerValues));

      if (!sourceAccountNumber) {
        throw new Error("Unable to resolve sender account number");
      }

      const transferCurrency = normalizePaymentHubCurrency(
        formData.currency,
        formData.destinationCurrency,
      );

      const paymentHubPayload = {
        switch_name: PAYMENT_HUB_SWITCH_NAME,
        amount: Number(formData.amount || 0).toFixed(2),
        currency: transferCurrency,
        to: {
          idType: "ACCOUNT_ID",
          idValue: formData.recipient,
          displayName: formData.recipientName || "Recipient",
        },
        from: {
          idType: "ACCOUNT_ID",
          idValue: sourceAccountNumber,
          displayName:
            selectedSourceAccount?.name ||
            selectedSourceAccount?.account_name ||
            "Sender",
        },
        destination: tenantName,
        note: formData.note || "Transfer",
      };

      const response = await fetch(
        `${CORE_BANKING_URL}/payment-hub/api/v1/transfers/initiate`,
        {
          method: "POST",
          headers: {
            ...headerValues,
            "x-switch-name": PAYMENT_HUB_SWITCH_NAME,
            "x-ams-name": PAYMENT_HUB_AMS_NAME,
            "x-tenant-name": tenantName,
          },
          body: JSON.stringify(paymentHubPayload),
        },
      );

      const result = await response.json();

      if (!response.ok) {
        const detailMessage = Array.isArray(result?.detail)
          ? result.detail.map((d) => d.msg || d.type).join(", ")
          : null;
        throw new Error(
          detailMessage ||
            result.message ||
            result.error ||
            "Failed to process transfer",
        );
      }

      setTransactionReference(result.data?.reference || result.reference);
      setSuccessMessage(
        `Transfer initiated successfully! Reference: ${result.data?.reference || result.reference || "N/A"}`,
      );
    } catch (err) {
      setError(err.message || "Failed to process transfer");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Validate step
  const isStepValid = (stepNum) => {
    switch (stepNum) {
      case 1:
        if (!selectedSourceAccountId) {
          return false;
        }
        if (formData.recipientType === "bank") {
          return formData.recipient.length >= 5 && !!formData.bankCode;
        }
        return (
          formData.recipientName.length >= 2 && formData.recipient.length >= 5
        );
      case 2:
        return parseFloat(formData.amount) > 0 && !!exchangeRate;
      case 3:
        return true;
      default:
        return false;
    }
  };

  // Format time remaining for rate lock
  const formatTimeRemaining = (expiresAt) => {
    const remaining = Math.max(
      0,
      Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000),
    );
    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Get delivery methods for selected currency
  const deliveryMethods = useMemo(() => {
    return (
      DELIVERY_METHODS[formData.destinationCurrency] || DELIVERY_METHODS.default
    );
  }, [formData.destinationCurrency]);

  // Auto-fetch exchange rate on mount and currency change
  useEffect(() => {
    fetchExchangeRate();
  }, [fetchExchangeRate]);

  // Rate refresh countdown
  useEffect(() => {
    if (rateLock) return;
    const interval = setInterval(() => {
      setRateRefreshCountdown((prev) => {
        if (prev <= 1) {
          fetchExchangeRate();
          return 30;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [rateLock, fetchExchangeRate]);

  // Rate lock expiry check
  useEffect(() => {
    if (!rateLock) return;
    const interval = setInterval(() => {
      const expiresAt = new Date(rateLock.expiresAt).getTime();
      const remaining = Math.max(
        0,
        Math.floor((expiresAt - Date.now()) / 1000),
      );
      if (remaining <= 0) {
        setRateLock(null);
        fetchExchangeRate();
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [rateLock, fetchExchangeRate]);

  // Reset form after success
  const handleReset = () => {
    setFormData({
      recipientType: "bank",
      recipientName: "",
      recipient: "",
      bankCode: "",
      amount: "",
      currency: "GBP",
      destinationCurrency: "NGN",
      note: "",
      deliveryMethod: "bank_transfer",
    });
    setSelectedSourceAccountId("");
    setStep(1);
    setRateLock(null);
    setSuccessMessage(null);
    setTransactionReference(null);
    setError(null);
    fetchExchangeRate();
  };

  if (successMessage) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Transfer Successful!
            </h2>
            <p className="text-gray-600 mb-6">{successMessage}</p>
            {transactionReference && (
              <div className="bg-gray-50 rounded-lg p-4 mb-6">
                <p className="text-sm text-gray-500 mb-1">
                  Transaction Reference
                </p>
                <p className="text-lg font-mono font-semibold text-gray-900">
                  {transactionReference}
                </p>
              </div>
            )}
            <div className="flex gap-4 justify-center">
              <button
                onClick={handleReset}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center"
              >
                <Send className="w-5 h-5 mr-2" />
                Send Another Transfer
              </button>
              <button
                onClick={() => (window.location.href = "/transactions")}
                className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                View Transactions
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-3 sm:p-4 lg:p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">
            Send Remittance
          </h1>
          <p className="text-gray-600">
            Send money internationally with competitive rates
          </p>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {[1, 2, 3].map((stepNum) => (
              <div key={stepNum} className="flex items-center flex-1">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                    step >= stepNum
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-500"
                  }`}
                >
                  {stepNum}
                </div>
                {stepNum < 3 && (
                  <div
                    className={`flex-1 h-1 mx-2 ${
                      step > stepNum ? "bg-blue-600" : "bg-gray-200"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-2">
            <span className="text-sm text-gray-600">Recipient</span>
            <span className="text-sm text-gray-600">Amount</span>
            <span className="text-sm text-gray-600">Review</span>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5 mr-3" />
            <div className="flex-1">
              <p className="text-sm font-medium text-red-800">{error}</p>
              <button
                onClick={() => setError(null)}
                className="text-xs text-red-600 hover:text-red-800 mt-1"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 sm:p-6"
        >
          {/* Step 1: Recipient Details */}
          {step === 1 && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900">
                Who are you sending to?
              </h2>

              {/* Recipient Type Selection */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                {[
                  { type: "bank", label: "Bank", icon: Building2 },
                  { type: "phone", label: "Phone", icon: Phone },
                  { type: "email", label: "Email", icon: Mail },
                ].map(({ type, label, icon: Icon }) => (
                  <button
                    key={type}
                    type="button"
                    onClick={() =>
                      setFormData((prev) => ({ ...prev, recipientType: type }))
                    }
                    className={`p-4 rounded-lg border-2 transition-all ${
                      formData.recipientType === type
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <Icon
                      className={`w-6 h-6 mx-auto mb-2 ${
                        formData.recipientType === type
                          ? "text-blue-600"
                          : "text-gray-400"
                      }`}
                    />
                    <div
                      className={`text-sm font-medium ${
                        formData.recipientType === type
                          ? "text-blue-700"
                          : "text-gray-700"
                      }`}
                    >
                      {label}
                    </div>
                  </button>
                ))}
              </div>

              {/* Source Account */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Source Account
                </label>
                <select
                  name="sourceAccount"
                  value={selectedSourceAccountId}
                  onChange={(e) => handleSourceAccountChange(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                  required
                >
                  <option value="">
                    {isLoadingSourceAccounts
                      ? "Loading source accounts..."
                      : sourceAccountLoadError
                        ? sourceAccountLoadError
                        : "Select source account"}
                  </option>
                  {sourceAccounts.map((account) => (
                    <option
                      key={account.account_number}
                      value={account.account_number}
                    >
                      {account.name} • {account.account_number} •{" "}
                      {account.account_currency}
                    </option>
                  ))}
                </select>
                {selectedSourceAccount && (
                  <p className="text-xs text-gray-500 mt-1">
                    Source currency: {selectedSourceAccount.account_currency}
                  </p>
                )}
                <p className="text-xs text-gray-500 mt-1">
                  Transfer request currency follows the selected source account.
                </p>
              </div>

              {/* Recipient Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Recipient Name
                </label>
                <input
                  type="text"
                  name="recipientName"
                  value={formData.recipientName}
                  onChange={handleChange}
                  placeholder="Enter recipient's full name"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                  required
                />
              </div>

              {/* Recipient Identifier */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {formData.recipientType === "phone"
                    ? "Phone Number"
                    : formData.recipientType === "email"
                      ? "Email Address"
                      : "Account Number"}
                </label>
                <input
                  type={formData.recipientType === "email" ? "email" : "text"}
                  name="recipient"
                  value={formData.recipient}
                  onChange={handleChange}
                  placeholder={
                    formData.recipientType === "phone"
                      ? "+234 XXX XXX XXXX"
                      : formData.recipientType === "email"
                        ? "recipient@email.com"
                        : "0123456789"
                  }
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                  required
                />
              </div>

              {/* Bank Selection (if recipient type is bank) */}
              {formData.recipientType === "bank" && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Bank
                  </label>
                  <select
                    name="bankCode"
                    value={formData.bankCode}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
                    required
                  >
                    <option value="">Select a bank</option>
                    {banks.map((bank) => (
                      <option key={bank.code} value={bank.code}>
                        {bank.name}
                      </option>
                    ))}
                  </select>
                  {isLoadingBanks && (
                    <p className="text-xs text-gray-500 mt-2">
                      Loading banks...
                    </p>
                  )}
                  {bankLoadError && (
                    <p className="text-xs text-red-600 mt-2">{bankLoadError}</p>
                  )}
                </div>
              )}

              {/* Destination Currency */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Sending to
                </label>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                  {SUPPORTED_CURRENCIES.destination.map((curr) => (
                    <button
                      key={curr}
                      type="button"
                      onClick={() =>
                        setFormData((prev) => ({
                          ...prev,
                          destinationCurrency: curr,
                        }))
                      }
                      className={`p-3 rounded-lg border-2 transition-all ${
                        formData.destinationCurrency === curr
                          ? "border-blue-600 bg-blue-50"
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <div className="text-lg">{CURRENCY_FLAGS[curr]}</div>
                      <div className="text-xs font-medium mt-1">{curr}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Amount & Currency */}
          {step === 2 && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900">
                How much are you sending?
              </h2>
              {selectedSourceAccount && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600 mb-1">Sending from</p>
                  <p className="font-medium text-gray-900">
                    {selectedSourceAccount.name} •{" "}
                    {selectedSourceAccount.account_number} •{" "}
                    {selectedSourceAccount.account_currency}
                  </p>
                </div>
              )}

              {/* Source Currency */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  You send
                </label>
                <div className="flex gap-2">
                  <select
                    name="currency"
                    value={formData.currency}
                    onChange={handleChange}
                    className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  >
                    {SUPPORTED_CURRENCIES.source.map((curr) => (
                      <option key={curr} value={curr}>
                        {CURRENCY_FLAGS[curr]} {curr}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    name="amount"
                    value={formData.amount}
                    onChange={handleChange}
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                    className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                    required
                  />
                </div>
              </div>

              {/* Exchange Rate Display */}
              {exchangeRate && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center">
                      <Globe className="w-5 h-5 text-blue-600 mr-2" />
                      <span className="text-sm font-medium text-blue-900">
                        Exchange Rate
                      </span>
                    </div>
                    {rateLock ? (
                      <button
                        type="button"
                        onClick={handleUnlockRate}
                        className="flex items-center text-xs text-blue-600 hover:text-blue-700"
                      >
                        <Lock className="w-4 h-4 mr-1" />
                        Locked ({formatTimeRemaining(rateLock.expiresAt)})
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handleLockRate}
                        className="flex items-center text-xs text-blue-600 hover:text-blue-700"
                        disabled={
                          !formData.amount || parseFloat(formData.amount) <= 0
                        }
                      >
                        <Unlock className="w-4 h-4 mr-1" />
                        Lock Rate
                      </button>
                    )}
                  </div>
                  <div className="text-2xl font-bold text-blue-900">
                    1 {formData.currency} = {exchangeRate.rate.toFixed(4)}{" "}
                    {formData.destinationCurrency}
                  </div>
                  {!rateLock && (
                    <div className="flex items-center mt-2 text-xs text-blue-600">
                      <RefreshCw className="w-3 h-3 mr-1" />
                      Refreshes in {rateRefreshCountdown}s
                    </div>
                  )}
                </div>
              )}

              {/* Received Amount */}
              {parseFloat(formData.amount) > 0 && exchangeRate && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center mb-2">
                    <DollarSign className="w-5 h-5 text-green-600 mr-2" />
                    <span className="text-sm font-medium text-green-900">
                      Recipient gets
                    </span>
                  </div>
                  <div className="text-3xl font-bold text-green-900">
                    {CURRENCY_SYMBOLS[formData.destinationCurrency]}
                    {receivedAmount}
                  </div>
                </div>
              )}

              {/* Fee Breakdown */}
              {feeBreakdown && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3">
                    Fee Breakdown
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Transfer fee</span>
                      <span className="font-medium">
                        {CURRENCY_SYMBOLS[formData.currency]}
                        {feeBreakdown.transferFee}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Network fee</span>
                      <span className="font-medium">
                        {CURRENCY_SYMBOLS[formData.currency]}
                        {feeBreakdown.networkFee}
                      </span>
                    </div>
                    <div className="border-t border-gray-200 pt-2 mt-2 flex justify-between font-semibold">
                      <span className="text-gray-900">Total fees</span>
                      <span className="text-gray-900">
                        {CURRENCY_SYMBOLS[formData.currency]}
                        {feeBreakdown.totalFees} ({feeBreakdown.feePercentage}%)
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Delivery Method */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Delivery Method
                </label>
                <div className="space-y-2">
                  {deliveryMethods.map((method) => (
                    <label
                      key={method.value}
                      className={`flex items-center p-4 border-2 rounded-lg cursor-pointer transition-all ${
                        formData.deliveryMethod === method.value
                          ? "border-blue-600 bg-blue-50"
                          : "border-gray-200 hover:border-gray-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="deliveryMethod"
                        value={method.value}
                        checked={formData.deliveryMethod === method.value}
                        onChange={handleChange}
                        className="w-4 h-4 text-blue-600"
                      />
                      <span className="text-2xl mx-3">{method.icon}</span>
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">
                          {method.label}
                        </div>
                        <div className="text-sm text-gray-500 flex items-center">
                          <Clock className="w-3 h-3 mr-1" />
                          {method.time}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Note */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Note (Optional)
                </label>
                <textarea
                  name="note"
                  value={formData.note}
                  onChange={handleChange}
                  placeholder="Add a message for the recipient"
                  rows={3}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none"
                />
              </div>
            </div>
          )}

          {/* Step 3: Review & Confirm */}
          {step === 3 && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900">
                Review & Confirm
              </h2>

              {/* Transfer Summary */}
              <div className="bg-linear-to-br from-blue-50 to-blue-100 rounded-lg p-6">
                <div className="text-center mb-4">
                  <div className="text-sm text-blue-700 mb-1">You send</div>
                  <div className="text-3xl font-bold text-blue-900">
                    {CURRENCY_SYMBOLS[formData.currency]}
                    {parseFloat(formData.amount).toFixed(2)} {formData.currency}
                  </div>
                </div>
                <div className="flex justify-center mb-4">
                  <ArrowRight className="w-6 h-6 text-blue-600" />
                </div>
                <div className="text-center">
                  <div className="text-sm text-blue-700 mb-1">
                    Recipient gets
                  </div>
                  <div className="text-3xl font-bold text-blue-900">
                    {CURRENCY_SYMBOLS[formData.destinationCurrency]}
                    {receivedAmount} {formData.destinationCurrency}
                  </div>
                </div>
              </div>

              {selectedSourceAccount && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Source Account
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Name</span>
                      <span className="font-medium text-gray-900">
                        {selectedSourceAccount.name}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Account</span>
                      <span className="font-medium text-gray-900">
                        {selectedSourceAccount.account_number}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Currency</span>
                      <span className="font-medium text-gray-900">
                        {selectedSourceAccount.account_currency}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Recipient Details */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">
                  Recipient Details
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Name</span>
                    <span className="font-medium text-gray-900">
                      {formData.recipientName}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">
                      {formData.recipientType === "phone"
                        ? "Phone"
                        : formData.recipientType === "email"
                          ? "Email"
                          : "Account"}
                    </span>
                    <span className="font-medium text-gray-900">
                      {formData.recipient}
                    </span>
                  </div>
                  {formData.recipientType === "bank" && formData.bankCode && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Bank</span>
                      <span className="font-medium text-gray-900">
                        {
                          banks.find(
                            (b) => String(b.code) === String(formData.bankCode),
                          )?.name
                        }
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-gray-600">Delivery</span>
                    <span className="font-medium text-gray-900">
                      {
                        deliveryMethods.find(
                          (m) => m.value === formData.deliveryMethod,
                        )?.label
                      }
                    </span>
                  </div>
                </div>
              </div>

              {/* Exchange Rate Info */}
              {exchangeRate && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Exchange Rate
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Rate</span>
                      <span className="font-medium text-gray-900">
                        1 {formData.currency} = {exchangeRate.rate.toFixed(4)}{" "}
                        {formData.destinationCurrency}
                      </span>
                    </div>
                    {rateLock && (
                      <div className="flex items-center text-green-600 text-xs">
                        <Lock className="w-3 h-3 mr-1" />
                        Rate locked for{" "}
                        {formatTimeRemaining(rateLock.expiresAt)}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Fee Summary */}
              {feeBreakdown && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Total Costs
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Amount to send</span>
                      <span className="font-medium">
                        {CURRENCY_SYMBOLS[formData.currency]}
                        {parseFloat(formData.amount).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Fees</span>
                      <span className="font-medium">
                        {CURRENCY_SYMBOLS[formData.currency]}
                        {feeBreakdown.totalFees}
                      </span>
                    </div>
                    <div className="border-t border-gray-300 pt-2 mt-2 flex justify-between font-semibold">
                      <span className="text-gray-900">Total to pay</span>
                      <span className="text-gray-900">
                        {CURRENCY_SYMBOLS[formData.currency]}
                        {(
                          parseFloat(formData.amount) + feeBreakdown.totalFees
                        ).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {formData.note && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">
                    Note
                  </h3>
                  <p className="text-sm text-gray-700">{formData.note}</p>
                </div>
              )}
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between mt-8 pt-6 border-t border-gray-200">
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors flex items-center"
              >
                <ArrowLeft className="w-5 h-5 mr-2" />
                Back
              </button>
            )}
            <button
              type="submit"
              disabled={
                !isStepValid(step) || isSubmitting || isValidatingRecipient
              }
              className="ml-auto px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isValidatingRecipient ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Validating Recipient...
                </>
              ) : isSubmitting ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  Processing...
                </>
              ) : step === 3 ? (
                <>
                  <Send className="w-5 h-5 mr-2" />
                  Confirm Transfer
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="w-5 h-5 ml-2" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SendRemittance;
