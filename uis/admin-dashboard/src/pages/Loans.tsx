import {
    CheckCircle,
    Clock,
    Download,
    Eye,
    FileText,
    RefreshCw,
    Search,
    TrendingUp,
    XCircle,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import LoanActions from "../components/Loans/LoanActions";
import { getTenantHeadersFromStorage } from "../services/tenant/getTenantHeadersFromStorage";

const CORE_BANKING_URL =
  import.meta.env.VITE_API_URL || "https://54agent.upi.dev";

interface LoanApplication {
  id: string;
  loan_application_id: string;
  status: string;
  applicant_id: string;
  loan_amount: number;
  loan_purpose: string;
  LoanInterestRatePercent: number;
  requested_term: number;
}

const Loans: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [applications, setApplications] = useState<LoanApplication[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null); // loan_application_id being processed
  // Approve/Reject/Disburse handlers
  const handleApprove = async (loan_application_id: string) => {
    setActionLoading(loan_application_id);
    setError(null);
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();
      const res = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/applications/${loan_application_id}/approve`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            ...tenantHeaders,
          },
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      await fetchLoanApplications();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDisburse = async (loan_application_id: string) => {
    setActionLoading(loan_application_id + "-disburse");
    setError(null);
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();
      const res = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/${loan_application_id}/disburse`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            ...tenantHeaders,
          },
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      await fetchLoanApplications();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (loan_application_id: string) => {
    setActionLoading(loan_application_id);
    setError(null);
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();
      const res = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/applications/${loan_application_id}/decline`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            ...tenantHeaders,
          },
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      await fetchLoanApplications();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const fetchLoanApplications = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("auth_token");
      const tenantHeaders = getTenantHeadersFromStorage();
      const res = await fetch(
        `${CORE_BANKING_URL}/loan/api/v1/loans/applications/administration`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            ...tenantHeaders,
          },
        },
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setApplications(Array.isArray(data) ? data : []);
    } catch (err: any) {
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

  const filteredApplications = useMemo(() => {
    return applications.filter((app) => {
      // Only show Float Loan applications
      const isFloatLoan = app.loan_purpose === "Float Loan";

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

      return isFloatLoan && matchesSearch && matchesStatus;
    });
  }, [applications, searchQuery, statusFilter]);

  const stats = useMemo(() => {
    const total = filteredApplications.length;
    const totalAmount = filteredApplications.reduce(
      (sum, app) => sum + (app.loan_amount || 0),
      0,
    );
    const pending = filteredApplications.filter(
      (app) => app.status?.toLowerCase() === "pending",
    ).length;
    const approved = filteredApplications.filter(
      (app) => app.status?.toLowerCase() === "approved",
    ).length;

    return {
      total,
      totalAmount,
      pending,
      approved,
      approvalRate: total > 0 ? ((approved / total) * 100).toFixed(1) : "0.0",
    };
  }, [filteredApplications]);

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "active")
      return "bg-green-100 text-green-800";
    if (statusLower === "rejected" || statusLower === "declined")
      return "bg-red-100 text-red-800";
    if (statusLower === "pending") return "bg-yellow-100 text-yellow-800";
    return "bg-gray-100 text-gray-800";
  };

  const getStatusIcon = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === "approved" || statusLower === "active")
      return <CheckCircle className="w-4 h-4" />;
    if (statusLower === "rejected" || statusLower === "declined")
      return <XCircle className="w-4 h-4" />;
    if (statusLower === "pending") return <Clock className="w-4 h-4" />;
    return null;
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp className="h-6 w-6" style={{ color: "var(--tenant-primary-color,#002082)" }} />
            Float Loans Applications
          </h1>
          <p className="text-gray-600 mt-1">
            View and manage float loan applications
          </p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)]">
          <Download className="h-5 w-5 mr-2" />
          Export
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Applications</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--tenant-primary-color,#002082)" }}>
            {stats.total}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Amount</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            ₦{(stats.totalAmount / 1000000).toFixed(1)}M
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Pending</p>
          <p className="text-2xl font-bold text-yellow-600 mt-1">
            {stats.pending}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Approval Rate</p>
          <p className="text-2xl font-bold text-green-600 mt-1">
            {stats.approvalRate}%
          </p>
        </div>
      </div>

      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search loan applications..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-3 border border-gray-300 rounded-lg"
        >
          <option value="all">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="text-center py-12">
            <RefreshCw className="h-8 w-8 text-blue-400 animate-spin mx-auto mb-2" />
            <p className="text-gray-500">Loading...</p>
          </div>
        ) : filteredApplications.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No loan applications found</p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Application ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Applicant
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Purpose
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Term
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
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
                          style={{ backgroundColor: "rgba(0,79,113,0.1)" }}
                        >
                          <FileText
                            className="h-4 w-4"
                            style={{ color: "var(--tenant-primary-color,#002082)" }}
                          />
                        </div>
                        <p className="font-mono text-sm">
                          {app.loan_application_id || app.id}
                        </p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm">{app.applicant_id}</td>
                    <td className="px-6 py-4 font-semibold">
                      ₦{(app.loan_amount || 0).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      {app.loan_purpose || "-"}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      {app.requested_term} months
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
                      <LoanActions
                        status={app.status}
                        onApprove={() =>
                          handleApprove(app.loan_application_id || app.id)
                        }
                        onReject={() =>
                          handleReject(app.loan_application_id || app.id)
                        }
                        onDisburse={
                          app.status.toLowerCase() === "approved"
                            ? () =>
                                handleDisburse(
                                  app.loan_application_id || app.id,
                                )
                            : undefined
                        }
                        disabled={!!actionLoading}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Loans;
