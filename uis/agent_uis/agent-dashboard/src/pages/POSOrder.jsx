import {
  AlertCircle,
  ArrowLeft,
  Banknote,
  Box,
  CheckCircle,
  ChevronRight,
  Clock,
  CreditCard,
  MapPin,
  MonitorSmartphone,
  Package,
  Plus,
  ShoppingCart,
  Truck,
  X,
  Zap,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { posHardwareApi, posRequestApi } from "../utils/api";

const colorPalette = ["blue", "green", "purple", "orange"];

const colorMap = {
  blue: {
    bg: "rgba(0,79,113,0.1)",
    text: "var(--tenant-primary-color,#004F71)",
    ring: "ring-[var(--tenant-secondary-color,#69BC5E)]",
    ringOpacity: "ring-opacity-50",
  },
  green: { bg: "bg-green-100", text: "text-green-600", ring: "ring-green-200" },
  purple: {
    bg: "bg-purple-100",
    text: "text-purple-600",
    ring: "ring-purple-200",
  },
  orange: {
    bg: "bg-orange-100",
    text: "text-orange-600",
    ring: "ring-orange-200",
  },
};

const statusConfig = {
  pending: {
    label: "Pending Review",
    color: "bg-gray-100 text-gray-700",
    icon: Clock,
  },
  approved: {
    label: "Approved",
    color: "text-[var(--tenant-primary-color,#004F71)]",
    bgColor: "rgba(0,79,113,0.1)",
    icon: CheckCircle,
  },
  assigned: {
    label: "Assigned",
    color: "bg-green-100 text-green-700",
    icon: Package,
  },
  rejected: {
    label: "Rejected",
    color: "bg-red-100 text-red-700",
    icon: X,
  },
  cancelled: {
    label: "Cancelled",
    color: "bg-gray-100 text-gray-600",
    icon: AlertCircle,
  },
};

const savedAddresses = [
  {
    id: "addr-1",
    label: "Tani Store – Ikeja",
    address: "12 Allen Ave, Ikeja, Lagos",
  },
  {
    id: "addr-2",
    label: "Tani Mart – Lekki",
    address: "45 Admiralty Way, Lekki Phase 1",
  },
  {
    id: "addr-3",
    label: "Tani Express – Victoria Island",
    address: "3 Ozumba Mbadiwe Ave, VI",
  },
];

const POSOrder = () => {
  const [activeTab, setActiveTab] = useState("catalog");
  const [selectedModel, setSelectedModel] = useState(null);
  const [orderForm, setOrderForm] = useState({
    qty: 1,
    addressId: "addr-1",
    note: "",
  });
  const [devices, setDevices] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [orderSuccess, setOrderSuccess] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    let active = true;

    const loadData = async () => {
      setLoading(true);
      setError(null);

      try {
        const [deviceRes, requestRes] = await Promise.all([
          posHardwareApi.getPOSDevices({ limit: 200 }),
          posRequestApi.getMyRequests(),
        ]);

        if (!active) return;
        setDevices(deviceRes?.data || []);
        setOrders(requestRes || []);
      } catch (err) {
        if (!active) return;
        setError(err?.message || "Failed to load POS catalog");
      } finally {
        if (active) setLoading(false);
      }
    };

    loadData();

    return () => {
      active = false;
    };
  }, []);

  const catalog = useMemo(() => {
    const grouped = new Map();

    devices.forEach((device) => {
      if (device.assigned_agent_id) return;
      const status = (device.device_status || "").toLowerCase();
      if (["decommissioned", "stolen", "quarantined"].includes(status)) return;

      const nameParts = [device.manufacturer, device.model].filter(Boolean);
      const name =
        nameParts.length > 0
          ? nameParts.join(" ")
          : device.device_name || device.device_id;
      const category = device.device_type
        ? device.device_type.replace(/_/g, " ")
        : "POS Device";
      const key = `${device.device_type || "device"}-${name}`;

      if (!grouped.has(key)) {
        const initials = name
          .split(" ")
          .map((p) => p[0])
          .join("")
          .slice(0, 2)
          .toUpperCase();
        grouped.set(key, {
          id: key,
          name,
          category,
          image: initials,
          specs: [
            device.device_type ? category : null,
            device.connectivity_type
              ? device.connectivity_type.replace(/_/g, " ")
              : null,
          ].filter(Boolean),
          available: 0,
          lead_days: 2,
        });
      }

      const entry = grouped.get(key);
      entry.available += 1;
    });

    return Array.from(grouped.values()).map((entry, index) => {
      const availability = entry.available <= 2 ? "low_stock" : "in_stock";
      return {
        ...entry,
        color: colorPalette[index % colorPalette.length],
        availability,
      };
    });
  }, [devices]);

  const handleOrder = async () => {
    if (!selectedModel) return;
    const model = catalog.find((m) => m.id === selectedModel);
    const addr = savedAddresses.find((a) => a.id === orderForm.addressId);
    if (!model || !addr) return;

    try {
      const request = await posRequestApi.createRequest({
        preferred_model: model.name,
        quantity: orderForm.qty,
        deployment_location: addr.label,
        deployment_address: addr.address,
        justification: orderForm.note || undefined,
      });

      setOrderSuccess({
        id: request.id,
        model: model.name,
        qty: request.quantity,
        status: request.status,
        date: new Date().toISOString().slice(0, 10),
        address: addr.address,
      });
      setConfirmOpen(false);
      setSelectedModel(null);
      setOrderForm({ qty: 1, addressId: "addr-1", note: "" });
      setActiveTab("orders");

      const updated = await posRequestApi.getMyRequests();
      setOrders(updated || []);
    } catch (err) {
      setError(err?.message || "Failed to place order");
    }
  };

  const selectedModelData = catalog.find((m) => m.id === selectedModel);
  const selectedAddr = savedAddresses.find((a) => a.id === orderForm.addressId);
  const formatDate = (value) =>
    value ? new Date(value).toISOString().slice(0, 10) : "—";

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          to="/pos"
          className="p-2 rounded-xl hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-gray-600" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Request POS Terminal
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Request new terminals — delivered to your registered address
          </p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-red-800">{error}</p>
            <p className="text-xs text-red-700 mt-0.5">
              Please try again or contact support if this persists.
            </p>
          </div>
        </div>
      )}

      {/* Success banner */}
      {orderSuccess && (
        <div className="flex items-start gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
          <CheckCircle className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-green-800">
              Order placed — {orderSuccess.id}
            </p>
            <p className="text-xs text-green-700 mt-0.5">
              {orderSuccess.qty}× {orderSuccess.model} · Status:{" "}
              {orderSuccess.status}
            </p>
          </div>
          <button
            onClick={() => setOrderSuccess(null)}
            className="ml-auto text-green-400 hover:text-green-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {[
          { key: "catalog", label: "Terminal Catalog" },
          { key: "orders", label: `My Orders (${orders.length})` },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Catalog */}
      {activeTab === "catalog" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-5">
          {loading && (
            <div className="col-span-full bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400">
              <Package className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm font-medium">Loading catalog...</p>
            </div>
          )}
          {!loading && catalog.length === 0 && (
            <div className="col-span-full bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400">
              <Package className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm font-medium">No devices available</p>
            </div>
          )}
          {!loading &&
            catalog.map((model) => {
              const c = colorMap[model.color];
              const isSelected = selectedModel === model.id;
              return (
                <div
                  key={model.id}
                  onClick={() => setSelectedModel(isSelected ? null : model.id)}
                  className={`bg-white rounded-2xl border shadow-sm cursor-pointer transition-all overflow-hidden ${
                    isSelected
                      ? `border-[var(--tenant-secondary-color,#69BC5E)] ring-2 ${c.ring} ${c.ringOpacity || ""}`
                      : "border-gray-100 hover:border-gray-300"
                  }`}
                >
                  <div className="p-5">
                    <div className="flex items-start gap-4">
                      <div
                        className={`w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 text-lg font-bold ${typeof c.bg === "string" && c.bg.startsWith("bg-") ? c.bg : ""} ${typeof c.text === "string" && c.text.startsWith("text-") ? c.text : ""}`}
                        style={
                          typeof c.bg === "string" && !c.bg.startsWith("bg-")
                            ? {
                                backgroundColor: c.bg,
                                color: c.text,
                              }
                            : undefined
                        }
                      >
                        {model.image}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h2 className="text-base font-bold text-gray-900">
                            {model.name}
                          </h2>
                          {model.availability === "low_stock" ? (
                            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                              Low stock
                            </span>
                          ) : (
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                              In stock
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {model.category}
                        </p>
                        <p className="text-xs text-gray-400 mt-1 italic">
                          Available: {model.available}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {model.specs.map((s) => (
                        <span
                          key={s}
                          className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-lg"
                        >
                          {s}
                        </span>
                      ))}
                    </div>

                    <div className="mt-4 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">
                          Lead time: {model.lead_days}–{model.lead_days + 2}{" "}
                          days
                        </p>
                        <p className="text-xs text-gray-400">
                          {model.available} units available
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedModel(model.id);
                        }}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-semibold transition-colors ${
                          isSelected
                            ? "bg-[var(--tenant-primary-color,#004F71)] text-white"
                            : "bg-gray-100 text-gray-700"
                        }`}
                        style={
                          !isSelected
                            ? {
                                ":hover": {
                                  backgroundColor: "rgba(0,79,113,0.05)",
                                  color: "var(--tenant-primary-color,#004F71)",
                                },
                              }
                            : undefined
                        }
                        onMouseEnter={
                          !isSelected
                            ? (e) => {
                                e.currentTarget.style.backgroundColor =
                                  "rgba(0,79,113,0.05)";
                                e.currentTarget.style.color = "var(--tenant-primary-color,#004F71)";
                              }
                            : undefined
                        }
                        onMouseLeave={
                          !isSelected
                            ? (e) => {
                                e.currentTarget.style.backgroundColor = "";
                                e.currentTarget.style.color = "";
                              }
                            : undefined
                        }
                      >
                        <ShoppingCart className="w-3.5 h-3.5" />
                        {isSelected ? "Selected" : "Select"}
                      </button>
                    </div>
                  </div>

                  {/* Expanded order form */}
                  {isSelected && (
                    <div
                      className="border-t border-gray-100 px-5 py-4 space-y-4"
                      style={{ backgroundColor: "rgba(0,79,113,0.03)" }}
                    >
                      <p className="text-sm font-semibold text-gray-800">
                        Configure your order
                      </p>

                      {/* Quantity */}
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1.5">
                          Quantity
                        </label>
                        <div className="flex items-center gap-3">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOrderForm((f) => ({
                                ...f,
                                qty: Math.max(1, f.qty - 1),
                              }));
                            }}
                            className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center text-gray-600 hover:bg-gray-50"
                          >
                            −
                          </button>
                          <span className="text-base font-bold text-gray-900 w-6 text-center">
                            {orderForm.qty}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOrderForm((f) => ({
                                ...f,
                                qty: Math.min(model.available, f.qty + 1),
                              }));
                            }}
                            className="w-8 h-8 rounded-lg bg-white border border-gray-200 flex items-center justify-center text-gray-600 hover:bg-gray-50"
                          >
                            +
                          </button>
                        </div>
                      </div>

                      {/* Delivery address */}
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1.5">
                          <MapPin className="w-3 h-3 inline mr-1" />
                          Delivery address
                        </label>
                        <div className="space-y-1.5">
                          {savedAddresses.map((addr) => (
                            <label
                              key={addr.id}
                              onClick={(e) => e.stopPropagation()}
                              className={`flex items-center gap-2.5 p-2.5 rounded-xl cursor-pointer border text-sm transition-all ${
                                orderForm.addressId === addr.id
                                  ? "border-[var(--tenant-secondary-color,#69BC5E)] bg-white"
                                  : "border-gray-200 bg-white hover:border-gray-300"
                              }`}
                            >
                              <input
                                type="radio"
                                name="address"
                                value={addr.id}
                                checked={orderForm.addressId === addr.id}
                                onChange={() =>
                                  setOrderForm((f) => ({
                                    ...f,
                                    addressId: addr.id,
                                  }))
                                }
                                style={{ accentColor: "var(--tenant-secondary-color,#69BC5E)" }}
                              />
                              <div>
                                <p className="font-medium text-gray-800">
                                  {addr.label}
                                </p>
                                <p className="text-xs text-gray-400">
                                  {addr.address}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>
                      </div>

                      {/* Note */}
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1.5">
                          Delivery note (optional)
                        </label>
                        <textarea
                          rows={2}
                          placeholder="e.g. Call before delivery, leave at gate…"
                          value={orderForm.note}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) =>
                            setOrderForm((f) => ({
                              ...f,
                              note: e.target.value,
                            }))
                          }
                          className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white resize-none"
                        />
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmOpen(true);
                        }}
                        disabled={model.available === 0}
                        className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2 ${
                          model.available === 0
                            ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                            : "bg-[var(--tenant-primary-color,#004F71)] text-white hover:bg-[var(--tenant-primary-color,#003F5A)]"
                        }`}
                      >
                        <Package className="w-4 h-4" />
                        Place Order
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
        </div>
      )}

      {/* Orders */}
      {activeTab === "orders" && (
        <div className="space-y-4">
          {orders.length === 0 && (
            <div className="bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400">
              <Box className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm font-medium">No orders yet</p>
              <button
                onClick={() => setActiveTab("catalog")}
                className="mt-3 text-sm font-medium hover:underline"
                style={{ color: "var(--tenant-primary-color,#004F71)" }}
              >
                Browse terminal catalog →
              </button>
            </div>
          )}
          {orders.map((order) => {
            const sc = statusConfig[order.status] || statusConfig.pending;
            const StatusIcon = sc.icon;
            return (
              <div
                key={order.id}
                className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5"
              >
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-100 rounded-xl flex items-center justify-center shrink-0">
                      <MonitorSmartphone className="w-5 h-5 text-gray-500" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-gray-900">
                        {order.quantity}×{" "}
                        {order.preferred_model || "POS Device"}
                      </p>
                      <p className="text-xs text-gray-400">
                        {order.id} · {formatDate(order.created_at)}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${sc.bgColor ? "" : sc.color}`}
                    style={
                      sc.bgColor
                        ? {
                            backgroundColor: sc.bgColor,
                            color: sc.color,
                          }
                        : undefined
                    }
                  >
                    <StatusIcon className="w-3.5 h-3.5" />
                    {sc.label}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs text-gray-500">
                  <div>
                    <p className="font-medium text-gray-700">Quantity</p>
                    <p className="font-bold text-gray-900 text-sm mt-0.5">
                      {order.quantity}
                    </p>
                  </div>
                  <div>
                    <p className="font-medium text-gray-700">Location</p>
                    <p className="mt-0.5">
                      {order.deployment_location || order.city || "—"}
                    </p>
                  </div>
                  <div>
                    <p className="font-medium text-gray-700">Address</p>
                    <p className="mt-0.5">{order.deployment_address || "—"}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Confirm modal */}
      {confirmOpen && selectedModelData && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6 space-y-4">
            <h2 className="text-lg font-bold text-gray-900">Confirm Order</h2>
            <div className="bg-gray-50 rounded-xl p-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Terminal</span>
                <span className="font-semibold">{selectedModelData.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Quantity</span>
                <span className="font-semibold">{orderForm.qty}</span>
              </div>
              <div className="flex justify-between text-xs text-gray-400 pt-1">
                <span>Deliver to</span>
                <span>{selectedAddr?.address}</span>
              </div>
            </div>
            <div className="bg-amber-50 border border-amber-100 rounded-xl px-3 py-2 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800">
                Payment will be deducted from your wallet or settled at
                delivery, based on your account type.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirmOpen(false)}
                className="flex-1 py-2.5 border border-gray-300 rounded-xl text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleOrder}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)]"
              >
                Confirm Order
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default POSOrder;
