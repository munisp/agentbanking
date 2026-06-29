import {
    AlertCircle,
    CheckCircle,
    Clock,
    Download,
    Eye,
    EyeOff,
    Filter,
    Mail,
    MoreVertical,
    Phone,
    Plus,
    RefreshCw,
    Search,
    Shield,
    Users,
    XCircle,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { CreateCustomerPayload, CustomerRecord, api } from "../../utils/api";

// ─── normalise ───────────────────────────────────────────────────────────────
interface DisplayCustomer {
  id: string;
  keycloakId: string;
  name: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  status: string;
  kycStatus: string;
  createdAt: string;
}

function normalise(r: CustomerRecord): DisplayCustomer {
  const full = [r.first_name, r.last_name].filter(Boolean).join(" ") || r.email;
  return {
    id: r.id,
    keycloakId: r.keycloak_id,
    name: full,
    email: r.email,
    phone: r.phone_number ?? "",
    address: "",
    city: "",
    state: "",
    status: r.status ?? "active",
    kycStatus: r.kyc_verification_status ?? "pending",
    createdAt: r.created_at ? new Date(r.created_at).toLocaleDateString() : "—",
  };
}

// ─── colour helpers ───────────────────────────────────────────────────────────
const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-800",
  suspended: "bg-red-100 text-red-800",
  pending: "bg-yellow-100 text-yellow-800",
};

const kycColors: Record<string, string> = {
  verified: "bg-green-100 text-green-800",
  approved: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  not_verified: "bg-gray-100 text-gray-800",
  failed: "bg-red-100 text-red-800",
  failed_verification: "bg-red-100 text-red-800",
};

// ─── empty form ───────────────────────────────────────────────────────────────
const emptyForm = (): CreateCustomerPayload => ({
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  uin: "",
  password: "",
  address: "",
  city: "",
  state: "",
  postalCode: "",
});

