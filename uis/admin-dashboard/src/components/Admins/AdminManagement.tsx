import {
  AlertCircle,
  CheckCircle,
  Download,
  Eye,
  EyeOff,
  Filter,
  Loader2,
  MoreVertical,
  Phone,
  Plus,
  RefreshCw,
  Search,
  Shield,
  ShieldOff,
  Trash2,
  UserCheck,
  Users,
  XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";

import { useTenantBranding } from "../../contexts/TenantBrandingContext";
import {
  ACCESS_LEVEL_OPTIONS,
  AdminRecord,
  TENANT_ROLES,
  api,
} from "../../utils/api";

// -------------------------------------------------------------------
// Role colour helper
// -------------------------------------------------------------------
const roleColor = (role: string) => {
  const map: Record<string, string> = {
    super_admin: "bg-purple-100 text-purple-800",
    branch_manager: "bg-[rgba(0,79,113,0.1)] text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]",
    operations_manager: "bg-teal-100 text-teal-800",
    risk_manager: "bg-red-100 text-red-800",
    compliance_officer: "bg-orange-100 text-orange-800",
    internal_auditor: "bg-yellow-100 text-yellow-800",
    it_admin: "bg-cyan-100 text-cyan-800",
    support_agent: "bg-gray-100 text-gray-700",
  };
  return map[role] ?? "bg-gray-100 text-gray-700";
};

// -------------------------------------------------------------------
// Normalise backend shape → display shape
// -------------------------------------------------------------------
interface DisplayAdmin {
  id: string;
  name: string;
  email: string;
  phone: string;
  accessLevel: string;
  status: "active" | "inactive";
  joinDate: string;
  raw: AdminRecord;
}

function normalise(a: AdminRecord): DisplayAdmin {
  return {
    id: String(a.id),
    name:
      a.first_name && a.last_name ? `${a.first_name} ${a.last_name}` : a.email,
    email: a.email,
    phone: a.phone,
    accessLevel: a.access_level ?? "support_agent",
    status: a.is_suspended ? "inactive" : "active",
    joinDate: a.created_at ? a.created_at.split("T")[0] : "—",
    raw: a,
  };
}

const emptyForm = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  uin: "",
  password: "",
  accessLevel: "7",
};

