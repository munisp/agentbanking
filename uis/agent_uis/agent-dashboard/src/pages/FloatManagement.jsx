import { CheckCircle, Clock, X, Zap } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const FloatManagement = () => {
  const [loanModal, setLoanModal] = useState(false);
  const [actionSuccess, setActionSuccess] = useState(null);
  const [loanApplications, setLoanApplications] = useState([]);
  const [loading, setLoading] = useState(false);

  // Loan application form state
  const [loanForm, setLoanForm] = useState({
    loan_amount: "",
    requested_term: "12",
  });

  // Fetch loan applications from core banking
  const fetchLoanApplications = async () => {
    try {
      const response = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/applications/administration`,
        { headers: authHeaders() },
      );
      if (response.ok) {
        const data = await response.json();
        // Filter for float loans only
        const floatLoans = Array.isArray(data)
          ? data.filter(
              (loan) =>
                loan.loan_purpose?.toLowerCase().includes("float") ||
                loan.loan_purpose?.toLowerCase() === "float loan",
            )
          : [];
        setLoanApplications(floatLoans);
      }
    } catch (error) {
      console.error("Error fetching loan applications:", error);
    }
  };

  useEffect(() => {
    fetchLoanApplications();
  }, []);

  const handleLoanRequest = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/applications`,
        {
          method: "POST",
          headers: {
            ...authHeaders(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            loan_amount: Number(loanForm.loan_amount),
            loan_purpose: "Float Loan",
            requested_term: Number(loanForm.requested_term),
            // Default values like mobile app
            monthly_income: 1000,
            existing_debt: 0,
            collateral_value: 5000,
            credit_score: 1100,
            employment_status: "employed",
            employment_duration: 24,
            bank_statement_score: 90,
            bvn_verified: true,
            nin_verified: true,
          }),
        },
      );

      if (response.ok) {
        setActionSuccess({
          type: "loan",
          amount: Number(loanForm.loan_amount),
        });
        setLoanForm({
          loan_amount: "",
          requested_term: "12",
        });
        setLoanModal(false);
        fetchLoanApplications();
        setTimeout(() => setActionSuccess(null), 5000);
      } else {
        const error = await response.json();
        alert(error.message || "Failed to submit loan application");
      }
    } catch (error) {
      console.error("Error submitting loan application:", error);
      alert("Failed to submit loan application");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Float Request Management
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Apply for float requests and track your loan applications
          </p>
        </div>
        <div>
          <button
            onClick={() => {
              setLoanModal(true);
              setActionSuccess(null);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)]"
          >
            <Zap className="w-4 h-4" />
            Request for Float
          </button>
        </div>
      </div>

      {/* Success banner */}
      {actionSuccess && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          <div className="text-sm text-green-800">
            <span>
              Float Request for ₦
              <strong>{actionSuccess.amount.toLocaleString()}</strong> submitted
              successfully. You'll be notified once it's approved.
            </span>
          </div>
          <button
            onClick={() => setActionSuccess(null)}
            className="ml-auto text-green-400 hover:text-green-600"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Loan Applications */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm max-h-[60vh] overflow-scroll">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-sm font-bold text-gray-800">
            Your Float Request
          </h2>
        </div>
        <div className="divide-y divide-gray-50">
          {loanApplications.length === 0 ? (
            <div className="px-5 py-8 text-center text-gray-500 text-sm">
              No float request yet. Click &quot;Request for float&quot; to get
              started.
            </div>
          ) : (
            loanApplications.map((loan) => {
              const s = loan.status?.toLowerCase();
              const isSuccess = s === "approved" || s === "active" || s === "disbursed" || s === "completed";
              const isDeclined = s === "declined" || s === "rejected";
              const statusColor = isSuccess
                ? "bg-green-100 text-green-700"
                : isDeclined
                  ? "bg-red-100 text-red-700"
                  : "bg-yellow-100 text-yellow-700";
              return (
                <div
                  key={loan.id}
                  className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50"
                >
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      isSuccess ? "bg-green-100" : isDeclined ? "bg-red-100" : "bg-yellow-100"
                    }`}
                  >
                    {isSuccess ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : isDeclined ? (
                      <X className="w-5 h-5 text-red-600" />
                    ) : (
                      <Clock className="w-5 h-5 text-yellow-600" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-800">
                      Float Request — {loan.loan_application_id || loan.id}
                    </p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {loan.requested_term} months · Interest Rate:{" "}
                      {loan.LoanInterestRatePercent}%
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-gray-900">
                      ₦{loan.loan_amount.toLocaleString()}
                    </p>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor}`}
                    >
                      {loan.status}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Float Loan Application Modal */}
      {loanModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5 my-8">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  Float Request
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Quick loan for float management
                </p>
              </div>
              <button
                onClick={() => setLoanModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleLoanRequest} className="space-y-4">
              <div
                style={{
                  backgroundColor: "rgba(0, 79, 113, 0.1)",
                  borderColor: "rgba(0, 79, 113, 0.3)",
                }}
                className="border rounded-xl px-4 py-3"
              >
                <p className="text-sm font-medium" style={{ color: "#1F2937" }}>
                  <strong>Loan Purpose:</strong> Float Request (Fixed)
                </p>
                <p className="text-xs mt-1" style={{ color: "var(--tenant-primary-color,#004F71)" }}>
                  This application is specifically for float management purposes
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Loan Amount (₦) *
                </label>
                <input
                  type="number"
                  min="10000"
                  max="5000000"
                  step="1000"
                  required
                  value={loanForm.loan_amount}
                  onChange={(e) =>
                    setLoanForm({ ...loanForm, loan_amount: e.target.value })
                  }
                  placeholder="Enter loan amount"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Min: ₦10,000 • Max: ₦5,000,000
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Repayment Period (months) *
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  required
                  value={loanForm.requested_term}
                  onChange={(e) =>
                    setLoanForm({
                      ...loanForm,
                      requested_term: e.target.value,
                    })
                  }
                  placeholder="e.g., 12"
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)]"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Min: 1 month • Max: 60 months
                </p>
              </div>

              <div className="bg-gray-50 rounded-xl px-4 py-3">
                <p className="text-xs text-gray-600">
                  <strong>Note:</strong> Your application will be reviewed based
                  on your transaction history and account standing. You'll be
                  notified once approved.
                </p>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setLoanModal(false)}
                  className="flex-1 py-2.5 border border-gray-300 rounded-xl text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {loading ? (
                    "Submitting..."
                  ) : (
                    <>
                      <Zap className="w-4 h-4" />
                      Submit Application
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default FloatManagement;
