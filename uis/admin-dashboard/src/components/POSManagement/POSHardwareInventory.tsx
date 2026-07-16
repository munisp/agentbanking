import {
    AlertCircle,
    CheckCircle,
    Filter,
    MapPin,
    MonitorSmartphone,
    Package,
    Plus,
    Search,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import {
    api,
    CatalogManufacturer,
    CatalogModel,
    CreatePOSHardwareDevicePayload,
    POSHardwareDevice,
} from "../../utils/api";

const DEVICE_TYPES = [
  "pos_terminal",
  "mobile_pos",
  "tablet_pos",
  "smart_pos",
  "card_reader",
  "receipt_printer",
];

const CONNECTIVITY_TYPES = [
  "wifi",
  "ethernet",
  "cellular_4g",
  "cellular_5g",
  "bluetooth",
  "nfc",
];

const statusBadge = (status: string) => {
  const normalized = status?.toLowerCase() || "unknown";
  const configs: Record<
    string,
    { label: string; className: string; icon: React.ReactNode }
  > = {
    active: {
      label: "Active",
      className: "bg-green-100 text-green-800",
      icon: <CheckCircle className="w-3 h-3" />,
    },
    provisioning: {
      label: "Provisioning",
      className: "bg-[rgba(0,79,113,0.1)] text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]",
      icon: <Package className="w-3 h-3" />,
    },
    maintenance: {
      label: "Maintenance",
      className: "bg-yellow-100 text-yellow-800",
      icon: <AlertCircle className="w-3 h-3" />,
    },
    offline: {
      label: "Offline",
      className: "bg-gray-100 text-gray-800",
      icon: <AlertCircle className="w-3 h-3" />,
    },
    faulty: {
      label: "Faulty",
      className: "bg-red-100 text-red-800",
      icon: <AlertCircle className="w-3 h-3" />,
    },
  };

  const config = configs[normalized] || {
    label: status || "Unknown",
    className: "bg-gray-100 text-gray-800",
    icon: <AlertCircle className="w-3 h-3" />,
  };

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${config.className}`}
    >
      {config.icon}
      {config.label}
    </span>
  );
};

const BLANK_FORM: CreatePOSHardwareDevicePayload = {
  device_id: "",
  device_name: "",
  device_type: "pos_terminal",
  manufacturer: "",
  model: "",
  serial_number: "",
  connectivity_type: "cellular_4g",
  address: "",
};

const POSHardwareInventory: React.FC = () => {
  const [devices, setDevices] = useState<POSHardwareDevice[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Catalog state
  const [manufacturers, setManufacturers] = useState<CatalogManufacturer[]>([]);
  const [models, setModels] = useState<CatalogModel[]>([]);
  const [selectedManufacturer, setSelectedManufacturer] =
    useState<CatalogManufacturer | null>(null);
  const [selectedModel, setSelectedModel] = useState<CatalogModel | null>(null);

  const [form, setForm] = useState<CreatePOSHardwareDevicePayload>(BLANK_FORM);

  const loadDevices = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getPOSHardwareDevices({ page: 1, limit: 100 });
      setDevices(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    } finally {
      setLoading(false);
    }
  };

  const loadManufacturers = async () => {
    try {
      const res = await api.getCatalogManufacturers();
      setManufacturers(res.manufacturers ?? []);
    } catch {}
  };

  const onManufacturerChange = async (mfrId: string) => {
    const mfr = manufacturers.find((m) => m.id === mfrId) ?? null;
    setSelectedManufacturer(mfr);
    setSelectedModel(null);
    setModels([]);
    setForm((f) => ({
      ...f,
      manufacturer: mfr?.name ?? "",
      model: "",
      connectivity_type: "cellular_4g",
    }));
    if (mfrId) {
      try {
        const res = await api.getCatalogModels(mfrId);
        setModels(res.models ?? []);
      } catch {}
    }
  };

  const onModelChange = (modelId: string) => {
    const mdl = models.find((m) => m.id === modelId) ?? null;
    setSelectedModel(mdl);
    setForm((f) => ({
      ...f,
      model: mdl?.name ?? "",
      connectivity_type:
        (mdl?.connectivity as CreatePOSHardwareDevicePayload["connectivity_type"]) ??
        "cellular_4g",
    }));
  };

  useEffect(() => {
    loadDevices();
    loadManufacturers();
  }, []);

  const filtered = useMemo(() => {
    const term = search.toLowerCase();
    return devices.filter((device) => {
      const matchesSearch =
        device.device_name?.toLowerCase().includes(term) ||
        device.device_id?.toLowerCase().includes(term) ||
        device.model?.toLowerCase().includes(term) ||
        device.serial_number?.toLowerCase().includes(term);
      const matchesStatus =
        statusFilter === "all" ||
        device.device_status?.toLowerCase() === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [devices, search, statusFilter]);

  const stats = useMemo(() => {
    const total = devices.length;
    const available = devices.filter(
      (device) =>
        !device.assigned_agent_id && device.device_status !== "decommissioned",
    ).length;
    const active = devices.filter(
      (device) => device.device_status?.toLowerCase() === "active",
    ).length;
    return { total, available, active };
  }, [devices]);

  const handleCreate = async () => {
    setError(null);
    try {
      const createdBy = localStorage.getItem("keycloakId") || undefined;
      await api.registerPOSHardwareDevice({ ...form, created_by: createdBy });

      // MDM provision — mdm_model_id comes directly from the selected catalog model
      if (selectedModel) {
        try {
          await api.provisionMdmDevice({
            terminal_id: form.device_id,
            model_id: selectedModel.mdm_model_id,
            serial_number: form.serial_number,
            agent_id: "",
          });
        } catch (mdmErr) {
          console.warn("MDM provisioning failed (non-fatal):", mdmErr);
        }
      }

      setShowCreateModal(false);
      setSelectedManufacturer(null);
      setSelectedModel(null);
      setModels([]);
      setForm(BLANK_FORM);
      loadDevices();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to register device",
      );
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            POS Hardware Inventory
          </h1>
          <p className="text-gray-500 mt-1">
            Register physical POS devices that agents can request
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Register Device
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            label: "Total Devices",
            value: stats.total,
            icon: MonitorSmartphone,
            color: "text-[var(--tenant-primary-color,#002082)]",
          },
          {
            label: "Available",
            value: stats.available,
            icon: Package,
            color: "text-green-500",
          },
          {
            label: "Active",
            value: stats.active,
            icon: CheckCircle,
            color: "text-emerald-500",
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

      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by device ID, model, or serial..."
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
            <option value="active">Active</option>
            <option value="provisioning">Provisioning</option>
            <option value="maintenance">Maintenance</option>
            <option value="offline">Offline</option>
            <option value="faulty">Faulty</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow overflow-hidden">
        <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {[
                  "Device",
                  "Model",
                  "Serial",
                  "Status",
                  "Assigned",
                  "Location",
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
              {loading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-6 text-center text-gray-500"
                  >
                    Loading devices...
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-6 text-center text-gray-500"
                  >
                    No devices found.
                  </td>
                </tr>
              ) : (
                filtered.map((device) => (
                  <tr
                    key={device.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-[rgba(0,79,113,0.1)] rounded-lg flex items-center justify-center">
                          <MonitorSmartphone className="w-4 h-4 text-[var(--tenant-primary-color,#002082)]" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {device.device_name}
                          </p>
                          <p className="text-xs text-gray-500">
                            {device.device_id}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {device.manufacturer} {device.model}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {device.serial_number}
                    </td>
                    <td className="px-4 py-3">
                      {statusBadge(device.device_status)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {device.assigned_agent_id || "Unassigned"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-gray-600">
                        <MapPin className="w-3 h-3" />
                        <span>
                          {device.address || device.assigned_location || "-"}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-xl">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Register POS Device
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Device ID
                </label>
                <input
                  type="text"
                  value={form.device_id}
                  onChange={(e) =>
                    setForm({ ...form, device_id: e.target.value })
                  }
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="POS-DEV-0001"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Device Name
                </label>
                <input
                  type="text"
                  value={form.device_name}
                  onChange={(e) =>
                    setForm({ ...form, device_name: e.target.value })
                  }
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Ikeja Unit A"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Device Type
                </label>
                <select
                  value={form.device_type}
                  onChange={(e) =>
                    setForm({ ...form, device_type: e.target.value })
                  }
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  {DEVICE_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Manufacturer
                </label>
                <select
                  value={selectedManufacturer?.id ?? ""}
                  onChange={(e) => onManufacturerChange(e.target.value)}
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value="">Select manufacturer…</option>
                  {manufacturers.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Model
                </label>
                <select
                  value={selectedModel?.id ?? ""}
                  onChange={(e) => onModelChange(e.target.value)}
                  disabled={!selectedManufacturer}
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
                >
                  <option value="">
                    {selectedManufacturer
                      ? "Select model…"
                      : "Select manufacturer first"}
                  </option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
                {selectedModel && (
                  <p className="mt-1 text-xs text-gray-400">
                    MDM ID: {selectedModel.mdm_model_id} · APK:{" "}
                    {selectedModel.apk_variant}
                  </p>
                )}
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Serial Number
                </label>
                <input
                  type="text"
                  value={form.serial_number}
                  onChange={(e) =>
                    setForm({ ...form, serial_number: e.target.value })
                  }
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="SN-123456"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Connectivity
                </label>
                <select
                  value={form.connectivity_type}
                  onChange={(e) =>
                    setForm({ ...form, connectivity_type: e.target.value })
                  }
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  {CONNECTIVITY_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Location
                </label>
                <input
                  type="text"
                  value={form.address || ""}
                  onChange={(e) =>
                    setForm({ ...form, address: e.target.value })
                  }
                  className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                  placeholder="Warehouse or branch location"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]"
              >
                Register Device
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default POSHardwareInventory;
