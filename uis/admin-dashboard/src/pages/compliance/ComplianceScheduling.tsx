import React, { useMemo, useState } from "react";
import { Clock, Calendar, Search, Edit, Save, X } from "lucide-react";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

interface ScheduleWindow {
  id: string;
  policyName: string;
  description: string;
  startTime: string;
  endTime: string;
  daysOfWeek: string[];
  enforced: boolean;
  severity: "critical" | "high" | "medium" | "low";
}

const DEFAULT_SCHEDULES: ScheduleWindow[] = [
  { id: "1", policyName: "Minimum Battery (30%)", description: "Enforce minimum battery level during business hours", startTime: "08:00", endTime: "18:00", daysOfWeek: ["Mon","Tue","Wed","Thu","Fri"], enforced: true, severity: "high" },
  { id: "2", policyName: "Geofence Enforcement", description: "Restrict device movement to assigned zones", startTime: "06:00", endTime: "22:00", daysOfWeek: ["Mon","Tue","Wed","Thu","Fri","Sat"], enforced: true, severity: "critical" },
  { id: "3", policyName: "App Version Check", description: "Require minimum app version v3.2.0", startTime: "00:00", endTime: "23:59", daysOfWeek: DAYS, enforced: true, severity: "medium" },
  { id: "4", policyName: "Network Whitelist", description: "Only allow approved WiFi networks", startTime: "08:00", endTime: "20:00", daysOfWeek: ["Mon","Tue","Wed","Thu","Fri"], enforced: false, severity: "low" },
  { id: "5", policyName: "Screen Lock Timeout", description: "Auto-lock after 2 min inactivity", startTime: "00:00", endTime: "23:59", daysOfWeek: DAYS, enforced: true, severity: "high" },
  { id: "6", policyName: "Transaction Limit Cap", description: "Enforce daily transaction limits per device", startTime: "06:00", endTime: "23:00", daysOfWeek: ["Mon","Tue","Wed","Thu","Fri","Sat"], enforced: true, severity: "critical" },
];

const SEVERITY_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-blue-100 text-blue-700",
};

export default function ComplianceScheduling() {
  const [schedules, setSchedules] = useState<ScheduleWindow[]>(DEFAULT_SCHEDULES);
  const [search, setSearch] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");

  const filtered = useMemo(() => {
    if (!search) return schedules;
    const q = search.toLowerCase();
    return schedules.filter(s => s.policyName.toLowerCase().includes(q) || s.description.toLowerCase().includes(q));
  }, [schedules, search]);

  const toggleEnforced = (id: string) => {
    setSchedules(prev => prev.map(s => s.id === id ? { ...s, enforced: !s.enforced } : s));
  };

  const startEdit = (s: ScheduleWindow) => { setEditId(s.id); setEditStart(s.startTime); setEditEnd(s.endTime); };
  const saveEdit = (id: string) => { setSchedules(prev => prev.map(s => s.id === id ? { ...s, startTime: editStart, endTime: editEnd } : s)); setEditId(null); };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><Clock className="w-7 h-7 text-blue-600" />Compliance Scheduling</h1>
          <p className="text-gray-500 text-sm mt-1">Configure time-based enforcement windows for MDM compliance policies</p>
        </div>
        <div className="flex gap-2">
          <span className="text-xs px-3 py-1 rounded-full border border-emerald-300 text-emerald-700 bg-emerald-50">{schedules.filter(s => s.enforced).length} Active Schedules</span>
          <span className="text-xs px-3 py-1 rounded-full border border-gray-300 text-gray-600">{schedules.length} Total Policies</span>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search policies..." className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-gray-500" />
          <h2 className="text-sm font-semibold text-gray-800">Enforcement Windows</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="bg-gray-50 border-b border-gray-100 text-gray-500">
              <th className="px-4 py-3 text-left">Policy</th>
              <th className="px-4 py-3 text-center">Severity</th>
              <th className="px-4 py-3 text-center">Window</th>
              <th className="px-4 py-3 text-center">Days</th>
              <th className="px-4 py-3 text-center">Enforced</th>
              <th className="px-4 py-3 text-center">Actions</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(s => (
                <tr key={s.id} className="hover:bg-gray-50/50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-800">{s.policyName}</div>
                    <div className="text-gray-400 text-[10px]">{s.description}</div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full capitalize ${SEVERITY_COLOR[s.severity]}`}>{s.severity}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {editId === s.id ? (
                      <div className="flex items-center gap-1 justify-center">
                        <input value={editStart} onChange={e => setEditStart(e.target.value)} className="w-16 h-6 text-[10px] border border-gray-200 rounded px-1 text-center" />
                        <span className="text-gray-400">-</span>
                        <input value={editEnd} onChange={e => setEditEnd(e.target.value)} className="w-16 h-6 text-[10px] border border-gray-200 rounded px-1 text-center" />
                      </div>
                    ) : (
                      <span className="font-mono text-gray-600">{s.startTime} – {s.endTime}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex gap-0.5 justify-center flex-wrap">
                      {DAYS.map(d => (
                        <span key={d} className={`px-1 py-0.5 rounded text-[9px] ${s.daysOfWeek.includes(d) ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-400"}`}>{d[0]}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => toggleEnforced(s.id)}
                      className={`w-10 h-5 rounded-full transition-colors relative ${s.enforced ? "bg-blue-600" : "bg-gray-200"}`}
                    >
                      <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${s.enforced ? "translate-x-5" : "translate-x-0.5"}`} />
                    </button>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {editId === s.id ? (
                      <div className="flex gap-1 justify-center">
                        <button onClick={() => saveEdit(s.id)} className="p-1 hover:bg-emerald-50 rounded text-emerald-600"><Save className="w-3 h-3" /></button>
                        <button onClick={() => setEditId(null)} className="p-1 hover:bg-red-50 rounded text-red-500"><X className="w-3 h-3" /></button>
                      </div>
                    ) : (
                      <button onClick={() => startEdit(s)} className="p-1 hover:bg-gray-100 rounded text-gray-400"><Edit className="w-3 h-3" /></button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Policies", value: schedules.length, color: "text-blue-600" },
          { label: "Active", value: schedules.filter(s => s.enforced).length, color: "text-emerald-600" },
          { label: "Critical", value: schedules.filter(s => s.severity === "critical").length, color: "text-red-600" },
          { label: "24/7 Enforced", value: schedules.filter(s => s.startTime === "00:00" && s.endTime === "23:59").length, color: "text-purple-600" },
        ].map(stat => (
          <div key={stat.label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm text-center">
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
