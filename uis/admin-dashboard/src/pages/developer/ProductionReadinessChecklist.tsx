import { ClipboardList, RefreshCw, Download, CheckSquare, Square, ChevronDown, ChevronRight } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

type TaskStatus = "done" | "in-progress" | "blocked" | "pending";

interface ChecklistTask {
  id: string;
  title: string;
  assignee: string;
  status: TaskStatus;
  notes: string;
  completed: boolean;
}

interface ChecklistPhase {
  id: string;
  name: string;
  tasks: ChecklistTask[];
}

const INITIAL_PHASES: ChecklistPhase[] = [
  {
    id: "pre-deploy", name: "Pre-Deploy",
    tasks: [
      { id: "pd1", title: "Freeze feature branch and create release tag", assignee: "Chidi O.", status: "done", notes: "Tagged v1.8.0-rc1 on 2024-12-09", completed: true },
      { id: "pd2", title: "Run full regression test suite", assignee: "QA Team", status: "done", notes: "96% pass rate. 2 known non-critical failures deferred.", completed: true },
      { id: "pd3", title: "Security penetration test sign-off", assignee: "SecOps", status: "in-progress", notes: "Report from CyberSafe NG pending review.", completed: false },
      { id: "pd4", title: "CBN pre-deployment notification submitted", assignee: "Compliance", status: "done", notes: "Notification ref: CBN/2024/1204/54L", completed: true },
      { id: "pd5", title: "Database migration dry-run on staging", assignee: "DevOps", status: "done", notes: "Migration completed in 4m 22s. No data anomalies.", completed: true },
      { id: "pd6", title: "Rollback runbook reviewed and updated", assignee: "Platform Eng.", status: "in-progress", notes: "Awaiting sign-off from Taiwo A.", completed: false },
    ],
  },
  {
    id: "deploy", name: "Deploy",
    tasks: [
      { id: "dp1", title: "Enable maintenance mode on portal", assignee: "DevOps", status: "pending", notes: "", completed: false },
      { id: "dp2", title: "Apply database migrations to production", assignee: "DevOps", status: "pending", notes: "", completed: false },
      { id: "dp3", title: "Deploy backend services via Kubernetes rolling update", assignee: "Platform Eng.", status: "pending", notes: "", completed: false },
      { id: "dp4", title: "Deploy admin dashboard and agent web app", assignee: "Frontend", status: "pending", notes: "", completed: false },
      { id: "dp5", title: "Warm CDN and Redis caches post-deploy", assignee: "DevOps", status: "pending", notes: "", completed: false },
      { id: "dp6", title: "Disable maintenance mode and verify login", assignee: "DevOps", status: "pending", notes: "", completed: false },
    ],
  },
  {
    id: "post-deploy", name: "Post-Deploy",
    tasks: [
      { id: "pp1", title: "Run smoke tests on production endpoints", assignee: "QA Team", status: "pending", notes: "", completed: false },
      { id: "pp2", title: "Verify NIBSS and Mojaloop connectivity", assignee: "Integrations", status: "pending", notes: "", completed: false },
      { id: "pp3", title: "Confirm Termii SMS OTP delivery in production", assignee: "QA Team", status: "pending", notes: "", completed: false },
      { id: "pp4", title: "Monitor error rate for 30 minutes post-deploy", assignee: "Platform Eng.", status: "pending", notes: "", completed: false },
      { id: "pp5", title: "Send release notes to all stakeholders", assignee: "Product", status: "pending", notes: "", completed: false },
    ],
  },
  {
    id: "rollback", name: "Rollback Plan",
    tasks: [
      { id: "rb1", title: "Trigger Kubernetes rollback to previous image tag", assignee: "Platform Eng.", status: "pending", notes: "kubectl rollout undo deployment/54agent-backend", completed: false },
      { id: "rb2", title: "Revert database migrations using down scripts", assignee: "DevOps", status: "pending", notes: "Scripts located at /migrations/rollback/v1.8.0/", completed: false },
      { id: "rb3", title: "Notify CBN of rollback within 2 hours per policy", assignee: "Compliance", status: "pending", notes: "Contact: CBN IT Dept +234 9 462 3606", completed: false },
      { id: "rb4", title: "Post incident report within 24 hours", assignee: "Engineering Lead", status: "pending", notes: "", completed: false },
    ],
  },
];

const STATUS_CONFIG: Record<TaskStatus, { label: string; bg: string; text: string }> = {
  done: { label: "Done", bg: "bg-green-100", text: "text-green-700" },
  "in-progress": { label: "In Progress", bg: "bg-blue-100", text: "text-blue-700" },
  blocked: { label: "Blocked", bg: "bg-red-100", text: "text-red-700" },
  pending: { label: "Pending", bg: "bg-gray-100", text: "text-gray-500" },
};

