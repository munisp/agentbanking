import {
    Calendar,
    Download,
    Eye,
    Plus,
    Printer,
    Receipt,
    Search,
} from "lucide-react";
import React, { useState } from "react";

const Receipts = () => {
  const [searchQuery, setSearchQuery] = useState("");

  const receipts = [
    {
      id: "RCP-001",
      transactionId: "TXN-001",
      business: "Tani Store - Ikeja",
      customer: "Adewale Johnson",
      items: [
        { name: "Rice - Golden Penny 50kg", qty: 1, price: 45000 },
        { name: "Vegetable Oil - 25L", qty: 2, price: 28000 },
      ],
      totalAmount: 101000,
      date: "2026-02-22",
      time: "09:45 AM",
      paymentMethod: "Cash",
    },
    {
      id: "RCP-002",
      transactionId: "TXN-002",
      business: "Tani Mart - Lekki",
      customer: "Chiamaka Okonkwo",
      items: [
        { name: "Indomie Noodles (Carton)", qty: 3, price: 3500 },
        { name: "Coca-Cola Crate", qty: 2, price: 2200 },
      ],
      totalAmount: 14900,
      date: "2026-02-22",
      time: "10:15 AM",
      paymentMethod: "Transfer",
    },
    {
      id: "RCP-003",
      transactionId: "TXN-004",
      business: "Tani Express - VI",
      customer: "Oluwaseun Bello",
      items: [{ name: "Rice - Golden Penny 50kg", qty: 1, price: 45000 }],
      totalAmount: 45000,
      date: "2026-02-21",
      time: "02:20 PM",
      paymentMethod: "POS",
    },
  ];

  const filteredReceipts = receipts.filter(
    (receipt) =>
      receipt.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      receipt.customer.toLowerCase().includes(searchQuery.toLowerCase()) ||
      receipt.business.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const totalReceipts = receipts.length;
  const totalAmount = receipts.reduce((sum, r) => sum + r.totalAmount, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Receipts</h1>
          <p className="text-gray-600 mt-1">
            Generate and manage customer receipts
          </p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="h-5 w-5 mr-2" />
          New Receipt
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Receipts</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {totalReceipts}
          </p>
          <p className="text-xs text-gray-500 mt-1">All time</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Value</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            ₦{totalAmount.toLocaleString()}
          </p>
          <p className="text-xs text-gray-500 mt-1">From all receipts</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Today's Receipts</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">2</p>
          <p className="text-xs text-gray-500 mt-1">Generated today</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by receipt ID, customer, or business..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <button className="flex items-center px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50">
          <Calendar className="h-5 w-5 mr-2 text-gray-400" />
          Filter
        </button>
      </div>

      {/* Receipts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {filteredReceipts.map((receipt) => (
          <div
            key={receipt.id}
            className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow"
          >
            <div className="p-6">
              {/* Receipt Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="p-3 bg-blue-100 rounded-lg">
                    <Receipt className="h-6 w-6 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      {receipt.id}
                    </h3>
                    <p className="text-sm text-gray-500">
                      {receipt.transactionId}
                    </p>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title="View"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                  <button
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Print"
                  >
                    <Printer className="h-4 w-4" />
                  </button>
                  <button
                    className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                    title="Download"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {/* Business & Customer */}
              <div className="space-y-2 mb-4 pb-4 border-b border-gray-200">
                <div>
                  <p className="text-xs text-gray-500">Business</p>
                  <p className="text-sm font-medium text-gray-900">
                    {receipt.business}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Customer</p>
                  <p className="text-sm font-medium text-gray-900">
                    {receipt.customer}
                  </p>
                </div>
              </div>

              {/* Items */}
              <div className="space-y-2 mb-4">
                <p className="text-xs text-gray-500 font-medium">Items</p>
                {receipt.items.map((item, idx) => (
                  <div key={idx} className="flex justify-between text-sm">
                    <span className="text-gray-600">
                      {item.name} (x{item.qty})
                    </span>
                    <span className="text-gray-900 font-medium">
                      ₦{(item.price * item.qty).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>

              {/* Total & Payment Info */}
              <div className="pt-4 border-t border-gray-200">
                <div className="flex justify-between items-center mb-3">
                  <p className="text-sm font-medium text-gray-600">
                    Total Amount
                  </p>
                  <p className="text-xl font-bold text-green-600">
                    ₦{receipt.totalAmount.toLocaleString()}
                  </p>
                </div>
                <div className="flex justify-between text-sm text-gray-600">
                  <span>Payment: {receipt.paymentMethod}</span>
                  <span>
                    {receipt.date} at {receipt.time}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredReceipts.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Receipt className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            No receipts found matching your search.
          </p>
        </div>
      )}
    </div>
  );
};

export default Receipts;
