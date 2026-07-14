import {
    ArrowDownLeft,
    ArrowUpRight,
    Building2,
    Download,
    Filter,
    Loader,
    Search,
    Store,
    TrendingUp,
    Users,
    Wallet,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import type { AgentRecord, StoreRecord } from "../../utils/api";
import { api } from "../../utils/api";

interface Account {
  id: number;
  account_number: string;
  name: string;
  balance: number;
  status: string;
  keycloak_id: string;
  created_at: string;
  account_type: string;
}

interface Transaction {
  id: string;
  amount: number;
  credit?: number;
  debit?: number;
  description: string;
  created_at: string;
  status: string;
}

interface AgentBusinessData {
  agent: AgentRecord;
  agentAccount: Account | null;
  stores: StoreRecord[];
  storeAccounts: Account[];
  totalBalance: number;
  totalTransactions: number;
  recentTransactions: Transaction[];
}

const AgentBusinessReports: React.FC = () => {
  const [agentData, setAgentData] = useState<AgentBusinessData[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterRole, setFilterRole] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Fetch all agents
      const agentsRes = await api.getAgents();
      const agents = agentsRes.agents || [];

      // Fetch all stores
      const storesRes = await api.getAllStores();
      const allStores = Array.isArray(storesRes) ? storesRes : [];

      // Fetch all accounts
      const accountsRes = await api.getAllAccounts();
      const allAccounts = accountsRes.account || [];

      // Process data for each agent
      const processedData: AgentBusinessData[] = await Promise.all(
        agents.map(async (agent: AgentRecord) => {
          // Find agent's account
          const agentAccount = allAccounts.find(
            (acc: Account) => acc.keycloak_id === agent.keycloak_id,
          );

          // Find agent's stores
          const agentStores = allStores.filter(
            (store: import("../../utils/api").StoreRecord) =>
              store.owner_keycloak_id === agent.keycloak_id,
          );

          // Find store accounts
          const storeAccounts = agentStores
            .map((store: import("../../utils/api").StoreRecord) =>
              allAccounts.find(
                (acc: Account) =>
                  acc.account_number === (store as any).account_number,
              ),
            )
            .filter(Boolean);

          // Calculate total balance
          const agentBalance = agentAccount?.balance || 0;
          const storeBalance = storeAccounts.reduce(
            (sum: number, acc: any) => sum + (acc?.balance || 0),
            0,
          );
          const totalBalance = agentBalance + storeBalance;

          // Fetch recent transactions for agent account
          let recentTransactions: Transaction[] = [];
          let totalTransactions = 0;

          if (agentAccount?.account_number) {
            try {
              const txnRes = await fetch(
                `https://54agent.upi.dev/ledger/txn/account-number/${agentAccount.account_number}?limit=5&page=1`,
                {
                  headers: {
                    Authorization: `Bearer ${localStorage.getItem("auth_token")}`,
                    "Content-Type": "application/json",
                    "x-tenant-id": import.meta.env.VITE_TENANT_ID || "54agent",
                  },
                },
              );

              if (txnRes.ok) {
                const txnData = await txnRes.json();
                recentTransactions = txnData.transactions || [];
                totalTransactions = txnData.total || recentTransactions.length;
              }
            } catch (err) {
              console.error(
                `Failed to fetch transactions for agent ${agent.keycloak_id}:`,
                err,
              );
            }
          }

          return {
            agent,
            agentAccount,
            stores: agentStores,
            storeAccounts,
            totalBalance,
            totalTransactions,
            recentTransactions,
          };
        }),
      );

      setAgentData(processedData);
    } catch (error) {
      console.error("Error loading agent business data:", error);
    } finally {
      setLoading(false);
    }
  };

  const filteredData = agentData.filter((data) => {
    const matchesSearch =
      !searchQuery ||
      `${data.agent.first_name} ${data.agent.last_name}`
        .toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      data.agent.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      data.agent.business_name
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      data.agentAccount?.account_number?.includes(searchQuery);

    const matchesRole =
      filterRole === "all" || data.agent.agent_role === filterRole;
    const matchesStatus =
      filterStatus === "all" || data.agent.status === filterStatus;

    return matchesSearch && matchesRole && matchesStatus;
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
    }).format(amount || 0);
  };

  const exportToCSV = () => {
    const headers = [
      "Agent Name",
      "Email",
      "Agent Role",
      "Status",
      "Business Name",
      "Account Number",
      "Agent Balance",
      "Number of Stores",
      "Store Accounts Balance",
      "Total Balance",
      "Total Transactions",
    ];

    const rows = filteredData.map((data) => [
      `${data.agent.first_name} ${data.agent.last_name}`,
      data.agent.email,
      data.agent.agent_role,
      data.agent.status,
      data.agent.business_name || "",
      data.agentAccount?.account_number || "",
      data.agentAccount?.balance || 0,
      data.stores.length,
      data.storeAccounts.reduce((sum, acc) => sum + (acc?.balance || 0), 0),
      data.totalBalance,
      data.totalTransactions,
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map((cell) => `"${cell}"`).join(","))
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-business-reports-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  // Calculate summary statistics
  const totalAgents = filteredData.length;
  const totalStores = filteredData.reduce(
    (sum, data) => sum + data.stores.length,
    0,
  );
  const totalBalance = filteredData.reduce(
    (sum, data) => sum + data.totalBalance,
    0,
  );
  const totalTransactions = filteredData.reduce(
    (sum, data) => sum + data.totalTransactions,
    0,
  );

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "active":
        return "bg-green-100 text-green-800";
      case "inactive":
        return "bg-gray-100 text-gray-800";
      case "suspended":
        return "bg-red-100 text-red-800";
      case "pending":
        return "bg-yellow-100 text-yellow-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="h-7 w-7 text-[var(--tenant-primary-color,#004F71)]" />
            Agent Businesses Accounting & Performance Reports
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Comprehensive overview of all agents, their businesses, and
            financial performance
          </p>
        </div>
        <button
          onClick={exportToCSV}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors"
          disabled={filteredData.length === 0}
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Agents</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {totalAgents}
              </p>
            </div>
            <div className="bg-[rgba(0,79,113,0.1)] p-3 rounded-lg">
              <Users className="h-6 w-6 text-[var(--tenant-primary-color,#004F71)]" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Stores</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {totalStores}
              </p>
            </div>
            <div className="bg-orange-100 p-3 rounded-lg">
              <Store className="h-6 w-6 text-orange-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Balance</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {formatCurrency(totalBalance)}
              </p>
            </div>
            <div className="bg-green-100 p-3 rounded-lg">
              <Wallet className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Transactions</p>
              <p className="text-2xl font-bold text-purple-600 mt-1">
                {totalTransactions.toLocaleString()}
              </p>
            </div>
            <div className="bg-purple-100 p-3 rounded-lg">
              <TrendingUp className="h-6 w-6 text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name, email, business, or account number..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            />
          </div>
          <div className="flex gap-4">
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <select
                value={filterRole}
                onChange={(e) => setFilterRole(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent appearance-none bg-white"
              >
                <option value="all">All Roles</option>
                <option value="master">Master Agent</option>
                <option value="standard">Standard Agent</option>
                <option value="sub">Sub Agent</option>
              </select>
            </div>
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent appearance-none bg-white"
              >
                <option value="all">All Status</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="suspended">Suspended</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto text-[var(--tenant-primary-color,#004F71)]" />
          <p className="mt-2 text-gray-600">Loading agent business data...</p>
        </div>
      )}

      {/* Agent List */}
      {!loading && filteredData.length > 0 && (
        <div className="space-y-4">
          {filteredData.map((data) => (
            <div
              key={data.agent.keycloak_id}
              className="bg-white rounded-lg shadow overflow-hidden"
            >
              {/* Agent Summary */}
              <div
                className="p-6 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() =>
                  setExpandedAgent(
                    expandedAgent === data.agent.keycloak_id
                      ? null
                      : data.agent.keycloak_id,
                  )
                }
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-sm text-gray-600">Agent</p>
                      <p className="font-semibold text-gray-900">
                        {data.agent.first_name} {data.agent.last_name}
                      </p>
                      <p className="text-sm text-gray-500">
                        {data.agent.email}
                      </p>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize mt-1 ${getStatusColor(
                          data.agent.status,
                        )}`}
                      >
                        {data.agent.status}
                      </span>
                    </div>

                    <div>
                      <p className="text-sm text-gray-600">Business</p>
                      <p className="font-semibold text-gray-900">
                        {data.agent.business_name || "—"}
                      </p>
                      <p className="text-sm text-gray-500 capitalize">
                        {data.agent.agent_role} Agent
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-gray-600">Account</p>
                      <p className="font-mono font-semibold text-gray-900">
                        {data.agentAccount?.account_number || "—"}
                      </p>
                      <p className="text-sm font-semibold text-green-600">
                        {formatCurrency(data.agentAccount?.balance || 0)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-gray-600">Performance</p>
                      <p className="font-semibold text-gray-900">
                        {data.stores.length} Store
                        {data.stores.length !== 1 ? "s" : ""}
                      </p>
                      <p className="text-sm text-gray-500">
                        {data.totalTransactions.toLocaleString()} Transactions
                      </p>
                      <p className="text-sm font-semibold text-[var(--tenant-primary-color,#004F71)] mt-1">
                        Total: {formatCurrency(data.totalBalance)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Expanded Details */}
              {expandedAgent === data.agent.keycloak_id && (
                <div className="border-t border-gray-200 p-6 bg-gray-50">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Stores */}
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <Store className="h-5 w-5 text-orange-600" />
                        Stores ({data.stores.length})
                      </h3>
                      {data.stores.length === 0 ? (
                        <p className="text-sm text-gray-500">No stores</p>
                      ) : (
                        <div className="space-y-3">
                          {data.stores.map((store) => {
                            const storeAccount = data.storeAccounts.find(
                              (acc) =>
                                acc.account_number ===
                                (store as any).account_number,
                            );
                            return (
                              <div
                                key={store.id}
                                className="bg-white rounded-lg p-4 border border-gray-200"
                              >
                                <div className="flex items-start justify-between">
                                  <div>
                                    <p className="font-medium text-gray-900">
                                      {store.name}
                                    </p>
                                    <p className="text-sm text-gray-500">
                                      {store.description || "No description"}
                                    </p>
                                    {storeAccount && (
                                      <p className="text-xs font-mono text-gray-600 mt-1">
                                        {storeAccount.account_number}
                                      </p>
                                    )}
                                  </div>
                                  {storeAccount && (
                                    <p className="font-semibold text-green-600">
                                      {formatCurrency(storeAccount.balance)}
                                    </p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Recent Transactions */}
                    <div>
                      <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                        <Building2 className="h-5 w-5 text-[var(--tenant-primary-color,#004F71)]" />
                        Recent Transactions
                      </h3>
                      {data.recentTransactions.length === 0 ? (
                        <p className="text-sm text-gray-500">
                          No recent transactions
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {data.recentTransactions.map((txn, index) => {
                            const isCredit =
                              parseFloat((txn.credit ?? 0).toString()) > 0;
                            const amount = isCredit
                              ? parseFloat((txn.credit ?? 0).toString())
                              : parseFloat((txn.debit ?? 0).toString());
                            return (
                              <div
                                key={txn.id || index}
                                className="bg-white rounded-lg p-4 border border-gray-200 flex items-center justify-between"
                              >
                                <div className="flex items-center gap-3">
                                  <div
                                    className={`p-2 rounded-lg ${
                                      isCredit
                                        ? "bg-green-100"
                                        : "bg-orange-100"
                                    }`}
                                  >
                                    {isCredit ? (
                                      <ArrowUpRight className="h-4 w-4 text-green-600" />
                                    ) : (
                                      <ArrowDownLeft className="h-4 w-4 text-orange-600" />
                                    )}
                                  </div>
                                  <div>
                                    <p className="text-sm font-medium text-gray-900">
                                      {txn.description || "Transaction"}
                                    </p>
                                    <p className="text-xs text-gray-500">
                                      {new Date(
                                        txn.created_at,
                                      ).toLocaleDateString("en-NG", {
                                        month: "short",
                                        day: "numeric",
                                        hour: "2-digit",
                                        minute: "2-digit",
                                      })}
                                    </p>
                                  </div>
                                </div>
                                <p
                                  className={`font-semibold ${
                                    isCredit
                                      ? "text-green-600"
                                      : "text-orange-600"
                                  }`}
                                >
                                  {isCredit ? "+" : "-"}
                                  {formatCurrency(amount)}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredData.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <TrendingUp className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {searchQuery || filterRole !== "all" || filterStatus !== "all"
              ? "No agents found matching your criteria."
              : "No agent business data available."}
          </p>
        </div>
      )}
    </div>
  );
};

export default AgentBusinessReports;
