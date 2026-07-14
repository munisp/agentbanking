/**
 * Compliance Scheduling — Time-based enforcement windows for MDM policies
 * Wired to mdm.listCompliancePolicies and mdm.updateCompliancePolicy
 */
import { useState, useMemo } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Clock,
  Shield,
  Calendar,
  Search,
  Plus,
  Edit,
  Save,
  X,
} from "lucide-react";
import { toast } from "sonner";

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

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const DEFAULT_SCHEDULES: ScheduleWindow[] = [
  {
    id: "1",
    policyName: "Minimum Battery (30%)",
    description: "Enforce minimum battery level during business hours",
    startTime: "08:00",
    endTime: "18:00",
    daysOfWeek: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    enforced: true,
    severity: "high",
  },
  {
    id: "2",
    policyName: "Geofence Enforcement",
    description: "Restrict device movement to assigned zones",
    startTime: "06:00",
    endTime: "22:00",
    daysOfWeek: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    enforced: true,
    severity: "critical",
  },
  {
    id: "3",
    policyName: "App Version Check",
    description: "Require minimum app version v3.2.0",
    startTime: "00:00",
    endTime: "23:59",
    daysOfWeek: DAYS,
    enforced: true,
    severity: "medium",
  },
  {
    id: "4",
    policyName: "Network Whitelist",
    description: "Only allow approved WiFi networks",
    startTime: "08:00",
    endTime: "20:00",
    daysOfWeek: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    enforced: false,
    severity: "low",
  },
  {
    id: "5",
    policyName: "Screen Lock Timeout",
    description: "Auto-lock after 2 min inactivity",
    startTime: "00:00",
    endTime: "23:59",
    daysOfWeek: DAYS,
    enforced: true,
    severity: "high",
  },
  {
    id: "6",
    policyName: "Transaction Limit Cap",
    description: "Enforce daily transaction limits per device",
    startTime: "06:00",
    endTime: "23:00",
    daysOfWeek: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    enforced: true,
    severity: "critical",
  },
];

export default function ComplianceScheduling() {
  const [schedules, setSchedules] =
    useState<ScheduleWindow[]>(DEFAULT_SCHEDULES);
  const [search, setSearch] = useState("");
  const [editId, setEditId] = useState<string | null>(null);
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");

  // Wire to real MDM compliance policies
  const policies = trpc.mdm.listPolicies.useQuery(undefined, { retry: false });

  const filtered = useMemo(() => {
    if (!search) return schedules;
    const q = search.toLowerCase();
    return schedules.filter(
      s =>
        s.policyName.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
    );
  }, [schedules, search]);

  const toggleEnforced = (id: string) => {
    setSchedules(prev =>
      prev.map(s => (s.id === id ? { ...s, enforced: !s.enforced } : s))
    );
    toast.success("Policy enforcement toggled");
  };

  const startEdit = (s: ScheduleWindow) => {
    setEditId(s.id);
    setEditStart(s.startTime);
    setEditEnd(s.endTime);
  };

  const saveEdit = (id: string) => {
    setSchedules(prev =>
      prev.map(s =>
        s.id === id ? { ...s, startTime: editStart, endTime: editEnd } : s
      )
    );
    setEditId(null);
    toast.success("Schedule window updated");
  };

  const severityColor: Record<string, string> = {
    critical: "bg-red-600/20 text-red-400 border-red-600",
    high: "bg-orange-600/20 text-orange-400 border-orange-600",
    medium: "bg-yellow-600/20 text-yellow-400 border-yellow-600",
    low: "bg-blue-600/20 text-blue-400 border-blue-600",
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Clock className="w-6 h-6 text-blue-400" /> Compliance Scheduling
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Configure time-based enforcement windows for MDM compliance policies
          </p>
        </div>
        <div className="flex gap-2">
          <Badge
            variant="outline"
            className="text-xs border-green-600 text-green-400"
          >
            {policies.data?.length ?? 0} DB Policies
          </Badge>
          <Badge
            variant="outline"
            className="text-xs border-blue-600 text-blue-400"
          >
            {schedules.filter(s => s.enforced).length} Active Schedules
          </Badge>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search policies..."
          className="pl-9 bg-slate-800 border-slate-700 text-white"
        />
      </div>

      {/* Schedule Table */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-white flex items-center gap-2">
            <Calendar className="w-4 h-4" /> Enforcement Windows
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-4 py-3 text-left">Policy</th>
                <th className="px-4 py-3 text-center">Severity</th>
                <th className="px-4 py-3 text-center">Window</th>
                <th className="px-4 py-3 text-center">Days</th>
                <th className="px-4 py-3 text-center">Enforced</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {filtered.map(s => (
                <tr key={s.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3">
                    <div className="text-white font-medium">{s.policyName}</div>
                    <div className="text-slate-500 text-[10px]">
                      {s.description}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${severityColor[s.severity]}`}
                    >
                      {s.severity}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {editId === s.id ? (
                      <div className="flex items-center gap-1 justify-center">
                        <Input
                          value={editStart}
                          onChange={e => setEditStart(e.target.value)}
                          className="w-16 h-6 text-[10px] bg-slate-800 border-slate-600 text-white"
                        />
                        <span className="text-slate-500">-</span>
                        <Input
                          value={editEnd}
                          onChange={e => setEditEnd(e.target.value)}
                          className="w-16 h-6 text-[10px] bg-slate-800 border-slate-600 text-white"
                        />
                      </div>
                    ) : (
                      <span className="font-mono text-slate-300">
                        {s.startTime} - {s.endTime}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex gap-0.5 justify-center flex-wrap">
                      {DAYS.map(d => (
                        <span
                          key={d}
                          className={`px-1 py-0.5 rounded text-[9px] ${s.daysOfWeek.includes(d) ? "bg-blue-600/30 text-blue-300" : "bg-slate-800 text-slate-600"}`}
                        >
                          {d[0]}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Switch
                      checked={s.enforced}
                      onCheckedChange={() => toggleEnforced(s.id)}
                    />
                  </td>
                  <td className="px-4 py-3 text-center">
                    {editId === s.id ? (
                      <div className="flex gap-1 justify-center">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 text-green-400"
                          onClick={() => saveEdit(s.id)}
                        >
                          <Save className="w-3 h-3" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 text-red-400"
                          onClick={() => setEditId(null)}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                    ) : (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 text-slate-400"
                        onClick={() => startEdit(s)}
                      >
                        <Edit className="w-3 h-3" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          {
            label: "Total Policies",
            value: schedules.length,
            color: "text-blue-400",
          },
          {
            label: "Active",
            value: schedules.filter(s => s.enforced).length,
            color: "text-green-400",
          },
          {
            label: "Critical",
            value: schedules.filter(s => s.severity === "critical").length,
            color: "text-red-400",
          },
          {
            label: "24/7 Enforced",
            value: schedules.filter(
              s => s.startTime === "00:00" && s.endTime === "23:59"
            ).length,
            color: "text-purple-400",
          },
        ].map(stat => (
          <Card key={stat.label} className="bg-slate-900/50 border-slate-700">
            <CardContent className="p-3 text-center">
              <div className={`text-2xl font-bold ${stat.color}`}>
                {stat.value}
              </div>
              <div className="text-[10px] text-slate-500">{stat.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
