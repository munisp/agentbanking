import {
    AlertCircle,
    CheckCircle2,
    Clock,
    DollarSign,
    FileText,
    Loader2,
    Send,
    Shield,
} from "lucide-react";
import React, { useState } from "react";
import { authHeaders } from "../utils/api";

// Remittance Banking URL
const REMITTANCE_BANKING_URL =
  import.meta.env.VITE_REMITTANCE_BANKING_URL || "https://54remit.upi.dev";

const RemittanceVerification = () => {
  const [verificationForm, setVerificationForm] = useState({
    transaction_reference: "",
    disburse_code: "",
  });

  const [transactionDetails, setTransactionDetails] = useState(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isDisbursing, setIsDisbursing] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [verificationStatus, setVerificationStatus] = useState(null); // 'verified', 'disbursed', 'failed'

  // Verify transaction
  const handleVerifyTransaction = async (e) => {
    e.preventDefault();
    setIsVerifying(true);
    setErrorMessage("");
    setSuccessMessage("");
    setTransactionDetails(null);
    setVerificationStatus(null);

    try {
      const response = await fetch(
        `${REMITTANCE_BANKING_URL}/remittance/api/v1/transactions/verify`,
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({
            transaction_reference: verificationForm.transaction_reference,
            disburse_code: verificationForm.disburse_code,
          }),
        },
      );

      const data = await response.json();

      if (response.ok && data.success) {
        setTransactionDetails(data.data);
        setVerificationStatus("verified");
        setSuccessMessage(data.message || "Transaction verified successfully!");
      } else {
        setErrorMessage(
          data.message ||
            "Failed to verify transaction. Please check your details.",
        );
        setVerificationStatus("failed");
      }
    } catch (error) {
      console.error("Verification error:", error);
      setErrorMessage(
        "An error occurred while verifying the transaction. Please try again.",
      );
      setVerificationStatus("failed");
    } finally {
      setIsVerifying(false);
    }
  };

  // Mark as disbursed
  const handleMarkAsDisbursed = async () => {
    if (!transactionDetails) return;

    setIsDisbursing(true);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const response = await fetch(
        `${REMITTANCE_BANKING_URL}/remittance/api/v1/transactions/${transactionDetails.transaction_id}/disburse`,
        {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({
            transaction_reference: verificationForm.transaction_reference,
            disburse_code: verificationForm.disburse_code,
            agent_id: localStorage.getItem("keycloakId"),
          }),
        },
      );

      const data = await response.json();

      if (response.ok && data.success) {
        setVerificationStatus("disbursed");
        setSuccessMessage(
          data.message || "Transaction marked as disbursed successfully!",
        );
        setTransactionDetails({
          ...transactionDetails,
          status: "disbursed",
          disbursed_at: new Date().toISOString(),
        });
      } else {
        setErrorMessage(
          data.message || "Failed to mark transaction as disbursed.",
        );
      }
    } catch (error) {
      console.error("Disburse error:", error);
      setErrorMessage(
        "An error occurred while marking the transaction as disbursed. Please try again.",
      );
    } finally {
      setIsDisbursing(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setVerificationForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleReset = () => {
    setVerificationForm({
      transaction_reference: "",
      disburse_code: "",
    });
    setTransactionDetails(null);
    setVerificationStatus(null);
    setSuccessMessage("");
    setErrorMessage("");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">
          Remittance Transaction Verification
        </h1>
        <p className="text-gray-600 mt-1">
          Verify and disburse remittance transactions to customers
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Left Column - Verification Form */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 sm:p-6">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                <Shield className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Verify Transaction
                </h2>
                <p className="text-sm text-gray-500">
                  Enter transaction details
                </p>
              </div>
            </div>

            <form onSubmit={handleVerifyTransaction} className="space-y-4">
              {/* Transaction Reference */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Transaction Reference *
                </label>
                <div className="relative">
                  <FileText className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    name="transaction_reference"
                    value={verificationForm.transaction_reference}
                    onChange={handleInputChange}
                    placeholder="TXN-REF-XXXXXX"
                    required
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              {/* Disburse Code */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Disburse Code *
                </label>
                <div className="relative">
                  <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="text"
                    name="disburse_code"
                    value={verificationForm.disburse_code}
                    onChange={handleInputChange}
                    placeholder="6-digit code"
                    required
                    maxLength={6}
                    className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
                  />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  6-digit code provided to the recipient
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={
                    isVerifying ||
                    !verificationForm.transaction_reference ||
                    !verificationForm.disburse_code
                  }
                  className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isVerifying ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    <>
                      <Shield className="w-4 h-4" />
                      Verify
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2.5 border border-gray-300 text-gray-700 rounded-xl font-medium hover:bg-gray-50 transition-colors"
                >
                  Reset
                </button>
              </div>
            </form>

            {/* Status Messages */}
            {errorMessage && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{errorMessage}</p>
              </div>
            )}

            {successMessage && verificationStatus === "verified" && (
              <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-xl flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
                <p className="text-sm text-green-700">{successMessage}</p>
              </div>
            )}

            {successMessage && verificationStatus === "disbursed" && (
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-2">
                <CheckCircle2 className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                <p className="text-sm text-blue-700">{successMessage}</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Transaction Details */}
        <div className="lg:col-span-2">
          {!transactionDetails && !verificationStatus && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                <FileText className="w-8 h-8 text-gray-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                No Transaction Verified
              </h3>
              <p className="text-gray-600 max-w-md">
                Enter the transaction reference and disburse code to verify and
                view transaction details
              </p>
            </div>
          )}

          {verificationStatus === "failed" && (
            <div className="bg-white rounded-2xl border border-red-200 shadow-sm p-12 flex flex-col items-center justify-center text-center">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
                <AlertCircle className="w-8 h-8 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Verification Failed
              </h3>
              <p className="text-gray-600 max-w-md">
                The transaction could not be verified. Please check your details
                and try again.
              </p>
            </div>
          )}

          {transactionDetails && verificationStatus === "verified" && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              {/* Header */}
              <div className="bg-linear-to-r from-blue-600 to-blue-700 p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                      <CheckCircle2 className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">
                        Transaction Verified
                      </h2>
                      <p className="text-blue-100 text-sm">Ready to disburse</p>
                    </div>
                  </div>
                  <div className="px-3 py-1 bg-green-500 rounded-lg">
                    <span className="text-white text-sm font-medium">
                      Verified
                    </span>
                  </div>
                </div>
              </div>

              {/* Transaction Details */}
              <div className="p-6 space-y-6">
                {/* Amount */}
                <div className="bg-gray-50 rounded-xl p-4">
                  <p className="text-sm text-gray-600 mb-1">Amount</p>
                  <div className="flex items-baseline gap-2">
                    <DollarSign className="w-6 h-6 text-gray-700" />
                    <p className="text-3xl font-bold text-gray-900">
                      {transactionDetails.currency || "NGN"}{" "}
                      {parseFloat(
                        transactionDetails.amount || 0,
                      ).toLocaleString()}
                    </p>
                  </div>
                </div>

                {/* Sender & Recipient Info */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="border border-gray-200 rounded-xl p-4">
                    <p className="text-xs text-gray-500 uppercase font-medium mb-2">
                      Sender
                    </p>
                    <p className="font-semibold text-gray-900">
                      {transactionDetails.sender_name || "N/A"}
                    </p>
                    <p className="text-sm text-gray-600">
                      {transactionDetails.sender_account ||
                        transactionDetails.sender_id ||
                        ""}
                    </p>
                  </div>
                  <div className="border border-gray-200 rounded-xl p-4">
                    <p className="text-xs text-gray-500 uppercase font-medium mb-2">
                      Recipient
                    </p>
                    <p className="font-semibold text-gray-900">
                      {transactionDetails.recipient_name || "N/A"}
                    </p>
                    <p className="text-sm text-gray-600">
                      {transactionDetails.recipient_account ||
                        transactionDetails.recipient_id ||
                        ""}
                    </p>
                  </div>
                </div>

                {/* Other Details */}
                <div className="space-y-3">
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-600">Transaction ID</span>
                    <span className="font-mono text-sm text-gray-900">
                      {transactionDetails.transaction_id ||
                        transactionDetails.id}
                    </span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-600">Reference</span>
                    <span className="font-mono text-sm text-gray-900">
                      {transactionDetails.transaction_reference ||
                        verificationForm.transaction_reference}
                    </span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-600">Status</span>
                    <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-lg text-xs font-medium">
                      {transactionDetails.status || "Pending Disbursement"}
                    </span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-600">Date</span>
                    <span className="text-sm text-gray-900">
                      {transactionDetails.created_at
                        ? new Date(
                            transactionDetails.created_at,
                          ).toLocaleString()
                        : "N/A"}
                    </span>
                  </div>
                  {transactionDetails.description && (
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-600">Description</span>
                      <span className="text-sm text-gray-900 text-right max-w-xs">
                        {transactionDetails.description}
                      </span>
                    </div>
                  )}
                </div>

                {/* Disburse Button */}
                <button
                  onClick={handleMarkAsDisbursed}
                  disabled={isDisbursing}
                  className="w-full px-6 py-3 bg-green-600 text-white rounded-xl font-semibold hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isDisbursing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <Send className="w-5 h-5" />
                      Mark as Disbursed
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {transactionDetails && verificationStatus === "disbursed" && (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
              {/* Success Header */}
              <div className="bg-linear-to-r from-green-600 to-green-700 p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center">
                      <CheckCircle2 className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-white">
                        Transaction Disbursed
                      </h2>
                      <p className="text-green-100 text-sm">
                        Successfully completed
                      </p>
                    </div>
                  </div>
                  <div className="px-3 py-1 bg-white/20 rounded-lg">
                    <span className="text-white text-sm font-medium">
                      Complete
                    </span>
                  </div>
                </div>
              </div>

              {/* Transaction Summary */}
              <div className="p-6">
                <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6">
                  <div className="flex items-start gap-3">
                    <CheckCircle2 className="w-6 h-6 text-green-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-green-900 mb-1">
                        Disbursement Successful
                      </p>
                      <p className="text-sm text-green-700">
                        The transaction has been marked as disbursed and the
                        funds have been released to the recipient.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Summary Details */}
                <div className="space-y-3">
                  <div className="flex justify-between py-2">
                    <span className="text-gray-600">Amount Disbursed</span>
                    <span className="font-semibold text-gray-900">
                      {transactionDetails.currency || "NGN"}{" "}
                      {parseFloat(
                        transactionDetails.amount || 0,
                      ).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-gray-600">Recipient</span>
                    <span className="font-medium text-gray-900">
                      {transactionDetails.recipient_name || "N/A"}
                    </span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-gray-600">Transaction Reference</span>
                    <span className="font-mono text-sm text-gray-900">
                      {verificationForm.transaction_reference}
                    </span>
                  </div>
                  <div className="flex justify-between py-2">
                    <span className="text-gray-600">Disbursed At</span>
                    <span className="text-sm text-gray-900">
                      {transactionDetails.disbursed_at
                        ? new Date(
                            transactionDetails.disbursed_at,
                          ).toLocaleString()
                        : new Date().toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex gap-3 mt-6">
                  <button
                    onClick={handleReset}
                    className="flex-1 px-4 py-2.5 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors"
                  >
                    Verify Another Transaction
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
          <div className="flex items-start gap-3">
            <Clock className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-blue-900 mb-1">
                Quick Verification
              </h3>
              <p className="text-sm text-blue-700">
                Verify transactions in seconds using the transaction reference
                and disburse code
              </p>
            </div>
          </div>
        </div>

        <div className="bg-green-50 rounded-xl p-4 border border-green-100">
          <div className="flex items-start gap-3">
            <Shield className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-green-900 mb-1">
                Secure Process
              </h3>
              <p className="text-sm text-green-700">
                All transactions require verification codes for added security
              </p>
            </div>
          </div>
        </div>

        <div className="bg-purple-50 rounded-xl p-4 border border-purple-100">
          <div className="flex items-start gap-3">
            <Send className="w-5 h-5 text-purple-600 shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-purple-900 mb-1">
                Instant Disbursement
              </h3>
              <p className="text-sm text-purple-700">
                Funds are released immediately upon successful verification
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RemittanceVerification;
