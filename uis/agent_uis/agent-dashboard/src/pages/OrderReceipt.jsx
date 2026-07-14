import {
    ArrowLeft,
    CheckCircle,
    FileText,
    Printer,
    Share2,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { orderApi } from "../utils/api";

const OrderReceipt = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { orderId } = useParams();
  const [order, setOrder] = useState(location.state?.order || null);
  const [loading, setLoading] = useState(!order);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!order && orderId) {
      loadOrder();
    }
  }, [orderId]);

  const loadOrder = async () => {
    setLoading(true);
    setError(null);
    try {
      // Try to load from API first
      try {
        const data = await orderApi.getOrder(orderId);
        setOrder(data);
      } catch (apiError) {
        console.log("Orders API not available, checking local storage");
        // If API fails, check local storage
        const localOrders = JSON.parse(
          localStorage.getItem("agent_orders") || "[]",
        );
        const localOrder = localOrders.find((o) => o.id === orderId);
        if (localOrder) {
          setOrder(localOrder);
        } else {
          throw new Error("Order not found");
        }
      }
    } catch (err) {
      console.error("Error loading order:", err);
      setError("Failed to load order details");
    } finally {
      setLoading(false);
    }
  };

  const handleShare = () => {
    if (navigator.share && order) {
      navigator
        .share({
          title: `Order #${order.id}`,
          text: `Order Receipt - Total: ₦${order.total?.toLocaleString() || "0"}`,
        })
        .catch((err) => console.error("Error sharing:", err));
    } else {
      alert("Share functionality not supported on this browser");
    }
  };

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading order details...</p>
        </div>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-lg">
          {error || "Order not found"}
        </div>
        <button
          onClick={() => navigate("/orders")}
          className="px-6 py-3 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors font-semibold"
        >
          Back to Orders
        </button>
      </div>
    );
  }

  const orderDate = order.created_at
    ? new Date(order.created_at).toLocaleString("en-NG", {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "N/A";

  return (
    <div className="space-y-6">
      {/* Success Header */}
      <div className="bg-gradient-to-r from-green-600 to-emerald-600 rounded-2xl shadow-lg p-8 text-white">
        <div className="text-center">
          <CheckCircle className="h-16 w-16 mx-auto mb-4" />
          <h1 className="text-3xl font-bold mb-2">
            Order Created Successfully!
          </h1>
          <p className="text-green-100 text-lg">
            Order #{order.id?.substring(0, 8).toUpperCase()}
          </p>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3 print:hidden">
        <button
          onClick={() => navigate("/orders")}
          className="flex items-center gap-2 px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
          Back to Orders
        </button>
        <button
          onClick={() => navigate("/orders/create")}
          className="flex items-center gap-2 px-6 py-3 bg-[var(--tenant-primary-color,#002082)] hover:bg-[var(--tenant-primary-color,#003F5A)] text-white font-semibold rounded-lg transition-colors"
        >
          <FileText className="h-5 w-5" />
          Create Another Order
        </button>
        <button
          onClick={handleShare}
          className="flex items-center gap-2 px-6 py-3 bg-[var(--tenant-primary-color,#002082)] hover:bg-[var(--tenant-primary-color,#003F5A)] text-white font-semibold rounded-lg transition-colors"
        >
          <Share2 className="h-5 w-5" />
          Share
        </button>
        <button
          onClick={handlePrint}
          className="flex items-center gap-2 px-6 py-3 bg-[var(--tenant-primary-color,#002082)] hover:bg-[var(--tenant-primary-color,#003F5A)] text-white font-semibold rounded-lg transition-colors"
        >
          <Printer className="h-5 w-5" />
          Print Receipt
        </button>
      </div>

      {/* Receipt */}
      <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-8 max-w-3xl mx-auto">
        {/* Store/Business Header */}
        <div className="text-center border-b border-gray-200 pb-6 mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            {order.store_name || "Store"}
          </h2>
          <p className="text-sm text-gray-500">Sales Receipt</p>
          <p className="text-xs text-gray-400 mt-1">{orderDate}</p>
        </div>

        {/* Order Details */}
        <div className="space-y-4 mb-6">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Order ID:</span>
            <span className="font-mono font-semibold">
              {order.id?.substring(0, 8).toUpperCase()}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Payment Method:</span>
            <span className="font-semibold capitalize">
              {order.payment_method || "N/A"}
            </span>
          </div>
          {order.transaction_id && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Transaction ID:</span>
              <span className="font-mono text-xs">{order.transaction_id}</span>
            </div>
          )}
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Status:</span>
            <span
              className={`px-2 py-1 rounded text-xs font-medium ${
                order.status === "completed"
                  ? "bg-green-100 text-green-700"
                  : order.status === "pending"
                    ? "bg-yellow-100 text-yellow-700"
                    : "bg-gray-100 text-gray-700"
              }`}
            >
              {order.status?.toUpperCase() || "PENDING"}
            </span>
          </div>
        </div>

        {/* Customer Details */}
        {(order.customer_name ||
          order.customer_phone ||
          order.customer_email) && (
          <div className="border-t border-gray-200 pt-4 mb-6">
            <h3 className="font-semibold text-gray-900 mb-3">
              Customer Details
            </h3>
            <div className="space-y-2 text-sm">
              {order.customer_name && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Name:</span>
                  <span className="font-semibold">{order.customer_name}</span>
                </div>
              )}
              {order.customer_phone && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Phone:</span>
                  <span className="font-semibold">{order.customer_phone}</span>
                </div>
              )}
              {order.customer_email && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Email:</span>
                  <span className="font-semibold">{order.customer_email}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Items Table */}
        <div className="border-t border-gray-200 pt-4 mb-6">
          <h3 className="font-semibold text-gray-900 mb-3">Items</h3>
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 text-left text-sm text-gray-600">
                <th className="pb-2 font-semibold">Item</th>
                <th className="pb-2 font-semibold text-center">Qty</th>
                <th className="pb-2 font-semibold text-right">Price</th>
                <th className="pb-2 font-semibold text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {order.items?.map((item, index) => (
                <tr key={index} className="border-b border-gray-100 text-sm">
                  <td className="py-3">
                    <div>
                      <p className="font-semibold text-gray-900">
                        {item.name || item.item_name || "Item"}
                      </p>
                      {item.sku && (
                        <p className="text-xs text-gray-500">SKU: {item.sku}</p>
                      )}
                    </div>
                  </td>
                  <td className="py-3 text-center">{item.quantity || 0}</td>
                  <td className="py-3 text-right">
                    ₦{(item.unit_price || 0).toLocaleString()}
                  </td>
                  <td className="py-3 text-right font-semibold">
                    ₦
                    {(
                      (item.quantity || 0) * (item.unit_price || 0)
                    ).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Totals */}
        <div className="border-t-2 border-gray-200 pt-4 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Subtotal:</span>
            <span className="font-semibold">
              ₦{(order.subtotal || 0).toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Tax (7.5%):</span>
            <span className="font-semibold">
              ₦{(order.tax || 0).toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-lg font-bold pt-2 border-t border-gray-200">
            <span>Total:</span>
            <span style={{ color: "var(--tenant-primary-color,#002082)" }}>
              ₦{(order.total || 0).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8 pt-6 border-t border-gray-200">
          <p className="text-sm text-gray-600">Thank you for your business!</p>
          <p className="text-xs text-gray-400 mt-1">
            This is a computer-generated receipt
          </p>
        </div>
      </div>

      {/* Print Styles */}
      <style>{`
        @media print {
          body {
            background: white;
          }
          .print\\:hidden {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
};

export default OrderReceipt;
