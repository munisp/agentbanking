import {
    Activity,
    AlertCircle,
    CheckCircle,
    Clock,
    Link2,
    Loader2,
    MonitorSmartphone,
    Package,
    RefreshCw,
    Store,
    WifiOff,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { posTerminalApi } from "../utils/api";

// Map pos-terminal-management status values to visual config
const statusConfig = {
  Active: {
    color: "bg-green-100 text-green-800",
    dot: "bg-green-500",
    label: "Online",
  },
  Inactive: {
    color: "bg-gray-100 text-gray-600",
    dot: "bg-gray-400",
    label: "Offline",
  },
  Maintenance: {
    color: "bg-red-100 text-red-700",
    dot: "bg-red-500",
    label: "Faulty",
  },
};

// Group assigned terminals by their assigned_to value (business name)
function buildBusinesses(assigned) {
  const map = {};
  for (const t of assigned) {
    const name = t.assigned_to || "Unknown Business";
    if (!map[name]) {
      map[name] = { id: name, name, location: t.location || "", terminals: [] };
    }
    map[name].terminals.push(t);
  }
  return Object.values(map);
}

const POSManagement = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [terminals, setTerminals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedBusiness, setSelectedBusiness] = useState("all");
  const [assignModal, setAssignModal] = useState(null);
  const [assignBizName, setAssignBizName] = useState("");
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignSuccess, setAssignSuccess] = useState(null);

  const loadTerminals = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await posTerminalApi.getTerminals();
      setTerminals(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to load terminals");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTerminals();
  }, []);

  const handleAssign = async () => {
    if (!assignBizName.trim() || !assignModal) return;
    const tId = assignModal.ID || assignModal.id;
    setAssignLoading(true);
    try {
      await posTerminalApi.updateTerminal(tId, {
        assigned_to: assignBizName.trim(),
      });
      setAssignSuccess({
        terminal: assignModal,
        bizName: assignBizName.trim(),
      });
      setAssignModal(null);
      setAssignBizName("");
      await loadTerminals();
      setTimeout(() => setAssignSuccess(null), 4000);
    } catch (err) {
      alert(`Failed to assign terminal: ${err.message}`);
    } finally {
      setAssignLoading(false);
    }
  };

  const unassigned = terminals.filter((t) => !t.assigned_to);
  const assigned = terminals.filter((t) => !!t.assigned_to);
  const businesses = buildBusinesses(assigned);
  const existingBizNames = [
    ...new Set(assigned.map((t) => t.assigned_to).filter(Boolean)),
  ];

  const allActive = terminals.filter(
    (t) => t.status === "Active" && t.is_online,
  ).length;
  const allFaulty = terminals.filter(
    (t) => t.status === "Maintenance" || t.status === "Inactive",
  ).length;
  const totalTxns = terminals.reduce(
    (sum, t) => sum + (t.transaction_count || 0),
    0,
  );

  const displayedBusinesses =
    selectedBusiness === "all"
      ? businesses
      : businesses.filter((b) => b.id === selectedBusiness);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading terminals…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="w-10 h-10 text-red-400" />
        <p className="text-sm text-gray-600">{error}</p>
        <button
          onClick={loadTerminals}
          className="px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm hover:bg-[var(--tenant-primary-color,#003F5A)]"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">POS Terminals</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage your POS terminals across all your businesses
          </p>
        </div>
        <button
          onClick={loadTerminals}
          className="flex items-center gap-2 px-3 py-2 bg-white border border-gray-200 text-gray-600 rounded-xl text-sm hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {[
          {
            label: "Total Terminals",
            value: terminals.length,
            icon: MonitorSmartphone,
            color: "text-[var(--tenant-primary-color,#002082)]",
            bgColor: "rgba(0,79,113,0.05)",
            iconBg: "rgba(0,79,113,0.1)",
          },
          {
            label: "Total Transactions",
            value: totalTxns,
            icon: Activity,
            color: "text-[var(--tenant-primary-color,#002082)]",
            bgColor: "rgba(0,79,113,0.05)",
            iconBg: "rgba(0,79,113,0.1)",
          },
          {
            label: "Active Terminals",
            value: allActive,
            icon: CheckCircle,
            color: "bg-emerald-50 text-emerald-600",
            iconBg: "bg-emerald-100",
          },
          {
            label: "Needs Attention",
            value: allFaulty,
            icon: AlertCircle,
            color: "bg-red-50 text-red-600",
            iconBg: "bg-red-100",
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className={`rounded-xl p-4 ${stat.bgColor ? "" : stat.color} border border-white`}
            style={
              stat.bgColor
                ? {
                    backgroundColor: stat.bgColor,
                    color: stat.color,
                  }
                : undefined
            }
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium opacity-80">{stat.label}</p>
                <p className="text-xl font-bold mt-1">{stat.value}</p>
              </div>
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center ${stat.iconBg && !stat.bgColor ? stat.iconBg : ""}`}
                style={
                  stat.bgColor ? { backgroundColor: stat.iconBg } : undefined
                }
              >
                <stat.icon className="w-5 h-5" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Assign success banner */}
      {assignSuccess && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl px-4 py-3">
          <CheckCircle className="w-5 h-5 text-green-600 shrink-0" />
          <p className="text-sm text-green-800 font-medium">
            Terminal{" "}
            <strong>
              {assignSuccess.terminal.TerminalModel ||
                assignSuccess.terminal.model}{" "}
              ({assignSuccess.terminal.ID || assignSuccess.terminal.id})
            </strong>{" "}
            assigned to <strong>{assignSuccess.bizName}</strong>
          </p>
        </div>
      )}

      {/* Unassigned Terminals */}
      {unassigned.length > 0 && (
        <div className="bg-white rounded-2xl border border-amber-200 shadow-sm overflow-hidden">
          <div className="px-5 py-4 bg-amber-50 border-b border-amber-100 flex items-center gap-3">
            <div className="w-9 h-9 bg-amber-100 rounded-xl flex items-center justify-center">
              <Package className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-900">
                Unassigned Terminals
              </h2>
              <p className="text-xs text-amber-700">
                Delivered but not yet assigned to a business
              </p>
            </div>
            <span className="ml-auto text-xs font-semibold bg-amber-100 text-amber-700 px-2.5 py-1 rounded-full">
              {unassigned.length} pending
            </span>
          </div>
          <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {unassigned.map((terminal) => {
              const tId = terminal.ID || terminal.id;
              return (
                <div
                  key={tId}
                  className="border border-amber-100 rounded-xl p-4 space-y-3 bg-amber-50/40"
                >
                  <div className="flex items-start gap-2">
                    <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
                      <MonitorSmartphone className="w-4 h-4 text-gray-600" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {tId}
                      </p>
                      <p className="text-xs text-gray-400">
                        {terminal.SerialNumber || terminal.serial_number}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500">
                    {terminal.TerminalModel || terminal.model}
                  </p>
                  <div className="text-xs text-gray-400">
                    <p>
                      Location: {terminal.Location || terminal.location || "—"}
                    </p>
                    <p>
                      Added:{" "}
                      {terminal.CreatedAt || terminal.created_at
                        ? new Date(
                            terminal.CreatedAt || terminal.created_at,
                          ).toLocaleDateString()
                        : "—"}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setAssignModal(terminal);
                      setAssignBizName("");
                    }}
                    className="w-full py-2 bg-[var(--tenant-primary-color,#002082)] text-white text-xs font-semibold rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors flex items-center justify-center gap-1.5"
                  >
                    <Link2 className="w-3.5 h-3.5" />
                    Assign to Business
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Business Filter */}
      {businesses.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedBusiness("all")}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              selectedBusiness === "all"
                ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            All Businesses
          </button>
          {businesses.map((biz) => (
            <button
              key={biz.id}
              onClick={() => setSelectedBusiness(biz.id)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                selectedBusiness === biz.id
                  ? "bg-[var(--tenant-primary-color,#002082)] text-white"
                  : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {biz.name}
            </button>
          ))}
        </div>
      )}

      {/* Business Sections */}
      {displayedBusinesses.length > 0 ? (
        <div className="space-y-6">
          {displayedBusinesses.map((business) => (
            <div
              key={business.id}
              className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
            >
              {/* Business Header */}
              <div className="px-5 py-4 bg-gray-50 border-b border-gray-100 flex items-center gap-3">
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: "rgba(0,79,113,0.1)" }}
                >
                  <Store className="w-5 h-5" style={{ color: "var(--tenant-primary-color,#002082)" }} />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-gray-900">
                    {business.name}
                  </h2>
                  <p className="text-xs text-gray-500">{business.location}</p>
                </div>
                <span
                  className="ml-auto text-xs font-medium px-2 py-1 rounded-full"
                  style={{
                    backgroundColor: "rgba(0,79,113,0.1)",
                    color: "var(--tenant-primary-color,#002082)",
                  }}
                >
                  {business.terminals.length} terminal
                  {business.terminals.length !== 1 ? "s" : ""}
                </span>
              </div>

              {/* Terminals Grid */}
              <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {business.terminals.map((terminal) => {
                  const tId = terminal.ID || terminal.id;
                  const tStatus =
                    terminal.Status || terminal.status || "Inactive";
                  const sc = statusConfig[tStatus] || statusConfig.Inactive;
                  const battery =
                    terminal.BatteryLevel ?? terminal.battery_level ?? 0;
                  const txnCount =
                    terminal.TransactionCount ||
                    terminal.transaction_count ||
                    0;
                  const lastTxn =
                    terminal.LastTransactionTime ||
                    terminal.last_transaction_time;

                  return (
                    <div
                      key={tId}
                      onClick={() => navigate(`/pos/${tId}`)}
                      className="border border-gray-100 rounded-xl p-4 space-y-3 hover:shadow-sm transition-all cursor-pointer"
                      style={{ "--hover-border-color": "rgba(0,79,113,0.3)" }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.borderColor =
                          "rgba(0,79,113,0.3)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.borderColor = "")
                      }
                    >
                      {/* Terminal header */}
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center">
                            <MonitorSmartphone className="w-4 h-4 text-gray-600" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-gray-900">
                              {tId}
                            </p>
                            <p className="text-xs text-gray-400">
                              {terminal.SerialNumber || terminal.serial_number}
                            </p>
                          </div>
                        </div>
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${sc.color}`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${sc.dot}`}
                          />
                          {sc.label}
                        </span>
                      </div>

                      {/* Model */}
                      <p className="text-xs text-gray-500">
                        {terminal.TerminalModel || terminal.model}
                      </p>

                      {/* Stats */}
                      {tStatus === "Active" && (
                        <div className="grid grid-cols-2 gap-2 text-center">
                          <div
                            className="rounded-lg p-2"
                            style={{ backgroundColor: "rgba(0,79,113,0.05)" }}
                          >
                            <p className="text-xs text-gray-500">Total Txns</p>
                            <p
                              className="text-sm font-bold"
                              style={{ color: "var(--tenant-primary-color,#002082)" }}
                            >
                              {txnCount}
                            </p>
                          </div>
                          <div className="bg-green-50 rounded-lg p-2">
                            <p className="text-xs text-gray-500">Battery</p>
                            <p className="text-sm font-bold text-green-700">
                              {battery > 0 ? `${Math.round(battery)}%` : "—"}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Last Active */}
                      <div className="flex items-center justify-between text-xs text-gray-400">
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {lastTxn
                            ? `Last: ${new Date(lastTxn).toLocaleDateString()}`
                            : "No transactions"}
                        </div>
                        {tStatus === "Active" && battery > 0 && (
                          <span
                            className={`font-medium ${battery < 20 ? "text-red-500" : "text-gray-500"}`}
                          >
                            🔋 {Math.round(battery)}%
                          </span>
                        )}
                      </div>

                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/pos/${tId}`);
                          }}
                          className="flex-1 py-1.5 text-xs rounded-lg font-medium transition-colors"
                          style={{
                            backgroundColor: "rgba(0,79,113,0.05)",
                            color: "var(--tenant-primary-color,#002082)",
                          }}
                          onMouseEnter={(e) =>
                            (e.currentTarget.style.backgroundColor =
                              "rgba(0,79,113,0.1)")
                          }
                          onMouseLeave={(e) =>
                            (e.currentTarget.style.backgroundColor =
                              "rgba(0,79,113,0.05)")
                          }
                        >
                          View Details
                        </button>
                        {tStatus !== "Active" && (
                          <button
                            onClick={(e) => e.stopPropagation()}
                            className="flex-1 py-1.5 text-xs bg-red-50 text-red-600 rounded-lg font-medium hover:bg-red-100 transition-colors flex items-center justify-center gap-1"
                          >
                            <AlertCircle className="w-3 h-3" />
                            Report Issue
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            loadTerminals();
                          }}
                          className="p-1.5 bg-gray-50 text-gray-500 rounded-lg hover:bg-gray-100 transition-colors"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        assigned.length === 0 && (
          <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center">
            <MonitorSmartphone className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 text-sm">No terminals assigned yet.</p>
            <p className="text-gray-400 text-xs mt-1">
              Request a POS terminal and assign it to a business to get started.
            </p>
          </div>
        )
      )}

      {/* Assign Terminal Modal */}
      {assignModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-gray-900">
                Assign Terminal
              </h2>
              <button
                onClick={() => setAssignModal(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>
            <div className="bg-gray-50 rounded-xl px-4 py-3 flex items-center gap-3">
              <MonitorSmartphone className="w-5 h-5 text-gray-500" />
              <div>
                <p className="text-sm font-semibold text-gray-800">
                  {assignModal.TerminalModel || assignModal.model}
                </p>
                <p className="text-xs text-gray-400">
                  {assignModal.ID || assignModal.id} ·{" "}
                  {assignModal.SerialNumber || assignModal.serial_number}
                </p>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Business name
              </label>
              <input
                type="text"
                list="biz-datalist"
                placeholder="Select existing or type new business name…"
                value={assignBizName}
                onChange={(e) => setAssignBizName(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {existingBizNames.length > 0 && (
                <datalist id="biz-datalist">
                  {existingBizNames.map((name) => (
                    <option key={name} value={name} />
                  ))}
                </datalist>
              )}
              <p className="text-xs text-gray-400 mt-1">
                Pick an existing business or type a new name
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setAssignModal(null)}
                className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAssign}
                disabled={assignLoading || !assignBizName.trim()}
                className="flex-1 py-2.5 bg-[var(--tenant-primary-color,#002082)] text-white rounded-xl text-sm font-semibold hover:bg-[var(--tenant-primary-color,#003F5A)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {assignLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Link2 className="w-4 h-4" />
                )}{" "}
                Assign Terminal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default POSManagement;
