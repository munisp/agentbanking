import {
    Activity,
    AlertCircle,
    CheckCircle,
    Clock,
    Download,
    Edit,
    Filter,
    MapPin,
    MonitorSmartphone,
    MoreVertical,
    Plus,
    RefreshCw,
    Search,
    Shield,
    Trash2,
    XCircle,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import {
    AgentRecord,
    api,
    POSHardwareDevice,
    POSTerminal,
} from "../../utils/api";

import MapPicker from "./MapPicker";

const POSManagement: React.FC = () => {
  const [terminals, setTerminals] = useState<POSTerminal[]>([]);
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [geoLatitude, setGeoLatitude] = useState("");
  const [geoLongitude, setGeoLongitude] = useState("");
  const [geoRadius, setGeoRadius] = useState("");
  const [hardwareDevices, setHardwareDevices] = useState<POSHardwareDevice[]>(
    [],
  );
  const [hardwareLoading, setHardwareLoading] = useState(false);
  const [selectedDevice, setSelectedDevice] =
    useState<POSHardwareDevice | null>(null);
  const [serialNumber, setSerialNumber] = useState("");
  const [location, setLocation] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [geocoding, setGeocoding] = useState(false);
  const geocodeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load terminals on mount
  useEffect(() => {
    loadTerminals();
  }, []);

  const loadAgents = async () => {
    setAgentsLoading(true);
    try {
      const data = await api.getAgents();
      setAgents(data.agents ?? []);
    } catch (err) {
      console.error("Error loading agents:", err);
    } finally {
      setAgentsLoading(false);
    }
  };

  const loadHardwareDevices = async () => {
    setHardwareLoading(true);
    try {
      const data = await api.getPOSHardwareDevices({ limit: 200 });
      // Exclude only decommissioned devices — provisioning + active are both valid to assign
      const assignable = (data.data ?? []).filter(
        (d) => d.device_status !== "decommissioned",
      );
      setHardwareDevices(assignable);
    } catch (err) {
      console.error("Error loading hardware devices:", err);
      setHardwareDevices([]);
    } finally {
      setHardwareLoading(false);
    }
  };

  const openAssignModal = () => {
    setSelectedAgent("");
    setSelectedDevice(null);
    setSerialNumber("");
    setLocation("");
    setContactPerson("");
    setAssignError(null);
    setShowAssignModal(true);
    loadAgents();
    loadHardwareDevices();
    setGeoLatitude("");
    setGeoLongitude("");
    setGeoRadius("");
  };

  const geocodeLocation = (address: string) => {
    if (geocodeTimer.current) clearTimeout(geocodeTimer.current);
    if (address.trim().length < 5) return;
    geocodeTimer.current = setTimeout(async () => {
      setGeocoding(true);
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(address)}`,
          { headers: { "Accept-Language": "en" } },
        );
        const results = await res.json();
        if (results.length > 0) {
          setGeoLatitude(parseFloat(results[0].lat).toFixed(6));
          setGeoLongitude(parseFloat(results[0].lon).toFixed(6));
        }
      } catch {
      } finally {
        setGeocoding(false);
      }
    }, 800);
  };

  const sanitizeSerial = (raw: string) =>
    raw
      .replace(/[^a-zA-Z0-9]/g, "")
      .padEnd(10, "0")
      .slice(0, 10)
      .toUpperCase();

  const handleDeviceSelect = (deviceId: string) => {
    const device = hardwareDevices.find((d) => d.id === deviceId) ?? null;
    setSelectedDevice(device);
    setSerialNumber(device ? sanitizeSerial(device.serial_number) : "");
    // Show warning if device is already assigned
    if (device?.assigned_agent_id) {
      setAssignError(
        `Note: This device is currently assigned to another agent. Reassigning will unlink it from the previous agent.`,
      );
    } else {
      setAssignError(null);
    }
  };

  const getMdmModelId = (manufacturer: string, model: string): string => {
    const mfr = manufacturer.toLowerCase().trim();
    const mdl = model.toLowerCase().replace(/\s+/g, "_").trim();
    const key = `${mfr}_${mdl}`;
    const mapping: Record<string, string> = {
      pax_a920: "pax_a920_max",
      pax_a920_max: "pax_a920_max",
      pax_a8900: "pax_a8900",
      newland_n750: "newland_n750",
      newland_n910: "newland_n910",
      newland_n910_pro: "newland_n910_pro",
      newland_me30su: "newland_me30su",
      horizonpay_k11: "horizonpay_k11",
      horizonpay_k11_lite: "horizonpay_k11_lite",
      topwise_t11_pro: "topwise_t11_pro",
      topwise_mp45p: "topwise_mp45p",
      sunmi_p1: "sunmi_p1",
      sunmi_p2: "sunmi_p2",
      sunmi_p2_pro: "sunmi_p2_pro",
      sunmi_p3: "sunmi_p3",
    };
    return mapping[key] ?? mdl;
  };

  const getApkVariant = (mdmModelId: string): string => {
    const variants: Record<string, string> = {
      pax_a920_max: "paxbiz-a920",
      pax_a8900: "paxbiz-a8900",
      newland_n750: "aosp-mini-keypad",
      newland_n910: "paydroid-n910",
      newland_n910_pro: "paydroid-n910pro",
      newland_me30su: "mpos-companion",
      topwise_mp45p: "aosp-compact",
      sunmi_p1: "sunmi",
      sunmi_p2: "sunmi",
      sunmi_p2_pro: "sunmi",
      sunmi_p3: "sunmi",
    };
    return variants[mdmModelId] ?? "aosp-full";
  };

  const handleAssign = async () => {
    if (!selectedDevice) {
      setAssignError("Please select a terminal device.");
      return;
    }
    if (!selectedAgent) {
      setAssignError("Please select an agent.");
      return;
    }
    if (!location.trim()) {
      setAssignError("Please enter a location.");
      return;
    }
    if (contactPerson.trim().length > 0 && contactPerson.trim().length < 3) {
      setAssignError("Contact person name must be at least 3 characters.");
      return;
    }
    setAssignError(null);
    setAssigning(true);
    try {
      const manufacturer = (selectedDevice.manufacturer ?? "").trim();
      const mdmModelId = getMdmModelId(
        selectedDevice.manufacturer ?? "",
        selectedDevice.model ?? "",
      );

      // Create the terminal
      const createdTerminal = await api.createPOSTerminal({
        serial_number: sanitizeSerial(selectedDevice.serial_number),
        device_id: selectedDevice.device_id,
        manufacturer:
          manufacturer.length >= 2 ? manufacturer : manufacturer.padEnd(2, "X"),
        model: selectedDevice.model?.trim() || manufacturer,
        operating_system: "Android",
        processor: "ARM",
        memory_gb: 1,
        storage_gb: 8,
        status: "Active",
        location: location.trim(),
        contact_person: contactPerson.trim() || undefined,
        assigned_to: selectedAgent,
        notes:
          [
            geoLatitude && geoLongitude
              ? `Geofence: ${geoLatitude}, ${geoLongitude}`
              : null,
            geoRadius ? `Radius: ${geoRadius}m` : null,
          ]
            .filter(Boolean)
            .join(" | ") || undefined,
      });

      // MDM: Deploy the correct APK for this device model
      try {
        await api.deployMdmApk({
          terminal_ids: [selectedDevice.device_id],
          model_id: mdmModelId,
          apk_variant: getApkVariant(mdmModelId),
          force: false,
        });
      } catch (mdmErr) {
        console.warn("MDM APK deploy failed (non-fatal):", mdmErr);
      }

      // If geofence data is provided, create geofence record + send MDM enable command
      if (geoLatitude && geoLongitude && geoRadius) {
        try {
          const tenantId = localStorage.getItem("tenantId") || "default";
          await api.createGeofence({
            agent_id: selectedAgent,
            tenant_id: tenantId,
            device_id: selectedDevice.device_id,
            name: `${location.trim()} Geofence`,
            center_latitude: parseFloat(geoLatitude),
            center_longitude: parseFloat(geoLongitude),
            radius_km: parseFloat(geoRadius) / 1000,
          });

          // Tell the device to activate geofence enforcement via MDM
          await api.createMdmCommand({
            terminal_id: selectedDevice.device_id,
            model_id: selectedDevice.model ?? selectedDevice.device_id,
            command_type: "enable_geofence",
            params: {
              latitude: parseFloat(geoLatitude),
              longitude: parseFloat(geoLongitude),
              radius_m: parseFloat(geoRadius),
            },
            priority: 7,
            issued_by: localStorage.getItem("keycloakId") ?? "admin-dashboard",
          });
        } catch (geoErr) {
          console.error("Failed to create geofence:", geoErr);
          setAssignError(
            `Terminal created but geofence setup failed: ${geoErr instanceof Error ? geoErr.message : "Unknown error"}`,
          );
          setTimeout(() => {
            setShowAssignModal(false);
            loadTerminals();
          }, 3000);
          return;
        }
      }

      setShowAssignModal(false);
      loadTerminals();
    } catch (err) {
      setAssignError(
        err instanceof Error ? err.message : "Failed to assign terminal.",
      );
    } finally {
      setAssigning(false);
    }
  };

  const loadTerminals = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getPOSTerminals();
      setTerminals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load terminals");
      console.error("Error loading terminals:", err);
    } finally {
      setLoading(false);
    }
  };

  const filteredTerminals = terminals.filter((t) => {
    const matchesSearch =
      t.assigned_to?.toLowerCase().includes(search.toLowerCase()) ||
      t.serial_number?.toLowerCase().includes(search.toLowerCase()) ||
      t.id?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === "all" || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: terminals.length,
    active: terminals.filter((t) => t.status === "Active").length,
    offline: terminals.filter((t) => t.status === "Inactive").length,
    faulty: terminals.filter((t) => t.status === "Maintenance").length,
  };

  const getStatusConfig = (status: string) => {
    const configs: Record<string, { color: string; icon: React.ReactNode }> = {
      Active: {
        color: "bg-green-100 text-green-800",
        icon: <CheckCircle className="w-3 h-3" />,
      },
      Inactive: {
        color: "bg-gray-100 text-gray-800",
        icon: <Clock className="w-3 h-3" />,
      },
      Maintenance: {
        color: "bg-red-100 text-red-800",
        icon: <AlertCircle className="w-3 h-3" />,
      },
    };
    return configs[status] || configs.Inactive;
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            POS Terminal Management
          </h1>
          <p className="text-gray-500 mt-1">
            Manage all POS terminals and their assignments to agents
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2 text-sm">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={openAssignModal}
            className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            Assign Terminal
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Total Terminals",
            value: stats.total,
            icon: MonitorSmartphone,
            color: "text-[var(--tenant-primary-color,#002082)]",
          },
          {
            label: "Active",
            value: stats.active,
            icon: CheckCircle,
            color: "text-green-500",
          },
          {
            label: "Offline",
            value: stats.offline,
            icon: Clock,
            color: "text-gray-500",
          },
          {
            label: "Faulty",
            value: stats.faulty,
            icon: AlertCircle,
            color: "text-red-500",
          },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl shadow p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">
                  {stat.label}
                </p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {stat.value}
                </p>
              </div>
              <stat.icon className={`w-10 h-10 ${stat.color}`} />
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by agent, business or serial..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          >
            <option value="all">All Status</option>
            <option value="Active">Active</option>
            <option value="Inactive">Offline</option>
            <option value="Maintenance">Maintenance</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {[
                  "Terminal",
                  "Model",
                  "Assigned Agent",
                  "Location",
                  "Status",
                  "Transactions",
                  "Last Active",
                  "Actions",
                ].map((col) => (
                  <th
                    key={col}
                    className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredTerminals.map((terminal) => {
                const sc = getStatusConfig(terminal.status);
                return (
                  <tr
                    key={terminal.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-[rgba(0,79,113,0.1)] rounded-lg flex items-center justify-center">
                          <MonitorSmartphone className="w-4 h-4 text-[var(--tenant-primary-color,#002082)]" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {terminal.id}
                          </p>
                          <p className="text-xs text-gray-500">
                            {terminal.serial_number}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {terminal.model}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900">
                        {terminal.assigned_to || "Unassigned"}
                      </p>
                      <p className="text-xs text-gray-500">
                        {terminal.location}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-gray-600">
                        <MapPin className="w-3 h-3" />
                        {terminal.location}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${sc.color}`}
                      >
                        {sc.icon}
                        {terminal.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-900">
                        {terminal.transaction_count?.toLocaleString() || 0}
                      </p>
                      <p className="text-xs text-gray-500">
                        {terminal.is_online ? "Online" : "Offline"}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {terminal.last_transaction_time
                        ? new Date(
                            terminal.last_transaction_time,
                          ).toLocaleString()
                        : "N/A"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          title="Edit"
                          className="p-1.5 hover:bg-[rgba(0,79,113,0.05)] rounded-lg text-[var(--tenant-primary-color,#002082)] transition-colors"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          title="Refresh"
                          onClick={loadTerminals}
                          className="p-1.5 hover:bg-gray-50 rounded-lg text-gray-500 transition-colors"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </button>
                        <button
                          title="Remove"
                          className="p-1.5 hover:bg-red-50 rounded-lg text-red-500 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredTerminals.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <MonitorSmartphone className="w-12 h-12 mx-auto mb-2 opacity-40" />
            <p>No terminals found</p>
          </div>
        )}
      </div>

      {/* Assign Terminal Modal */}
      {showAssignModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center rounded-t-2xl">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  Assign New Terminal
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  {hardwareDevices.filter((d) => !d.assigned_agent_id).length}{" "}
                  unassigned • {hardwareDevices.length} total device
                  {hardwareDevices.length !== 1 ? "s" : ""}
                </p>
              </div>
              <button
                onClick={() => setShowAssignModal(false)}
                className="text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg p-2 transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5">
              {/* Device Selection Section */}
              <div className="bg-[rgba(0,79,113,0.05)] border border-[rgba(0,79,113,0.15)] rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <MonitorSmartphone className="w-5 h-5 text-[var(--tenant-primary-color,#002082)]" />
                  <h3 className="text-sm font-semibold text-gray-900">
                    Select POS Device
                  </h3>
                  <span className="text-xs text-gray-600 ml-auto">
                    {hardwareDevices.filter((d) => !d.assigned_agent_id).length}{" "}
                    unassigned | {hardwareDevices.length} total
                  </span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Terminal Device
                  </label>
                  <select
                    value={selectedDevice?.id ?? ""}
                    onChange={(e) => handleDeviceSelect(e.target.value)}
                    disabled={hardwareLoading}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400 transition-all"
                  >
                    <option value="">
                      {hardwareLoading
                        ? "Loading devices..."
                        : "Select a device"}
                    </option>
                    {hardwareDevices.map((device) => (
                      <option key={device.id} value={device.id}>
                        {device.assigned_agent_id ? "⚠️ " : "✓ "}
                        {device.manufacturer} {device.model} |{" "}
                        {device.device_type?.toUpperCase()} | S/N:{" "}
                        {device.serial_number}
                        {device.device_name ? ` | ${device.device_name}` : ""}
                        {device.assigned_agent_id ? " (Already Assigned)" : ""}
                      </option>
                    ))}
                  </select>
                  {selectedDevice && (
                    <div
                      className={`mt-3 p-3 border rounded-lg ${
                        selectedDevice.assigned_agent_id
                          ? "bg-amber-50 border-amber-200"
                          : "bg-white border-gray-200"
                      }`}
                    >
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-gray-500">Type:</span>
                          <span className="ml-2 font-medium text-gray-900">
                            {selectedDevice.device_type}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Status:</span>
                          <span className="ml-2 font-medium text-green-600">
                            {selectedDevice.device_status}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Connectivity:</span>
                          <span className="ml-2 font-medium text-gray-900">
                            {selectedDevice.connectivity_type || "N/A"}
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Device ID:</span>
                          <span className="ml-2 font-medium text-gray-900">
                            {selectedDevice.device_id}
                          </span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-gray-500">Location:</span>
                          <span className="ml-2 font-medium text-gray-900">
                            {selectedDevice.assigned_location || "N/A"}
                          </span>
                        </div>
                        <div className="col-span-2">
                          <span className="text-gray-500">Transactions:</span>
                          <span className="ml-2 font-medium text-gray-900">
                            {selectedDevice.total_transactions_processed?.toLocaleString() ||
                              0}
                          </span>
                        </div>
                        {selectedDevice.assigned_agent_id && (
                          <div className="col-span-2 mt-1 pt-2 border-t border-amber-300">
                            <div className="flex items-center gap-1 text-amber-700">
                              <AlertCircle className="w-3 h-3" />
                              <span className="font-medium">
                                Currently assigned to another agent
                              </span>
                            </div>
                            <p className="text-amber-600 mt-1">
                              Reassigning will unlink from previous agent
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {hardwareDevices.length === 0 && !hardwareLoading && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-red-600" />
                      <p className="text-xs text-red-700">
                        No devices available in inventory. Please register
                        devices first.
                      </p>
                    </div>
                  )}
                </div>
                <div className="mt-3">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Serial Number
                  </label>
                  <input
                    type="text"
                    value={serialNumber}
                    readOnly
                    placeholder="Auto-filled from selected device"
                    className="w-full px-4 py-2.5 border border-gray-200 bg-gray-50 rounded-lg text-sm text-gray-600 cursor-not-allowed font-mono"
                  />
                </div>
              </div>

              {/* Assignment Details Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-1">
                  <Shield className="w-5 h-5 text-gray-600" />
                  <h3 className="text-sm font-semibold text-gray-900">
                    Assignment Details
                  </h3>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Assign to Agent
                  </label>
                  <select
                    value={selectedAgent}
                    onChange={(e) => setSelectedAgent(e.target.value)}
                    disabled={agentsLoading}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400 transition-all"
                  >
                    <option value="">
                      {agentsLoading ? "Loading agents..." : "Select an agent"}
                    </option>
                    {agents
                      .filter((a) => a.is_approved && a.status !== "suspended")
                      .map((agent) => (
                        <option
                          key={agent.keycloak_id}
                          value={agent.keycloak_id}
                        >
                          {agent.first_name} {agent.last_name}
                          {agent.business_name
                            ? ` — ${agent.business_name}`
                            : ""}
                          {agent.uin ? ` (${agent.uin})` : ""}
                        </option>
                      ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Location <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      value={location}
                      onChange={(e) => {
                        setLocation(e.target.value);
                        geocodeLocation(e.target.value);
                      }}
                      placeholder="e.g. 23 Broad Street, Lagos Island"
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent transition-all pr-8"
                    />
                    {geocoding && (
                      <RefreshCw className="absolute right-3 top-3 w-3.5 h-3.5 text-gray-400 animate-spin" />
                    )}
                  </div>
                  <p className="mt-1 text-xs text-gray-400">
                    Type an address — coordinates auto-fill below after a moment
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Contact Person{" "}
                    <span className="text-gray-400 font-normal">
                      (optional)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={contactPerson}
                    onChange={(e) => setContactPerson(e.target.value)}
                    placeholder="e.g. John Doe"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent transition-all"
                  />
                </div>
              </div>

              {/* Geo-fencing Section */}
              <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <MapPin className="w-5 h-5 text-gray-600" />
                  <h3 className="text-sm font-semibold text-gray-900">
                    Geo-fence Configuration
                  </h3>
                  <span className="text-xs text-gray-500 ml-auto">
                    (optional)
                  </span>
                </div>

                {/* Manual coordinate inputs — primary method */}
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Latitude
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={geoLatitude}
                      onChange={(e) => setGeoLatitude(e.target.value)}
                      placeholder="e.g. 6.5244"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] transition-all font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Longitude
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={geoLongitude}
                      onChange={(e) => setGeoLongitude(e.target.value)}
                      placeholder="e.g. 3.3792"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] transition-all font-mono"
                    />
                  </div>
                </div>

                {/* Map picker — syncs with the lat/lng inputs above */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Or click on the map to pin location
                  </label>
                  <MapPicker
                    latitude={geoLatitude}
                    longitude={geoLongitude}
                    onLocationChange={(lat, lng) => {
                      setGeoLatitude(lat.toString());
                      setGeoLongitude(lng.toString());
                    }}
                    className="mb-3"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Radius (meters)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={geoRadius}
                    onChange={(e) => setGeoRadius(e.target.value)}
                    placeholder="e.g. 500"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent transition-all"
                  />
                  {geoLatitude && geoLongitude && !geoRadius && (
                    <p className="mt-1 text-xs text-amber-600">
                      Enter a radius to activate geofencing
                    </p>
                  )}
                </div>
              </div>

              {assignError && (
                <div
                  className={`p-3 border rounded-lg flex items-start gap-2 ${
                    assignError.startsWith("Note:")
                      ? "bg-amber-50 border-amber-200"
                      : "bg-red-50 border-red-200"
                  }`}
                >
                  <AlertCircle
                    className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                      assignError.startsWith("Note:")
                        ? "text-amber-600"
                        : "text-red-600"
                    }`}
                  />
                  <p
                    className={`text-sm ${
                      assignError.startsWith("Note:")
                        ? "text-amber-700"
                        : "text-red-700"
                    }`}
                  >
                    {assignError}
                  </p>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex gap-3 rounded-b-2xl">
              <button
                onClick={() => setShowAssignModal(false)}
                disabled={assigning}
                className="flex-1 py-3 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-white transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAssign}
                disabled={
                  assigning ||
                  !selectedDevice ||
                  !selectedAgent ||
                  !location.trim()
                }
                className="flex-1 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {assigning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Assigning...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Assign Terminal
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default POSManagement;
