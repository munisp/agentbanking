import {
    Activity,
    AlertTriangle,
    Cpu,
    RefreshCw,
    Smartphone,
    Terminal,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import MDMCommandsDrawer from "../components/POSManagement/MDMCommandsDrawer";
import {
    api,
    type MdmDevice,
    type MdmFleetStats,
    type MdmTamperAlert,
} from "../utils/api";

const MDMPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [fleetStats, setFleetStats] = useState<MdmFleetStats | null>(null);
  const [devices, setDevices] = useState<MdmDevice[]>([]);
  const [tamperAlerts, setTamperAlerts] = useState<MdmTamperAlert[]>([]);
  const [actionLoading, setActionLoading] = useState<Record<string, string>>(
    {},
  );
  const [commandsDevice, setCommandsDevice] = useState<MdmDevice | null>(null);

  const [filters, setFilters] = useState({
    model_id: "",
    state: "",
    agent_id: "",
  });

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [fleet, devicesResult, alerts] = await Promise.all([
        api.getMdmFleetStats(),
        api.getMdmDevices(),
        api.getMdmTamperAlerts(),
      ]);

      setFleetStats(fleet);
      setDevices(
        Array.isArray(devicesResult?.devices) ? devicesResult.devices : [],
      );
      setTamperAlerts(Array.isArray(alerts?.alerts) ? alerts.alerts : []);
      setSuccess("Data refreshed successfully");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load MDM data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const applyFilters = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getMdmDevices({
        model_id: filters.model_id || undefined,
        state: filters.state || undefined,
        agent_id: filters.agent_id || undefined,
      });
      setDevices(Array.isArray(response?.devices) ? response.devices : []);
      setSuccess(`Loaded ${response?.devices?.length ?? 0} device(s)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply filters");
    } finally {
      setLoading(false);
    }
  };

  const getStateColor = (state: string) => {
    if (state === "active") return "bg-green-100 text-green-800";
    if (state === "suspended") return "bg-yellow-100 text-yellow-800";
    if (state === "decommissioned") return "bg-red-100 text-red-800";
    return "bg-gray-100 text-gray-700";
  };

  const runRemoteCommand = async (
    device: MdmDevice,
    commandType: string,
    successLabel: string,
    options?: { confirmMessage?: string },
  ) => {
    if (options?.confirmMessage && !window.confirm(options.confirmMessage)) {
      return;
    }

    const actionKey = `${device.terminal_id}:${commandType}`;
    setActionLoading((previous) => ({ ...previous, [actionKey]: "running" }));
    setError(null);
    setSuccess(null);

    try {
      await api.createMdmCommand({
        terminal_id: device.terminal_id,
        model_id: device.model_id,
        command_type: commandType,
        issued_by: "admin-dashboard",
      });
      setSuccess(`${successLabel} queued for ${device.terminal_id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : `Failed to queue ${commandType} for ${device.terminal_id}`,
      );
    } finally {
      setActionLoading((previous) => {
        const next = { ...previous };
        delete next[actionKey];
        return next;
      });
    }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="bg-primary rounded-lg shadow-lg p-6 text-white">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <Smartphone className="w-10 h-10" />
            <div>
              <h1 className="text-3xl font-bold">Mobile Device Management</h1>
              <p className="opacity-90">
                Monitor and manage device fleet, deployments, and alerts
              </p>
            </div>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-white hover:bg-opacity-20 disabled:opacity-60 transition"
          >
            <RefreshCw className={`w-6 h-6 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-100 text-red-700 p-4 rounded-lg font-medium">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-100 text-green-700 p-4 rounded-lg font-medium">
          {success}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">TOTAL DEVICES</p>
              <p className="text-3xl font-bold mt-1">
                {fleetStats?.total_devices ?? 0}
              </p>
            </div>
            <Smartphone className="w-10 h-10 text-blue-500 opacity-20" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">ACTIVE</p>
              <p className="text-3xl font-bold mt-1">
                {fleetStats?.by_state?.active ?? 0}
              </p>
            </div>
            <Activity className="w-10 h-10 text-green-500 opacity-20" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-yellow-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">SUSPENDED</p>
              <p className="text-3xl font-bold mt-1">
                {fleetStats?.by_state?.suspended ?? 0}
              </p>
            </div>
            <AlertTriangle className="w-10 h-10 text-yellow-500 opacity-20" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-red-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">
                DECOMMISSIONED
              </p>
              <p className="text-3xl font-bold mt-1">
                {fleetStats?.by_state?.decommissioned ?? 0}
              </p>
            </div>
            <Cpu className="w-10 h-10 text-red-500 opacity-20" />
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-orange-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm font-medium">ALERTS</p>
              <p className="text-3xl font-bold mt-1">{tamperAlerts.length}</p>
            </div>
            <AlertTriangle className="w-10 h-10 text-orange-500 opacity-20" />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-bold mb-4">FILTERS</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <input
            type="text"
            placeholder="Model ID"
            value={filters.model_id}
            onChange={(e) =>
              setFilters({ ...filters, model_id: e.target.value })
            }
            className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <input
            type="text"
            placeholder="State (active, suspended, decommissioned)"
            value={filters.state}
            onChange={(e) => setFilters({ ...filters, state: e.target.value })}
            className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <input
            type="text"
            placeholder="Agent ID"
            value={filters.agent_id}
            onChange={(e) =>
              setFilters({ ...filters, agent_id: e.target.value })
            }
            className="border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            onClick={applyFilters}
            disabled={loading}
            className="bg-primary text-white rounded-lg px-4 py-2 font-semibold text-sm hover:opacity-90 disabled:opacity-60"
          >
            Apply Filters
          </button>
        </div>
      </div>

      {/* Devices Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-bold">DEVICES ({devices.length})</h2>
        </div>
        <div className="overflow-x-auto max-h-[50vh] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 sticky top-0">
              <tr>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  TERMINAL ID
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  MODEL ID
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  AGENT ID
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  STATE
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  APK VERSION
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  FIRMWARE
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  LAST SEEN
                </th>
                <th className="px-6 py-3 text-left font-semibold text-gray-700">
                  ACTIONS
                </th>
              </tr>
            </thead>
            <tbody>
              {devices.length === 0 ? (
                <tr>
                  <td
                    colSpan={8}
                    className="px-6 py-4 text-center text-gray-500"
                  >
                    No devices found
                  </td>
                </tr>
              ) : (
                devices.map((device) => (
                  <tr
                    key={device.terminal_id}
                    className="border-t hover:bg-gray-50"
                  >
                    <td className="px-6 py-3 font-medium text-gray-900">
                      {device.terminal_id}
                    </td>
                    <td className="px-6 py-3 text-gray-700">
                      {device.model_id}
                    </td>
                    <td className="px-6 py-3 text-gray-700">
                      {device.agent_id}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${getStateColor(device.state)}`}
                      >
                        {device.state}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-gray-700">
                      {device.apk_version || "-"}
                    </td>
                    <td className="px-6 py-3 text-gray-700">
                      {device.firmware_version || "-"}
                    </td>
                    <td className="px-6 py-3 text-gray-500 text-xs">
                      {device.last_seen || "-"}
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() =>
                            runRemoteCommand(device, "reboot", "Reboot")
                          }
                          disabled={
                            Boolean(
                              actionLoading[`${device.terminal_id}:reboot`],
                            ) || device.state === "decommissioned"
                          }
                          className="px-2.5 py-1 rounded-md text-xs font-semibold bg-blue-100 text-blue-700 hover:bg-blue-200 disabled:opacity-50"
                        >
                          {actionLoading[`${device.terminal_id}:reboot`]
                            ? "..."
                            : "Reboot"}
                        </button>
                        <button
                          onClick={() =>
                            runRemoteCommand(device, "lock_terminal", "Lock")
                          }
                          disabled={
                            Boolean(
                              actionLoading[
                                `${device.terminal_id}:lock_terminal`
                              ],
                            ) || device.state === "decommissioned"
                          }
                          className="px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-100 text-amber-800 hover:bg-amber-200 disabled:opacity-50"
                        >
                          {actionLoading[`${device.terminal_id}:lock_terminal`]
                            ? "..."
                            : "Lock"}
                        </button>
                        <button
                          onClick={() =>
                            runRemoteCommand(
                              device,
                              "unlock_terminal",
                              "Unlock",
                            )
                          }
                          disabled={
                            Boolean(
                              actionLoading[
                                `${device.terminal_id}:unlock_terminal`
                              ],
                            ) || device.state === "decommissioned"
                          }
                          className="px-2.5 py-1 rounded-md text-xs font-semibold bg-green-100 text-green-700 hover:bg-green-200 disabled:opacity-50"
                        >
                          {actionLoading[
                            `${device.terminal_id}:unlock_terminal`
                          ]
                            ? "..."
                            : "Unlock"}
                        </button>
                        <button
                          onClick={() =>
                            runRemoteCommand(
                              device,
                              "get_diagnostics",
                              "Diagnostics request",
                            )
                          }
                          disabled={
                            Boolean(
                              actionLoading[
                                `${device.terminal_id}:get_diagnostics`
                              ],
                            ) || device.state === "decommissioned"
                          }
                          className="px-2.5 py-1 rounded-md text-xs font-semibold bg-purple-100 text-purple-700 hover:bg-purple-200 disabled:opacity-50"
                        >
                          {actionLoading[
                            `${device.terminal_id}:get_diagnostics`
                          ]
                            ? "..."
                            : "Diagnostics"}
                        </button>
                        <button
                          onClick={() =>
                            runRemoteCommand(
                              device,
                              "remote_wipe",
                              "Remote wipe",
                              {
                                confirmMessage:
                                  "This will erase terminal data and apps. Continue with remote wipe?",
                              },
                            )
                          }
                          disabled={
                            Boolean(
                              actionLoading[
                                `${device.terminal_id}:remote_wipe`
                              ],
                            ) || device.state === "decommissioned"
                          }
                          className="px-2.5 py-1 rounded-md text-xs font-semibold bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50"
                        >
                          {actionLoading[`${device.terminal_id}:remote_wipe`]
                            ? "..."
                            : "Remote Wipe"}
                        </button>
                        <button
                          onClick={() => setCommandsDevice(device)}
                          className="px-2.5 py-1 rounded-md text-xs font-semibold bg-gray-800 text-white hover:bg-gray-900 flex items-center gap-1"
                        >
                          <Terminal size={12} />
                          All Commands
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MDM Commands Drawer */}
      {commandsDevice && (
        <MDMCommandsDrawer
          device={commandsDevice}
          onClose={() => setCommandsDevice(null)}
        />
      )}

      {/* Tamper Alerts */}
      {tamperAlerts.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            TAMPER ALERTS ({tamperAlerts.length})
          </h2>
          <div className="space-y-3 max-h-[40vh] overflow-y-auto">
            {tamperAlerts.map((alert) => (
              <div
                key={`${alert.terminal_id}-${alert.timestamp}`}
                className={`border-l-4 rounded-lg p-4 ${
                  alert.severity === "critical"
                    ? "border-red-500 bg-red-50"
                    : alert.severity === "high"
                      ? "border-orange-500 bg-orange-50"
                      : "border-yellow-500 bg-yellow-50"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-gray-900">
                      {alert.terminal_id}
                    </p>
                    <p className="text-gray-700 text-sm mt-1">
                      {alert.alert_type}: {alert.details}
                    </p>
                    <p className="text-gray-500 text-xs mt-2">
                      {alert.timestamp}
                    </p>
                  </div>
                  <span
                    className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                      alert.severity === "critical"
                        ? "bg-red-200 text-red-800"
                        : alert.severity === "high"
                          ? "bg-orange-200 text-orange-800"
                          : "bg-yellow-200 text-yellow-800"
                    }`}
                  >
                    {alert.severity.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MDMPage;
