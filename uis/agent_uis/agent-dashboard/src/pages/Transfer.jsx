import { ArrowRight, Building2, CheckCircle, Send, Users } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

// Use Core Banking URL for transfers and accounts
const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";
const PAYMENT_HUB_SWITCH_NAME = "mojaloop";
const PAYMENT_HUB_AMS_NAME = "core_banking";

const Transfer = () => {
  const [transferForm, setTransferForm] = useState({
    from_account_id: "",
    from_account_number: "",
    to_account_id: "",
    to_account_number: "",
    amount: "",
    currency: "NGN",
    transfer_type: "internal",
    description: "",
    beneficiary_name: "",
    beneficiary_bank: "",
    beneficiary_bank_code: "",
    narration: "",
    pin: "",
  });

  const [accounts, setAccounts] = useState([]);
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [recentTransfers, setRecentTransfers] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Fetch accounts
  useEffect(() => {
    const fetchAccounts = async () => {
      setAccountsLoading(true);
      try {
        const keycloakId = localStorage.getItem("keycloakId");
        if (!keycloakId) {
          console.error("No keycloak ID found in localStorage");
          setAccountsLoading(false);
          return;
        }

        const res = await fetch(
          `${CORE_BANKING_URL}/account/account/keycloak/${keycloakId}`,
          {
            headers: authHeaders(),
          },
        );
        if (res.ok) {
          const data = await res.json();
          // The endpoint returns a single account object or an array
          const accountsData = Array.isArray(data)
            ? data
            : data.account
              ? [data.account]
              : data.accounts || data.data || [];
          setAccounts(accountsData);
          console.log("Fetched accounts for transfer:", accountsData);
        }
      } catch (err) {
        console.error("Failed to fetch accounts:", err);
      } finally {
        setAccountsLoading(false);
      }
    };

    const fetchRecentTransfers = async (accountNumber) => {
      if (!accountNumber) {
        setRecentTransfers([]);
        return;
      }
      try {
        const res = await fetch(
          `${CORE_BANKING_URL}/ledger/txn/account-number/${accountNumber}?limit=5&page=1`,
          {
            headers: authHeaders(),
          },
        );
        if (res.ok) {
          const data = await res.json();
          const transactions = data.transactions || [];
          setRecentTransfers(transactions);
        }
      } catch (err) {
        console.error("Failed to fetch recent transfers:", err);
      }
    };

    fetchAccounts().then(() => {
      // After accounts are fetched, get the agent's account number
      const keycloakId = localStorage.getItem("keycloakId");
      if (!keycloakId) return;
      // Try to get the account number from localStorage or from fetched accounts
      const accountsData =
        JSON.parse(localStorage.getItem("agentAccounts")) || [];
      const accountNumber = accountsData[0]?.account_number;
      if (accountNumber) {
        fetchRecentTransfers(accountNumber);
      }
    });
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      // Validate required fields
      if (!transferForm.from_account_id) {
        setErrorMessage("Please select source account");
        setIsSubmitting(false);
        return;
      }

      if (!transferForm.from_account_number) {
        setErrorMessage("Unable to resolve source account number");
        setIsSubmitting(false);
        return;
      }

      if (
        transferForm.transfer_type === "internal" &&
        // !transferForm.to_account_id &&
        !transferForm.to_account_number
      ) {
        setErrorMessage("Please select or enter destination account");
        setIsSubmitting(false);
        return;
      }

      if (
        transferForm.transfer_type === "external" &&
        (!transferForm.to_account_number || !transferForm.beneficiary_bank_code)
      ) {
        setErrorMessage("Please enter account number and select bank");
        setIsSubmitting(false);
        return;
      }

      if (!transferForm.pin || transferForm.pin.length !== 4) {
        setErrorMessage("Please enter your 4-digit PIN");
        setIsSubmitting(false);
        return;
      }

      const authHeaderValues = authHeaders();
      const tenantId = authHeaderValues["x-tenant-id"] || "default";
      const payload = {
        switch_name: PAYMENT_HUB_SWITCH_NAME,
        amount: Number(transferForm.amount || 0).toFixed(2),
        currency: transferForm.currency || "NGN",
        to: {
          idType: "ACCOUNT_ID",
          idValue: transferForm.to_account_number || transferForm.to_account_id,
          displayName: transferForm.beneficiary_name || "Recipient",
        },
        from: {
          idType: "ACCOUNT_ID",
          idValue: transferForm.from_account_number,
          displayName:
            accounts.find(
              (a) => String(a.id) === String(transferForm.from_account_id),
            )?.account_name || "Sender",
        },
        destination:
          transferForm.transfer_type === "external"
            ? "external-bank"
            : tenantId,
        note:
          transferForm.transfer_type === "internal"
            ? transferForm.description || "Transfer"
            : transferForm.narration || transferForm.description || "Transfer",
        pin: transferForm.pin,
      };

      const res = await fetch(
        `${CORE_BANKING_URL}/payment-hub/api/v1/transfers/initiate`,
        {
          method: "POST",
          headers: {
            ...authHeaderValues,
            "Content-Type": "application/json",
            "x-switch-name": PAYMENT_HUB_SWITCH_NAME,
            "x-ams-name": PAYMENT_HUB_AMS_NAME,
            "x-tenant-name": tenantId,
          },
          body: JSON.stringify(payload),
        },
      );

      const data = await res.json();

      if (!res.ok) {
        const detailMessage = Array.isArray(data?.detail)
          ? data.detail.map((d) => d.msg || d.type).join(", ")
          : null;
        throw new Error(
          detailMessage || data.message || data.error || "Transfer failed",
        );
      }

      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);

      // Reset form
      setTransferForm({
        from_account_id: "",
        from_account_number: "",
        to_account_id: "",
        to_account_number: "",
        amount: "",
        currency: "NGN",
        transfer_type: "internal",
        description: "",
        beneficiary_name: "",
        beneficiary_bank: "",
        beneficiary_bank_code: "",
        narration: "",
        pin: "",
      });

      // Refresh recent transfers using account-number endpoint
      if (transferForm.from_account_number) {
        try {
          const res = await fetch(
            `${CORE_BANKING_URL}/ledger/txn/account-number/${transferForm.from_account_number}?limit=5&page=1`,
            {
              headers: authHeaders(),
            },
          );
          if (res.ok) {
            const data = await res.json();
            const transactions = data.transactions || [];
            setRecentTransfers(transactions);
          }
        } catch (err) {
          console.error("Failed to refresh recent transfers:", err);
        }
      }
    } catch (err) {
      console.error("Transfer error:", err);
      setErrorMessage(err.message || "Failed to process transfer");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setTransferForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleFromAccountChange = (e) => {
    const accountId = e.target.value;
    const account = accounts.find((acc) => acc.id == accountId);
    setTransferForm((prev) => ({
      ...prev,
      from_account_id: accountId,
      from_account_number: account?.account_number || "",
    }));
  };

  const handleToAccountChange = (e) => {
    const accountId = e.target.value;
    const account = accounts.find((acc) => acc.id == accountId);
    setTransferForm((prev) => ({
      ...prev,
      to_account_id: accountId,
      to_account_number: account?.account_number || "",
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">
            Money Transfer
          </h1>
          <p className="text-gray-600 mt-1">
            Send money to customers, vendors, or other accounts
          </p>
        </div>
      </div>

      {showSuccess && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center">
          <CheckCircle className="h-5 w-5 mr-2" />
          Transfer successful!
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {errorMessage}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Transfer Form */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow p-4 sm:p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-6">
              New Transfer
            </h2>

            {/* Transfer Type Selection */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Transfer Type
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <button
                  type="button"
                  onClick={() =>
                    setTransferForm((prev) => ({
                      ...prev,
                      transfer_type: "internal",
                    }))
                  }
                  className={`flex items-center justify-center p-3 sm:p-4 border-2 rounded-lg transition-all ${
                    transferForm.transfer_type === "internal"
                      ? "bg-[var(--tenant-secondary-color,#69BC5E)] bg-opacity-20 border-[var(--tenant-secondary-color,#69BC5E)]"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <Users
                    className="h-5 w-5 mr-2"
                    style={{ color: "var(--tenant-primary-color,#004F71)" }}
                  />
                  <span className="font-medium">Internal</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setTransferForm((prev) => ({
                      ...prev,
                      transfer_type: "external",
                    }))
                  }
                  className={`flex items-center justify-center p-3 sm:p-4 border-2 rounded-lg transition-all ${
                    transferForm.transfer_type === "external"
                      ? "bg-[var(--tenant-secondary-color,#69BC5E)] bg-opacity-20 border-[var(--tenant-secondary-color,#69BC5E)]"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <Building2
                    className="h-5 w-5 mr-2"
                    style={{ color: "var(--tenant-primary-color,#004F71)" }}
                  />
                  <span className="font-medium">External</span>
                </button>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* From Account */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  From Account
                </label>
                <select
                  name="from_account_id"
                  value={transferForm.from_account_id}
                  onChange={handleFromAccountChange}
                  required
                  disabled={accountsLoading}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                >
                  <option value="">
                    {accountsLoading
                      ? "Loading accounts..."
                      : "Select source account"}
                  </option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_name} - {account.account_number} (
                      {account.currency}{" "}
                      {parseFloat(account.balance || 0).toLocaleString()})
                    </option>
                  ))}
                </select>
              </div>

              {/* To Account - Internal */}
              {transferForm.transfer_type === "internal" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      To Account (Select or Enter Account Number)
                    </label>
                    <select
                      name="to_account_id"
                      value={transferForm.to_account_id}
                      onChange={handleToAccountChange}
                      disabled={accountsLoading}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                    >
                      <option value="">Select destination account</option>
                      {accounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.account_name} - {account.account_number}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Or Enter Account Number
                    </label>
                    <input
                      type="text"
                      name="to_account_number"
                      value={transferForm.to_account_number}
                      onChange={handleInputChange}
                      placeholder="Enter account number"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                    />
                  </div>
                </>
              )}

              {/* To Account - External */}
              {transferForm.transfer_type === "external" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Account Number
                    </label>
                    <input
                      type="text"
                      name="to_account_number"
                      value={transferForm.to_account_number}
                      onChange={handleInputChange}
                      required
                      placeholder="Enter account number"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Beneficiary Name
                    </label>
                    <input
                      type="text"
                      name="beneficiary_name"
                      value={transferForm.beneficiary_name}
                      onChange={handleInputChange}
                      required
                      placeholder="Enter beneficiary name"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Bank Name
                    </label>
                    <select
                      name="beneficiary_bank_code"
                      value={transferForm.beneficiary_bank_code}
                      onChange={(e) => {
                        const option = e.target.options[e.target.selectedIndex];
                        setTransferForm((prev) => ({
                          ...prev,
                          beneficiary_bank_code: e.target.value,
                          beneficiary_bank: option.text,
                        }));
                      }}
                      required
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                    >
                      <option value="">Select bank</option>
                      <option value="058">GTBank</option>
                      <option value="044">Access Bank</option>
                      <option value="011">First Bank</option>
                      <option value="033">UBA</option>
                      <option value="057">Zenith Bank</option>
                    </select>
                  </div>
                </>
              )}

              {/* Amount */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Amount
                </label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-500">
                    ₦
                  </span>
                  <input
                    type="number"
                    name="amount"
                    value={transferForm.amount}
                    onChange={handleInputChange}
                    required
                    min="1"
                    step="0.01"
                    placeholder="0.00"
                    className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                  />
                </div>
              </div>

              {/* Description/Narration */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {transferForm.transfer_type === "internal"
                    ? "Description"
                    : "Narration"}{" "}
                  (Optional)
                </label>
                <textarea
                  name={
                    transferForm.transfer_type === "internal"
                      ? "description"
                      : "narration"
                  }
                  value={
                    transferForm.transfer_type === "internal"
                      ? transferForm.description
                      : transferForm.narration
                  }
                  onChange={handleInputChange}
                  rows="3"
                  placeholder="Enter transfer description..."
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                />
              </div>

              {/* PIN */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Transaction PIN
                </label>
                <input
                  type="password"
                  name="pin"
                  value={transferForm.pin}
                  onChange={handleInputChange}
                  required
                  maxLength={4}
                  placeholder="Enter 4-digit PIN"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
                />
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full flex items-center justify-center px-6 py-3 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                <Send className="h-5 w-5 mr-2" />
                {isSubmitting ? "Processing..." : "Send Money"}
              </button>
            </form>
          </div>
        </div>

        {/* Recent Transfers */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Recent Transfers
          </h2>
          <div className="space-y-4">
            {recentTransfers.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">
                No recent transfers
              </p>
            ) : (
              recentTransfers.map((transfer) => (
                <div key={transfer.id} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      <div
                        className="p-2 rounded-lg"
                        style={{ backgroundColor: "rgba(0, 79, 113, 0.1)" }}
                      >
                        <ArrowRight
                          className="h-4 w-4"
                          style={{ color: "var(--tenant-primary-color,#004F71)" }}
                        />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900 text-sm">
                          {transfer.payee || "Transfer"}
                        </p>
                        <p className="text-xs text-gray-500 font-mono">
                          {transfer.payee_account_number || "-"}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-between items-center mt-2">
                    <span className="text-sm font-semibold text-gray-900">
                      {transfer.currency}{" "}
                      {parseFloat(transfer.amount || 0).toLocaleString()}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(
                        transfer.created_at?.replace(" ", "T"),
                      ).toLocaleDateString()}
                    </span>
                  </div>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mt-2 ${
                      transfer.status?.toLowerCase() === "success"
                        ? "bg-green-100 text-green-800"
                        : transfer.status?.toLowerCase() === "pending"
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-red-100 text-red-800"
                    }`}
                  >
                    {transfer.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Transfer;
