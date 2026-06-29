import {
    AlertCircle,
    AlertTriangle,
    ArrowUpRight,
    Award,
    BarChart3,
    CheckCircle,
    ChevronRight,
    Clock,
    Eye,
    EyeOff,
    MapPin,
    MoreVertical,
    Phone,
    Plus,
    RefreshCcw,
    Search,
    Shield,
    Store,
    TrendingUp,
    UserCheck,
    Users,
    XCircle,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { agentApi, inventoryApi, orchestratorApi } from "../utils/api";

// ─── constants ────────────────────────────────────────────────────────────────
const AGENT_ROLES = ["agent", "super_agent", "aggregator"];

const statusConfig = {
  active: {
    color: "bg-green-100 text-green-800",
    dot: "bg-green-500",
    label: "Active",
  },
  pending_approval: {
    color: "bg-yellow-100 text-yellow-800",
    dot: "bg-yellow-500",
    label: "Pending Approval",
  },
  invited: {
    color: "bg-blue-100 text-blue-800",
    dot: "bg-blue-400",
    label: "Invited",
  },
  suspended: {
    color: "bg-red-100 text-red-700",
    dot: "bg-red-500",
    label: "Suspended",
  },
  inactive: {
    color: "bg-gray-100 text-gray-600",
    dot: "bg-gray-400",
    label: "Inactive",
  },
};

const kycConfig = {
  verified: {
    color: "text-green-600 bg-green-50",
    icon: CheckCircle,
    label: "Verified",
  },
  approved: {
    color: "text-green-600 bg-green-50",
    icon: CheckCircle,
    label: "Verified",
  },
  pending: {
    color: "text-yellow-600 bg-yellow-50",
    icon: Clock,
    label: "Pending",
  },
  not_verified: {
    color: "text-gray-500 bg-gray-50",
    icon: AlertCircle,
    label: "Not Verified",
  },
  failed_verification: {
    color: "text-red-600 bg-red-50",
    icon: XCircle,
    label: "Failed",
  },
};

const emptyForm = () => ({
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
  // inviter fields are injected at submit time
});

// ─── helpers ─────────────────────────────────────────────────────────────────
const initials = (name = "") =>
  name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

const formatLocation = (city, state) =>
  [city, state].filter(Boolean).join(", ") || "—";

// ─── component ───────────────────────────────────────────────────────────────
const AgentHierarchy = () => {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [formData, setFormData] = useState(emptyForm());
  const [stores, setStores] = useState([]);
  const [storesLoading, setStoresLoading] = useState(false);
  const [storesError, setStoresError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [actionMenuId, setActionMenuId] = useState(null);
  const actionRef = useRef(null);

  // close action menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (actionRef.current && !actionRef.current.contains(e.target)) {
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
      const data = await agentApi.getInvitedAgents();
      setAgents(data.agents ?? []);
    } catch (err) {
      setFetchError(err?.message || "Failed to load agents");
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
    pending: agents.filter(
      (a) => a.status === "pending_approval" || a.status === "invited",
    ).length,
    suspended: agents.filter((a) => a.status === "suspended").length,
  };

  // ── filtering ──────────────────────────────────────────────────────────────
  const filtered = agents.filter((a) => {
    const name = [a.first_name, a.last_name].filter(Boolean).join(" ");
    const q = search.toLowerCase();
    const matchSearch =
      name.toLowerCase().includes(q) ||
      (a.email || "").toLowerCase().includes(q) ||
      (a.business_name || "").toLowerCase().includes(q) ||
      (a.city || "").toLowerCase().includes(q);
    const matchStatus = statusFilter === "all" || a.status === statusFilter;
    return matchSearch && matchStatus;
  });

  // ── form helpers ───────────────────────────────────────────────────────────
  const updateForm = (field, val) =>
    setFormData((prev) => ({ ...prev, [field]: val }));

  const fetchStores = async () => {
    const keycloakId = localStorage.getItem("keycloakId");
    if (!keycloakId) {
      setStores([]);
      return;
    }

    setStoresLoading(true);
    setStoresError(null);
    try {
      const data = await inventoryApi.getStores(keycloakId);
      const storeList = Array.isArray(data)
        ? data
        : data?.stores || data?.data || [];
      setStores(storeList);
    } catch (err) {
      setStores([]);
      setStoresError(err?.message || "Failed to load stores");
    } finally {
      setStoresLoading(false);
    }
  };

  const openInviteModal = () => {
    setFormData(emptyForm());
    setSubmitError(null);
    setSubmitSuccess(false);
    fetchStores();
    setShowInviteModal(true);
  };

  const closeInviteModal = () => {
    setShowInviteModal(false);
    setSubmitError(null);
    setSubmitSuccess(false);
    setFormData(emptyForm());
  };

  const handleInvite = async () => {
    setSubmitting(true);
    setSubmitError(null);
    const inviterKeycloakId = localStorage.getItem("keycloakId") || "";
    const inviterType = localStorage.getItem("agentRole") || "agent";
    try {
      await orchestratorApi.registerAgent({
        ...formData,
        invitedBy: inviterKeycloakId,
        inviterType,
      });
      setSubmitSuccess(true);
      await fetchAgents();
      setTimeout(closeInviteModal, 1500);
    } catch (err) {
      setSubmitError(
        err?.message || "Failed to invite agent. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Network</h1>
          <p className="text-sm text-gray-500 mt-0.5 whitespace-normal">
            Monitor and supervise your registered sub-agents (CBN-mandated)
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
          <button
            onClick={fetchAgents}
            disabled={loading}
            className="flex items-center justify-center gap-2 px-3 py-2 bg-white border border-gray-300 text-gray-700 rounded-xl text-sm hover:bg-gray-50 w-full sm:w-auto"
          >
            <RefreshCcw
              className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
          <button
            onClick={openInviteModal}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-medium hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors w-full sm:w-auto"
          >
            <Plus className="w-4 h-4" />
            Invite Agent
          </button>
        </div>
      </div>

      {/* Fetch error */}
      {fetchError && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {fetchError}
          <button onClick={fetchAgents} className="ml-auto underline">
            Retry
          </button>
        </div>
      )}

      {/* CBN Requirement Banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 flex items-start gap-3">
        <Shield className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-semibold text-amber-800">
            CBN Super-Agent Obligations
          </p>
          <p className="text-xs text-amber-700 mt-0.5">
            You are required to monitor agent activities, ensure KYC compliance,
            and report transaction volumes to CBN monthly (by the 10th of the
            following month).
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          {
            label: "Total Agents",
            value: stats.total,
            icon: Users,
            color: "bg-blue-50 text-blue-700",
            iconBg: "bg-blue-100",
          },
          {
            label: "Active Agents",
            value: stats.active,
            icon: UserCheck,
            color: "bg-green-50 text-green-700",
            iconBg: "bg-green-100",
          },
          {
            label: "Pending / Invited",
            value: stats.pending,
            icon: Clock,
            color: "bg-yellow-50 text-yellow-700",
            iconBg: "bg-yellow-100",
          },
          {
            label: "Suspended",
            value: stats.suspended,
            icon: XCircle,
            color: "bg-red-50 text-red-700",
            iconBg: "bg-red-100",
          },
        ].map((s) => (
          <div key={s.label} className={`rounded-xl p-4 ${s.color}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium opacity-75">{s.label}</p>
                <p className="text-xl font-bold mt-1">
                  {loading ? "…" : s.value}
                </p>
              </div>
              <div
                className={`w-10 h-10 ${s.iconBg} rounded-xl flex items-center justify-center`}
              >
                <s.icon className="w-5 h-5" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* CBN Min Requirement Progress */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-gray-800">
            CBN Minimum Requirement
          </h2>
          <span className="text-xs text-gray-500">Min. 50 agents required</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-gray-100 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all ${stats.total >= 50 ? "bg-green-500" : "bg-amber-400"}`}
              style={{ width: `${Math.min((stats.total / 50) * 100, 100)}%` }}
            />
          </div>
          <span
            className={`text-sm font-bold ${stats.total >= 50 ? "text-green-600" : "text-amber-600"}`}
          >
            {stats.total}/50
          </span>
        </div>
        {stats.total < 50 && !loading && (
          <p className="text-xs text-amber-600 mt-2 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            You need {50 - stats.total} more agents to meet CBN minimum
            requirements.
          </p>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, email, business or city…"
            className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-2 overflow-x-auto sm:overflow-visible sm:flex-wrap pb-1">
          {["all", "active", "pending_approval", "invited", "suspended"].map(
            (s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-2 rounded-xl text-xs font-medium capitalize transition-colors shrink-0 ${
                  statusFilter === s
                    ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                    : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {s === "all" ? "All" : statusConfig[s]?.label || s}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Agent Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20 gap-3 text-gray-400">
            <RefreshCcw className="w-6 h-6 animate-spin" />
            <span>Loading agents…</span>
          </div>
        ) : (
          <>
            <div className="lg:hidden divide-y divide-gray-100">
              {filtered.length === 0 ? (
                <div className="text-center py-12 text-gray-400 px-4">
                  <Users className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p>No agents found</p>
                </div>
              ) : (
                filtered.map((agent) => {
                  const name =
                    [agent.first_name, agent.last_name]
                      .filter(Boolean)
                      .join(" ") || agent.email;
                  const sc =
                    statusConfig[agent.status] || statusConfig.inactive;
                  const kc =
                    kycConfig[agent.kyc_verification_status] ||
                    kycConfig.pending;
                  const KycIcon = kc.icon;
                  return (
                    <div key={agent.id} className="p-4 space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
                            <span className="text-blue-700 font-bold text-xs">
                              {initials(name)}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-gray-800 truncate">
                              {name}
                            </p>
                            <p className="text-xs text-gray-400 truncate">
                              {agent.email}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => setSelectedAgent(agent)}
                          className="p-1.5 rounded-lg transition-colors"
                          style={{
                            backgroundColor: "rgba(0,79,113,0.1)",
                            color: "var(--tenant-primary-color,#002082)",
                          }}
                          title="View Details"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                        <div>
                          <p className="text-gray-500">Phone</p>
                          <p className="text-gray-700 truncate">
                            {agent.phone_number || "—"}
                          </p>
                        </div>
                        <div>
                          <p className="text-gray-500">Role</p>
                          <p className="text-gray-700 capitalize truncate">
                            {(agent.agent_role || "agent").replace(/_/g, " ")}
                          </p>
                        </div>
                        <div className="col-span-2">
                          <p className="text-gray-500">Business / Location</p>
                          <p className="text-gray-700 truncate">
                            {agent.business_name || "—"} •{" "}
                            {formatLocation(agent.city, agent.state)}
                          </p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${kc.color}`}
                        >
                          <KycIcon className="w-3 h-3" />
                          {kc.label}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold ${sc.color}`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${sc.dot}`}
                          />
                          {sc.label}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            <div className="hidden lg:block overflow-x-auto max-h-[60vh] overflow-scroll">
              <table className="min-w-full divide-y divide-gray-100">
                <thead className="bg-gray-50">
                  <tr>
                    {[
                      "Agent",
                      "Phone",
                      "Business / Location",
                      "Role",
                      "Invited By",
                      "Inviter Type",
                      "KYC",
                      "Status",
                      "Actions",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filtered.length === 0 ? (
                    <tr>
                      <td
                        colSpan={9}
                        className="text-center py-16 text-gray-400"
                      >
                        <Users className="w-12 h-12 mx-auto mb-2 opacity-40" />
                        <p>No agents found</p>
                      </td>
                    </tr>
                  ) : (
                    filtered.map((agent) => {
                      const name =
                        [agent.first_name, agent.last_name]
                          .filter(Boolean)
                          .join(" ") || agent.email;
                      const sc =
                        statusConfig[agent.status] || statusConfig.inactive;
                      const kc =
                        kycConfig[agent.kyc_verification_status] ||
                        kycConfig.pending;
                      const KycIcon = kc.icon;
                      return (
                        <tr
                          key={agent.id}
                          className="hover:bg-gray-50 transition-colors"
                        >
                          {/* Agent */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center shrink-0">
                                <span className="text-blue-700 font-bold text-xs">
                                  {initials(name)}
                                </span>
                              </div>
                              <div>
                                <p className="text-sm font-semibold text-gray-800">
                                  {name}
                                </p>
                                <p className="text-xs text-gray-400">
                                  {agent.email}
                                </p>
                              </div>
                            </div>
                          </td>
                          {/* Phone */}
                          <td className="px-4 py-3">
                            <span className="text-xs text-gray-600 flex items-center gap-1">
                              <Phone className="w-3 h-3 text-gray-400" />
                              {agent.phone_number || "—"}
                            </span>
                          </td>
                          {/* Business / Location */}
                          <td className="px-4 py-3">
                            <p className="text-sm text-gray-700 flex items-center gap-1">
                              <Store className="w-3 h-3 text-gray-400" />
                              {agent.business_name || "—"}
                            </p>
                            <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                              <MapPin className="w-3 h-3" />
                              {formatLocation(agent.city, agent.state)}
                            </p>
                          </td>
                          {/* Role */}
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 capitalize">
                              {(agent.agent_role || "agent").replace(/_/g, " ")}
                            </span>
                          </td>
                          {/* Invited By */}
                          <td className="px-4 py-3">
                            <span className="text-xs text-gray-600 font-mono">
                              {agent.invited_by
                                ? agent.invited_by.slice(0, 8) + "..."
                                : "—"}
                            </span>
                          </td>
                          {/* Inviter Type */}
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 capitalize">
                              {agent.inviter_type || "—"}
                            </span>
                          </td>
                          {/* KYC */}
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${kc.color}`}
                            >
                              <KycIcon className="w-3 h-3" />
                              {kc.label}
                            </span>
                          </td>
                          {/* Status */}
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold ${sc.color}`}
                            >
                              <span
                                className={`w-1.5 h-1.5 rounded-full ${sc.dot}`}
                              />
                              {sc.label}
                            </span>
                          </td>
                          {/* Actions */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => setSelectedAgent(agent)}
                                className="p-1.5 rounded-lg transition-colors"
                                style={{
                                  backgroundColor: "rgba(0,79,113,0.1)",
                                  color: "var(--tenant-primary-color,#002082)",
                                }}
                                onMouseEnter={(e) =>
                                  (e.currentTarget.style.backgroundColor =
                                    "rgba(0,79,113,0.2)")
                                }
                                onMouseLeave={(e) =>
                                  (e.currentTarget.style.backgroundColor =
                                    "rgba(0,79,113,0.1)")
                                }
                                title="View Details"
                              >
                                <ChevronRight className="w-4 h-4" />
                              </button>
                              <div
                                className="relative"
                                ref={
                                  actionMenuId === agent.id ? actionRef : null
                                }
                              >
                                <button
                                  onClick={() =>
                                    setActionMenuId(
                                      actionMenuId === agent.id
                                        ? null
                                        : agent.id,
                                    )
                                  }
                                  className="p-1.5 bg-gray-50 text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
                                >
                                  <MoreVertical className="w-4 h-4" />
                                </button>
                                {actionMenuId === agent.id && (
                                  <div className="absolute right-0 mt-1 w-44 bg-white rounded-xl shadow-lg border border-gray-100 py-1 z-20">
                                    <button
                                      onClick={() => {
                                        setActionMenuId(null);
                                        setSelectedAgent(agent);
                                      }}
                                      className="w-full px-4 py-2 text-sm text-left hover:bg-gray-50 flex items-center gap-2"
                                    >
                                      <BarChart3 className="w-4 h-4 text-gray-400" />
                                      View Details
                                    </button>
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {/* Agent Detail Drawer */}
      {selectedAgent && (
        <div
          className="fixed inset-0 bg-black/40 z-50 flex justify-end"
          onClick={() => setSelectedAgent(null)}
        >
          <div
            className="w-full max-w-md bg-white h-full overflow-y-auto shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-5 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-blue-700 font-bold">
                    {initials(
                      [selectedAgent.first_name, selectedAgent.last_name]
                        .filter(Boolean)
                        .join(" ") || selectedAgent.email,
                    )}
                  </span>
                </div>
                <div>
                  <h2 className="font-bold text-gray-900">
                    {[selectedAgent.first_name, selectedAgent.last_name]
                      .filter(Boolean)
                      .join(" ") || selectedAgent.email}
                  </h2>
                  <p className="text-xs text-gray-500">{selectedAgent.email}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedAgent(null)}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ✕
              </button>
            </div>

            <div className="p-5 space-y-5">
              {/* Status badges */}
              <div className="flex gap-2 flex-wrap">
                {(() => {
                  const sc =
                    statusConfig[selectedAgent.status] || statusConfig.inactive;
                  return (
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${sc.color}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                      {sc.label}
                    </span>
                  );
                })()}
                {(() => {
                  const kc =
                    kycConfig[selectedAgent.kyc_verification_status] ||
                    kycConfig.pending;
                  return (
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${kc.color}`}
                    >
                      KYC: {kc.label}
                    </span>
                  );
                })()}
                <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 capitalize">
                  {(selectedAgent.agent_role || "agent").replace(/_/g, " ")}
                </span>
              </div>

              {/* Contact */}
              <div className="bg-gray-50 rounded-xl p-4 space-y-2">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide">
                  Contact & Location
                </h3>
                {[
                  { label: "Phone", value: selectedAgent.phone_number || "—" },
                  { label: "Email", value: selectedAgent.email },
                  {
                    label: "Business",
                    value: selectedAgent.business_name || "—",
                  },
                  {
                    label: "Address",
                    value: selectedAgent.business_address || "—",
                  },
                  {
                    label: "Location",
                    value: formatLocation(
                      selectedAgent.city,
                      selectedAgent.state,
                    ),
                  },
                  { label: "LGA", value: selectedAgent.lga || "—" },
                  {
                    label: "Postal Code",
                    value: selectedAgent.postal_code || "—",
                  },
                ].map((row) => (
                  <div key={row.label} className="flex justify-between text-sm">
                    <span className="text-gray-500">{row.label}</span>
                    <span className="font-medium text-gray-800 text-right max-w-xs">
                      {row.value}
                    </span>
                  </div>
                ))}
              </div>

              {/* Inviter Information */}
              <div className="bg-gray-50 rounded-xl p-4 space-y-2">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide">
                  Inviter Information
                </h3>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Invited By</span>
                  <span className="font-mono text-xs text-gray-800">
                    {selectedAgent.invited_by || "—"}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Inviter Type</span>
                  <span className="capitalize font-medium text-gray-800">
                    {selectedAgent.inviter_type || "—"}
                  </span>
                </div>
              </div>

              {/* Onboarding */}
              <div className="bg-gray-50 rounded-xl p-4 space-y-2">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wide">
                  Onboarding Status
                </h3>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Onboarding</span>
                  <span className="capitalize font-medium text-gray-800">
                    {(selectedAgent.onboarding_status || "—").replace(
                      /_/g,
                      " ",
                    )}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">KYC</span>
                  <span className="capitalize font-medium text-gray-800">
                    {(selectedAgent.kyc_verification_status || "—").replace(
                      /_/g,
                      " ",
                    )}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setSelectedAgent(null)}
                className="w-full py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 flex items-center justify-center gap-1.5"
              >
                <ArrowUpRight className="w-4 h-4" /> Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invite Agent Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-4 sm:p-6 space-y-5 my-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-bold text-gray-900">
                  Invite Agent
                </h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  The new agent will be registered and pending approval.
                </p>
              </div>
              <button
                onClick={closeInviteModal}
                className="text-gray-400 hover:text-gray-600 text-xl leading-none"
              >
                ✕
              </button>
            </div>

            {submitError && (
              <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {submitError}
              </div>
            )}

            {submitSuccess && (
              <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 rounded-lg px-3 py-2 text-sm">
                <CheckCircle className="w-4 h-4 shrink-0" />
                Agent invited successfully!
              </div>
            )}

            <div className="space-y-4">
              {/* Name */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    First Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.firstName}
                    onChange={(e) => updateForm("firstName", e.target.value)}
                    placeholder="Chidi"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                    placeholder="Okafor"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  placeholder="agent@email.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Phone + UIN */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => updateForm("phone", e.target.value)}
                    placeholder="0801 234 5678"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    NIN
                  </label>
                  <input
                    type="text"
                    value={formData.uin}
                    onChange={(e) => updateForm("uin", e.target.value)}
                    placeholder="NIN"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Temporary Password <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={formData.password}
                    onChange={(e) => updateForm("password", e.target.value)}
                    placeholder="Set a temporary password"
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  Agent Role
                </label>
                <select
                  value={formData.agentRole}
                  onChange={(e) => updateForm("agentRole", e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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

              {/* Business Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Name
                </label>
                <select
                  value={formData.businessName}
                  onChange={(e) => {
                    const selectedStore = stores.find((store) => {
                      const storeName = store.name || store.store_name || "";
                      return storeName === e.target.value;
                    });

                    setFormData((prev) => ({
                      ...prev,
                      businessName: e.target.value,
                      businessAddress:
                        selectedStore?.address ||
                        selectedStore?.location ||
                        prev.businessAddress,
                    }));
                  }}
                  disabled={storesLoading}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">
                    {storesLoading ? "Loading stores..." : "Select store"}
                  </option>
                  {stores.map((store, index) => {
                    const storeName = store.name || store.store_name || "";
                    const storeId = store.id || `${storeName}-${index}`;
                    return (
                      <option key={storeId} value={storeName}>
                        {storeName}
                      </option>
                    );
                  })}
                </select>
                {!storesLoading && stores.length === 0 && (
                  <p className="text-xs text-gray-500 mt-1">
                    No stores found. Create one in Business Management.
                  </p>
                )}
                {storesError && (
                  <p className="text-xs text-red-600 mt-1">{storesError}</p>
                )}
              </div>

              {/* Business Address */}
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
                  placeholder="12 Market Street"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* City + State */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    City
                  </label>
                  <input
                    type="text"
                    value={formData.city}
                    onChange={(e) => updateForm("city", e.target.value)}
                    placeholder="Lagos"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                    placeholder="Lagos"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Postal Code + LGA */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Postal Code
                  </label>
                  <input
                    type="text"
                    value={formData.postalCode}
                    onChange={(e) => updateForm("postalCode", e.target.value)}
                    placeholder="100001"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                    placeholder="Surulere"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={closeInviteModal}
                disabled={submitting}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleInvite}
                disabled={
                  submitting ||
                  !formData.firstName ||
                  !formData.email ||
                  !formData.password
                }
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {submitting && <RefreshCcw className="w-4 h-4 animate-spin" />}
                {submitting ? "Inviting…" : "Invite Agent"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentHierarchy;
