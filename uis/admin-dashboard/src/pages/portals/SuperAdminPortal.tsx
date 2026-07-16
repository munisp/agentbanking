import { ShieldAlert, Settings, Eye, UserX, ToggleLeft, ToggleRight, Zap } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface Tenant {
  id: string;
  name: string;
  status: "active" | "suspended";
  plan: "Starter" | "Growth" | "Enterprise";
  agentsCount: number;
  mrr: number;
  lastActivity: string;
}

interface GlobalConfig {
  maintenanceMode: boolean;
  registrationOpen: boolean;
  kycRequired: boolean;
}

const MOCK_TENANTS: Tenant[] = [
  { id: "t-001", name: "QuickCash NG", status: "active", plan: "Enterprise", agentsCount: 4820, mrr: 12400000, lastActivity: "2 mins ago" },
  { id: "t-002", name: "PayEasy Africa", status: "active", plan: "Growth", agentsCount: 1230, mrr: 3200000, lastActivity: "1 hr ago" },
  { id: "t-003", name: "NairaLink", status: "suspended", plan: "Starter", agentsCount: 210, mrr: 0, lastActivity: "3 days ago" },
  { id: "t-004", name: "CashPoint Ltd", status: "active", plan: "Growth", agentsCount: 890, mrr: 2100000, lastActivity: "25 mins ago" },
  { id: "t-005", name: "Zonal Finance", status: "active", plan: "Starter", agentsCount: 145, mrr: 480000, lastActivity: "4 hrs ago" },
];

const MOCK_CONFIG: GlobalConfig = { maintenanceMode: false, registrationOpen: true, kycRequired: true };

const PLAN_STYLE: Record<string, string> = {
  Starter: "bg-gray-100 text-gray-600",
  Growth: "bg-blue-100 text-blue-700",
  Enterprise: "bg-purple-100 text-purple-700",
};

const SuperAdminPortal: React.FC = () => {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [config, setConfig] = useState<GlobalConfig>(MOCK_CONFIG);
  const [loading, setLoading] = useState(false);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/portals/api/v1/superadmin/overview`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setTenants(d.tenants ?? MOCK_TENANTS);
        setConfig(d.config ?? MOCK_CONFIG);
      } else { setTenants(MOCK_TENANTS); }
    } catch { setTenants(MOCK_TENANTS); }
    finally { setLoading(false); }
  };

  const toggleConfig = async (key: keyof GlobalConfig) => {
    const updated = { ...config, [key]: !config[key] };
    setConfig(updated);
    try {
      await fetch(`${CORE_URL}/portals/api/v1/superadmin/config`, {
        method: "PATCH",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: updated[key] }),
      });
    } catch { setConfig(config); }
  };

  const tenantAction = async (tenantId: string, action: "suspend" | "activate" | "impersonate") => {
    if (action === "impersonate") { alert(`Impersonating tenant ${tenantId}`); return; }
    try {
      await fetch(`${CORE_URL}/portals/api/v1/superadmin/tenants/${tenantId}/${action}`, {
        method: "POST", headers: getTenantHeadersFromStorage(),
      });
      fetchAll();
    } catch { alert("Action failed (demo mode)"); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <ShieldAlert className="w-7 h-7 text-red-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Super Admin Portal</h1>
          <p className="text-gray-500 text-sm mt-0.5">Platform-wide tenant management and system controls</p>
        </div>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Tenant Management</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                <th className="pb-2 font-medium">Tenant</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Plan</th>
                <th className="pb-2 font-medium">Agents</th>
                <th className="pb-2 font-medium">MRR</th>
                <th className="pb-2 font-medium">Last Active</th>
                <th className="pb-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {tenants.map(t => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="py-3">
                    <p className="font-medium text-gray-800">{t.name}</p>
                    <p className="text-xs text-gray-400">{t.id}</p>
                  </td>
                  <td className="py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${t.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600"}`}>{t.status}</span>
                  </td>
                  <td className="py-3"><span className={`text-xs px-2 py-0.5 rounded-full ${PLAN_STYLE[t.plan]}`}>{t.plan}</span></td>
                  <td className="py-3 text-gray-700">{t.agentsCount.toLocaleString()}</td>
                  <td className="py-3 text-gray-700">{t.mrr > 0 ? `₦${(t.mrr / 1e6).toFixed(1)}M` : "—"}</td>
                  <td className="py-3 text-gray-400 text-xs">{t.lastActivity}</td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <button onClick={() => tenantAction(t.id, t.status === "active" ? "suspend" : "activate")}
                        className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${t.status === "active" ? "bg-red-50 text-red-600 hover:bg-red-100" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}>
                        <UserX className="w-3 h-3" /> {t.status === "active" ? "Suspend" : "Activate"}
                      </button>
                      <button onClick={() => alert(`Viewing config for ${t.name}`)} className="text-xs px-2 py-1 bg-gray-50 text-gray-600 hover:bg-gray-100 rounded flex items-center gap-1">
                        <Settings className="w-3 h-3" /> Config
                      </button>
                      <button onClick={() => tenantAction(t.id, "impersonate")} className="text-xs px-2 py-1 bg-amber-50 text-amber-700 hover:bg-amber-100 rounded flex items-center gap-1">
                        <Eye className="w-3 h-3" /> Impersonate
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><ToggleRight className="w-4 h-4 text-indigo-500" /> Global System Config</h2>
          <div className="space-y-4">
            {(Object.keys(config) as (keyof GlobalConfig)[]).map(key => (
              <div key={key} className="flex items-center justify-between p-3 border border-gray-100 rounded-xl">
                <span className="text-sm text-gray-700 capitalize">{key.replace(/([A-Z])/g, " $1")}</span>
                <button onClick={() => toggleConfig(key)}
                  className={`flex items-center gap-2 text-sm font-medium px-3 py-1 rounded-lg transition-colors ${config[key] ? "bg-indigo-50 text-indigo-700" : "bg-gray-100 text-gray-500"}`}>
                  {config[key] ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
                  {config[key] ? "ON" : "OFF"}
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 flex items-center gap-2 mb-4"><Zap className="w-4 h-4 text-red-500" /> Emergency Controls</h2>
          <div className="space-y-3">
            {[
              { label: "Halt All Transactions", desc: "Freeze all inbound/outbound transfers platform-wide", style: "bg-red-600 hover:bg-red-700 text-white" },
              { label: "Force Reconciliation", desc: "Trigger immediate settlement reconciliation run", style: "bg-amber-500 hover:bg-amber-600 text-white" },
              { label: "Broadcast System Alert", desc: "Send emergency notification to all agents and users", style: "bg-indigo-600 hover:bg-indigo-700 text-white" },
            ].map(({ label, desc, style }) => (
              <div key={label} className="flex items-center justify-between p-3 border border-gray-100 rounded-xl">
                <div>
                  <p className="text-sm font-medium text-gray-800">{label}</p>
                  <p className="text-xs text-gray-400">{desc}</p>
                </div>
                <button onClick={() => alert(`${label} — confirm before executing`)} className={`text-xs px-3 py-1.5 rounded-lg font-medium ${style}`}>{label.split(" ")[0]}</button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SuperAdminPortal;
