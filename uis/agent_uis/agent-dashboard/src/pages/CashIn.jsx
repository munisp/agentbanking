import {
    ArrowDownLeft,
    CheckCircle,
    Copy,
    RefreshCw,
    Share2,
    User,
    Wallet,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { accountApi, agentApi, authHeaders } from "../utils/api";

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const CashIn = () => {
  const { user } = useAuth();
  const [agentProfile, setAgentProfile] = useState(null);
  const [accountDetails, setAccountDetails] = useState(null);
  const [recentDeposits, setRecentDeposits] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [copiedField, setCopiedField] = useState("");

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

            // Filter to only credits (deposits) — transactions where this account is the payee
            const deposits = allTxns.filter(
              (txn) => txn.payee_account_number === accountNumber,
            );

            setRecentDeposits(deposits);
          }
        } catch (txnErr) {
          console.error("Transactions fetch error:", txnErr);
        }
      }
    } catch (err) {
      console.error("CashIn data fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = async (text, fieldName) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(fieldName);
      setTimeout(() => setCopiedField(""), 2000);
    } catch (err) {
      console.error("Copy failed:", err);
    }
  };

  const shareAccountDetails = () => {
    const message = `54agent Agent Wallet

Account Name: ${accountDetails?.account_name || user?.name || "N/A"}
Account Number: ${accountDetails?.account_number || "N/A"}
Bank: 54agent Microfinance Bank

Transfer to this account to fund your agent wallet.`;

    if (navigator.share) {
      navigator
        .share({ title: "54agent Agent Wallet", text: message })
        .catch((err) => console.log("Share cancelled", err));
    } else {
      copyToClipboard(message, "details");
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
        return "text-red-600 bg-red-100";
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
            <div
              className="w-12 h-12 sm:w-16 sm:h-16 rounded-2xl flex items-center justify-center"
              style={{ backgroundColor: "rgba(0, 79, 113, 0.1)" }}
            >
              <ArrowDownLeft
                className="w-6 h-6 sm:w-8 sm:h-8"
                style={{ color: "var(--tenant-primary-color,#002082)" }}
              />
            </div>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-1">
                Fund Your Wallet
              </h1>
              <p className="text-gray-600 text-sm sm:text-base">
                Transfer money to your agent wallet account
              </p>
            </div>
          </div>
          <div
            className="w-full lg:w-auto border rounded-xl px-4 sm:px-6 py-3 sm:py-4"
            style={{
              backgroundColor: "rgba(0, 79, 113, 0.1)",
              borderColor: "rgba(0, 79, 113, 0.3)",
            }}
          >
            <p
              className="text-sm font-semibold mb-1"
              style={{ color: "var(--tenant-primary-color,#002082)" }}
            >
              Current Balance
            </p>
            <p
              className="text-2xl sm:text-3xl font-bold break-all"
              style={{ color: "var(--tenant-primary-color,#003F5A)" }}
            >
              ₦
              {accountDetails?.balance
                ? Number(accountDetails.balance).toLocaleString()
                : "0.00"}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Account Details Card */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-4 sm:p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                <Wallet className="w-6 h-6" style={{ color: "var(--tenant-primary-color,#002082)" }} />
                Transfer To This Account
              </h2>
              <button
                onClick={shareAccountDetails}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl hover:bg-[var(--tenant-primary-color,#003F5A)] transition-all font-medium shadow-sm"
              >
                <Share2 className="w-4 h-4" />
                Share
              </button>
            </div>

            {/* Account Name */}
            <div className="mb-4">
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-2">
                <User className="w-4 h-4 text-gray-500" />
                Account Name
              </label>
              <div
                className="flex items-center gap-2 border-2 rounded-xl p-4"
                style={{
                  backgroundColor: "rgba(0, 79, 113, 0.1)",
                  borderColor: "rgba(0, 79, 113, 0.3)",
                }}
              >
                <span className="flex-1 text-base font-semibold text-gray-900">
                  {user?.name || "—"}
                </span>
                <button
                  onClick={() =>
                    copyToClipboard(
                      accountDetails?.account_name || user?.name,
                      "name",
                    )
                  }
                  className="p-2 rounded-lg transition-all"
                  style={{
                    ":hover": { backgroundColor: "rgba(0, 79, 113, 0.15)" },
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor =
                      "rgba(0, 79, 113, 0.15)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                  title="Copy account name"
                >
                  {copiedField === "name" ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <Copy className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#002082)" }} />
                  )}
                </button>
              </div>
            </div>

            {/* Account Number */}
            <div className="mb-4">
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-2">
                <Wallet className="w-4 h-4 text-gray-500" />
                Account Number
              </label>
              <div
                className="flex items-center gap-2 border-2 rounded-xl p-4"
                style={{
                  backgroundColor: "rgba(0, 79, 113, 0.1)",
                  borderColor: "rgba(0, 79, 113, 0.3)",
                }}
              >
                <span className="flex-1 text-lg font-mono font-bold text-gray-900">
                  {accountDetails?.account_number || "Loading..."}
                </span>
                <button
                  onClick={() =>
                    copyToClipboard(accountDetails?.account_number, "number")
                  }
                  className="p-2 rounded-lg transition-all"
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.backgroundColor =
                      "rgba(0, 79, 113, 0.15)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.backgroundColor = "transparent")
                  }
                  title="Copy account number"
                >
                  {copiedField === "number" ? (
                    <CheckCircle className="w-5 h-5 text-green-600" />
                  ) : (
                    <Copy className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#002082)" }} />
                  )}
                </button>
              </div>
            </div>

            {/* Bank Name */}
            <div className="mb-5">
              <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-2">
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                  />
                </svg>
                Bank Name
              </label>
              <div
                className="border-2 rounded-xl p-4"
                style={{
                  backgroundColor: "rgba(0, 79, 113, 0.1)",
                  borderColor: "rgba(0, 79, 113, 0.3)",
                }}
              >
                <span className="text-base font-semibold text-gray-900">
                  54agent Microfinance Bank
                </span>
              </div>
            </div>

            {/* Instructions */}
            <div
              className="border rounded-xl p-4"
              style={{
                backgroundColor: "rgba(0, 79, 113, 0.1)",
                borderColor: "rgba(0, 79, 113, 0.3)",
              }}
            >
              <div className="flex gap-3">
                <svg
                  className="w-5 h-5 shrink-0 mt-0.5"
                  style={{ color: "var(--tenant-primary-color,#002082)" }}
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                    clipRule="evenodd"
                  />
                </svg>
                <p
                  className="text-sm leading-relaxed"
                  style={{ color: "#1F2937" }}
                >
                  <strong className="font-semibold">Quick Fund:</strong> Use
                  your bank app or USSD to transfer to this account. Funds
                  reflect within 1-5 minutes.
                </p>
              </div>
            </div>
          </div>

          {/* Recent Deposits */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Recent Deposits
            </h2>

            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw
                  className="h-6 w-6 animate-spin"
                  style={{ color: "var(--tenant-primary-color,#002082)" }}
                />
                <span className="ml-2 text-gray-500">Loading deposits...</span>
              </div>
            ) : recentDeposits.length === 0 ? (
              <div className="text-center py-12">
                <Wallet className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500 font-medium">No deposits yet</p>
                <p className="text-sm text-gray-400 mt-1">
                  Your recent deposits will appear here
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                        Date
                      </th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                        Amount
                      </th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                        From
                      </th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                        Note
                      </th>
                      <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentDeposits.map((deposit, index) => (
                      <tr
                        key={deposit.id || index}
                        className="border-b border-gray-100"
                      >
                        <td className="py-3 px-4 text-sm text-gray-600">
                          {new Date(
                            deposit.created_at?.replace(" ", "T"),
                          ).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </td>
                        <td className="py-3 px-4 text-sm font-semibold text-green-600">
                          ₦{parseFloat(deposit.amount || 0).toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-600 font-mono">
                          {deposit.payer_account_number || deposit.payer || "—"}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-600">
                          {deposit.note || "—"}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                              deposit.status,
                            )}`}
                          >
                            {deposit.status || "Unknown"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* How It Works */}
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-6">
              How to Fund Your Wallet
            </h2>
            <div className="space-y-5">
              {[
                {
                  step: 1,
                  title: "Open Your Bank App",
                  desc: "Launch your mobile banking app or dial your bank's USSD code",
                },
                {
                  step: 2,
                  title: "Make Transfer",
                  desc: "Transfer to the account number shown above",
                },
                {
                  step: 3,
                  title: "Funds Added",
                  desc: "Your wallet balance will update within 1-5 minutes",
                },
              ].map(({ step, title, desc }) => (
                <div key={step} className="flex gap-4">
                  <div
                    className="shrink-0 w-12 h-12 text-white rounded-xl flex items-center justify-center font-bold text-lg shadow-sm"
                    style={{ backgroundColor: "var(--tenant-primary-color,#002082)" }}
                  >
                    {step}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold text-gray-900 mb-1.5 text-base">
                      {title}
                    </h3>
                    <p className="text-sm text-gray-600 leading-relaxed">
                      {desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Sidebar: Agent Info */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl shadow-lg border border-gray-200 p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <User className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#002082)" }} />
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
        </div>
      </div>
    </div>
  );
};

export default CashIn;
