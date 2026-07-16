import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export default function CbnReportingDashboard() {
  const [activeTab, setActiveTab] = useState<
    "monthly" | "quarterly" | "sar" | "compliance"
  >("monthly");
  const [reportMonth, setReportMonth] = useState(new Date().getMonth() + 1);
  const [reportYear, setReportYear] = useState(new Date().getFullYear());
  const [sarForm, setSarForm] = useState({
    agentId: "",
    transactionIds: "",
    totalAmount: "",
    reason: "",
    description: "",
  });

  const generateMut = trpc.cbnReporting.generateMonthlyReport.useMutation({
    onSuccess: () =>
      toast.success(`Monthly activity report generated successfully.`),
    onError: (e: any) => toast.error(e.message),
  });
  const quarterlyMut =
    trpc.cbnReporting.generateQuarterlyFraudReport.useMutation({
      onSuccess: () => toast.success("Quarterly fraud report generated."),
      onError: (e: any) => toast.error(e.message),
    });
  const sarMut = trpc.cbnReporting.fileSar.useMutation({
    onSuccess: () => toast.success("SAR filed with CBN/NFIU."),
    onError: (e: any) => toast.error(e.message),
  });
  const complianceQ = trpc.cbnReporting.complianceDashboard.useQuery(
    { year: new Date().getFullYear() },
    { retry: false }
  );

  const tabs = [
    { id: "monthly" as const, label: "Monthly Activity" },
    { id: "quarterly" as const, label: "Quarterly Fraud" },
    { id: "sar" as const, label: "SAR Filing" },
    { id: "compliance" as const, label: "Compliance Dashboard" },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">CBN Regulatory Reporting</h1>
            <p className="text-gray-400 text-sm">
              Central Bank of Nigeria compliance reports — MAR, QFR, SAR
            </p>
          </div>
          <a href="/" className="text-sm text-gray-400 hover:text-white">
            ← Back
          </a>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Monthly Reports", value: "12", sub: "This year" },
            { label: "Quarterly Reports", value: "4", sub: "This year" },
            { label: "SARs Filed", value: "3", sub: "Last 90 days" },
            { label: "Compliance Score", value: "98%", sub: "CBN rating" },
          ].map((kpi, i) => (
            <Card key={i} className="bg-gray-900 border-gray-800">
              <CardContent className="pt-4">
                <div className="text-xs text-gray-400">{kpi.label}</div>
                <div className="text-2xl font-bold text-white">{kpi.value}</div>
                <div className="text-xs text-gray-500">{kpi.sub}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="flex gap-2 border-b border-gray-800 pb-2">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 rounded-t text-sm font-medium transition-colors ${activeTab === t.id ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {activeTab === "monthly" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">
                Monthly Activity Report (MAR)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-gray-400 text-sm">
                Generate the CBN-mandated Monthly Activity Report covering
                transaction volumes, agent activity, float utilization, and
                compliance metrics.
              </p>
              <div className="flex gap-3 items-end">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">
                    Year
                  </label>
                  <Input
                    type="number"
                    value={reportYear}
                    onChange={e => setReportYear(Number(e.target.value))}
                    className="bg-gray-800 border-gray-700 text-white w-28"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">
                    Month
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={12}
                    value={reportMonth}
                    onChange={e => setReportMonth(Number(e.target.value))}
                    className="bg-gray-800 border-gray-700 text-white w-20"
                  />
                </div>
                <Button
                  onClick={() =>
                    generateMut.mutate({ year: reportYear, month: reportMonth })
                  }
                  disabled={generateMut.isPending}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  {generateMut.isPending ? "Generating..." : "Generate MAR"}
                </Button>
              </div>
              <div className="bg-gray-800 rounded p-4 text-xs text-gray-400 space-y-2">
                <p>
                  <strong className="text-gray-300">Sections:</strong> Agent
                  network summary, Transaction volume by type, Float
                  utilization, Commission disbursement, KYC compliance, Fraud
                  incidents
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {activeTab === "quarterly" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">
                Quarterly Fraud Report (QFR)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-gray-400 text-sm">
                Generate the CBN Quarterly Fraud Report detailing fraud
                incidents, resolution rates, and preventive measures.
              </p>
              <Button
                onClick={() =>
                  quarterlyMut.mutate({
                    quarter: Math.ceil((new Date().getMonth() + 1) / 3),
                    year: new Date().getFullYear(),
                  })
                }
                disabled={quarterlyMut.isPending}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {quarterlyMut.isPending ? "Generating..." : "Generate QFR"}
              </Button>
              <div className="grid grid-cols-3 gap-4 mt-4">
                {[
                  { label: "Total Fraud Cases", value: "47", change: "-12%" },
                  { label: "Resolution Rate", value: "94.2%", change: "+3.1%" },
                  { label: "Amount Recovered", value: "₦2.4M", change: "+18%" },
                ].map((m, i) => (
                  <div key={i} className="bg-gray-800 rounded p-3 text-center">
                    <div className="text-xs text-gray-400">{m.label}</div>
                    <div className="text-xl font-bold text-white">
                      {m.value}
                    </div>
                    <div
                      className={`text-xs ${m.change.startsWith("+") ? "text-green-400" : "text-red-400"}`}
                    >
                      {m.change} vs last quarter
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {activeTab === "sar" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">
                Suspicious Activity Report (SAR)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-gray-400 text-sm">
                File a Suspicious Activity Report with the CBN Nigerian
                Financial Intelligence Unit (NFIU).
              </p>
              <div className="bg-amber-900/20 border border-amber-800 rounded p-3 text-sm text-amber-300">
                SARs must be filed within 72 hours of detecting suspicious
                activity.
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-400 block mb-1">
                    Agent ID
                  </label>
                  <Input
                    value={sarForm.agentId}
                    onChange={e =>
                      setSarForm(p => ({ ...p, agentId: e.target.value }))
                    }
                    placeholder="Numeric agent ID"
                    className="bg-gray-800 border-gray-700 text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">
                    Total Amount (₦)
                  </label>
                  <Input
                    value={sarForm.totalAmount}
                    onChange={e =>
                      setSarForm(p => ({ ...p, totalAmount: e.target.value }))
                    }
                    type="number"
                    placeholder="Amount in NGN"
                    className="bg-gray-800 border-gray-700 text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">
                    Transaction IDs (comma-separated)
                  </label>
                  <Input
                    value={sarForm.transactionIds}
                    onChange={e =>
                      setSarForm(p => ({
                        ...p,
                        transactionIds: e.target.value,
                      }))
                    }
                    placeholder="1,2,3"
                    className="bg-gray-800 border-gray-700 text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">
                    Reason
                  </label>
                  <Input
                    value={sarForm.reason}
                    onChange={e =>
                      setSarForm(p => ({ ...p, reason: e.target.value }))
                    }
                    placeholder="e.g., Structuring, Unusual pattern"
                    className="bg-gray-800 border-gray-700 text-white"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">
                  Description
                </label>
                <textarea
                  value={sarForm.description}
                  onChange={e =>
                    setSarForm(p => ({ ...p, description: e.target.value }))
                  }
                  className="w-full bg-gray-800 border border-gray-700 rounded p-3 text-white text-sm min-h-[100px]"
                  placeholder="Describe the suspicious activity in detail (min 20 chars)..."
                />
              </div>
              <Button
                onClick={() =>
                  sarMut.mutate({
                    agentId: Number(sarForm.agentId),
                    transactionIds: sarForm.transactionIds
                      .split(",")
                      .map(s => Number(s.trim()))
                      .filter(Boolean),
                    totalAmount: Number(sarForm.totalAmount),
                    reason: sarForm.reason,
                    description: sarForm.description,
                  })
                }
                disabled={
                  sarMut.isPending ||
                  sarForm.reason.length < 10 ||
                  sarForm.description.length < 20
                }
                className="bg-red-600 hover:bg-red-700"
              >
                {sarMut.isPending ? "Filing..." : "File SAR"}
              </Button>
            </CardContent>
          </Card>
        )}

        {activeTab === "compliance" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">Compliance Dashboard</CardTitle>
            </CardHeader>
            <CardContent>
              {complianceQ.data ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    {Object.entries(complianceQ.data)
                      .slice(0, 6)
                      .map(([k, v], i) => (
                        <div key={i} className="bg-gray-800 rounded p-3">
                          <div className="text-xs text-gray-400">
                            {k.replace(/([A-Z])/g, " $1").trim()}
                          </div>
                          <div className="text-lg font-bold text-white">
                            {typeof v === "number"
                              ? v.toLocaleString()
                              : String(v)}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  Loading compliance data...
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
