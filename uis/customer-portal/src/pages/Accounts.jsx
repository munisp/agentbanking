import { Building2, Download, Loader, Wallet } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { accountApi } from "../utils/api";

const Accounts = () => {
  const { user } = useAuth();

  const [account, setAccount] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadAccount();
  }, [user?.keycloakId]);

  const loadAccount = async () => {
    if (!user?.keycloakId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);

      const response = await accountApi.getByKeycloakId(user.keycloakId);
      const accountData = response.account || response.data || response;
      setAccount(accountData);
    } catch (err) {
      console.error("Failed to load account:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
        return "bg-blue-100 text-blue-800";
      case "savings":
        return "bg-green-100 text-green-800";
      case "mint":
        return "bg-purple-100 text-purple-800";
      case "current":
        return "bg-indigo-100 text-indigo-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const exportToCSV = () => {
    if (!account) return;

    const headers = [
      "Account Number",
      "Name",
      "Account Type",
      "Status",
      "Balance",
      "Created Date",
      "Keycloak ID",
    ];

    const row = [
      account.account_number,
      account.name || user?.firstName + " " + user?.lastName || "My Account",
      account.account_type || "N/A",
      account.status || "active",
      account.balance || 0,
      new Date(account.created_at).toLocaleDateString(),
      account.keycloak_id || user?.keycloakId || "",
    ];

    const csvContent = [headers, row]
      .map((r) => r.map((cell) => `"${cell}"`).join(","))
      .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `my-account-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto text-green-600" />
          <p className="mt-2 text-gray-600">Loading account...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-7 w-7 text-green-600" />
            My Account
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            View your account details and balance
          </p>
        </div>
        {account && (
          <button
            onClick={exportToCSV}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Download className="h-4 w-4" />
            Export Details
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Account Summary Card */}
      {account && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex items-center gap-4">
              <div className="bg-green-100 p-3 rounded-lg">
                <Wallet className="h-8 w-8 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Account Balance</p>
                <p className="text-2xl font-bold text-gray-900">
                  {formatCurrency(account.balance)}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="bg-blue-100 p-3 rounded-lg">
                <Building2 className="h-8 w-8 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Account Number</p>
                <p className="text-xl font-bold text-gray-900">
                  {account.account_number}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="bg-purple-100 p-3 rounded-lg">
                <Building2 className="h-8 w-8 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Account Status</p>
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium capitalize ${getStatusColor(
                    account.status,
                  )}`}
                >
                  {account.status || "active"}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Account Details Table */}
      {account && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Account Details
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Field
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Account Number
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {account.account_number}
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Account Name
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {account.name ||
                      `${user?.firstName || ""} ${user?.lastName || ""}`.trim() ||
                      "My Account"}
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Account Type
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getAccountTypeColor(
                        account.account_type,
                      )}`}
                    >
                      {account.account_type || "Primary"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Status
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getStatusColor(
                        account.status,
                      )}`}
                    >
                      {account.status || "active"}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Balance
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-green-600">
                    {formatCurrency(account.balance)}
                  </td>
                </tr>
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Created Date
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                    {new Date(account.created_at).toLocaleDateString("en-NG", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </td>
                </tr>
                {account.updated_at && (
                  <tr>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      Last Updated
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {new Date(account.updated_at).toLocaleDateString(
                        "en-NG",
                        {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        },
                      )}
                    </td>
                  </tr>
                )}
                {/* <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    Keycloak ID
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-700 font-mono break-all">
                    {account.keycloak_id || user?.keycloakId || "N/A"}
                  </td>
                </tr> */}
                {/* {account.ledger_id && (
                  <tr>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      Ledger ID
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {account.ledger_id}
                    </td>
                  </tr>
                )} */}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && !account && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No account found.</p>
          <p className="text-sm text-gray-400 mt-2">
            Please contact support if you believe this is an error.
          </p>
        </div>
      )}
    </div>
  );
};

export default Accounts;
