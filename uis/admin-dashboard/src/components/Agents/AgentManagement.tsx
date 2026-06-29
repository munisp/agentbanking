import {
    AlertCircle,
    CheckCircle,
    Clock,
    Download,
    Eye,
    EyeOff,
    Filter,
    MapPin,
    MoreVertical,
    Phone,
    Plus,
    RefreshCw,
    Search,
    Store,
    UserCheck,
    UserX,
    Users,
    XCircle,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import {
    AGENT_ROLES,
    AgentRecord,
    CreateAgentPayload,
    api,
} from "../../utils/api";

// ─── normalise ───────────────────────────────────────────────────────────────
interface DisplayAgent {
  id: string;
  keycloakId: string;
  name: string;
  email: string;
  phone: string;
  businessName: string;
  businessAddress: string;
  city: string;
  state: string;
  agentRole: string;
  status: string;
  kycStatus: string;
}

function normalise(r: AgentRecord): DisplayAgent {
  const full = [r.first_name, r.last_name].filter(Boolean).join(" ") || r.email;
  return {
    id: r.id,
    keycloakId: r.keycloak_id,
    name: full,
    email: r.email,
    phone: r.phone_number ?? "",
    businessName: r.business_name ?? "",
    businessAddress: r.business_address ?? "",
    city: r.city ?? "",
    state: r.state ?? "",
    agentRole: r.agent_role ?? "agent",
    status: r.status ?? "active",
    kycStatus: r.kyc_verification_status ?? "pending",
  };
}

// ─── colour maps ─────────────────────────────────────────────────────────────
const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  pending_approval: "bg-yellow-100 text-yellow-800",
  suspended: "bg-red-100 text-red-800",
  inactive: "bg-gray-100 text-gray-800",
};

const kycColors: Record<string, string> = {
  verified: "bg-green-100 text-green-800",
  approved: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  not_verified: "bg-gray-100 text-gray-800",
  failed_verification: "bg-red-100 text-red-800",
};

// ─── empty form ──────────────────────────────────────────────────────────────
const emptyForm = (): CreateAgentPayload => ({
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  uin: "",
  password: "",
  agentRole: "agent",
  businessName: "",
  businessAddress: "",
  city: "",
  state: "",
  postalCode: "",
  lga: "",
});

