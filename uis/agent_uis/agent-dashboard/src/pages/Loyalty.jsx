import React, { useState } from "react";
import { loyaltyApi } from "../utils/api";

const inputClass = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm";

export default function Loyalty() {
  const [userId, setUserId] = useState("");
  const [points, setPoints] = useState("");
  const [referenceId, setReferenceId] = useState("");
  const [description, setDescription] = useState("");
  const [account, setAccount] = useState(null);
  const [activities, setActivities] = useState([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const run = async (action, okMessage) => {
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

  const loadAccount = async () => {
    const data = await loyaltyApi.getAccount(Number(userId));
    setAccount(data);
  };

  const loadActivities = async () => {
    const data = await loyaltyApi.getActivities(Number(userId), { limit: 50 });
    setActivities(Array.isArray(data) ? data : []);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Loyalty (Agent)</h1>

      {error && (
        <div className="bg-red-100 text-red-700 p-3 rounded-lg">{error}</div>
      )}
      {message && (
        <div className="bg-green-100 text-green-700 p-3 rounded-lg">
          {message}
        </div>
      )}

      <div className="bg-white border rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Customer</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            className={inputClass}
            placeholder="User ID"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
          <button
            className="bg-primary text-white rounded-lg px-4 py-2"
            disabled={loading}
            onClick={() =>
              run(async () => {
                await loyaltyApi.createAccount(Number(userId));
                await loadAccount();
              }, "Loyalty account created")
            }
          >
            Enroll Customer
          </button>
          <button
            className="bg-gray-800 text-white rounded-lg px-4 py-2"
            disabled={loading}
            onClick={() => run(loadAccount, "Account loaded")}
          >
            Load Account
          </button>
          <button
            className="bg-gray-700 text-white rounded-lg px-4 py-2"
            disabled={loading}
            onClick={() => run(loadActivities, "Activities loaded")}
          >
            Load Activities
          </button>
        </div>
      </div>

      <div className="bg-white border rounded-xl p-4 space-y-3">
        <h2 className="font-semibold">Points Transaction</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            className={inputClass}
            placeholder="Points"
            value={points}
            onChange={(e) => setPoints(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Reference ID"
            value={referenceId}
            onChange={(e) => setReferenceId(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <button
            className="bg-green-600 text-white rounded-lg px-4 py-2"
            disabled={loading}
            onClick={() =>
              run(async () => {
                await loyaltyApi.earnPoints(Number(userId), {
                  type: "EARN",
                  points_change: Number(points),
                  description,
                  reference_id: referenceId || undefined,
                });
                await Promise.all([loadAccount(), loadActivities()]);
              }, "Points earned")
            }
          >
            Earn
          </button>
          <button
            className="bg-amber-600 text-white rounded-lg px-4 py-2"
            disabled={loading}
            onClick={() =>
              run(async () => {
                await loyaltyApi.spendPoints(Number(userId), {
                  type: "SPEND",
                  points_change: Number(points),
                  description,
                  reference_id: referenceId || undefined,
                });
                await Promise.all([loadAccount(), loadActivities()]);
              }, "Points spent")
            }
          >
            Spend
          </button>
        </div>
      </div>

      {account && (
        <div className="bg-white border rounded-xl p-4">
          <h2 className="font-semibold mb-2">Account</h2>
          <p>User: {account.user_id}</p>
          <p>Points: {account.current_points}</p>
          <p>Tier: {account.tier}</p>
          <p>Updated: {new Date(account.updated_at).toLocaleString()}</p>
        </div>
      )}

      <div className="bg-white border rounded-xl p-4">
        <h2 className="font-semibold mb-2">Activities</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Points</th>
                <th className="px-3 py-2 text-left">Description</th>
                <th className="px-3 py-2 text-left">Reference</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((activity) => (
                <tr key={activity.id} className="border-t">
                  <td className="px-3 py-2">{activity.type}</td>
                  <td className="px-3 py-2">{activity.points_change}</td>
                  <td className="px-3 py-2">{activity.description}</td>
                  <td className="px-3 py-2">{activity.reference_id || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
