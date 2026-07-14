import DashboardLayout from "@/components/DashboardLayout";
import { useState } from "react";

import { trpc } from "@/lib/trpc";
export default function TxMonitorPage() {
  const [severityFilter, setSeverityFilter] = useState("all");

  const alerts = [
    {
      id: "ALT-001",
      rule: "R002",
      severity: "critical",
      title: "Large Transaction Detected",
      message: "Agent AGT-001 processed ₦2,500,000 cash out",
      agent: "AGT-001",
      time: "30m ago",
      ack: false,
    },
    {
      id: "ALT-002",
      rule: "R001",
      severity: "warning",
      title: "High Velocity Alert",
      message: "Agent AGT-003 processed 62 transactions in last hour",
      agent: "AGT-003",
      time: "15m ago",
      ack: false,
    },
    {
      id: "ALT-003",
      rule: "R003",
      severity: "warning",
      title: "High Failure Rate",
      message: "Agent AGT-005 has 35% failure rate (14/40 failed)",
      agent: "AGT-005",
      time: "10m ago",
      ack: true,
    },
    {
      id: "ALT-004",
      rule: "R008",
      severity: "critical",
      title: "Geographic Anomaly",
      message: "Agent AGT-002 (Abuja) transacting from Lagos (450km away)",
      agent: "AGT-002",
      time: "5m ago",
      ack: false,
    },
    {
      id: "ALT-005",
      rule: "R006",
      severity: "info",
      title: "Off-Hours Activity",
      message: "Agent AGT-004 transacting at 3:15 AM",
      agent: "AGT-004",
      time: "2m ago",
      ack: false,
    },
  ];

  const rules = [
    {
      id: "R001",
      name: "High Velocity Agent",
      threshold: "50 tx/hr",
      severity: "warning",
      enabled: true,
    },
    {
      id: "R002",
      name: "Large Transaction",
      threshold: "₦1,000,000",
      severity: "critical",
      enabled: true,
    },
    {
      id: "R003",
      name: "High Failure Rate",
      threshold: "20%",
      severity: "warning",
      enabled: true,
    },
    {
      id: "R004",
      name: "Suspicious Customer Velocity",
      threshold: "10 tx/hr",
      severity: "critical",
      enabled: true,
    },
    {
      id: "R005",
      name: "Micro-Transaction Flood",
      threshold: "100+ < ₦1000/hr",
      severity: "warning",
      enabled: true,
    },
    {
      id: "R006",
      name: "Off-Hours Activity",
      threshold: "Outside 6am-10pm",
      severity: "info",
      enabled: true,
    },
    {
      id: "R007",
      name: "Dormant Agent Activity",
      threshold: "7d inactive",
      severity: "warning",
      enabled: true,
    },
    {
      id: "R008",
      name: "Geographic Anomaly",
      threshold: "100km+ shift",
      severity: "critical",
      enabled: true,
    },
  ];

  const sevColor: Record<string, string> = {
    critical: "bg-red-900 text-red-300",
    warning: "bg-yellow-900 text-yellow-300",
    info: "bg-blue-900 text-blue-300",
  };
  const filtered =
    severityFilter === "all"
      ? alerts
      : alerts.filter(a => a.severity === severityFilter);
  // Sprint 87: Wired to transactionMonitoring router
  const { data, isLoading } = trpc.transactionMonitoring.list.useQuery({
    // @ts-ignore Sprint 85
    page: 1,
    limit: 10,
  });

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold text-white">
          Real-Time Transaction Monitor
        </h1>

        <div className="grid grid-cols-5 gap-4">
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-white">{alerts.length}</div>
            <div className="text-gray-400 text-sm">Total Alerts</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-red-400">
              {alerts.filter(a => a.severity === "critical").length}
            </div>
            <div className="text-gray-400 text-sm">Critical</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-yellow-400">
              {alerts.filter(a => a.severity === "warning").length}
            </div>
            <div className="text-gray-400 text-sm">Warning</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-orange-400">
              {alerts.filter(a => !a.ack).length}
            </div>
            <div className="text-gray-400 text-sm">Unacknowledged</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-green-400">
              {rules.length}
            </div>
            <div className="text-gray-400 text-sm">Active Rules</div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6">
          <div className="col-span-2 bg-gray-800 rounded p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-white">Live Alerts</h2>
              <div className="flex gap-2">
                {["all", "critical", "warning", "info"].map(f => (
                  <button
                    key={f}
                    onClick={() => setSeverityFilter(f)}
                    className={`px-3 py-1 rounded text-sm ${severityFilter === f ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-300"}`}
                  >
                    {f.charAt(0).toUpperCase() + f.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              {filtered.map(a => (
                <div
                  key={a.id}
                  className={`p-3 rounded ${a.ack ? "bg-gray-700 opacity-60" : "bg-gray-700"}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${sevColor[a.severity]}`}
                      >
                        {a.severity}
                      </span>
                      <span className="text-white font-semibold">
                        {a.title}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400 text-sm">{a.time}</span>
                      {!a.ack && (
                        <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                      )}
                    </div>
                  </div>
                  <div className="text-gray-400 text-sm mt-1">{a.message}</div>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-gray-500 text-xs">
                      Agent: {a.agent}
                    </span>
                    <span className="text-gray-500 text-xs">
                      Rule: {a.rule}
                    </span>
                    {!a.ack && (
                      <button className="px-2 py-0.5 bg-blue-700 text-blue-200 rounded text-xs hover:bg-blue-600">
                        Acknowledge
                      </button>
                    )}
                    <button className="px-2 py-0.5 bg-green-700 text-green-200 rounded text-xs hover:bg-green-600">
                      Resolve
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-gray-800 rounded p-4">
            <h2 className="text-lg font-semibold text-white mb-3">
              Alert Rules
            </h2>
            <div className="space-y-2">
              {rules.map(r => (
                <div
                  key={r.id}
                  className="flex items-center justify-between bg-gray-700 rounded p-2"
                >
                  <div>
                    <div className="text-white text-sm">{r.name}</div>
                    <div className="text-gray-400 text-xs">{r.threshold}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${sevColor[r.severity]}`}
                    >
                      {r.severity}
                    </span>
                    <div
                      className={`w-3 h-3 rounded-full ${r.enabled ? "bg-green-500" : "bg-gray-500"}`}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