const ProductionReadinessChecklist: React.FC = () => {
  const [phases, setPhases] = useState<ChecklistPhase[]>([]);
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  useEffect(() => { fetchChecklist(); }, []);

  const fetchChecklist = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/production-checklist`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setPhases(Array.isArray(d.phases) ? d.phases : INITIAL_PHASES); }
      else { setPhases(INITIAL_PHASES); }
    } catch { setPhases(INITIAL_PHASES); }
    finally { setLoading(false); }
  };

  const toggleTask = async (phaseId: string, taskId: string) => {
    setPhases(prev => prev.map(phase => phase.id !== phaseId ? phase : {
      ...phase,
      tasks: phase.tasks.map(task => task.id !== taskId ? task : {
        ...task,
        completed: !task.completed,
        status: (!task.completed ? "done" : "pending") as TaskStatus,
      }),
    }));
    try {
      await fetch(`${CORE_URL}/developer/api/v1/production-checklist/${taskId}/toggle`, {
        method: "PATCH", headers: getTenantHeadersFromStorage(),
      });
    } catch { /* no-op */ }
  };

  const exportPDF = () => {
    alert("Export to PDF: Feature will generate a printable checklist report. (Demo mode)");
  };

  const toggleCollapse = (id: string) => setCollapsed(prev => ({ ...prev, [id]: !prev[id] }));

  const allTasks = phases.flatMap(p => p.tasks);
  const completedCount = allTasks.filter(t => t.completed).length;
  const totalCount = allTasks.length;
  const completionPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
  const pctColor = completionPct >= 90 ? "text-green-600" : completionPct >= 60 ? "text-blue-600" : "text-amber-600";
  const barColor = completionPct >= 90 ? "bg-green-500" : completionPct >= 60 ? "bg-blue-500" : "bg-amber-500";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ClipboardList className="w-7 h-7 text-blue-600" /> Production Readiness Checklist
          </h1>
          <p className="text-gray-500 text-sm mt-1">Track pre-deploy, deployment, post-deploy and rollback tasks for every go-live</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={exportPDF}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
            <Download className="w-4 h-4" /> Export PDF
          </button>
          <button onClick={fetchChecklist} disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-xs text-gray-500">Overall Completion</p>
            <p className={`text-3xl font-bold mt-0.5 ${pctColor}`}>{completionPct}%</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-500">{completedCount} of {totalCount} tasks done</p>
            <p className="text-xs text-gray-400 mt-0.5">{totalCount - completedCount} remaining</p>
          </div>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-3">
          <div className={`${barColor} h-3 rounded-full transition-all duration-300`} style={{ width: `${completionPct}%` }} />
        </div>
        <div className="grid grid-cols-4 gap-3 mt-4">
          {phases.map(phase => {
            const done = phase.tasks.filter(t => t.completed).length;
            const tot = phase.tasks.length;
            const phasePct = tot > 0 ? Math.round((done / tot) * 100) : 0;
            return (
              <div key={phase.id} className="text-center">
                <p className="text-xs text-gray-500">{phase.name}</p>
                <p className="font-semibold text-gray-800 text-sm">{done}/{tot}</p>
                <div className="w-full bg-gray-100 rounded-full h-1 mt-1">
                  <div className="bg-blue-400 h-1 rounded-full" style={{ width: `${phasePct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-4">
        {phases.map(phase => {
          const isCollapsed = collapsed[phase.id];
          const doneInPhase = phase.tasks.filter(t => t.completed).length;
          return (
            <div key={phase.id} className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <button onClick={() => toggleCollapse(phase.id)}
                className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-center gap-3">
                  {isCollapsed ? <ChevronRight className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                  <h2 className="font-semibold text-gray-900">{phase.name}</h2>
                  <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full font-medium">
                    {doneInPhase}/{phase.tasks.length}
                  </span>
                </div>
              </button>
              {!isCollapsed && (
                <div className="border-t border-gray-100">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-gray-400 border-b border-gray-100 bg-gray-50">
                        <th className="text-left py-2 px-6 w-8"></th>
                        <th className="text-left py-2 pr-4">Task</th>
                        <th className="text-left py-2 pr-4">Assignee</th>
                        <th className="text-left py-2 pr-4">Status</th>
                        <th className="text-left py-2 pr-6">Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {phase.tasks.map(task => {
                        const cfg = STATUS_CONFIG[task.status];
                        return (
                          <tr key={task.id} className={`border-b border-gray-50 hover:bg-gray-50 ${task.completed ? "opacity-60" : ""}`}>
                            <td className="py-3 px-6">
                              <button onClick={() => toggleTask(phase.id, task.id)} className="text-blue-500 hover:text-blue-700">
                                {task.completed
                                  ? <CheckSquare className="w-4 h-4 text-green-500" />
                                  : <Square className="w-4 h-4 text-gray-300" />}
                              </button>
                            </td>
                            <td className={`py-3 pr-4 font-medium ${task.completed ? "line-through text-gray-400" : "text-gray-800"}`}>{task.title}</td>
                            <td className="py-3 pr-4 text-gray-500 text-xs">{task.assignee}</td>
                            <td className="py-3 pr-4">
                              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>{cfg.label}</span>
                            </td>
                            <td className="py-3 pr-6 text-xs text-gray-400 max-w-xs truncate">{task.notes || "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ProductionReadinessChecklist;
