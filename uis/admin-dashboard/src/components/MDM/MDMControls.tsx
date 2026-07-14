import React, { useEffect, useMemo, useState } from "react";
import {
  api,
  type MdmApkDeploymentStatus,
  type MdmApkVariant,
  type MdmBulkStatusResponse,
  type MdmCommandTypesResponse,
  type MdmDevice,
  type MdmDiagnostics,
  type MdmFirmwareDeployStatus,
  type MdmFirmwareUpdate,
  type MdmFleetStats,
  type MdmModelStats,
  type MdmTamperAlert,
} from "../../utils/api";

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-primary";

const buttonClass =
  "bg-primary text-white px-4 py-2 rounded-lg font-semibold text-sm hover:opacity-90 disabled:opacity-60";

const MDMControls: React.FC = () => {
  const tabs = ["overview", "operations", "deployments", "lookups"] as const;
  type MdmTab = (typeof tabs)[number];

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [success, setSuccess] = useState<string>("");
  const [activeTab, setActiveTab] = useState<MdmTab>("overview");

  const [devices, setDevices] = useState<MdmDevice[]>([]);
  const [fleetStats, setFleetStats] = useState<MdmFleetStats | null>(null);
  const [tamperAlerts, setTamperAlerts] = useState<MdmTamperAlert[]>([]);
  const [commandTypes, setCommandTypes] = useState<string[]>([]);
  const [apkVariants, setApkVariants] = useState<MdmApkVariant[]>([]);

  const [lookupResult, setLookupResult] = useState<unknown>(null);
  const [deploymentStatus, setDeploymentStatus] =
    useState<MdmApkDeploymentStatus | null>(null);
  const [firmwareStatus, setFirmwareStatus] =
    useState<MdmFirmwareDeployStatus | null>(null);
  const [bulkStatus, setBulkStatus] = useState<MdmBulkStatusResponse | null>(
    null,
  );

  const [deviceFilters, setDeviceFilters] = useState({
    model_id: "",
    state: "",
    agent_id: "",
  });

  const [provisionForm, setProvisionForm] = useState({
    terminal_id: "",
    model_id: "",
    serial_number: "",
    agent_id: "",
    location_id: "",
  });

  const [commandForm, setCommandForm] = useState({
    terminal_id: "",
    model_id: "",
    command_type: "",
    priority: "5",
    issued_by: "",
    params: "{}",
  });

  const [apkDeployForm, setApkDeployForm] = useState({
    terminal_ids: "",
    model_id: "",
    apk_variant: "",
    force: false,
    scheduled_at: "",
  });
  const [apkFile, setApkFile] = useState<File | null>(null);

  const [firmwareForm, setFirmwareForm] = useState({
    terminal_id: "",
    model_id: "",
    version: "",
  });

  const [stateForm, setStateForm] = useState({
    terminal_id: "",
    state: "",
    reason: "",
  });

  const [bulkCommandForm, setBulkCommandForm] = useState({
    command_type: "",
    model_id: "",
    agent_id: "",
    params: "{}",
  });

  const [bulkDeployForm, setBulkDeployForm] = useState({
    model_id: "",
    apk_variant: "",
  });

  const [configPushForm, setConfigPushForm] = useState({
    terminal_id: "",
    config: '{"log_level":"debug","sync_interval":120}',
  });

  const [queryForm, setQueryForm] = useState({
    terminal_id: "",
    model_id: "",
    command_id: "",
    deployment_id: "",
    update_id: "",
    batch_id: "",
  });

  const stateBadgeClass = useMemo(
    () => (state: string) => {
      if (state === "active") return "bg-green-100 text-green-800";
      if (state === "suspended") return "bg-yellow-100 text-yellow-800";
      if (state === "decommissioned") return "bg-red-100 text-red-800";
      return "bg-gray-100 text-gray-700";
    },
    [],
  );

  const lookupDevices = useMemo(() => {
    if (
      lookupResult &&
      typeof lookupResult === "object" &&
      "devices" in lookupResult
    ) {
      const maybeDevices = (lookupResult as { devices?: unknown }).devices;
      if (Array.isArray(maybeDevices)) {
        return maybeDevices as MdmDevice[];
      }
    }
    return [] as MdmDevice[];
  }, [lookupResult]);

  const showError = (err: unknown) => {
    const message = err instanceof Error ? err.message : "Request failed";
    setError(message);
    setSuccess("");
  };

  const showSuccess = (message: string) => {
    setSuccess(message);
    setError("");
  };

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [fleet, devicesResponse, alerts, commands, variants] =
        await Promise.all([
          api.getMdmFleetStats(),
          api.getMdmDevices(),
          api.getMdmTamperAlerts(),
          api.getMdmCommandTypes(),
          api.getMdmApkVariants(),
        ]);

      const normalizedDevices = Array.isArray(devicesResponse?.devices)
        ? devicesResponse.devices
        : [];
      const normalizedAlerts = Array.isArray(alerts?.alerts)
        ? alerts.alerts
        : [];
      const normalizedCommandTypes = Array.isArray(
        (commands as MdmCommandTypesResponse)?.command_types,
      )
        ? (commands as MdmCommandTypesResponse).command_types
        : [];
      const normalizedVariants = Array.isArray(variants?.variants)
        ? variants.variants
        : [];

      setFleetStats(fleet);
      setDevices(normalizedDevices);
      setTamperAlerts(normalizedAlerts);
      setCommandTypes(normalizedCommandTypes);
      setApkVariants(normalizedVariants);
      if (normalizedVariants.length && !apkDeployForm.apk_variant) {
        setApkDeployForm((previous) => ({
          ...previous,
          apk_variant: normalizedVariants[0].name,
        }));
      }
    } catch (err) {
      showError(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const fetchDevices = async () => {
    try {
      const response = await api.getMdmDevices({
        model_id: deviceFilters.model_id || undefined,
        state: deviceFilters.state || undefined,
        agent_id: deviceFilters.agent_id || undefined,
      });
      const normalizedDevices = Array.isArray(response?.devices)
        ? response.devices
        : [];
      setDevices(normalizedDevices);
      showSuccess(`Loaded ${normalizedDevices.length} device(s)`);
    } catch (err) {
      showError(err);
    }
  };

  const handleProvision = async () => {
    try {
      const response = await api.provisionMdmDevice(provisionForm);
      showSuccess(`Provisioning started for ${response.terminal_id}`);
      setLookupResult(response);
      await fetchDevices();
    } catch (err) {
      showError(err);
    }
  };

  const handleSendCommand = async () => {
    try {
      const parsedParams = commandForm.params
        ? JSON.parse(commandForm.params)
        : {};
      const response = await api.createMdmCommand({
        terminal_id: commandForm.terminal_id,
        model_id: commandForm.model_id,
        command_type: commandForm.command_type,
        params: parsedParams,
        priority: Number(commandForm.priority),
        issued_by: commandForm.issued_by,
      });
      showSuccess(`Command queued: ${response.command_id}`);
      setLookupResult(response);
    } catch (err) {
      showError(err);
    }
  };

  const handleApkDeploy = async () => {
    try {
      const payload = {
        terminal_ids: apkDeployForm.terminal_ids
          .split(",")
          .map((terminalId) => terminalId.trim())
          .filter(Boolean),
        model_id: apkDeployForm.model_id,
        apk_variant: apkDeployForm.apk_variant,
        force: apkDeployForm.force,
        scheduled_at: apkDeployForm.scheduled_at || undefined,
      };

      const response = apkFile
        ? await api.deployMdmApkWithFile(payload, apkFile)
        : await api.deployMdmApk(payload);

      setQueryForm((previous) => ({
        ...previous,
        deployment_id: response.deployment_id,
      }));
      showSuccess(`APK deployment queued: ${response.deployment_id}`);
    } catch (err) {
      showError(err);
    }
  };

  const handleFirmwareDeploy = async () => {
    try {
      const response = await api.deployMdmFirmware(firmwareForm);
      setQueryForm((previous) => ({
        ...previous,
        update_id: response.update_id,
      }));
      showSuccess(`Firmware update queued: ${response.update_id}`);
    } catch (err) {
      showError(err);
    }
  };

  const handleStateChange = async () => {
    try {
      const response = await api.updateMdmDeviceState(stateForm.terminal_id, {
        state: stateForm.state,
        reason: stateForm.reason || undefined,
      });
      showSuccess(`Device ${response.terminal_id} is now ${response.status}`);
      await fetchDevices();
    } catch (err) {
      showError(err);
    }
  };

  const handleDecommission = async () => {
    try {
      const response = await api.decommissionMdmDevice(stateForm.terminal_id);
      showSuccess(`Device ${response.terminal_id} decommissioned`);
      await fetchDevices();
    } catch (err) {
      showError(err);
    }
  };

  const handleBulkCommand = async () => {
    try {
      const response = await api.runMdmBulkCommand({
        command_type: bulkCommandForm.command_type,
        model_id: bulkCommandForm.model_id,
        agent_id: bulkCommandForm.agent_id || undefined,
        params: bulkCommandForm.params
          ? JSON.parse(bulkCommandForm.params)
          : undefined,
      });
      setQueryForm((previous) => ({
        ...previous,
        batch_id: response.batch_id,
      }));
      showSuccess(`Bulk command queued: ${response.batch_id}`);
    } catch (err) {
      showError(err);
    }
  };

  const handleBulkDeploy = async () => {
    try {
      const response = await api.runMdmBulkDeploy(bulkDeployForm);
      setQueryForm((previous) => ({
        ...previous,
        batch_id: response.batch_id,
      }));
      showSuccess(`Bulk deploy queued: ${response.batch_id}`);
    } catch (err) {
      showError(err);
    }
  };

  const handlePushConfig = async () => {
    try {
      const response = await api.pushMdmConfig(
        configPushForm.terminal_id,
        JSON.parse(configPushForm.config),
      );
      showSuccess(`Config push status: ${response.status}`);
      setLookupResult(response);
    } catch (err) {
      showError(err);
    }
  };

  const runLookup = async (action: string) => {
    try {
      if (action === "device") {
        const response = await api.getMdmDevices({
          model_id: queryForm.model_id || undefined,
        });
        const normalizedDevices = Array.isArray(response?.devices)
          ? response.devices
          : [];
        setLookupResult({
          count:
            typeof response?.count === "number"
              ? response.count
              : normalizedDevices.length,
          devices: normalizedDevices,
        });
      }
      if (action === "pending_commands") {
        setLookupResult(await api.getMdmPendingCommands(queryForm.terminal_id));
      }
      if (action === "diagnostics") {
        setLookupResult(
          (await api.getMdmDiagnostics(
            queryForm.terminal_id,
          )) as MdmDiagnostics,
        );
      }
      if (action === "request_diagnostics") {
        setLookupResult(await api.requestMdmDiagnostics(queryForm.terminal_id));
      }
      if (action === "provision") {
        setLookupResult(
          await api.getMdmProvisionedDevice(queryForm.terminal_id),
        );
      }
      if (action === "complete_provision") {
        setLookupResult(
          await api.completeMdmProvisioning(queryForm.terminal_id, {
            apk_version: "14.0.0",
            firmware_version: "3.2.1",
          }),
        );
      }
      if (action === "model_config") {
        setLookupResult(await api.getMdmModelConfig(queryForm.model_id));
      }
      if (action === "current_config") {
        setLookupResult(await api.getMdmCurrentConfig(queryForm.terminal_id));
      }
      if (action === "latest_apk") {
        setLookupResult(await api.getMdmLatestApkByModel(queryForm.model_id));
      }
      if (action === "firmware_updates") {
        const response = await api.getMdmFirmwareUpdates(queryForm.model_id);
        setLookupResult(response);
        const updates = Array.isArray(response?.updates)
          ? response.updates
          : [];
        if (updates.length > 0 && !firmwareForm.version) {
          const latestUpdate = updates[0] as MdmFirmwareUpdate;
          setFirmwareForm((previous) => ({
            ...previous,
            model_id: queryForm.model_id,
            version: latestUpdate.version,
          }));
        }
      }
      if (action === "model_stats") {
        setLookupResult(
          (await api.getMdmModelStats(queryForm.model_id)) as MdmModelStats,
        );
      }
      if (action === "command_status") {
        setLookupResult(
          await api.updateMdmCommandStatus(queryForm.command_id, {
            terminal_id: queryForm.terminal_id,
            status: "executed",
            result: "updated by admin dashboard",
          }),
        );
      }
      if (action === "apk_deployment_status") {
        const response = await api.getMdmApkDeploymentStatus(
          queryForm.deployment_id,
        );
        setDeploymentStatus(response);
      }
      if (action === "firmware_status") {
        const response = await api.getMdmFirmwareDeploymentStatus(
          queryForm.update_id,
        );
        setFirmwareStatus(response);
      }
      if (action === "bulk_status") {
        const response = await api.getMdmBulkStatus(queryForm.batch_id);
        setBulkStatus(response);
      }
      showSuccess("Lookup completed");
    } catch (err) {
      showError(err);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="bg-primary rounded-2xl shadow-lg p-6 text-white">
        <h2 className="text-2xl font-bold">MDM Admin Console</h2>
        <p className="opacity-90">
          Manage APKs, firmware, devices, commands and fleet state.
        </p>
      </div>

      {error && (
        <div className="bg-red-100 text-red-700 p-3 rounded-lg">{error}</div>
      )}
      {success && (
        <div className="bg-green-100 text-green-700 p-3 rounded-lg">
          {success}
        </div>
      )}

      <div className="bg-white border rounded-xl p-2">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => (
            <button
              key={tab}
              className={`px-4 py-2 rounded-lg text-sm font-semibold capitalize ${
                activeTab === tab
                  ? "bg-primary text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "overview" && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white border rounded-xl p-4">
              <p className="text-sm text-gray-500">Total Devices</p>
              <p className="text-2xl font-bold">
                {fleetStats?.total_devices ?? "-"}
              </p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-sm text-gray-500">Active</p>
              <p className="text-2xl font-bold">
                {fleetStats?.by_state?.active ?? "-"}
              </p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-sm text-gray-500">Suspended</p>
              <p className="text-2xl font-bold">
                {fleetStats?.by_state?.suspended ?? "-"}
              </p>
            </div>
            <div className="bg-white border rounded-xl p-4">
              <p className="text-sm text-gray-500">Tamper Alerts</p>
              <p className="text-2xl font-bold">{tamperAlerts.length}</p>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">Devices</h3>
              <button
                className={buttonClass}
                onClick={loadDashboardData}
                disabled={loading}
              >
                Refresh
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <input
                className={inputClass}
                placeholder="Model ID"
                value={deviceFilters.model_id}
                onChange={(event) =>
                  setDeviceFilters((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="State"
                value={deviceFilters.state}
                onChange={(event) =>
                  setDeviceFilters((previous) => ({
                    ...previous,
                    state: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Agent ID"
                value={deviceFilters.agent_id}
                onChange={(event) =>
                  setDeviceFilters((previous) => ({
                    ...previous,
                    agent_id: event.target.value,
                  }))
                }
              />
              <button className={buttonClass} onClick={fetchDevices}>
                Apply Filters
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">Terminal</th>
                    <th className="px-3 py-2 text-left">Model</th>
                    <th className="px-3 py-2 text-left">Agent</th>
                    <th className="px-3 py-2 text-left">State</th>
                    <th className="px-3 py-2 text-left">APK/FW</th>
                    <th className="px-3 py-2 text-left">Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => (
                    <tr key={device.terminal_id} className="border-t">
                      <td className="px-3 py-2 font-medium">
                        {device.terminal_id}
                      </td>
                      <td className="px-3 py-2">{device.model_id}</td>
                      <td className="px-3 py-2">{device.agent_id}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-1 rounded-full text-xs ${stateBadgeClass(device.state)}`}
                        >
                          {device.state}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {device.apk_version} / {device.firmware_version}
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">
                        {device.last_seen || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4">
            <h3 className="text-lg font-semibold mb-3">Tamper Alerts</h3>
            <div className="space-y-2 max-h-72 overflow-y-auto">
              {tamperAlerts.map((alert) => (
                <div
                  key={`${alert.terminal_id}-${alert.timestamp}`}
                  className="border rounded-lg p-3 text-sm"
                >
                  <p className="font-semibold">
                    {alert.terminal_id} • {alert.alert_type}
                  </p>
                  <p className="text-gray-600">{alert.details}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {alert.severity} • {alert.timestamp}
                  </p>
                </div>
              ))}
              {tamperAlerts.length === 0 && (
                <p className="text-sm text-gray-500">No alerts.</p>
              )}
            </div>
          </div>
        </>
      )}

      {activeTab === "operations" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Provision Device</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="Terminal ID"
                value={provisionForm.terminal_id}
                onChange={(event) =>
                  setProvisionForm((previous) => ({
                    ...previous,
                    terminal_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Model ID"
                value={provisionForm.model_id}
                onChange={(event) =>
                  setProvisionForm((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Serial Number"
                value={provisionForm.serial_number}
                onChange={(event) =>
                  setProvisionForm((previous) => ({
                    ...previous,
                    serial_number: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Agent ID"
                value={provisionForm.agent_id}
                onChange={(event) =>
                  setProvisionForm((previous) => ({
                    ...previous,
                    agent_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Location ID"
                value={provisionForm.location_id}
                onChange={(event) =>
                  setProvisionForm((previous) => ({
                    ...previous,
                    location_id: event.target.value,
                  }))
                }
              />
            </div>
            <button className={buttonClass} onClick={handleProvision}>
              Start Provisioning
            </button>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Device State</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                className={inputClass}
                placeholder="Terminal ID"
                value={stateForm.terminal_id}
                onChange={(event) =>
                  setStateForm((previous) => ({
                    ...previous,
                    terminal_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="State (active/suspended)"
                value={stateForm.state}
                onChange={(event) =>
                  setStateForm((previous) => ({
                    ...previous,
                    state: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Reason"
                value={stateForm.reason}
                onChange={(event) =>
                  setStateForm((previous) => ({
                    ...previous,
                    reason: event.target.value,
                  }))
                }
              />
            </div>
            <div className="flex gap-3">
              <button className={buttonClass} onClick={handleStateChange}>
                Update State
              </button>
              <button
                className="bg-red-600 text-white px-4 py-2 rounded-lg font-semibold text-sm hover:opacity-90"
                onClick={handleDecommission}
              >
                Decommission
              </button>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Remote Command</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="Terminal ID"
                value={commandForm.terminal_id}
                onChange={(event) =>
                  setCommandForm((previous) => ({
                    ...previous,
                    terminal_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Model ID"
                value={commandForm.model_id}
                onChange={(event) =>
                  setCommandForm((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <select
                className={inputClass}
                value={commandForm.command_type}
                onChange={(event) =>
                  setCommandForm((previous) => ({
                    ...previous,
                    command_type: event.target.value,
                  }))
                }
              >
                <option value="">Select command type</option>
                {commandTypes.map((commandType) => (
                  <option key={commandType} value={commandType}>
                    {commandType}
                  </option>
                ))}
              </select>
              <input
                className={inputClass}
                placeholder="Priority"
                value={commandForm.priority}
                onChange={(event) =>
                  setCommandForm((previous) => ({
                    ...previous,
                    priority: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Issued by (email)"
                value={commandForm.issued_by}
                onChange={(event) =>
                  setCommandForm((previous) => ({
                    ...previous,
                    issued_by: event.target.value,
                  }))
                }
              />
            </div>
            <textarea
              className={inputClass}
              rows={3}
              placeholder='Params JSON e.g. {"delay_seconds":30}'
              value={commandForm.params}
              onChange={(event) =>
                setCommandForm((previous) => ({
                  ...previous,
                  params: event.target.value,
                }))
              }
            />
            <button className={buttonClass} onClick={handleSendCommand}>
              Send Command
            </button>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Config Push</h3>
            <input
              className={inputClass}
              placeholder="Terminal ID"
              value={configPushForm.terminal_id}
              onChange={(event) =>
                setConfigPushForm((previous) => ({
                  ...previous,
                  terminal_id: event.target.value,
                }))
              }
            />
            <textarea
              className={inputClass}
              rows={4}
              placeholder="Config JSON"
              value={configPushForm.config}
              onChange={(event) =>
                setConfigPushForm((previous) => ({
                  ...previous,
                  config: event.target.value,
                }))
              }
            />
            <button className={buttonClass} onClick={handlePushConfig}>
              Push Config
            </button>
          </div>
        </div>
      )}

      {activeTab === "deployments" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">APK Deployment</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="Terminal IDs (comma-separated)"
                value={apkDeployForm.terminal_ids}
                onChange={(event) =>
                  setApkDeployForm((previous) => ({
                    ...previous,
                    terminal_ids: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Model ID"
                value={apkDeployForm.model_id}
                onChange={(event) =>
                  setApkDeployForm((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <select
                className={inputClass}
                value={apkDeployForm.apk_variant}
                onChange={(event) =>
                  setApkDeployForm((previous) => ({
                    ...previous,
                    apk_variant: event.target.value,
                  }))
                }
              >
                <option value="">Select variant</option>
                {apkVariants.map((variant) => (
                  <option key={variant.name} value={variant.name}>
                    {variant.name} ({variant.version})
                  </option>
                ))}
              </select>
              <input
                className={inputClass}
                placeholder="Scheduled At (ISO)"
                value={apkDeployForm.scheduled_at}
                onChange={(event) =>
                  setApkDeployForm((previous) => ({
                    ...previous,
                    scheduled_at: event.target.value,
                  }))
                }
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                APK File (optional)
              </label>
              <input
                type="file"
                accept=".apk,application/vnd.android.package-archive"
                className={inputClass}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setApkFile(file);
                }}
              />
              {apkFile && (
                <p className="text-xs text-gray-500 mt-1">
                  Selected: {apkFile.name}
                </p>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={apkDeployForm.force}
                onChange={(event) =>
                  setApkDeployForm((previous) => ({
                    ...previous,
                    force: event.target.checked,
                  }))
                }
              />
              Force deploy
            </label>
            <button className={buttonClass} onClick={handleApkDeploy}>
              Deploy APK
            </button>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Firmware Deployment</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                className={inputClass}
                placeholder="Terminal ID"
                value={firmwareForm.terminal_id}
                onChange={(event) =>
                  setFirmwareForm((previous) => ({
                    ...previous,
                    terminal_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Model ID"
                value={firmwareForm.model_id}
                onChange={(event) =>
                  setFirmwareForm((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Version"
                value={firmwareForm.version}
                onChange={(event) =>
                  setFirmwareForm((previous) => ({
                    ...previous,
                    version: event.target.value,
                  }))
                }
              />
            </div>
            <button className={buttonClass} onClick={handleFirmwareDeploy}>
              Deploy Firmware
            </button>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Bulk Operations</h3>
            <div className="space-y-3">
              <input
                className={inputClass}
                placeholder="Command Type"
                value={bulkCommandForm.command_type}
                onChange={(event) =>
                  setBulkCommandForm((previous) => ({
                    ...previous,
                    command_type: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Model ID"
                value={bulkCommandForm.model_id}
                onChange={(event) =>
                  setBulkCommandForm((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Agent ID (optional)"
                value={bulkCommandForm.agent_id}
                onChange={(event) =>
                  setBulkCommandForm((previous) => ({
                    ...previous,
                    agent_id: event.target.value,
                  }))
                }
              />
              <textarea
                className={inputClass}
                rows={3}
                placeholder="Params JSON"
                value={bulkCommandForm.params}
                onChange={(event) =>
                  setBulkCommandForm((previous) => ({
                    ...previous,
                    params: event.target.value,
                  }))
                }
              />
              <button className={buttonClass} onClick={handleBulkCommand}>
                Run Bulk Command
              </button>
            </div>
            <div className="border-t pt-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  className={inputClass}
                  placeholder="Model ID"
                  value={bulkDeployForm.model_id}
                  onChange={(event) =>
                    setBulkDeployForm((previous) => ({
                      ...previous,
                      model_id: event.target.value,
                    }))
                  }
                />
                <input
                  className={inputClass}
                  placeholder="APK Variant"
                  value={bulkDeployForm.apk_variant}
                  onChange={(event) =>
                    setBulkDeployForm((previous) => ({
                      ...previous,
                      apk_variant: event.target.value,
                    }))
                  }
                />
              </div>
              <button
                className={`${buttonClass} mt-3`}
                onClick={handleBulkDeploy}
              >
                Run Bulk Deploy
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === "lookups" && (
        <div className="space-y-6">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h3 className="text-lg font-semibold">Lookups & Status</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-3">
              <input
                className={inputClass}
                placeholder="Terminal ID"
                value={queryForm.terminal_id}
                onChange={(event) =>
                  setQueryForm((previous) => ({
                    ...previous,
                    terminal_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Model ID"
                value={queryForm.model_id}
                onChange={(event) =>
                  setQueryForm((previous) => ({
                    ...previous,
                    model_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Command ID"
                value={queryForm.command_id}
                onChange={(event) =>
                  setQueryForm((previous) => ({
                    ...previous,
                    command_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Deployment ID"
                value={queryForm.deployment_id}
                onChange={(event) =>
                  setQueryForm((previous) => ({
                    ...previous,
                    deployment_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Update ID"
                value={queryForm.update_id}
                onChange={(event) =>
                  setQueryForm((previous) => ({
                    ...previous,
                    update_id: event.target.value,
                  }))
                }
              />
              <input
                className={inputClass}
                placeholder="Batch ID"
                value={queryForm.batch_id}
                onChange={(event) =>
                  setQueryForm((previous) => ({
                    ...previous,
                    batch_id: event.target.value,
                  }))
                }
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                className={buttonClass}
                onClick={() => runLookup("device")}
              >
                Load Devices
              </button>
            </div>

            {deploymentStatus && (
              <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3">
                APK Deploy: {deploymentStatus.status} (
                {deploymentStatus.completed}/{deploymentStatus.total})
              </div>
            )}
            {firmwareStatus && (
              <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3">
                Firmware Update: {firmwareStatus.status} (
                {firmwareStatus.update_id})
              </div>
            )}
            {bulkStatus && (
              <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3">
                Bulk: {bulkStatus.batch_id} - {bulkStatus.status}
              </div>
            )}
          </div>

          <div className="bg-white border rounded-xl p-4">
            <h3 className="text-lg font-semibold mb-3">Devices</h3>
            {lookupDevices.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">Terminal</th>
                      <th className="px-3 py-2 text-left">Model</th>
                      <th className="px-3 py-2 text-left">Agent</th>
                      <th className="px-3 py-2 text-left">State</th>
                      <th className="px-3 py-2 text-left">APK/FW</th>
                      <th className="px-3 py-2 text-left">Registered</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lookupDevices.map((device) => (
                      <tr key={device.terminal_id} className="border-t">
                        <td className="px-3 py-2 font-medium">
                          {device.terminal_id}
                        </td>
                        <td className="px-3 py-2">{device.model_id}</td>
                        <td className="px-3 py-2">{device.agent_id}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`px-2 py-1 rounded-full text-xs ${stateBadgeClass(device.state)}`}
                          >
                            {device.state}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {device.apk_version || "-"} /{" "}
                          {device.firmware_version || "-"}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">
                          {device.registered_at || "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                Click "Load Devices" to fetch from the devices endpoint.
              </p>
            )}
          </div>

          <div className="bg-white border rounded-xl p-4">
            <h3 className="text-lg font-semibold mb-3">API Response Viewer</h3>
            <pre className="bg-gray-50 p-3 rounded-lg text-xs overflow-auto max-h-72">
              {lookupResult
                ? JSON.stringify(lookupResult, null, 2)
                : "Run a lookup/action to view response."}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default MDMControls;
