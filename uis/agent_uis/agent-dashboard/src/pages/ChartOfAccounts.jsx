import {
    Building2,
    Download,
    Filter,
    Loader,
    Search,
    Store,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { accountApi, authHeaders, inventoryApi } from "../utils/api";

const ChartOfAccounts = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const keycloakId = user?.keycloakId;
        if (!keycloakId) {
          console.warn("No keycloak ID found for user");
          return;
        }

        // Fetch agent's own account
        const agentAccountData =
          await accountApi.getAccountByKeycloakId(keycloakId);
        const agentAccount = agentAccountData.account || agentAccountData;

        // Fetch agent's stores
        const storesData = await inventoryApi.getStores(keycloakId);
        const storesList = Array.isArray(storesData.data)
          ? storesData.data
          : Array.isArray(storesData)
            ? storesData
            : [];
        setStores(storesList);

        // Fetch accounts for each store using ledger endpoint
        const storeAccountPromises = storesList.map(async (store) => {
          if (store.account_number) {
            try {
              const response = await fetch(
                `https://54agent.upi.dev/account/account/account-number/${store.account_number}`,
                {
                  headers: authHeaders(),
                },
              );
              if (response.ok) {
                const data = await response.json();
                // Extract account details from ledger response
                return data.account || data;
              }
              return null;
            } catch (err) {
              console.error(
                `Failed to fetch account for store ${store.id}:`,
                err,
              );
              return null;
            }
          }
          return null;
        });

        const storeAccounts = (await Promise.all(storeAccountPromises)).filter(
          Boolean,
        );

        // Combine agent account and store accounts
        const allAccounts = [agentAccount, ...storeAccounts].filter(Boolean);
        setAccounts(allAccounts);
      } catch (error) {
        console.error("Error fetching chart of accounts:", error);
      } finally {
        setLoading(false);
      }
    };

    if (user) {
      fetchData();
    }
  }, [user]);

  // Enrich accounts with owner information
  const enrichedAccounts = accounts.map((account) => {
    // Check if this is agent's own account
    const isAgentAccount = account.name === user?.name;

    // Find matching store
    const store = stores.find(
      (s) => s.account_number === account.account_number,
    );

    return {
      ...account,
      ownerName: isAgentAccount
        ? `${user?.firstName || ""} ${user?.lastName || ""}`.trim() ||
          "My Account"
        : store
          ? store.name
          : account.name,
      ownerType: isAgentAccount ? "agent" : "store",
      storeInfo: store,
    };
  });

  // Filter accounts
  const filteredAccounts = enrichedAccounts.filter((account) => {
    const matchesSearch =
      !searchQuery ||
      account.account_number
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      account.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      account.ownerName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      account.account_type?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesType =
      filterType === "all" ||
      (filterType === "agent" && account.ownerType === "agent") ||
      (filterType === "store" && account.ownerType === "store") ||
      account.account_type?.toLowerCase() === filterType.toLowerCase();

    return matchesSearch && matchesType;
  });

  // Calculate statistics
  const agentAccounts = enrichedAccounts.filter((a) => a.ownerType === "agent");
  const storeAccounts = enrichedAccounts.filter((a) => a.ownerType === "store");
  const totalBalance = enrichedAccounts.reduce(
    (sum, acc) => sum + (parseFloat(acc.balance) || 0),
    0,
  );

  // Export to CSV
  const exportToCSV = () => {
    const headers = [
      "Account Number",
      "Name",
      "Owner",
      "Owner Type",
      "Account Type",
      "Status",
      "Balance",
      "Created Date",
      "Keycloak ID",
    ];

    const rows = filteredAccounts.map((account) => [
      account.account_number,
      account.name,
      account.ownerName,
      account.ownerType,
      account.account_type || "",
      account.status || "",
      account.balance || 0,
      new Date(account.created_at).toLocaleDateString(),
      account.keycloak_id || "",
    ]);

    const csvContent = [headers, ...rows]
      .map((row) => row.map((cell) => `"${cell}"`).join(","))
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chart-of-accounts-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency: "NGN",
    }).format(amount || 0);
  };

  const getStatusColor = (status) => {
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

  const getAccountTypeColor = (type) => {
    switch (type?.toLowerCase()) {
      case "primary":
        return "text-white";
      case "savings":
        return "bg-green-100 text-green-800";
      case "mint":
        return "bg-purple-100 text-purple-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getOwnerTypeColor = (type) => {
    switch (type?.toLowerCase()) {
      case "agent":
        return "text-white";
      case "store":
        return "bg-orange-100 text-orange-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="p-3 sm:p-4 lg:p-6 space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-7 w-7" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            My Chart of Accounts
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            View your account and your business accounts
          </p>
        </div>
        <button
          onClick={exportToCSV}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors"
          disabled={filteredAccounts.length === 0}
        >
          <Download className="h-4 w-4" />
          Export CSV
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Accounts</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {enrichedAccounts.length}
              </p>
            </div>
            <div className="bg-gray-100 p-3 rounded-lg">
              <Building2 className="h-6 w-6 text-gray-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">My Account</p>
              <p
                className="text-2xl font-bold mt-1"
                style={{ color: "var(--tenant-primary-color,#002082)" }}
              >
                {agentAccounts.length}
              </p>
            </div>
            <div
              className="p-3 rounded-lg"
              style={{ backgroundColor: "rgba(0, 79, 113, 0.1)" }}
            >
              <Building2 className="h-6 w-6" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Store Accounts</p>
              <p className="text-2xl font-bold text-orange-600 mt-1">
                {storeAccounts.length}
              </p>
            </div>
            <div className="bg-orange-100 p-3 rounded-lg">
              <Store className="h-6 w-6 text-orange-600" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-4 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Balance</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {formatCurrency(totalBalance)}
              </p>
            </div>
            <div className="bg-green-100 p-3 rounded-lg">
              <Building2 className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search by account number, name, or owner..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="relative sm:w-64">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none bg-white"
            >
              <option value="all">All Accounts</option>
              <option value="agent">My Account</option>
              <option value="store">Store Accounts</option>
              <option value="primary">Primary</option>
              <option value="savings">Savings</option>
              <option value="mint">Mint</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto text-blue-600" />
          <p className="mt-2 text-gray-600">Loading accounts...</p>
        </div>
      )}

      {/* Accounts Table */}
      {!loading && filteredAccounts.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto max-h-[60vh] overflow-scroll">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Account Details
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Owner
                  </th>
                  {/* <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Owner Type
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Account Type
                  </th> */}
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Balance
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredAccounts.map((account) => (
                  <tr key={account.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-gray-900">
                          {account.account_number}
                        </p>
                        <p className="text-sm text-gray-500">{account.name}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-gray-900">
                          {account.ownerName}
                        </p>
                        {account.storeInfo && (
                          <p className="text-sm text-gray-500">
                            Store ID: {account.storeInfo.id}
                          </p>
                        )}
                      </div>
                    </td>
                    {/* <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getOwnerTypeColor(
                          account.ownerType,
                        )}`}
                      >
                        {account.ownerType}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getAccountTypeColor(
                          account.account_type,
                        )}`}
                      >
                        {account.account_type || "N/A"}
                      </span>
                    </td> */}
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                          account.status,
                        )}`}
                      >
                        {account.status || "pending"}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {formatCurrency(account.balance)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(account.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredAccounts.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {searchQuery || filterType !== "all"
              ? "No accounts found matching your criteria."
              : "No accounts available."}
          </p>
        </div>
      )}
    </div>
  );
};

export default ChartOfAccounts;
