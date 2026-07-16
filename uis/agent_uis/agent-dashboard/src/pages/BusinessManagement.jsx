import {
  AlertCircle,
  CreditCard,
  Edit2,
  Loader,
  MapPin,
  Package,
  Plus,
  Store as StoreIcon,
  Trash2,
  X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import MapPicker from "../components/MapPicker";
import { accountApi, inventoryApi, storeMapApi } from "../utils/api";

const BusinessManagement = () => {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editingStore, setEditingStore] = useState(null);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    address: "",
    latitude: "",
    longitude: "",
  });

  const keycloakId = localStorage.getItem("keycloakId");
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeError, setGeocodeError] = useState("");
  const [accountCreating, setAccountCreating] = useState({}); // storeId → bool

  useEffect(() => {
    if (keycloakId) fetchStores();
  }, [keycloakId]);

  const fetchStores = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await inventoryApi.getStores(keycloakId);
      setStores(data || []);
    } catch (err) {
      setError(err.message || "Failed to load businesses");
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      address: "",
      latitude: "",
      longitude: "",
    });
    setGeocodeError("");
    setEditingStore(null);
    setShowForm(false);
  };

  const openEditForm = (store) => {
    setEditingStore(store);
    setFormData({
      name: store.name,
      description: store.description || "",
      address: "",
      latitude: "",
      longitude: "",
    });
    setShowForm(true);
  };

  const handleFormChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (name === "address") setGeocodeError("");
  };

  const geocodeAddress = async () => {
    if (!formData.address.trim()) return;
    setGeocoding(true);
    setGeocodeError("");
    const parts = formData.address
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    const queries = parts.map((_, i) => parts.slice(i).join(", "));
    try {
      for (const q of queries) {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=1&countrycodes=ng`,
          { headers: { "Accept-Language": "en" } },
        );
        const results = await res.json();
        if (results.length > 0) {
          const { lat, lon } = results[0];
          setFormData((prev) => ({
            ...prev,
            latitude: parseFloat(lat).toFixed(6),
            longitude: parseFloat(lon).toFixed(6),
          }));
          return;
        }
      }
      setGeocodeError(
        "Address not found — try a more specific address or pin on the map.",
      );
    } catch {
      setGeocodeError(
        "Geocoding failed — please pin the location on the map manually.",
      );
    } finally {
      setGeocoding(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (editingStore) {
        const updated = await inventoryApi.updateStore(editingStore.id, {
          name: formData.name,
          description: formData.description,
        });
        setStores((prev) =>
          prev.map((s) => (s.id === updated.id ? updated : s)),
        );
        setSuccess("Business updated successfully!");
      } else {
        const newStore = await inventoryApi.createStore({
          name: formData.name,
          description: formData.description,
          owner_keycloak_id: keycloakId,
        });

        // Auto-create a bank account for this business
        let accountNumber = null;
        try {
          const accountResp = await accountApi.createAccount({
            account_type: "primary",
            name: newStore.name,
          });
          accountNumber =
            accountResp?.account?.account_number || accountResp?.account_number;
          if (accountNumber) {
            await inventoryApi.updateStore(newStore.id, {
              account_number: accountNumber,
            });
            newStore.account_number = accountNumber;
          }
        } catch (accErr) {
          console.error("Failed to create account for store:", accErr);
        }

        if (formData.latitude && formData.longitude && newStore.id) {
          try {
            await storeMapApi.registerStore({
              entity_id: String(newStore.id),
              entity_name: newStore.name,
              store_type: "MERCHANT",
              latitude: parseFloat(formData.latitude),
              longitude: parseFloat(formData.longitude),
              address: formData.address,
              country: "Nigeria",
              status: "OPEN",
            });
          } catch (mapErr) {
            console.error("Failed to register store on map:", mapErr);
          }
        }

        setStores((prev) => [newStore, ...prev]);
        setSuccess("Business registered successfully!");
      }
      resetForm();
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      setError(err.message || "Failed to save business");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (store) => {
    if (
      !window.confirm(
        `Delete "${store.name}" and all its inventory items? This cannot be undone.`,
      )
    )
      return;
    try {
      await inventoryApi.deleteStore(store.id);
      setStores((prev) => prev.filter((s) => s.id !== store.id));
      setSuccess("Business removed successfully!");
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      setError(err.message || "Failed to delete business");
    }
  };

  const createAccountForStore = async (store) => {
    setAccountCreating((prev) => ({ ...prev, [store.id]: true }));
    try {
      const accountResp = await accountApi.createAccount({
        account_type: "primary",
        name: store.name,
      });
      const accountNumber =
        accountResp?.account?.account_number || accountResp?.account_number;
      if (!accountNumber) throw new Error("No account number returned");
      const updated = await inventoryApi.updateStore(store.id, {
        account_number: accountNumber,
      });
      setStores((prev) =>
        prev.map((s) =>
          s.id === store.id
            ? { ...s, account_number: updated.account_number }
            : s,
        ),
      );
      setSuccess(`Account ${accountNumber} created for ${store.name}`);
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      setError(err.message || "Failed to create account");
    } finally {
      setAccountCreating((prev) => ({ ...prev, [store.id]: false }));
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-3 sm:p-4 lg:p-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-6 sm:mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              Business Management
            </h1>
            <p className="text-gray-600 mt-1">
              Register and manage your store businesses
            </p>
          </div>
          {!showForm && (
            <button
              onClick={() => {
                resetForm();
                setShowForm(true);
              }}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition"
            >
              <Plus size={20} />
              Add Business
            </button>
          )}
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-6 text-red-700 flex justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}>
              <X size={16} />
            </button>
          </div>
        )}
        {success && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg mb-6 text-green-700">
            {success}
          </div>
        )}

        {/* Create / Edit Form */}
        {showForm && (
          <div className="bg-white rounded-lg shadow-md p-4 sm:p-6 mb-8">
            <h2 className="text-xl font-bold mb-4">
              {editingStore
                ? `Edit: ${editingStore.name}`
                : "Register New Business"}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Business Name *
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={formData.name}
                    onChange={handleFormChange}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                    placeholder="e.g., Tani Mart - Ikeja"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    name="description"
                    value={formData.description}
                    onChange={handleFormChange}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] resize-none"
                    placeholder="Brief description of this business"
                  />
                </div>
              </div>

              {/* Location Section (create mode only) */}
              {!editingStore && (
                <div className="space-y-3 pt-2">
                  <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                    <MapPin size={14} /> Location
                    <span className="text-xs font-normal text-gray-500">
                      (optional — shows business on the map)
                    </span>
                  </h3>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      name="address"
                      value={formData.address}
                      onChange={handleFormChange}
                      onKeyDown={(e) =>
                        e.key === "Enter" &&
                        (e.preventDefault(), geocodeAddress())
                      }
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                      placeholder="e.g. 12 Marina Street, Lagos Island"
                    />
                    <button
                      type="button"
                      onClick={geocodeAddress}
                      disabled={geocoding || !formData.address.trim()}
                      className="px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:bg-gray-200 disabled:opacity-50 whitespace-nowrap flex items-center gap-1"
                    >
                      <MapPin size={14} />
                      {geocoding ? "Looking up..." : "Look up"}
                    </button>
                  </div>
                  {geocodeError && (
                    <p className="text-xs text-red-500">{geocodeError}</p>
                  )}
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Latitude
                      </label>
                      <input
                        type="number"
                        step="any"
                        name="latitude"
                        value={formData.latitude}
                        onChange={handleFormChange}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
                        placeholder="e.g. 6.5244"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Longitude
                      </label>
                      <input
                        type="number"
                        step="any"
                        name="longitude"
                        value={formData.longitude}
                        onChange={handleFormChange}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
                        placeholder="e.g. 3.3792"
                      />
                    </div>
                  </div>
                  <MapPicker
                    latitude={formData.latitude}
                    longitude={formData.longitude}
                    onLocationChange={(lat, lng) =>
                      setFormData((prev) => ({
                        ...prev,
                        latitude: lat.toFixed(6),
                        longitude: lng.toFixed(6),
                      }))
                    }
                  />
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:bg-gray-400 transition flex items-center gap-2"
                >
                  {loading && <Loader size={16} className="animate-spin" />}
                  {editingStore
                    ? "Save Changes"
                    : loading
                      ? "Registering..."
                      : "Register Business"}
                </button>
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Loading */}
        {loading && !showForm && (
          <div className="text-center py-12">
            <Loader
              size={32}
              className="animate-spin mx-auto"
              style={{ color: "var(--tenant-primary-color,#004F71)" }}
            />
            <p className="text-gray-600 mt-2">Loading businesses...</p>
          </div>
        )}

        {/* Empty state */}
        {!loading && stores.length === 0 && (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <StoreIcon size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No Businesses Yet
            </h3>
            <p className="text-gray-600 mb-4">
              Register your first business to get started
            </p>
            <button
              onClick={() => {
                resetForm();
                setShowForm(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)]"
            >
              <Plus size={18} />
              Register First Business
            </button>
          </div>
        )}

        {/* Stores list */}
        {!loading && stores.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[60vh] overflow-scroll">
            {stores.map((store) => (
              <div
                key={store.id}
                className="bg-white rounded-xl shadow-md p-6 flex flex-col gap-3"
              >
                <div className="flex items-start gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: "rgba(0, 79, 113, 0.1)" }}
                  >
                    <StoreIcon size={20} style={{ color: "var(--tenant-primary-color,#004F71)" }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-bold text-gray-900 truncate">
                      {store.name}
                    </h3>
                    <p className="text-xs text-gray-500">
                      Created {new Date(store.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                {store.description && (
                  <p className="text-sm text-gray-600 line-clamp-2">
                    {store.description}
                  </p>
                )}

                {/* Account number */}
                {store.account_number ? (
                  <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
                    <CreditCard size={14} className="text-green-600 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-green-600 font-medium">
                        Account Number
                      </p>
                      <p className="text-sm font-mono font-bold text-green-800 tracking-wider">
                        {store.account_number}
                      </p>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => createAccountForStore(store)}
                    disabled={accountCreating[store.id]}
                    className="flex items-center gap-2 px-3 py-2 bg-yellow-50 border border-yellow-300 text-yellow-800 rounded-lg hover:bg-yellow-100 transition text-sm font-medium disabled:opacity-60 w-full"
                  >
                    {accountCreating[store.id] ? (
                      <Loader size={14} className="animate-spin" />
                    ) : (
                      <CreditCard size={14} />
                    )}
                    {accountCreating[store.id]
                      ? "Creating account..."
                      : "Create Account"}
                  </button>
                )}

                <div className="mt-auto pt-3 border-t flex items-center gap-2">
                  <a
                    href="/inventory"
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-2 rounded-lg text-sm font-medium transition"
                    style={{
                      backgroundColor: "rgba(0, 79, 113, 0.1)",
                      color: "var(--tenant-primary-color,#004F71)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor =
                        "rgba(0, 79, 113, 0.15)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor =
                        "rgba(0, 79, 113, 0.1)";
                    }}
                  >
                    <Package size={14} />
                    Inventory
                  </a>
                  <button
                    onClick={() => openEditForm(store)}
                    className="px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition"
                    title="Edit"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(store)}
                    className="px-3 py-2 text-red-500 hover:bg-red-50 rounded-lg transition"
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default BusinessManagement;
