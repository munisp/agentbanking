import {
    CheckCircle,
    Clock,
    DollarSign,
    Download,
    Eye,
    FileText,
    Plus,
    RefreshCw,
    Search,
    TrendingUp,
    XCircle,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { authHeaders } from "../utils/api";

// Use Core Banking URL for loans
const CORE_BANKING_URL =
  import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const Loans = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [applications, setApplications] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showApplicationForm, setShowApplicationForm] = useState(false);
  const [selectedLoan, setSelectedLoan] = useState(null);

  // Fetch loan applications
  const fetchLoanApplications = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/applications/administration`,
        {
          headers: authHeaders(),
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setApplications(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Loan applications fetch error:", err);
      setError(err.message);
      setApplications([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLoanApplications();
  }, []);

  // Filter applications
  const filteredApplications = useMemo(() => {
    return applications.filter((app) => {
      const matchesSearch =
        !searchQuery ||
        app.loan_application_id
          ?.toLowerCase()
          .includes(searchQuery.toLowerCase()) ||
        app.applicant_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        app.loan_purpose?.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === "all" ||
        app.status?.toLowerCase() === statusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [applications, searchQuery, statusFilter]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = filteredApplications.length;
    const totalAmount = filteredApplications.reduce(
      (sum, app) => sum + (app.loan_amount || 0),
      0,
    );
    const pending = filteredApplications.filter(
      (app) =>
        app.status?.toLowerCase() === "pending" ||
        app.status?.toLowerCase() === "submitted",
    ).length;
    const approved = filteredApplications.filter(
      (app) =>
        app.status?.toLowerCase() === "approved" ||
        app.status?.toLowerCase() === "active",
    ).length;
    const rejected = filteredApplications.filter(
      (app) =>
        app.status?.toLowerCase() === "rejected" ||
        app.status?.toLowerCase() === "declined",
    ).length;

    return {
      total,
      totalAmount,
      pending,
      approved,
      rejected,
      approvalRate: total > 0 ? ((approved / total) * 100).toFixed(1) : "0.0",
    };
  }, [filteredApplications]);

  const getStatusColor = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "active")
      return "bg-green-100 text-green-800";
    if (statusLower === "rejected" || statusLower === "declined")
      return "bg-red-100 text-red-800";
    if (statusLower === "pending" || statusLower === "submitted")
      return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-800";
  };

  const getStatusIcon = (status) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "active")
      return <CheckCircle className="w-4 h-4" />;
    if (statusLower === "rejected" || statusLower === "declined")
      return <XCircle className="w-4 h-4" />;
    if (statusLower === "pending" || statusLower === "submitted")
      return <Clock className="w-4 h-4" />;
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="h-6 w-6" style={{ color: "var(--tenant-primary-color,#004F71)" }} />
            Loan Applications
          </h1>
          <p className="text-gray-600 mt-1">
            View and manage loan applications
          </p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#004F71)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors">
          <Download className="h-5 w-5 mr-2" />
          Export
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          Failed to load loan applications: {error}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Applications</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--tenant-primary-color,#004F71)" }}>
            {stats.total}
          </p>
          <p className="text-xs text-gray-500 mt-1">All time</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Amount</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            ₦{(stats.totalAmount / 1000000).toFixed(1)}M
          </p>
          <p className="text-xs text-gray-500 mt-1">Loan value</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Pending</p>
          <p className="text-2xl font-bold text-yellow-600 mt-1">
            {stats.pending}
          </p>
          <p className="text-xs text-gray-500 mt-1">Awaiting review</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Approval Rate</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {stats.approvalRate}%
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {stats.approved} approved
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by application ID, applicant, or purpose..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="active">Active</option>
        </select>
      </div>

      {/* Applications List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Application ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Applicant
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Loan Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Purpose
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Term
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Interest Rate
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredApplications.map((app) => (
                <tr key={app.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center">
                      <div
                        className="p-2 rounded-lg mr-3"
                        style={{ backgroundColor: "rgba(0, 79, 113, 0.1)" }}
                      >
                        <FileText
                          className="h-4 w-4"
                          style={{ color: "var(--tenant-primary-color,#004F71)" }}
                        />
                      </div>
                      <div>
                        <p className="font-mono text-sm font-medium text-gray-900">
                          {app.loan_application_id || app.id}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {app.applicant_id}
                  </td>
                  <td className="px-6 py-4">
                    <p className="font-semibold text-gray-900">
                      ₦{(app.loan_amount || 0).toLocaleString()}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {app.loan_purpose || "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {app.requested_term} months
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {app.LoanInterestRatePercent}%
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium gap-1 ${getStatusColor(
                        app.status,
                      )}`}
                    >
                      {getStatusIcon(app.status)}
                      {app.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => setSelectedLoan(app)}
                      className="hover:opacity-80"
                      style={{ color: "var(--tenant-primary-color,#004F71)" }}
                    >
                      <Eye className="h-5 w-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {filteredApplications.length === 0 && !isLoading && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {error
              ? "Could not load loan applications."
              : "No loan applications found matching your criteria."}
          </p>
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <RefreshCw
            className="h-8 w-8 animate-spin mx-auto mb-2"
            style={{ color: "var(--tenant-primary-color,#004F71)" }}
          />
          <p className="text-gray-500">Loading loan applications...</p>
        </div>
      )}
    </div>
  );
};

export default Loans;
