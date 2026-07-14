import { CheckCircle, Send } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeaders } from "../services/tenant/getTenantHeaders";
import { tenantService } from "../services/tenant/tenantService";

const CORE_BANKING_URL =
  import.meta.env.VITE_API_URL || "https://54agent.upi.dev";
const PAYMENT_HUB_SWITCH_NAME = "mojaloop";
const PAYMENT_HUB_AMS_NAME = "core_banking";

const sendTransferRequest = async (payload: Record<string, any>) => {
  const res = await fetch(
    `${CORE_BANKING_URL}/payment-hub/api/v1/transfers/initiate`,
    {
      method: "POST",
      headers: getPaymentHubHeaders(),
      body: JSON.stringify(payload),
    },
  );

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.message || data.error || "Transfer failed");
  }

  return data;
};

const getPaymentHubHeaders = (): Record<string, string> => {
  const token = localStorage.getItem("auth_token") || "";
  const tenantConfig = tenantService.getTenantConfig();
  const tenantHeaders = getTenantHeaders(tenantConfig);
  const keycloakId = localStorage.getItem("keycloakId");

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...tenantHeaders,
    ...(keycloakId && !tenantHeaders["x-keycloak-id"]
      ? { "x-keycloak-id": keycloakId }
      : {}),
    "x-switch-name": PAYMENT_HUB_SWITCH_NAME,
    "x-ams-name": PAYMENT_HUB_AMS_NAME,
    "x-user-id": keycloakId,
    "x-tenant-name":
      tenantConfig?.tenant_id ||
      tenantConfig?.name ||
      tenantHeaders["x-tenant-id"] ||
      "default",
  };
};

const Transfer: React.FC = () => {
  const [transferForm, setTransferForm] = useState({
    from_account_id: "",
    to_account_number: "",
    amount: "",
    transfer_type: "internal",
    description: "",
  });

  const [accounts, setAccounts] = useState<any[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState("Transfer successful!");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        const token = localStorage.getItem("auth_token");
        const res = await fetch(`${CORE_BANKING_URL}/account/accounts`, {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });
        if (res.ok) {
          const data = await res.json();
          setAccounts(Array.isArray(data) ? data : data.accounts || []);
        }
      } catch (err) {
        console.error("Failed to fetch accounts:", err);
      }
    };
    fetchAccounts();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setIsSubmitting(true);

    try {
      const payload = {
        switch_name: PAYMENT_HUB_SWITCH_NAME,
        amount: Number(transferForm.amount || 0).toFixed(2),
        currency: "NGN",
        to: {
          idType: "ACCOUNT_ID",
          idValue: transferForm.to_account_number,
          displayName: "Recipient",
        },
        from: {
          idType: "ACCOUNT_ID",
          idValue: transferForm.from_account_id,
          displayName: "Sender",
        },
        destination: "agent-banking",
        note: transferForm.description || "Transfer from agent admin dashboard",
      };

      await sendTransferRequest(payload);
      setSuccessMessage("Transfer successful!");
      setShowSuccess(true);
      setTimeout(() => setShowSuccess(false), 3000);
      setTransferForm({
        from_account_id: "",
        to_account_number: "",
        amount: "",
        transfer_type: "internal",
        description: "",
      });
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to process transfer");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Money Transfer</h1>
        <p className="text-gray-600 mt-1">Send money between accounts</p>
      </div>

      {showSuccess && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center">
          <CheckCircle className="h-5 w-5 mr-2" />
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {errorMessage}
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
        <h2 className="text-lg font-semibold text-gray-900 mb-6">
          New Transfer
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              From Account
            </label>
            <select
              value={transferForm.from_account_id}
              onChange={(e) =>
                setTransferForm({
                  ...transferForm,
                  from_account_id: e.target.value,
                })
              }
              required
              className="w-full px-4 py-3 border border-gray-300 rounded-lg"
            >
              <option value="">Select source account</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.account_name} - {account.account_number} (₦
                  {parseFloat(account.balance || 0).toLocaleString()})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              To Account Number
            </label>
            <input
              type="text"
              value={transferForm.to_account_number}
              onChange={(e) =>
                setTransferForm({
                  ...transferForm,
                  to_account_number: e.target.value,
                })
              }
              required
              placeholder="Enter account number"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Amount
            </label>
            <input
              type="number"
              value={transferForm.amount}
              onChange={(e) =>
                setTransferForm({ ...transferForm, amount: e.target.value })
              }
              required
              min="1"
              step="0.01"
              placeholder="0.00"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description (Optional)
            </label>
            <textarea
              value={transferForm.description}
              onChange={(e) =>
                setTransferForm({
                  ...transferForm,
                  description: e.target.value,
                })
              }
              rows={3}
              placeholder="Enter transfer description..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full flex items-center justify-center px-6 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:bg-gray-400"
          >
            <Send className="h-5 w-5 mr-2" />
            {isSubmitting ? "Processing..." : "Send Money"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Transfer;
