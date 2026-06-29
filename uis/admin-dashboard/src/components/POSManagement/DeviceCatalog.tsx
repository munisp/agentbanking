import { ChevronDown, ChevronRight, Edit2, Plus, Trash2 } from "lucide-react";
import React, { useEffect, useState } from "react";
import { api, CatalogManufacturer, CatalogModel } from "../../utils/api";

const APK_VARIANTS = [
  "aosp-full",
  "aosp-compact",
  "aosp-mini-keypad",
  "mpos-companion",
  "paydroid-n910",
  "paydroid-n910pro",
  "paxbiz-a920",
  "paxbiz-a8900",
  "sunmi",
];

const CONNECTIVITY_TYPES = [
  "wifi",
  "ethernet",
  "cellular_4g",
  "cellular_5g",
  "bluetooth",
  "nfc",
];

const DEVICE_TYPES = [
  "pos_terminal",
  "mobile_pos",
  "tablet_pos",
  "smart_pos",
  "card_reader",
  "receipt_printer",
];

const slugify = (s: string) =>
  s
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]/g, "");

// ── Modals ────────────────────────────────────────────────────────────────────

interface AddManufacturerModalProps {
  onClose: () => void;
  onSaved: () => void;
}
const AddManufacturerModal: React.FC<AddManufacturerModalProps> = ({
  onClose,
  onSaved,
}) => {
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!name.trim()) return setError("Name is required");
    setLoading(true);
    setError("");
    try {
      await api.createCatalogManufacturer({
        name: name.trim(),
        slug: slugify(name),
        website,
      });
      onSaved();
    } catch {
      setError(
        "Failed to create manufacturer — name or slug may already exist",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 className="text-lg font-bold text-gray-900 mb-4">
          Add Manufacturer
        </h3>
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-gray-700">Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. Sunmi"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">Website</label>
            <input
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="https://..."
            />
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50"
          >
            {loading ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
};

interface AddModelModalProps {
  manufacturer: CatalogManufacturer;
  model?: CatalogModel | null;
  onClose: () => void;
  onSaved: () => void;
}
const AddModelModal: React.FC<AddModelModalProps> = ({
  manufacturer,
  model,
  onClose,
  onSaved,
}) => {
  const [name, setName] = useState(model?.name ?? "");
  const [mdmModelId, setMdmModelId] = useState(model?.mdm_model_id ?? "");
  const [apkVariant, setApkVariant] = useState(
    model?.apk_variant ?? "aosp-full",
  );
  const [deviceType, setDeviceType] = useState(
    model?.device_type ?? "pos_terminal",
  );
  const [connectivity, setConnectivity] = useState(
    model?.connectivity ?? "cellular_4g",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!name.trim() || !mdmModelId.trim())
      return setError("Name and MDM Model ID are required");
    setLoading(true);
    setError("");
    try {
      if (model) {
        await api.updateCatalogModel(model.id, {
          name,
          mdm_model_id: mdmModelId,
          apk_variant: apkVariant,
          device_type: deviceType,
          connectivity,
        });
      } else {
        await api.createCatalogModel({
          manufacturer_id: manufacturer.id,
          name: name.trim(),
          slug: slugify(name),
          mdm_model_id: mdmModelId.trim(),
          apk_variant: apkVariant,
          device_type: deviceType,
          connectivity,
        });
      }
      onSaved();
    } catch {
      setError("Failed to save model — MDM model ID may already exist");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 className="text-lg font-bold text-gray-900 mb-1">
          {model ? "Edit Model" : "Add Model"}
        </h3>
        <p className="text-sm text-gray-500 mb-4">{manufacturer.name}</p>
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-gray-700">
              Model Name *
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              placeholder="e.g. P2 Pro"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">
              MDM Model ID *
            </label>
            <input
              value={mdmModelId}
              onChange={(e) => setMdmModelId(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
              placeholder="e.g. sunmi_p2_pro"
            />
            <p className="text-xs text-gray-400 mt-1">
              Unique key used by MDM service and adapters
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">
              APK Variant *
            </label>
            <select
              value={apkVariant}
              onChange={(e) => setApkVariant(e.target.value)}
              className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
            >
              {APK_VARIANTS.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-gray-700">
                Device Type
              </label>
              <select
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value)}
                className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {DEVICE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">
                Connectivity
              </label>
              <select
                value={connectivity}
                onChange={(e) => setConnectivity(e.target.value)}
                className="mt-1 w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                {CONNECTIVITY_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50"
          >
            {loading ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────

const DeviceCatalog: React.FC = () => {
  const [manufacturers, setManufacturers] = useState<CatalogManufacturer[]>([]);
  const [models, setModels] = useState<Record<string, CatalogModel[]>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [showAddMfr, setShowAddMfr] = useState(false);
  const [addModelFor, setAddModelFor] = useState<CatalogManufacturer | null>(
    null,
  );
  const [editModel, setEditModel] = useState<{
    mfr: CatalogManufacturer;
    model: CatalogModel;
  } | null>(null);

  const loadManufacturers = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.getCatalogManufacturers();
      setManufacturers(res.manufacturers ?? []);
    } catch {
      setError("Failed to load catalog");
    } finally {
      setLoading(false);
    }
  };

  const loadModels = async (mfrId: string) => {
    try {
      const res = await api.getCatalogModels(mfrId);
      setModels((prev) => ({ ...prev, [mfrId]: res.models ?? [] }));
    } catch {}
  };

  const toggleExpand = (mfrId: string) => {
    const next = !expanded[mfrId];
    setExpanded((prev) => ({ ...prev, [mfrId]: next }));
    if (next && !models[mfrId]) loadModels(mfrId);
  };

  const deleteMfr = async (id: string) => {
    if (!confirm("Delete this manufacturer and all its models?")) return;
    await api.deleteCatalogManufacturer(id);
    loadManufacturers();
  };

  const deleteModel = async (id: string, mfrId: string) => {
    if (!confirm("Delete this model?")) return;
    await api.deleteCatalogModel(id);
    loadModels(mfrId);
  };

  useEffect(() => {
    loadManufacturers();
  }, []);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Device Catalog</h1>
          <p className="text-gray-500 mt-1">
            Manage manufacturers and POS device models
          </p>
        </div>
        <button
          onClick={() => setShowAddMfr(true)}
          className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] flex items-center gap-2 text-sm"
        >
          <Plus className="w-4 h-4" /> Add Manufacturer
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl shadow divide-y divide-gray-100">
        {loading ? (
          <div className="px-6 py-10 text-center text-gray-400">Loading…</div>
        ) : manufacturers.length === 0 ? (
          <div className="px-6 py-10 text-center text-gray-400">
            No manufacturers yet. Add one to get started.
          </div>
        ) : (
          manufacturers.map((mfr) => (
            <div key={mfr.id}>
              {/* Manufacturer row */}
              <div
                className="flex items-center justify-between px-5 py-4 hover:bg-gray-50 cursor-pointer"
                onClick={() => toggleExpand(mfr.id)}
              >
                <div className="flex items-center gap-3">
                  {expanded[mfr.id] ? (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  )}
                  <div>
                    <p className="font-semibold text-gray-900">{mfr.name}</p>
                    {mfr.website && (
                      <a
                        href={mfr.website}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs text-[var(--tenant-primary-color,#002082)] hover:underline"
                      >
                        {mfr.website}
                      </a>
                    )}
                  </div>
                </div>
                <div
                  className="flex items-center gap-2"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => setAddModelFor(mfr)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-[rgba(0,79,113,0.08)] text-[var(--tenant-primary-color,#002082)] rounded-lg hover:bg-[rgba(0,79,113,0.15)]"
                  >
                    <Plus className="w-3 h-3" /> Add Model
                  </button>
                  <button
                    onClick={() => deleteMfr(mfr.id)}
                    className="p-1.5 text-red-400 hover:bg-red-50 rounded-lg"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Models list */}
              {expanded[mfr.id] && (
                <div className="bg-gray-50 border-t border-gray-100">
                  {!models[mfr.id] ? (
                    <p className="px-10 py-3 text-sm text-gray-400">
                      Loading models…
                    </p>
                  ) : models[mfr.id].length === 0 ? (
                    <p className="px-10 py-3 text-sm text-gray-400">
                      No models yet.
                    </p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-gray-500 uppercase tracking-wide border-b border-gray-200">
                          <th className="px-10 py-2 text-left">Model</th>
                          <th className="px-4 py-2 text-left">MDM Model ID</th>
                          <th className="px-4 py-2 text-left">APK Variant</th>
                          <th className="px-4 py-2 text-left">Connectivity</th>
                          <th className="px-4 py-2" />
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {models[mfr.id].map((m) => (
                          <tr key={m.id} className="hover:bg-gray-100">
                            <td className="px-10 py-2.5 font-medium text-gray-800">
                              {m.name}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-xs text-gray-600">
                              {m.mdm_model_id}
                            </td>
                            <td className="px-4 py-2.5">
                              <span className="px-2 py-0.5 bg-[rgba(0,79,113,0.08)] text-[var(--tenant-primary-color,#002082)] rounded text-xs font-medium">
                                {m.apk_variant}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-gray-500 text-xs">
                              {m.connectivity?.replace(/_/g, " ")}
                            </td>
                            <td className="px-4 py-2.5">
                              <div className="flex items-center justify-end gap-1">
                                <button
                                  onClick={() =>
                                    setEditModel({ mfr, model: m })
                                  }
                                  className="p-1.5 text-gray-400 hover:text-[var(--tenant-primary-color,#002082)] hover:bg-[rgba(0,79,113,0.08)] rounded"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </button>
                                <button
                                  onClick={() => deleteModel(m.id, mfr.id)}
                                  className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {showAddMfr && (
        <AddManufacturerModal
          onClose={() => setShowAddMfr(false)}
          onSaved={() => {
            setShowAddMfr(false);
            loadManufacturers();
          }}
        />
      )}
      {addModelFor && (
        <AddModelModal
          manufacturer={addModelFor}
          onClose={() => setAddModelFor(null)}
          onSaved={() => {
            loadModels(addModelFor.id);
            setAddModelFor(null);
          }}
        />
      )}
      {editModel && (
        <AddModelModal
          manufacturer={editModel.mfr}
          model={editModel.model}
          onClose={() => setEditModel(null)}
          onSaved={() => {
            loadModels(editModel.mfr.id);
            setEditModel(null);
          }}
        />
      )}
    </div>
  );
};

export default DeviceCatalog;