// ─── component ────────────────────────────────────────────────────────────────
const UserManagement: React.FC = () => {
  const [customers, setCustomers] = useState<DisplayCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [kycFilter, setKycFilter] = useState("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState<CreateCustomerPayload>(emptyForm());
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [actionMenuId, setActionMenuId] = useState<string | null>(null);
  const actionRef = useRef<HTMLDivElement | null>(null);

  // close action menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (actionRef.current && !actionRef.current.contains(e.target as Node)) {
        setActionMenuId(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // ── fetch ──────────────────────────────────────────────────────────────────
  const fetchCustomers = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await api.getCustomers();
      const list: CustomerRecord[] = Array.isArray(data)
        ? data
        : ((
            data as {
              customers?: CustomerRecord[];
              users?: CustomerRecord[];
              data?: CustomerRecord[];
            }
          ).customers ??
          (
            data as {
              customers?: CustomerRecord[];
              users?: CustomerRecord[];
              data?: CustomerRecord[];
            }
          ).users ??
          (
            data as {
              customers?: CustomerRecord[];
              users?: CustomerRecord[];
              data?: CustomerRecord[];
            }
          ).data ??
          []);
      setCustomers(list.map(normalise));
    } catch (err: unknown) {
      setFetchError(
        err instanceof Error ? err.message : "Failed to load customers",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  // ── stats ──────────────────────────────────────────────────────────────────
  const stats = {
    total: customers.length,
    active: customers.filter((c) => c.status === "active").length,
    inactive: customers.filter((c) => c.status === "inactive").length,
    suspended: customers.filter((c) => c.status === "suspended").length,
  };

  // ── filtering ──────────────────────────────────────────────────────────────
  const filtered = customers.filter((c) => {
    const q = search.toLowerCase();
    const matchSearch =
      c.name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.phone.toLowerCase().includes(q);
    const matchStatus = statusFilter === "all" || c.status === statusFilter;
    const matchKyc = kycFilter === "all" || c.kycStatus === kycFilter;
    return matchSearch && matchStatus && matchKyc;
  });

  // ── form helpers ───────────────────────────────────────────────────────────
  const updateForm = (field: keyof CreateCustomerPayload, val: string) =>
    setFormData((prev) => ({ ...prev, [field]: val }));

  const handleCreate = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.createCustomer(formData);
      setShowCreateModal(false);
      setFormData(emptyForm());
      await fetchCustomers();
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to create customer",
      );
    } finally {
      setSubmitting(false);
    }
  };

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Customer Management (customer's portal)
          </h1>
          <p className="text-gray-500 mt-1">
            View and manage all registered customers
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchCustomers}
            disabled={loading}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm">
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" />
            Add Customer
          </button>
        </div>
      </div>

      {/* Fetch error */}
      {fetchError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {fetchError}
          <button
            onClick={fetchCustomers}
            className="ml-auto underline text-red-600 hover:text-red-800"
          >
            Retry
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          {
            label: "Total Customers",
            value: stats.total,
            icon: Users,
            color: "text-[var(--tenant-primary-color,#002082)]",
          },
          {
            label: "Active",
            value: stats.active,
            icon: CheckCircle,
            color: "text-green-500",
          },
          // {
          //   label: "Inactive",
          //   value: stats.inactive,
          //   icon: Clock,
          //   color: "text-gray-500",
          // },
          {
            label: "Suspended",
            value: stats.suspended,
            icon: XCircle,
            color: "text-red-500",
          },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl shadow p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">{s.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {loading ? "…" : s.value}
                </p>
              </div>
              <s.icon className={`w-10 h-10 ${s.color}`} />
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, email or phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Suspended</option>
          </select>
          <select
            value={kycFilter}
            onChange={(e) => setKycFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="all">All KYC</option>
            <option value="verified">Verified</option>
            <option value="pending">Pending</option>
            <option value="not_verified">Not Verified</option>
            <option value="failed_verification">Failed</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 gap-3 text-gray-400">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span>Loading customers…</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="max-h-[65vh] overflow-y-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {[
                      "Customer",
                      "Contact",
                      // "Location",
                      "KYC",
                      "Status",
                      "Joined",
                      "Actions",
                    ].map((col) => (
                      <th
                        key={col}
                        className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 max-h-[60vh] overflow-scroll">
                  {filtered.map((customer) => (
                    <tr
                      key={customer.id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      {/* Customer */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                            <span className="text-white font-semibold text-sm">
                              {customer.name
                                .split(" ")
                                .map((n) => n[0])
                                .join("")
                                .slice(0, 2)}
                            </span>
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-gray-900">
                              {customer.name}
                            </p>
                            <p className="text-xs text-gray-500">
                              {customer.email}
                            </p>
                          </div>
                        </div>
                      </td>
                      {/* Contact */}
                      <td className="px-4 py-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-1 text-xs text-gray-600">
                            <Mail className="w-3 h-3" />
                            {customer.email}
                          </div>
                          {customer.phone && (
                            <div className="flex items-center gap-1 text-xs text-gray-500">
                              <Phone className="w-3 h-3" />
                              {customer.phone}
                            </div>
                          )}
                        </div>
                      </td>
                      {/* Location */}
                      {/* <td className="px-4 py-3 text-sm text-gray-600">
                      {[customer.city, customer.state]
                        .filter(Boolean)
                        .join(", ") || "—"}
                    </td> */}
                      {/* KYC */}
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1 w-fit ${kycColors[customer.kycStatus] ?? "bg-gray-100 text-gray-700"}`}
                        >
                          <Shield className="w-3 h-3" />
                          {customer.kycStatus.replace(/_/g, " ")}
                        </span>
                      </td>
                      {/* Status */}
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[customer.status] ?? "bg-gray-100 text-gray-700"}`}
                        >
                          {customer.status}
                        </span>
                      </td>
                      {/* Joined */}
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {customer.createdAt}
                      </td>
                      {/* Actions */}
                      <td className="px-4 py-3">
                        <div
                          className="relative"
                          ref={actionMenuId === customer.id ? actionRef : null}
                        >
                          <button
                            onClick={() =>
                              setActionMenuId(
                                actionMenuId === customer.id
                                  ? null
                                  : customer.id,
                              )
                            }
                            className="p-1.5 hover:bg-gray-100 rounded-lg"
                          >
                            <MoreVertical className="w-4 h-4 text-gray-500" />
                          </button>
                          {actionMenuId === customer.id && (
                            <div className="absolute right-0 top-8 bg-white border border-gray-200 rounded-xl shadow-lg z-10 min-w-[160px] py-1">
                              <div className="px-4 py-2 text-xs text-gray-400 border-b">
                                ID: {customer.keycloakId.slice(0, 8)}…
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {filtered.length === 0 && !loading && (
              <div className="text-center py-16 text-gray-400">
                <Users className="w-12 h-12 mx-auto mb-2 opacity-40" />
                <p>No customers found</p>
              </div>
            )}
          </div>
        )}

        {/* Footer count */}
        {!loading && customers.length > 0 && (
          <div className="bg-white px-6 py-3 border-t border-gray-200 text-sm text-gray-500">
            Showing <span className="font-medium">{filtered.length}</span> of{" "}
            <span className="font-medium">{customers.length}</span> customers
          </div>
        )}
      </div>

      {/* Create Customer Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 space-y-5 my-6">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-gray-900">
                Add New Customer
              </h2>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setSubmitError(null);
                  setFormData(emptyForm());
                }}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ✕
              </button>
            </div>

            {submitError && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                {submitError}
              </div>
            )}

            <div className="space-y-4">
              {/* Name */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.firstName}
                    onChange={(e) => updateForm("firstName", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Last Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.lastName}
                    onChange={(e) => updateForm("lastName", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email Address <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) => updateForm("email", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                />
              </div>

              {/* Phone + UIN */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => updateForm("phone", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    UIN
                  </label>
                  <input
                    type="text"
                    value={formData.uin}
                    onChange={(e) => updateForm("uin", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={formData.password}
                    onChange={(e) => updateForm("password", e.target.value)}
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2.5 top-2.5 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              {/* Address */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Address
                </label>
                <input
                  type="text"
                  value={formData.address}
                  onChange={(e) => updateForm("address", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                />
              </div>

              {/* City + State */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => updateForm("city", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    State
                  </label>
                  <input
                    type="text"
                    value={formData.state}
                    onChange={(e) => updateForm("state", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
              </div>

              {/* Postal Code */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Postal Code
                </label>
                <input
                  type="text"
                  value={formData.postalCode}
                  onChange={(e) => updateForm("postalCode", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                />
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  setSubmitError(null);
                  setFormData(emptyForm());
                }}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={submitting || !formData.firstName || !formData.email}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-semibold hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {submitting && <RefreshCw className="w-4 h-4 animate-spin" />}
                {submitting ? "Creating…" : "Create Customer"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
