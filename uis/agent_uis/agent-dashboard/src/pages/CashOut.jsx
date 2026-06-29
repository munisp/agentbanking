import {
    ArrowUpRight,
    CheckCircle,
    CreditCard,
    RefreshCw,
    User,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { accountApi, agentApi, authHeaders } from "../utils/api";

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const CashOut = () => {
  const { user } = useAuth();
  const [agentProfile, setAgentProfile] = useState(null);
  const [accountDetails, setAccountDetails] = useState(null);
  const [recentWithdrawals, setRecentWithdrawals] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const [step, setStep] = useState(1);

  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [description, setDescription] = useState("");

  const [cardNumber, setCardNumber] = useState("");
  const [cardProvider, setCardProvider] = useState("");
  const [accountType, setAccountType] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [cvv, setCvv] = useState("");
  const [pin, setPin] = useState("");

  useEffect(() => {
    if (user) loadDashboardData();
  }, [user]);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const keycloakId = user?.keycloakId;
      if (!keycloakId) return;

      // Fetch agent profile
      const profileResp = await agentApi.getAgentByKeycloakId(keycloakId);
      setAgentProfile(profileResp.agent ?? profileResp);

      // Fetch account details
      let accountNumber = null;
      try {
        const accountResp = await accountApi.getAccountByKeycloakId(keycloakId);
        const account = accountResp.account ?? accountResp;
        setAccountDetails(account);
        accountNumber = account?.account_number;
      } catch (err) {
        console.error("Account fetch error:", err);
      }

      // Fetch transactions using the same pattern as Dashboard/Transactions
      if (accountNumber) {
        try {
          const res = await fetch(
            `${CORE_BANKING_URL}/ledger/txn/account-number/${accountNumber}?limit=10&page=1`,
            { headers: { ...authHeaders() } },
          );
          if (res.ok) {
            const data = await res.json();
            const allTxns = data.transactions || [];

            // Filter to only debits (withdrawals) — transactions where this account is the payer
            const withdrawals = allTxns.filter(
              (txn) => txn.payer_account_number === accountNumber,
            );

            setRecentWithdrawals(withdrawals);
          }
        } catch (txnErr) {
          console.error("Transactions fetch error:", txnErr);
        }
      }
    } catch (err) {
      console.error("CashOut data fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const detectCardProvider = (number) => {
    const cleaned = number.replace(/\s/g, "");
    if (
      cleaned.startsWith("4") ||
      cleaned.startsWith("50") ||
      cleaned.startsWith("65")
    )
      return "Verve";
    if (cleaned.startsWith("5")) return "Mastercard";
    if (cleaned.startsWith("6")) return "Verve";
    return "";
  };

  const formatCardNumber = (text) => {
    const cleaned = text.replace(/\s/g, "");
    const chunks = cleaned.match(/.{1,4}/g);
    return chunks ? chunks.join(" ") : cleaned;
  };

  const handleCardNumberChange = (e) => {
    const cleaned = e.target.value.replace(/\s/g, "");
    if (cleaned.length <= 19) {
      setCardNumber(cleaned);
      setCardProvider(detectCardProvider(cleaned));
    }
  };

  const handleExpiryChange = (e) => {
    let value = e.target.value.replace(/[^\d]/g, "");
    if (value.length >= 2) {
      value = value.substring(0, 2) + " / " + value.substring(2, 4);
    }
    setExpiryDate(value);
  };

  const handleContinue = (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!amount || parseFloat(amount) <= 0) {
      setErrorMessage("Please enter a valid withdrawal amount");
      return;
    }

    const amountInKobo = parseFloat(amount) * 100;
    if (accountDetails && amountInKobo > accountDetails.balance) {
      setErrorMessage("Insufficient balance in your agent wallet");
      return;
    }

    setStep(2);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");

    if (!cardNumber || cardNumber.length < 15) {
      setErrorMessage("Please enter a valid card number");
      return;
    }
    if (!expiryDate || expiryDate.length < 7) {
      setErrorMessage("Please enter card expiry date (MM / YY)");
      return;
    }
    if (!cvv || cvv.length < 3) {
      setErrorMessage("Please enter CVV");
      return;
    }
    if (!accountType) {
      setErrorMessage("Please select account type");
      return;
    }
    if (!pin || pin.length !== 4) {
      setErrorMessage("Please enter 4-digit PIN");
      return;
    }

    setIsLoading(true);

    try {
      const keycloakId = user?.keycloakId;
      if (!keycloakId)
        throw new Error("Agent ID not found. Please log in again.");

      await accountApi.createCashOut({
        agent_id: keycloakId,
        customer_card_number: cardNumber,
        amount: parseFloat(amount),
        currency: "NGN",
        reference: reference || `CASHOUT-${Date.now()}`,
        description: description || "Cash withdrawal",
        card_details: {
          card_number: cardNumber,
          expiry: expiryDate,
          cvv: cvv,
          account_type: accountType,
          pin: pin,
        },
      });

      setShowSuccess(true);
      setStep(1);
      setAmount("");
      setReference("");
      setDescription("");
      setCardNumber("");
      setCardProvider("");
      setAccountType("");
      setExpiryDate("");
      setCvv("");
      setPin("");

      loadDashboardData();
      setTimeout(() => setShowSuccess(false), 5000);
    } catch (err) {
      console.error("Cash Out error:", err);
      setErrorMessage(err.message || "Failed to process cash out transaction");
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "success":
        return "text-green-600 bg-green-100";
      case "pending":
        return "text-yellow-600 bg-yellow-100";
      case "failed":
        return "text-[var(--tenant-primary-color,#002082)] bg-[#E8F4F8]";
      default:
        return "text-gray-600 bg-gray-100";
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4 sm:p-6 lg:p-8">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="flex items-center gap-3 sm:gap-4">
            <div className="w-12 h-12 sm:w-16 sm:h-16 bg-[#E8F4F8] rounded-2xl flex items-center justify-center">
              <ArrowUpRight className="w-6 h-6 sm:w-8 sm:h-8 text-[var(--tenant-primary-color,#002082)]" />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-1">
                Cash Withdrawal
              </h1>
              <p className="text-gray-600 text-sm sm:text-base">
                Process customer cash withdrawals
              </p>
            </div>
          </div>
          <div className="w-full lg:w-auto bg-[#E8F4F8] border border-[#B3D9E8] rounded-xl px-4 sm:px-6 py-3 sm:py-4">
            <p className="text-[var(--tenant-primary-color,#002082)] text-sm font-semibold mb-1">
              Your Agent Balance
            </p>
            <p className="text-2xl sm:text-3xl font-bold text-[var(--tenant-primary-color,#003047)] break-all">
              ₦
              {accountDetails?.balance
                ? Number(accountDetails.balance).toLocaleString()
                : "0.00"}
            </p>
          </div>
        </div>
      </div>

      {/* Success Message */}
      {showSuccess && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
          <CheckCircle className="h-6 w-6 text-green-600" />
          <div>
            <p className="text-green-800 font-semibold">
              Cash Withdrawal Successful!
            </p>
            <p className="text-green-700 text-sm">
              The transaction has been processed successfully.
            </p>
          </div>
        </div>
      )}

      {/* Error Message */}
      {errorMessage && (
        <div className="bg-[#E8F4F8] border border-[#B3D9E8] rounded-xl p-4">
          <p className="text-red-800 font-semibold">Error</p>
          <p className="text-[var(--tenant-primary-color,#003047)] text-sm">{errorMessage}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Main Form */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-lg border border-gray-200 p-4 sm:p-6">
          {/* Step 1: Amount */}
          {step === 1 && (
            <>
              <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                <CreditCard className="w-6 h-6 text-[var(--tenant-primary-color,#002082)]" />
                Cash Withdrawal Transaction
              </h2>

              <form onSubmit={handleContinue} className="space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Withdrawal Amount
                  </label>
                  <div className="relative">
                    <span className="absolute left-4 top-3 text-gray-500 font-semibold">
                      ₦
                    </span>
                    <input
                      type="number"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="0.00"
                      min="0"
                      step="0.01"
                      className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Reference (Optional)
                  </label>
                  <input
                    type="text"
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    placeholder="Transaction reference"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Description (Optional)
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Add a note..."
                    rows="3"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full bg-[var(--tenant-primary-color,#002082)] text-white py-3 px-6 rounded-xl font-semibold hover:bg-[var(--tenant-primary-color,#003047)] transition-all shadow-md hover:shadow-lg"
                >
                  Continue to Card Details
                </button>
              </form>
            </>
          )}

          {/* Step 2: Card Details */}
          {step === 2 && (
            <>
              <div className="flex items-center justify-between mb-6">
                <button
                  onClick={() => setStep(1)}
                  className="text-gray-600 hover:text-gray-900 flex items-center gap-2 font-medium"
                >
                  <span>←</span> Back
                </button>
                <h2 className="text-xl font-bold text-gray-900">
                  Customer Card Details
                </h2>
                <div className="w-20"></div>
              </div>

              <div className="bg-[#E8F4F8] border border-[#B3D9E8] rounded-xl p-4 sm:p-6 mb-6 text-center">
                <p className="text-sm text-[var(--tenant-primary-color,#003047)] font-semibold mb-1">
                  Withdrawal Amount
                </p>
                <p className="text-3xl sm:text-4xl font-bold text-[var(--tenant-primary-color,#002082)] mb-1 break-all">
                  ₦{parseFloat(amount).toLocaleString()}.00
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Card Number
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={formatCardNumber(cardNumber)}
                      onChange={handleCardNumberChange}
                      placeholder="0000 0000 0000 0000"
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      required
                    />
                    {cardProvider && (
                      <span className="absolute right-4 top-3 text-xs font-bold text-[var(--tenant-primary-color,#002082)] bg-[#E8F4F8] px-2 py-1 rounded">
                        {cardProvider}
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Account Type
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {["Savings", "Current", "Not Sure"].map((type) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => setAccountType(type)}
                        className={`px-4 py-3 rounded-xl border-2 font-semibold transition-all ${
                          accountType === type
                            ? "border-[var(--tenant-primary-color,#002082)] bg-[#E8F4F8] text-[var(--tenant-primary-color,#003047)]"
                            : "border-gray-200 text-gray-600 hover:border-gray-300"
                        }`}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Expiry (MM / YY)
                    </label>
                    <input
                      type="text"
                      value={expiryDate}
                      onChange={handleExpiryChange}
                      placeholder="MM / YY"
                      maxLength="7"
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      CVV
                    </label>
                    <input
                      type="password"
                      value={cvv}
                      onChange={(e) =>
                        e.target.value.length <= 3 && setCvv(e.target.value)
                      }
                      placeholder="123"
                      maxLength="3"
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    PIN
                  </label>
                  <input
                    type="password"
                    value={pin}
                    onChange={(e) =>
                      e.target.value.length <= 4 && setPin(e.target.value)
                    }
                    placeholder="Enter 4-digit PIN"
                    maxLength="4"
                    className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)] focus:border-transparent"
                    required
                  />
                </div>

                <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
                  <CreditCard className="w-5 h-5 text-green-600" />
                  <p className="text-sm text-green-800 font-medium">
                    All card details are encrypted and secure
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-[var(--tenant-primary-color,#002082)] text-white py-3 px-6 rounded-xl font-semibold hover:bg-[var(--tenant-primary-color,#003047)] transition-all shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? "Processing..." : "Process Withdrawal"}
                </button>

                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="w-full text-gray-600 hover:text-gray-900 py-2"
                >
                  Cancel
                </button>
              </form>
            </>
          )}
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          {/* Agent Info */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <User className="w-5 h-5 text-[var(--tenant-primary-color,#002082)]" />
              Agent Details
            </h3>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-gray-500 font-medium">Name</p>
                <p className="text-sm font-semibold text-gray-900">
                  {user?.name || "—"}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 font-medium">Agent Code</p>
                <p className="text-sm font-mono font-semibold text-gray-900">
                  {agentProfile?.uin || user?.agentCode || "—"}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 font-medium">Account No.</p>
                <p className="text-sm font-mono font-semibold text-gray-900">
                  {accountDetails?.account_number || "—"}
                </p>
              </div>
            </div>
          </div>

          {/* Recent Withdrawals */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4">
              Recent Withdrawals
            </h3>

            {isLoading ? (
              <div className="flex items-center justify-center py-6">
                <RefreshCw className="h-5 w-5 text-[var(--tenant-primary-color,#002082)] animate-spin" />
                <span className="ml-2 text-sm text-gray-500">Loading...</span>
              </div>
            ) : recentWithdrawals.length === 0 ? (
              <div className="text-center py-6">
                <ArrowUpRight className="w-10 h-10 mx-auto text-gray-300 mb-2" />
                <p className="text-sm text-gray-500">No withdrawals yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentWithdrawals.slice(0, 5).map((withdrawal, index) => (
                  <div
                    key={withdrawal.id || index}
                    className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0"
                  >
                    <div>
                      <p className="text-sm font-semibold text-[var(--tenant-primary-color,#002082)]">
                        -₦{parseFloat(withdrawal.amount || 0).toLocaleString()}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(
                          withdrawal.created_at?.replace(" ", "T"),
                        ).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                      {withdrawal.note && (
                        <p className="text-xs text-gray-400 truncate max-w-30">
                          {withdrawal.note}
                        </p>
                      )}
                    </div>
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${getStatusColor(
                        withdrawal.status,
                      )}`}
                    >
                      {withdrawal.status || "Unknown"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CashOut;
