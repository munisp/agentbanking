import { Plus, ShoppingCart } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { orderApi } from "../utils/api";

const Orders = () => {
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const keycloakId = localStorage.getItem("keycloakId");

      // Try to fetch from API first
      try {
        const data = await orderApi.getAgentOrders(keycloakId, {
          limit: 50,
          page: 1,
        });
        setOrders(Array.isArray(data) ? data : data.orders || []);
      } catch (apiError) {
        // If API endpoint doesn't exist (404), fall back to local storage
        console.log("Orders API not available, using local storage");
        const localOrders = JSON.parse(
          localStorage.getItem("agent_orders") || "[]",
        );
        // Filter orders by keycloak ID
        const agentOrders = localOrders.filter(
          (order) => order.agent_keycloak_id === keycloakId,
        );
        setOrders(
          agentOrders.sort(
            (a, b) => new Date(b.created_at) - new Date(a.created_at),
          ),
        );
      }
    } catch (err) {
      console.error("Error fetching orders:", err);
      setError("Failed to fetch orders. Using local data.");
      // Final fallback to empty array
      setOrders([]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString("en-NG", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case "completed":
        return "bg-green-100 text-green-700";
      case "pending":
        return "bg-yellow-100 text-yellow-700";
      case "cancelled":
        return "bg-red-100 text-red-700";
      default:
        return "bg-gray-100 text-gray-700";
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div
        className="rounded-2xl shadow-xl p-8 text-white"
        style={{
          background: "linear-gradient(to right, var(--tenant-primary-color,#002082), #003F5A, var(--tenant-primary-color,#003047))",
        }}
      >
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <ShoppingCart className="h-8 w-8" />
              Business Orders
            </h1>
            <p className="mt-2" style={{ color: "rgba(255,255,255,0.8)" }}>
              View and manage all your store orders
            </p>
          </div>
          <button
            onClick={() => navigate("/orders/create")}
            className="flex items-center gap-2 bg-white px-6 py-3 rounded-lg font-semibold transition-colors"
            style={{ color: "var(--tenant-primary-color,#002082)" }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor = "rgba(0, 79, 113, 0.05)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = "white")
            }
          >
            <Plus className="h-5 w-5" />
            Create Order
          </button>
        </div>
      </div>

      {/* Local Storage Notice */}
      {orders.length > 0 && orders[0]?.is_local && (
        <div
          className="border rounded-lg px-4 py-3"
          style={{
            backgroundColor: "rgba(0,79,113,0.05)",
            borderColor: "rgba(0,79,113,0.2)",
            color: "var(--tenant-primary-color,#002082)",
          }}
        >
          <p className="font-semibold">
            ℹ️ Orders are currently stored locally
          </p>
          <p className="text-sm mt-1">
            These orders will sync with the server once the backend API is
            available.
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-12">
          <div className="text-center">
            <div
              className="animate-spin rounded-full h-12 w-12 border-b-2 mx-auto mb-4"
              style={{ borderColor: "var(--tenant-primary-color,#002082)" }}
            ></div>
            <p className="text-gray-600">Loading orders...</p>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && orders.length === 0 && (
        <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-12">
          <div className="text-center">
            <ShoppingCart className="h-16 w-16 mx-auto mb-4 text-gray-400" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No orders found
            </h3>
            <p className="text-gray-600 mb-6">
              Create your first order to get started
            </p>
            <button
              onClick={() => navigate("/orders/create")}
              className="inline-flex items-center gap-2 px-6 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors"
            >
              <Plus className="h-5 w-5" />
              Create Order
            </button>
          </div>
        </div>
      )}

      {/* Orders List */}
      {!loading && orders.length > 0 && (
        <div className="space-y-4 max-h-[60vh] overflow-scroll">
          {orders.map((order) => (
            <div
              key={order.id}
              onClick={() => navigate(`/orders/${order.id}/receipt`)}
              className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-lg transition-all cursor-pointer"
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor = "rgba(0,79,113,0.3)")
              }
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "")}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-bold text-lg text-gray-900">
                      Order #{order.id?.substring(0, 8).toUpperCase()}
                    </h3>
                    <span
                      className={`text-xs px-3 py-1 rounded-full font-medium ${getStatusColor(order.status)}`}
                    >
                      {order.status?.toUpperCase() || "PENDING"}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Store</p>
                      <p className="font-semibold text-gray-900">
                        {order.store_name || "N/A"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Date</p>
                      <p className="font-semibold text-gray-900">
                        {formatDate(order.created_at)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">
                        Payment Method
                      </p>
                      <p className="font-semibold text-gray-900 capitalize">
                        {order.payment_method || "N/A"}
                      </p>
                      {order.transaction_id && (
                        <p className="text-xs text-gray-500 mt-1">
                          Txn ID: {order.transaction_id}
                        </p>
                      )}
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Items</p>
                      <p className="font-semibold text-gray-900">
                        {order.items?.length || 0} item(s)
                      </p>
                    </div>
                  </div>

                  {order.customer_name && (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <p className="text-xs text-gray-500">Customer</p>
                      <p className="font-semibold text-gray-900">
                        {order.customer_name}
                        {order.customer_phone && ` • ${order.customer_phone}`}
                      </p>
                    </div>
                  )}
                </div>

                <div className="text-right ml-6">
                  <p className="text-xs text-gray-500 mb-1">Total Amount</p>
                  <p
                    className="text-2xl font-bold"
                    style={{ color: "var(--tenant-primary-color,#002082)" }}
                  >
                    ₦{(order.total || 0).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Orders;
