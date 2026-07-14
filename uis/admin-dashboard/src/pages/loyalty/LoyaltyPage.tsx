import { RefreshCw, Star } from "lucide-react";
import React, { useEffect, useState } from "react";
import {
    loyaltyApi,
    type LoyaltyAccountResponse,
    type LoyaltyActivityResponse,
    type LoyaltyTier,
} from "../../utils/api";

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)]";
const buttonClass =
  "bg-[var(--tenant-primary-color,#002082)] text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-60 disabled:cursor-not-allowed";
const deleteButtonClass =
  "bg-red-600 text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-red-700 disabled:opacity-60";

const parseUserId = (value: string, fieldLabel = "User ID"): string => {
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${fieldLabel} is required`);
  }
  return trimmed;
};

const LoyaltyPage: React.FC = () => {
  const tabs = ["accounts", "activities", "monitoring"] as const;
  type LoyaltyTab = (typeof tabs)[number];

  const [accounts, setAccounts] = useState<LoyaltyAccountResponse[]>([]);
  const [activities, setActivities] = useState<LoyaltyActivityResponse[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [createUserId, setCreateUserId] = useState<string>("");
  const [updatePoints, setUpdatePoints] = useState<string>("");
  const [updateTier, setUpdateTier] = useState<LoyaltyTier | "">("");
  const [skip, setSkip] = useState<string>("0");
  const [limit, setLimit] = useState<string>("20");
  const [health, setHealth] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [activeTab, setActiveTab] = useState<LoyaltyTab>("accounts");

  const loadMonitoring = async () => {
    const [h, s, m] = await Promise.all([
      loyaltyApi.health(),
      loyaltyApi.status(),
      loyaltyApi.metrics(),
    ]);
    setHealth(h);
    setStatus(s);
    setMetrics(m);
  };

  const loadAccounts = async () => {
    const response = await loyaltyApi.listAccounts({
      skip: Number(skip) || 0,
      limit: Number(limit) || 20,
    });
    setAccounts(Array.isArray(response) ? response : []);
  };

  const loadActivities = async () => {
    if (!selectedUserId) return;
    const userId = parseUserId(selectedUserId, "Selected User ID");
    const response = await loyaltyApi.getActivities(userId, {
      skip: 0,
      limit: 100,
    });
    setActivities(Array.isArray(response) ? response : []);
  };

  const run = async (action: () => Promise<void>, okMessage: string) => {
    setLoading(true);
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(okMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    run(async () => {
      await Promise.all([loadMonitoring(), loadAccounts()]);
    }, "Loaded loyalty dashboard");
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Star className="h-6 w-6 text-yellow-500" />
            Loyalty Management
          </h1>
          <p className="text-gray-600 mt-1">
            Manage customer loyalty accounts, activities, and health metrics
          </p>
        </div>
        <button
          className={buttonClass}
          disabled={loading}
          onClick={() =>
            run(async () => {
              await Promise.all([loadMonitoring(), loadAccounts()]);
            }, "Loyalty dashboard refreshed")
          }
        >
          <RefreshCw className="h-4 w-4 inline mr-2" />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-yellow-500">
          <p className="text-sm text-gray-600">Accounts</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {accounts.length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
          <p className="text-sm text-gray-600">Activities Loaded</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {activities.length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
          <p className="text-sm text-gray-600">Requests Total</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {metrics?.requests_total ?? "-"}
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg">
          {error}
        </div>
      )}
      {message && (
        <div className="bg-green-50 border border-green-200 text-green-700 p-3 rounded-lg">
          {message}
        </div>
      )}

      <div className="bg-white border rounded-lg p-2 shadow">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab}
              className={`px-4 py-2 rounded-lg text-sm font-semibold capitalize transition-colors ${
                activeTab === tab
                  ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "accounts" && (
        <>
          <div className="bg-white border rounded-lg p-6 shadow">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Create New Account
            </h2>
            <div className="flex gap-2">
              <input
                className={inputClass}
                placeholder="User ID (string)"
                value={createUserId}
                onChange={(e) => setCreateUserId(e.target.value)}
              />
              <button
                className={buttonClass}
                disabled={loading}
                onClick={() =>
                  run(async () => {
                    const userId = parseUserId(createUserId, "Create User ID");
                    await loyaltyApi.createAccount(userId);
                    await loadAccounts();
                  }, "Loyalty account created")
                }
              >
                Create
              </button>
            </div>
          </div>

          <div className="bg-white border rounded-lg p-6 shadow space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Account Lookup & Admin Actions
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <input
                className={inputClass}
                placeholder="User ID (string)"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Current Points"
                value={updatePoints}
                onChange={(e) => setUpdatePoints(e.target.value)}
              />
              <select
                className={inputClass}
                value={updateTier}
                onChange={(e) =>
                  setUpdateTier(e.target.value as LoyaltyTier | "")
                }
              >
                <option value="">Tier (optional)</option>
                <option value="Bronze">Bronze</option>
                <option value="Silver">Silver</option>
                <option value="Gold">Gold</option>
                <option value="Platinum">Platinum</option>
              </select>
              <button
                className={buttonClass}
                disabled={loading}
                onClick={() =>
                  run(async () => {
                    const userId = parseUserId(
                      selectedUserId,
                      "Selected User ID",
                    );
                    await loyaltyApi.getAccount(userId);
                    await loadActivities();
                  }, "Account loaded")
                }
              >
                Load
              </button>
            </div>
            <div className="flex flex-wrap gap-2 pt-2">
              <button
                className={buttonClass}
                disabled={loading}
                onClick={() =>
                  run(async () => {
                    const userId = parseUserId(
                      selectedUserId,
                      "Selected User ID",
                    );
                    await loyaltyApi.updateAccount(userId, {
                      tier: updateTier || undefined,
                      current_points: updatePoints
                        ? Number(updatePoints)
                        : undefined,
                    });
                    await Promise.all([loadAccounts(), loadActivities()]);
                  }, "Account updated")
                }
              >
                Update Account
              </button>
              <button
                className={deleteButtonClass}
                disabled={loading}
                onClick={() =>
                  run(async () => {
                    const userId = parseUserId(
                      selectedUserId,
                      "Selected User ID",
                    );
                    await loyaltyApi.deleteAccount(userId);
                    setActivities([]);
                    await loadAccounts();
                  }, "Account deleted")
                }
              >
                Delete Account
              </button>
            </div>
          </div>

          <div className="bg-white border rounded-lg p-6 shadow">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                All Accounts
              </h2>
              <div className="flex gap-2 items-center">
                <input
                  className={inputClass}
                  style={{ maxWidth: 100 }}
                  placeholder="Skip"
                  value={skip}
                  onChange={(e) => setSkip(e.target.value)}
                />
                <input
                  className={inputClass}
                  style={{ maxWidth: 100 }}
                  placeholder="Limit"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                />
                <button
                  className={buttonClass}
                  disabled={loading}
                  onClick={() => run(loadAccounts, "Accounts refreshed")}
                >
                  Refresh
                </button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">User</th>
                    <th className="px-3 py-2 text-left">Points</th>
                    <th className="px-3 py-2 text-left">Tier</th>
                    <th className="px-3 py-2 text-left">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id} className="border-t">
                      <td className="px-3 py-2">{account.user_id}</td>
                      <td className="px-3 py-2">{account.current_points}</td>
                      <td className="px-3 py-2">{account.tier}</td>
                      <td className="px-3 py-2">
                        {new Date(account.updated_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {activeTab === "activities" && (
        <div className="bg-white border rounded-lg p-6 shadow">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Activities (Selected User)
            </h2>
            <div className="flex gap-2">
              <input
                className={inputClass}
                placeholder="User ID (string)"
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
              />
              <button
                className={buttonClass}
                disabled={loading}
                onClick={() => run(loadActivities, "Activities refreshed")}
              >
                Refresh
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Points</th>
                  <th className="px-3 py-2 text-left">Reference</th>
                  <th className="px-3 py-2 text-left">Created</th>
                </tr>
              </thead>
              <tbody>
                {activities.map((activity) => (
                  <tr key={activity.id} className="border-t">
                    <td className="px-3 py-2">{activity.type}</td>
                    <td className="px-3 py-2">{activity.points_change}</td>
                    <td className="px-3 py-2">
                      {activity.reference_id || "-"}
                    </td>
                    <td className="px-3 py-2">
                      {new Date(activity.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "monitoring" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border rounded-lg p-4 shadow border-l-4 border-blue-500">
              <p className="text-sm text-gray-600">Health Status</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {health?.status ?? "-"}
              </p>
            </div>
            <div className="bg-white border rounded-lg p-4 shadow border-l-4 border-green-500">
              <p className="text-sm text-gray-600">Service Status</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {status?.status ?? "-"}
              </p>
            </div>
            <div className="bg-white border rounded-lg p-4 shadow border-l-4 border-purple-500">
              <p className="text-sm text-gray-600">Total Requests</p>
              <p className="text-xl font-bold text-gray-900 mt-1">
                {metrics?.requests_total ?? "-"}
              </p>
            </div>
          </div>
          <div className="bg-white border rounded-lg p-6 shadow">
            <button
              className={buttonClass}
              disabled={loading}
              onClick={() => run(loadMonitoring, "Monitoring refreshed")}
            >
              <RefreshCw className="h-4 w-4 inline mr-2" />
              Refresh Monitoring Data
            </button>
          </div>
        </>
      )}
    </div>
  );
};

export default LoyaltyPage;
