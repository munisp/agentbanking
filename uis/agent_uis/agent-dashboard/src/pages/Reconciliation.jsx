import {
    AlertCircle,
    Calculator,
    CheckCircle,
    Download,
    RefreshCw,
} from "lucide-react";
import React, { useState } from "react";

const Reconciliation = () => {
  const [selectedBusiness, setSelectedBusiness] = useState("");
  const [reconciliationDate, setReconciliationDate] = useState("2026-02-22");

  const businesses = [
    { id: "business1", name: "Tani Store - Ikeja" },
    { id: "business2", name: "Tani Mart - Lekki" },
    { id: "business3", name: "Tani Express - VI" },
    { id: "business4", name: "Tani Shop - Yaba" },
  ];

  // Mock reconciliation data
  const reconciliationData = {
    systemBalance: 1250000,
    physicalCash: 1235000,
    posTransactions: 850000,
    cashSales: 385000,
    expenses: 50000,
    difference: -15000,
    transactions: [
      {
        id: 1,
        type: "Cash Sale",
        amount: 25000,
        time: "09:45 AM",
        matched: true,
      },
      {
        id: 2,
        type: "POS Transaction",
        amount: 15000,
        time: "10:15 AM",
        matched: true,
      },
      {
        id: 3,
        type: "Cash Sale",
        amount: 8500,
        time: "11:30 AM",
        matched: false,
      },
      {
        id: 4,
        type: "POS Transaction",
        amount: 35000,
        time: "02:20 PM",
        matched: true,
      },
      {
        id: 5,
        type: "Expense",
        amount: -5000,
        time: "03:45 PM",
        matched: false,
      },
    ],
  };

  const handleReconcile = () => {
    console.log(
      "Starting reconciliation for:",
      selectedBusiness,
      reconciliationDate,
    );
  };

  const matchedCount = reconciliationData.transactions.filter(
    (t) => t.matched,
  ).length;
  const unmatchedCount = reconciliationData.transactions.filter(
    (t) => !t.matched,
  ).length;
  const isDifferenceResolved = Math.abs(reconciliationData.difference) < 100;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          Account Reconciliation
        </h1>
        <p className="text-gray-600 mt-1">
          Match and verify your business transactions
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Business
            </label>
            <select
              value={selectedBusiness}
              onChange={(e) => setSelectedBusiness(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Choose a business</option>
              {businesses.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reconciliation Date
            </label>
            <input
              type="date"
              value={reconciliationDate}
              onChange={(e) => setReconciliationDate(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={handleReconcile}
              disabled={!selectedBusiness}
              className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className="h-5 w-5 inline mr-2" />
              Run Reconciliation
            </button>
          </div>
        </div>
      </div>

      {selectedBusiness && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-600">System Balance</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                ₦{reconciliationData.systemBalance.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">From transactions</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-600">Physical Cash</p>
              <p className="text-2xl font-bold text-blue-600 mt-1">
                ₦{reconciliationData.physicalCash.toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">Counted cash</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-600">Matched</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {matchedCount}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Transactions verified
              </p>
            </div>
            <div
              className={`rounded-lg shadow p-4 ${
                isDifferenceResolved ? "bg-green-50" : "bg-red-50"
              }`}
            >
              <p className="text-sm text-gray-600">Difference</p>
              <p
                className={`text-2xl font-bold mt-1 ${
                  isDifferenceResolved ? "text-green-600" : "text-red-600"
                }`}
              >
                ₦{Math.abs(reconciliationData.difference).toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {isDifferenceResolved ? "Within tolerance" : "Needs attention"}
              </p>
            </div>
          </div>

          {/* Reconciliation Status */}
          <div
            className={`rounded-lg p-4 ${
              isDifferenceResolved
                ? "bg-green-50 border border-green-200"
                : "bg-yellow-50 border border-yellow-200"
            }`}
          >
            <div className="flex items-start">
              {isDifferenceResolved ? (
                <CheckCircle className="h-5 w-5 text-green-600 mt-0.5 mr-3 flex-shrink-0" />
              ) : (
                <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5 mr-3 flex-shrink-0" />
              )}
              <div>
                <h3
                  className={`font-medium mb-1 ${
                    isDifferenceResolved ? "text-green-900" : "text-yellow-900"
                  }`}
                >
                  {isDifferenceResolved
                    ? "Reconciliation Complete"
                    : "Discrepancy Detected"}
                </h3>
                <p
                  className={`text-sm ${
                    isDifferenceResolved ? "text-green-700" : "text-yellow-700"
                  }`}
                >
                  {isDifferenceResolved
                    ? "Your accounts are balanced. All transactions have been verified and matched successfully."
                    : `There is a difference of ₦${Math.abs(reconciliationData.difference).toLocaleString()} between your system balance and physical cash. Review unmatched transactions below.`}
                </p>
              </div>
            </div>
          </div>

          {/* Transaction Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Transaction Details */}
            <div className="lg:col-span-2 bg-white rounded-lg shadow">
              <div className="p-6 border-b border-gray-200 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">
                  Transaction Details
                </h2>
                <button className="flex items-center text-sm text-blue-600 hover:text-blue-700 font-medium">
                  <Download className="h-4 w-4 mr-1" />
                  Export
                </button>
              </div>
              <div className="p-6">
                <div className="space-y-3">
                  {reconciliationData.transactions.map((transaction) => (
                    <div
                      key={transaction.id}
                      className={`flex items-center justify-between p-4 rounded-lg ${
                        transaction.matched ? "bg-green-50" : "bg-yellow-50"
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div
                          className={`p-2 rounded-lg ${
                            transaction.matched
                              ? "bg-green-100"
                              : "bg-yellow-100"
                          }`}
                        >
                          {transaction.matched ? (
                            <CheckCircle className="h-5 w-5 text-green-600" />
                          ) : (
                            <AlertCircle className="h-5 w-5 text-yellow-600" />
                          )}
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">
                            {transaction.type}
                          </p>
                          <p className="text-sm text-gray-500">
                            {transaction.time}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p
                          className={`font-semibold ${
                            transaction.amount > 0
                              ? "text-green-600"
                              : "text-orange-600"
                          }`}
                        >
                          {transaction.amount > 0 ? "+" : ""}₦
                          {Math.abs(transaction.amount).toLocaleString()}
                        </p>
                        <span
                          className={`text-xs ${
                            transaction.matched
                              ? "text-green-600"
                              : "text-yellow-600"
                          }`}
                        >
                          {transaction.matched ? "Matched" : "Unmatched"}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Summary Breakdown */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Summary
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between items-center pb-3 border-b border-gray-200">
                  <span className="text-gray-600">POS Transactions</span>
                  <span className="font-semibold text-gray-900">
                    ₦{reconciliationData.posTransactions.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center pb-3 border-b border-gray-200">
                  <span className="text-gray-600">Cash Sales</span>
                  <span className="font-semibold text-gray-900">
                    ₦{reconciliationData.cashSales.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center pb-3 border-b border-gray-200">
                  <span className="text-gray-600">Expenses</span>
                  <span className="font-semibold text-red-600">
                    -₦{reconciliationData.expenses.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-2">
                  <span className="font-semibold text-gray-900">Total</span>
                  <span className="font-bold text-blue-600 text-lg">
                    ₦{reconciliationData.systemBalance.toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-6 border-t border-gray-200">
                <h3 className="font-medium text-gray-900 mb-3">
                  Transaction Status
                </h3>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Matched</span>
                    <span className="font-medium text-green-600">
                      {matchedCount}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Unmatched</span>
                    <span className="font-medium text-yellow-600">
                      {unmatchedCount}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm font-semibold">
                    <span className="text-gray-900">Total</span>
                    <span className="text-gray-900">
                      {reconciliationData.transactions.length}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {!selectedBusiness && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Calculator className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            Select a business to start reconciliation
          </p>
        </div>
      )}
    </div>
  );
};

export default Reconciliation;
