import {
  ArrowDownLeft,
  ArrowUpRight,
  DollarSign,
  Eye,
  EyeOff,
  Package,
  Receipt,
  RefreshCw,
  ShoppingCart,
  Store,
  TrendingUp,
  Users,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { accountApi, agentApi, authHeaders, inventoryApi } from "../utils/api";

const Dashboard = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [agentProfile, setAgentProfile] = useState(null);
  const [accountDetails, setAccountDetails] = useState(null);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const [isLoadingData, setIsLoadingData] = useState(true);
  const [dataError, setDataError] = useState(null);
  const [balanceVisible, setBalanceVisible] = useState(true);

  useEffect(() => {
    const loadBalanceVisibility = () => {
      const visibility = localStorage.getItem("balanceVisible");
      if (visibility !== null) {
        setBalanceVisible(visibility === "true");
      }
    };
    loadBalanceVisibility();
  }, []);

  const toggleBalanceVisibility = () => {
    const newVisibility = !balanceVisible;
    setBalanceVisible(newVisibility);
    localStorage.setItem("balanceVisible", String(newVisibility));
  };

  useEffect(() => {
    const fetchDashboardData = async () => {
      setIsLoadingData(true);
      setDataError(null);
      try {
        const keycloakId = user?.keycloakId;
        if (keycloakId) {
          const profileResp = await agentApi.getAgentByKeycloakId(keycloakId);
          setAgentProfile(profileResp.agent ?? profileResp);

          // Fetch account details
          let accountNumber = null;
          try {
            const accountResp =
              await accountApi.getAccountByKeycloakId(keycloakId);
            const account = accountResp.account ?? accountResp;
            setAccountDetails(account);
            accountNumber = account?.account_number;
          } catch (accountErr) {
            console.error("Account fetch error:", accountErr);
          }

          // Fetch stores owned by the agent
          let stores = [];
          try {
            const storesResp = await inventoryApi.getStores(keycloakId);
            stores = Array.isArray(storesResp.data)
              ? storesResp.data
              : Array.isArray(storesResp)
                ? storesResp
                : [];
          } catch (storesErr) {
            console.error("Stores fetch error:", storesErr);
          }

          // Fetch transactions for agent's account and all store accounts
          const allTransactions = [];
          console.log("Fetching transactions for account:", accountNumber);
          // Fetch agent account transactions
          if (accountNumber) {
            try {
              const res = await fetch(
                `https://54agent.upi.dev/ledger/txn/account-number/${accountNumber}?limit=10&page=1`,
                {
                  headers: { ...authHeaders() },
                },
              );
              if (res.ok) {
                const data = await res.json();
                const agentTxns = (data.transactions || []).map((txn) => ({
                  ...txn,
                  source: "My Account",
                  sourceType: "agent",
                }));
                allTransactions.push(...agentTxns);
              }
            } catch (txnErr) {
              console.error("Agent transactions fetch error:", txnErr);
            }
          }

          // Fetch transactions for each store
          const storeTransactionPromises = stores.map(async (store) => {
            if (store.account_number) {
              try {
                const res = await fetch(
                  `https://54agent.upi.dev/ledger/txn/account-number/${store.account_number}?limit=10&page=1`,
                  {
                    headers: { ...authHeaders() },
                  },
                );
                if (res.ok) {
                  const data = await res.json();
                  return (data.transactions || []).map((txn) => ({
                    ...txn,
                    source: store.name,
                    sourceType: "store",
                    storeId: store.id,
                  }));
                }
              } catch (err) {
                console.error(
                  `Transactions fetch error for store ${store.id}:`,
                  err,
                );
              }
            }
            return [];
          });

          const storeTransactionsArrays = await Promise.all(
            storeTransactionPromises,
          );
          storeTransactionsArrays.forEach((txns) => {
            allTransactions.push(...txns);
          });

          // Sort all transactions by date (newest first)
          allTransactions.sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at),
          );

          // Take only the 10 most recent
          setRecentTransactions(allTransactions.slice(0, 10));
        } else {
          setRecentTransactions([]);
        }
      } catch (err) {
        console.error("Dashboard data fetch error:", err);
        setDataError(err.message);
      } finally {
        setIsLoadingData(false);
      }
    };

    if (user) fetchDashboardData();
  }, [user]);

  const stats = [
    // {
    //   label: "Account Balance",
    //   value: accountDetails?.balance
    //     ? `₦${(accountDetails.balance / 100).toLocaleString()}`
    //     : "—",
    //   icon: DollarSign,
    //   color: "bg-green-500",
    //   change: accountDetails?.status ?? "",
    // },
    // {
    //   label: "Credits Posted",
    //   value: accountDetails?.credits_posted
    //     ? `₦${(accountDetails.credits_posted / 100).toLocaleString()}`
    //     : "—",
    //   icon: ArrowUpRight,
    //   color: "bg-emerald-500",
    //   change: accountDetails?.credits_pending
    //     ? `${accountDetails.credits_pending / 100} pending`
    //     : "",
    // },
    // {
    //   label: "Debits Posted",
    //   value: accountDetails?.debits_posted
    //     ? `₦${(accountDetails.debits_posted / 100).toLocaleString()}`
    //     : "—",
    //   icon: ArrowDownLeft,
    //   color: "bg-red-500",
    //   change: accountDetails?.debits_pending
    //     ? `${accountDetails.debits_pending / 100} pending`
    //     : "",
    // },
    {
      label: "Agent Role",
      value: agentProfile?.agent_role ?? user?.agentRole ?? "—",
      icon: Store,
      color: "bg-blue-500",
      change: agentProfile?.status ?? user?.status ?? "",
    },
    // {
    //   label: "Business Name",
    //   value: agentProfile?.business_name ?? user?.businessName ?? "—",
    //   icon: Users,
    //   color: "bg-purple-500",
    //   change: agentProfile?.city ?? "",
    // },
    {
      label: "KYC Status",
      value: agentProfile?.kyc_verification_status ?? "—",
      icon: TrendingUp,
      color: "bg-[var(--tenant-primary-color,#004F71)]",
      // change: agentProfile?.onboarding_status ?? "",
      change: "",
    },
    {
      label: "Account ID",
      value: accountDetails?.account_number ?? "—",
      icon: Package,
      color: "bg-orange-500",
      // change: accountDetails?.account_type ?? "",
    },
    {
      label: "Account Type",
      value: accountDetails?.account_type ?? "—",
      icon: Receipt,
      color: "bg-cyan-500",
      change:
        // accountDetails?.ledger_id
        // ? `Ledger: ${accountDetails.ledger_id}`
        // :
        "",
    },
  ];

  return (
    <div className="space-y-4 sm:space-y-6 lg:space-y-8">
      {/* Header with gradient background */}
      <div className="bg-linear-to-r from-[var(--tenant-primary-color,#00196a)] via-[var(--tenant-primary-color,#00196a)] to-[var(--tenant-secondary-color,#69BC5E)] rounded-2xl shadow-xl p-4 sm:p-6 lg:p-8 text-white">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="flex-1">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold mb-2">
              Dashboard Overview
            </h1>
            <p className="text-blue-100 text-sm sm:text-base lg:text-lg">
              Welcome back, {user?.name || "Agent"}
              {/* {user?.agentCode ? ` (${user.agentCode})` : ""} */}
            </p>
            {dataError && (
              <p className="mt-2 text-sm text-red-200">
                Could not load profile data: {dataError}
              </p>
            )}
          </div>
          <div className="flex w-full lg:w-auto flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            {accountDetails?.account_number && (
              <div className="w-full sm:w-auto bg-white/10 backdrop-blur-sm border border-white/30 rounded-xl px-4 sm:px-6 py-3 sm:py-4">
                <p className="text-blue-100 text-sm font-medium mb-1">
                  Account Number
                </p>
                <p className="text-lg sm:text-xl lg:text-2xl font-bold font-mono tracking-wider break-all">
                  {accountDetails.account_number}
                </p>
              </div>
            )}
            {accountDetails?.balance !== undefined && (
              <div className="w-full sm:w-auto bg-white/10 backdrop-blur-sm border border-white/30 rounded-xl px-4 sm:px-6 py-3 sm:py-4">
                <div className="flex items-center justify-between gap-3 mb-1">
                  <p className="text-blue-100 text-sm font-medium">
                    Available Balance
                  </p>
                  <button
                    onClick={toggleBalanceVisibility}
                    className="text-white hover:text-blue-200 transition-colors p-1"
                  >
                    {balanceVisible ? (
                      <Eye className="h-5 w-5" />
                    ) : (
                      <EyeOff className="h-5 w-5" />
                    )}
                  </button>
                </div>
                <p className="text-lg sm:text-xl lg:text-2xl font-bold tracking-wider break-all">
                  {balanceVisible
                    ? `₦${(Number(accountDetails.balance) || 0).toLocaleString()}`
                    : "₦••••••"}
                </p>
              </div>
            )}
            {isLoadingData && (
              <RefreshCw className="h-6 w-6 text-blue-200 animate-spin" />
            )}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-6">
        {stats.map((stat, index) => (
          <div
            key={index}
            className="bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 p-4 sm:p-6 border border-gray-100 hover:border-blue-200 transform hover:-translate-y-1"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
                  {stat.label}
                </p>
                <p className="text-xl sm:text-2xl lg:text-3xl font-bold text-gray-900 mt-3 wrap-break-word">
                  {stat.value}
                </p>
                <p className="text-xs text-gray-500 mt-2 font-medium">
                  {stat.change}
                </p>
              </div>
              <div className={`${stat.color} p-3 sm:p-4 rounded-2xl shadow-md`}>
                <stat.icon className="h-6 w-6 sm:h-7 sm:w-7 text-white" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Transactions */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow">
          <div className="p-4 sm:p-6 border-b border-gray-200 bg-linear-to-r from-gray-50 to-blue-50">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center gap-2">
                <Receipt className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
                Recent Transactions
              </h2>
              <a
                href="/transactions"
                className="text-sm hover:underline font-semibold"
                style={{ color: "var(--tenant-primary-color,#004F71)" }}
              >
                View All →
              </a>
            </div>
          </div>
          <div className="p-4 sm:p-6">
            {isLoadingData ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 text-blue-400 animate-spin" />
                <span className="ml-2 text-gray-500">
                  Loading transactions...
                </span>
              </div>
            ) : recentTransactions.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <Receipt className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                <p>No recent transactions</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-[40vh] overflow-y-auto">
                {recentTransactions.map((transaction, index) => {
                  // Determine if this is incoming or outgoing
                  // For the current account, if payee_account_number matches, it's incoming (credit)
                  const currentAccountNumber = accountDetails?.account_number;
                  const isCredit =
                    transaction.payee_account_number === currentAccountNumber;

                  // Parse amount from string
                  const amount = parseFloat(transaction.amount || 0);

                  // Get counterparty details
                  const counterpartyName = isCredit
                    ? transaction.payer_name
                    : transaction.payee_name;
                  const counterpartyAccount = isCredit
                    ? transaction.payer_account_number
                    : transaction.payee_account_number;

                  // Format date
                  const txnDate = new Date(
                    transaction.created_at || transaction.completed_at,
                  );
                  const formattedDate = txnDate.toLocaleDateString("en-NG", {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  });

                  // Get transaction type label from tag
                  const typeLabels = {
                    deposit: "Deposit",
                    withdrawal: "Withdrawal",
                    transfer: "Transfer",
                    airtime_purchase: "Airtime",
                    data_bundle: "Data Bundle",
                    bill_payment: "Bill Payment",
                  };
                  const txnType =
                    typeLabels[transaction.tag] ||
                    transaction.tag ||
                    "Transaction";

                  return (
                    <div
                      key={transaction.id || index}
                      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 sm:p-4 bg-linear-to-r from-gray-50 to-blue-50 rounded-xl hover:from-blue-50 hover:to-indigo-50 transition-all border border-gray-100 hover:border-blue-200 hover:shadow-md max-h-[40vh] overflow-y-auto"
                    >
                      <div className="flex items-start sm:items-center space-x-3 flex-1 min-w-0">
                        <div
                          className={`p-2 rounded-lg ${
                            isCredit ? "bg-green-100" : "bg-orange-100"
                          }`}
                        >
                          {isCredit ? (
                            <ArrowUpRight className="h-5 w-5 text-green-600" />
                          ) : (
                            <ArrowDownLeft className="h-5 w-5 text-orange-600" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 truncate">
                            {transaction.note || txnType}
                          </p>
                          <div className="flex flex-wrap items-center gap-2 text-xs sm:text-sm text-gray-500">
                            <span>{formattedDate}</span>
                            <span className="text-gray-300">•</span>
                            <span
                              className={`font-medium ${
                                transaction.sourceType === "agent"
                                  ? "text-indigo-600"
                                  : "text-orange-600"
                              }`}
                            >
                              {transaction.source || counterpartyName}
                            </span>
                          </div>
                          <p className="text-xs text-gray-400 mt-1 break-all sm:truncate">
                            {counterpartyAccount &&
                              `Acct: ${counterpartyAccount}`}
                          </p>
                        </div>
                      </div>
                      <div className="w-full sm:w-auto text-left sm:text-right sm:ml-4">
                        <p
                          className={`font-semibold whitespace-nowrap ${
                            isCredit ? "text-green-600" : "text-orange-600"
                          }`}
                        >
                          {isCredit ? "+" : "-"}₦{amount.toLocaleString()}
                        </p>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            transaction.status?.toLowerCase() === "completed" ||
                            transaction.status?.toLowerCase() === "success"
                              ? "bg-green-100 text-green-800"
                              : transaction.status?.toLowerCase() === "pending"
                                ? "bg-yellow-100 text-yellow-800"
                                : "bg-red-100 text-red-800"
                          }`}
                        >
                          {transaction.status || "completed"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Agent Info Panel */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow">
          <div className="p-4 sm:p-6 border-b border-gray-200 bg-linear-to-r from-gray-50 to-purple-50">
            <h2 className="text-lg sm:text-xl font-bold text-gray-900 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-purple-600" />
              Agent Info
            </h2>
          </div>
          <div className="p-4 sm:p-6">
            {isLoadingData ? (
              <div className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 text-purple-400 animate-spin" />
              </div>
            ) : (
              <div className="space-y-4">
                {[
                  { label: "Email", value: agentProfile?.email ?? user?.email },
                  {
                    label: "Phone",
                    value: agentProfile?.phone_number ?? user?.phone,
                  },
                  {
                    label: "Address",
                    value: agentProfile?.business_address ?? "—",
                  },
                  {
                    label: "Approval",
                    value: agentProfile?.is_approved
                      ? "Approved"
                      : "Pending Approval",
                  },
                ].map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start justify-between gap-2"
                  >
                    <p className="text-sm font-medium text-gray-500 shrink-0">
                      {item.label}
                    </p>
                    <p className="text-sm font-semibold text-gray-900 text-right wrap-break-word">
                      {item.value ?? "—"}
                    </p>
                  </div>
                ))}

                {accountDetails && (
                  <>
                    <div className="border-t border-gray-200 pt-4 mt-4">
                      <p className="text-xs font-semibold text-purple-600 uppercase tracking-wide mb-3">
                        Account Details
                      </p>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-500 shrink-0">
                        Account No.
                      </p>
                      <p className="text-sm font-mono font-semibold text-gray-900 text-right break-all">
                        {accountDetails.account_number ?? "—"}
                      </p>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-500 shrink-0">
                        Account Name
                      </p>
                      <p className="text-sm font-semibold text-gray-900 text-right">
                        {accountDetails.name ?? "—"}
                      </p>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-500 shrink-0">
                        Balance
                      </p>
                      <p className="text-sm font-semibold text-green-600 text-right">
                        {accountDetails.balance !== undefined
                          ? `₦${(Number(accountDetails.balance) || 0).toLocaleString()}`
                          : "—"}
                      </p>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-500 shrink-0">
                        Account Type
                      </p>
                      <p className="text-sm font-semibold text-gray-900 text-right">
                        {accountDetails.account_type ?? "—"}
                      </p>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-500 shrink-0">
                        Status
                      </p>
                      <p className="text-sm font-semibold text-gray-900 text-right">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            accountDetails.status === "active"
                              ? "bg-green-100 text-green-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {accountDetails.status ?? "—"}
                        </span>
                      </p>
                    </div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-medium text-gray-500 shrink-0">
                        Tenant ID
                      </p>
                      <p className="text-sm font-mono font-semibold text-gray-900 text-right break-all">
                        {accountDetails.tenant_id ?? "—"}
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      {/* <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow">
        <h2 className="text-xl font-bold text-gray-900 mb-6">Quick Actions</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button
            onClick={() => navigate("/orders/create")}
            className="flex flex-col items-center justify-center p-6 bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl hover:from-purple-100 hover:to-purple-200 border-2 border-purple-200 hover:border-purple-300 transition-all transform hover:-translate-y-1 hover:shadow-md"
          >
            <ShoppingCart className="h-10 w-10 text-purple-600 mb-3" />
            <span className="text-sm font-semibold text-gray-900">
              Create Order
            </span>
          </button>
          <button
            onClick={() => navigate("/cash-in")}
            className="flex flex-col items-center justify-center p-6 rounded-xl border-2 transition-all transform hover:-translate-y-1 hover:shadow-md"
            style={{backgroundColor: 'rgba(0,79,113,0.05)', borderColor: 'rgba(0,79,113,0.2)'}}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(0,79,113,0.1)';
              e.currentTarget.style.borderColor = 'rgba(0,79,113,0.3)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'rgba(0,79,113,0.05)';
              e.currentTarget.style.borderColor = 'rgba(0,79,113,0.2)';
            }}
          >
            <ArrowDownLeft className="h-10 w-10 mb-3" style={{color: 'var(--tenant-primary-color,#004F71)'}} />
            <span className="text-sm font-semibold text-gray-900">Cash In</span>
          </button>
          <button
            onClick={() => navigate("/cash-out")}
            className="flex flex-col items-center justify-center p-6 bg-gradient-to-br from-green-50 to-green-100 rounded-xl hover:from-green-100 hover:to-green-200 border-2 border-green-200 hover:border-green-300 transition-all transform hover:-translate-y-1 hover:shadow-md"
          >
            <ArrowUpRight className="h-10 w-10 text-green-600 mb-3" />
            <span className="text-sm font-semibold text-gray-900">
              Cash Out
            </span>
          </button>
          <button
            onClick={() => navigate("/inventory")}
            className="flex flex-col items-center justify-center p-6 bg-gradient-to-br from-orange-50 to-orange-100 rounded-xl hover:from-orange-100 hover:to-orange-200 border-2 border-orange-200 hover:border-orange-300 transition-all transform hover:-translate-y-1 hover:shadow-md"
          >
            <Package className="h-10 w-10 text-orange-600 mb-3" />
            <span className="text-sm font-medium text-gray-900">Inventory</span>
          </button>
        </div>
      </div> */}
    </div>
  );
};

export default Dashboard;