// ─── component ───────────────────────────────────────────────────────────────
const AgentManagement: React.FC = () => {
  const [agents, setAgents] = useState<DisplayAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState<CreateAgentPayload>(emptyForm());
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
  const fetchAgents = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await api.getAgents();
      const list: AgentRecord[] = data.agents ?? [];
      setAgents(list.map(normalise));
    } catch (err: unknown) {
      setFetchError(
        err instanceof Error ? err.message : "Failed to load agents",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  // ── stats ──────────────────────────────────────────────────────────────────
  const stats = {
    total: agents.length,
    active: agents.filter((a) => a.status === "active").length,
    pending: agents.filter((a) => a.status === "pending_approval").length,
    suspended: agents.filter((a) => a.status === "suspended").length,
  };

  // ── filtering ──────────────────────────────────────────────────────────────
  const filtered = agents.filter((a) => {
    const q = search.toLowerCase();
    const matchSearch =
      a.name.toLowerCase().includes(q) ||
      a.email.toLowerCase().includes(q) ||
      a.businessName.toLowerCase().includes(q);
    const matchStatus = statusFilter === "all" || a.status === statusFilter;
    const matchRole = roleFilter === "all" || a.agentRole === roleFilter;
    return matchSearch && matchStatus && matchRole;
  });

  // ── form helpers ───────────────────────────────────────────────────────────
  const updateForm = (field: keyof CreateAgentPayload, val: string) =>
    setFormData((prev) => ({ ...prev, [field]: val }));

  const handleCreate = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await api.createAgent(formData);
      setShowCreateModal(false);
      setFormData(emptyForm());
      await fetchAgents();
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : "Failed to create agent",
      );
    } finally {
      setSubmitting(false);
    }
  };

  // ── row actions ────────────────────────────────────────────────────────────
  const handleApprove = async (keycloakId: string) => {
    setActionMenuId(null);
    try {
      await api.approveAgent(keycloakId);
      await fetchAgents();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Approval failed");
    }
  };

  const handleSuspend = async (keycloakId: string) => {
    setActionMenuId(null);
    try {
      await api.suspendAgent(keycloakId);
      await fetchAgents();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Suspend failed");
    }
  };

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Agent Management</h1>
          <p className="text-gray-500 mt-1">
            Manage agents, approve applications and monitor activity
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchAgents}
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
            Add Agent
          </button>
        </div>
      </div>

      {/* Fetch error */}
      {fetchError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {fetchError}
          <button
            onClick={fetchAgents}
            className="ml-auto underline text-red-600 hover:text-red-800"
          >
            Retry
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Total Agents",
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
          {
            label: "Pending Approval",
            value: stats.pending,
            icon: Clock,
            color: "text-yellow-500",
          },
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
            placeholder="Search by name, email or business…"
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
            <option value="pending_approval">Pending Approval</option>
            <option value="suspended">Suspended</option>
            <option value="inactive">Inactive</option>
          </select>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="all">All Roles</option>
            {AGENT_ROLES.map((r) => (
              <option key={r} value={r}>
                {r.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 gap-3 text-gray-400">
            <RefreshCw className="w-6 h-6 animate-spin" />
            <span>Loading agents…</span>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {[
                    "Agent",
                    "Phone",
                    "Business",
                    "Location",
                    "Role",
                    "KYC",
                    "Status",
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
                {filtered.map((agent) => (
                  <tr
                    key={agent.id}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    {/* Agent */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 bg-[rgba(0,79,113,0.1)] rounded-full flex items-center justify-center">
                          <span className="text-[var(--tenant-primary-color,#002082)] font-semibold text-sm">
                            {agent.name
                              .split(" ")
                              .map((n) => n[0])
                              .join("")
                              .slice(0, 2)}
                          </span>
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">
                            {agent.name}
                          </p>
                          <p className="text-xs text-gray-500">{agent.email}</p>
                        </div>
                      </div>
                    </td>
                    {/* Phone */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-xs text-gray-600">
                        <Phone className="w-3 h-3" />
                        {agent.phone || "—"}
                      </div>
                    </td>
                    {/* Business */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm text-gray-700">
                        <Store className="w-3 h-3 text-gray-400" />
                        {agent.businessName || "—"}
                      </div>
                    </td>
                    {/* Location */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <MapPin className="w-3 h-3" />
                        {[agent.city, agent.state].filter(Boolean).join(", ") ||
                          "—"}
                      </div>
                    </td>
                    {/* Role */}
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-[rgba(0,79,113,0.1)] text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)] capitalize">
                        {agent.agentRole.replace(/_/g, " ")}
                      </span>
                    </td>
                    {/* KYC */}
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${kycColors[agent.kycStatus] ?? "bg-gray-100 text-gray-700"}`}
                      >
                        {agent.kycStatus.replace(/_/g, " ")}
                      </span>
                    </td>
                    {/* Status */}
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[agent.status] ?? "bg-gray-100 text-gray-700"}`}
                      >
                        {agent.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    {/* Actions */}
                    <td className="px-4 py-3">
                      <div
                        className="relative"
                        ref={actionMenuId === agent.id ? actionRef : null}
                      >
                        <button
                          onClick={() =>
                            setActionMenuId(
                              actionMenuId === agent.id ? null : agent.id,
                            )
                          }
                          className="p-1.5 hover:bg-gray-100 rounded-lg"
                        >
                          <MoreVertical className="w-4 h-4 text-gray-500" />
                        </button>
                        {actionMenuId === agent.id && (
                          <div className="absolute right-0 top-8 bg-white border border-gray-200 rounded-xl shadow-lg z-10 min-w-[160px] py-1">
                            {agent.status === "pending_approval" && (
                              <button
                                onClick={() => handleApprove(agent.keycloakId)}
                                className="w-full text-left px-4 py-2 text-sm text-green-600 hover:bg-green-50 flex items-center gap-2"
                              >
                                <UserCheck className="w-4 h-4" /> Approve
                              </button>
                            )}
                            {agent.status === "active" && (
                              <button
                                onClick={() => handleSuspend(agent.keycloakId)}
                                className="w-full text-left px-4 py-2 text-sm text-yellow-600 hover:bg-yellow-50 flex items-center gap-2"
                              >
                                <UserX className="w-4 h-4" /> Suspend
                              </button>
                            )}
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
                <p>No agents found</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Agent Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-6 space-y-5 my-6">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-gray-900">Add New Agent</h2>
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

              {/* Agent Role */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Agent Role <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.agentRole}
                  onChange={(e) => updateForm("agentRole", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                >
                  {AGENT_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r
                        .replace(/_/g, " ")
                        .replace(/\b\w/g, (c) => c.toUpperCase())}
                    </option>
                  ))}
                </select>
              </div>

              {/* Business */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Name
                </label>
                <input
                  type="text"
                  value={formData.businessName}
                  onChange={(e) => updateForm("businessName", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Address
                </label>
                <input
                  type="text"
                  value={formData.businessAddress}
                  onChange={(e) =>
                    updateForm("businessAddress", e.target.value)
                  }
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

              {/* Postal Code + LGA */}
              <div className="grid grid-cols-2 gap-3">
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
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    LGA
                  </label>
                  <input
                    type="text"
                    value={formData.lga}
                    onChange={(e) => updateForm("lga", e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
                  />
                </div>
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
                {submitting ? "Creating…" : "Create Agent"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentManagement;