// -------------------------------------------------------------------
// Component
// -------------------------------------------------------------------
const AdminManagement: React.FC = () => {
  const { name: tenantName } = useTenantBranding();
  const [admins, setAdmins] = useState<DisplayAdmin[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState("");

  const [search, setSearch] = useState("");
  const [filterRole, setFilterRole] = useState("all");

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [createError, setCreateError] = useState("");
  const [createSuccess, setCreateSuccess] = useState("");

  const [actionMenuId, setActionMenuId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // ── Fetch ──────────────────────────────────────────────────────
  const fetchAdmins = async () => {
    setLoading(true);
    setFetchError("");
    try {
      const data = await api.getAdmins();
      setAdmins((data.admins ?? []).map(normalise));
    } catch (e: unknown) {
      setFetchError((e as Error).message ?? "Failed to load admins.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    fetchAdmins();
  }, []);

  // ── Create ────────────────────────────────────────────────────
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setCreateError("");
    setCreateSuccess("");
    try {
      await api.createAdmin({
        firstName: form.firstName,
        lastName: form.lastName,
        email: form.email,
        phone: form.phone,
        uin: form.uin,
        password: form.password || undefined,
        accessLevel: form.accessLevel,
      });
      setCreateSuccess(
        `Admin ${form.firstName} ${form.lastName} created. They will receive an email to complete KYC.`,
      );
      setForm(emptyForm);
      fetchAdmins();
      setTimeout(() => {
        setShowCreate(false);
        setCreateSuccess("");
      }, 3500);
    } catch (e: unknown) {
      setCreateError((e as Error).message ?? "Failed to create admin.");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Suspend / Unsuspend ───────────────────────────────────────
  const handleToggleSuspend = async (admin: DisplayAdmin) => {
    setActionLoading(admin.id);
    try {
      if (admin.status === "active") await api.suspendAdmin(admin.id);
      else await api.unsuspendAdmin(admin.id);
      fetchAdmins();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setActionLoading(null);
      setActionMenuId(null);
    }
  };

  // ── Filtered view ─────────────────────────────────────────────
  const filtered = admins.filter((a) => {
    const matchSearch =
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.email.toLowerCase().includes(search.toLowerCase());
    const matchRole = filterRole === "all" || a.accessLevel === filterRole;
    return matchSearch && matchRole;
  });

  const stats = {
    total: admins.length,
    active: admins.filter((a) => a.status === "active").length,
    superAdmins: admins.filter((a) => a.accessLevel === "super_admin").length,
    inactive: admins.filter((a) => a.status === "inactive").length,
  };

  // ── Render ────────────────────────────────────────────────────
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Management</h1>
          <p className="text-gray-500 mt-1">
            Manage {tenantName} administrators and their access levels
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchAdmins}
            disabled={loading}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />{" "}
            Refresh
          </button>
          <button className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm">
            <Download className="w-4 h-4" /> Export
          </button>
          <button
            onClick={() => {
              setShowCreate(true);
              setCreateError("");
              setCreateSuccess("");
            }}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2 text-sm"
          >
            <Plus className="w-4 h-4" /> Add Admin
          </button>
        </div>
      </div>

      {/* Fetch error */}
      {fetchError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3 text-red-700 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          {fetchError}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Total Admins",
            value: stats.total,
            icon: Shield,
            color: "text-purple-500",
          },
          {
            label: "Active",
            value: stats.active,
            icon: CheckCircle,
            color: "text-green-500",
          },
          {
            label: "Super Admins",
            value: stats.superAdmins,
            icon: UserCheck,
            color: "text-purple-600",
          },
          {
            label: "Inactive",
            value: stats.inactive,
            icon: XCircle,
            color: "text-gray-500",
          },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl shadow p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">{s.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {s.value}
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
            placeholder="Search by name or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="all">All Roles</option>
            {TENANT_ROLES.map((r) => (
              <option key={r} value={r}>
                {r.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {loading && admins.length === 0 ? (
          <div className="flex items-center justify-center py-24 text-gray-400 gap-3">
            <Loader2 className="w-6 h-6 animate-spin" /> Loading admins…
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {[
                    "Admin",
                    "Contact",
                    "Access Level",
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
              <tbody className="divide-y divide-gray-100">
                {filtered.map((admin) => (
                  <tr
                    key={admin.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 bg-purple-100 rounded-full flex items-center justify-center">
                          <span className="text-purple-700 font-semibold text-sm">
                            {admin.name
                              .split(" ")
                              .map((n) => n[0])
                              .join("")
                              .slice(0, 2)
                              .toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {admin.name}
                          </p>
                          <p className="text-xs text-gray-500">{admin.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <Phone className="w-3 h-3" /> {admin.phone}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${roleColor(admin.accessLevel)}`}
                      >
                        {admin.accessLevel.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${admin.status === "active" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-700"}`}
                      >
                        {admin.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {admin.joinDate}
                    </td>
                    <td className="px-4 py-3">
                      <div className="relative">
                        <button
                          onClick={() =>
                            setActionMenuId(
                              actionMenuId === admin.id ? null : admin.id,
                            )
                          }
                          className="p-1.5 hover:bg-gray-100 rounded-lg"
                        >
                          {actionLoading === admin.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-gray-500" />
                          ) : (
                            <MoreVertical className="w-4 h-4 text-gray-500" />
                          )}
                        </button>
                        {actionMenuId === admin.id && (
                          <div className="absolute right-0 top-8 bg-white border border-gray-200 rounded-xl shadow-lg z-10 min-w-[160px] py-1">
                            {admin.status === "active" ? (
                              <button
                                onClick={() => handleToggleSuspend(admin)}
                                className="w-full text-left px-4 py-2 text-sm text-yellow-600 hover:bg-yellow-50 flex items-center gap-2"
                              >
                                <ShieldOff className="w-4 h-4" /> Suspend
                              </button>
                            ) : (
                              <button
                                onClick={() => handleToggleSuspend(admin)}
                                className="w-full text-left px-4 py-2 text-sm text-green-600 hover:bg-green-50 flex items-center gap-2"
                              >
                                <Shield className="w-4 h-4" /> Reactivate
                              </button>
                            )}
                            <button className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2">
                              <Trash2 className="w-4 h-4" /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && !loading && (
              <div className="text-center py-16 text-gray-400">
                <Users className="w-12 h-12 mx-auto mb-2 opacity-40" />
                <p>
                  {admins.length === 0
                    ? "No admins yet. Create the first one above."
                    : "No admins match your filters."}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Create Admin Modal ─────────────────────────────────── */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  Create New Admin
                </h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Create new {tenantName} admin account via Keycloak + Temporal
                  workflow.
                </p>
              </div>
              <button
                onClick={() => setShowCreate(false)}
                className="text-gray-400 hover:text-gray-600 text-xl"
              >
                ✕
              </button>
            </div>

            {createSuccess && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-3 flex items-start gap-2 text-green-700 text-sm">
                <CheckCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />{" "}
                {createSuccess}
              </div>
            )}
            {createError && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-3 flex items-start gap-2 text-red-700 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />{" "}
                {createError}
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name *
                  </label>
                  <input
                    required
                    value={form.firstName}
                    onChange={(e) =>
                      setForm({ ...form, firstName: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Last Name *
                  </label>
                  <input
                    required
                    value={form.lastName}
                    onChange={(e) =>
                      setForm({ ...form, lastName: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email *
                </label>
                <input
                  required
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone *
                  </label>
                  <input
                    required
                    value={form.phone}
                    onChange={(e) =>
                      setForm({ ...form, phone: e.target.value })
                    }
                    placeholder="+234 800 000 0000"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    NIN / UIN *
                  </label>
                  <input
                    required
                    value={form.uin}
                    onChange={(e) => setForm({ ...form, uin: e.target.value })}
                    placeholder="11-digit NIN"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Temporary Password{" "}
                  <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={form.password}
                    onChange={(e) =>
                      setForm({ ...form, password: e.target.value })
                    }
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? (
                      <EyeOff className="w-4 h-4" />
                    ) : (
                      <Eye className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Access Level *
                </label>
                <select
                  value={form.accessLevel}
                  onChange={(e) =>
                    setForm({ ...form, accessLevel: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  {ACCESS_LEVEL_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.value} — {opt.label} ({opt.desc})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-400 mt-1">
                  Maps to Permify roles automatically. Level 7 = Super Admin
                  (platform:super + bank:admin).
                </p>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-2.5 bg-purple-600 text-white rounded-xl text-sm font-semibold hover:bg-purple-700 flex items-center justify-center gap-2 disabled:opacity-60"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {submitting ? "Creating…" : "Create Admin"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminManagement;
