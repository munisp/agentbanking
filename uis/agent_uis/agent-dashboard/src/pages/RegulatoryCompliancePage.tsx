import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { FileCheck, Search, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

type ComplianceCheck = {
  name: string;
  category: string;
  description: string;
  status: "passed" | "failed" | "warning";
  lastRun: string;
};

type Summary = {
  total: number;
  passed: number;
  failed: number;
  warnings: number;
};

export default function RegulatoryCompliancePage() {
  const [search, setSearch] = useState("");
  const [checks, setChecks] = useState<ComplianceCheck[]>([]);
  const [summary, setSummary] = useState<Summary>({ total: 0, passed: 0, failed: 0, warnings: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const load = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/compliance/api/v1/regulatory-compliance/checks`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error("Failed to fetch compliance checks");
      const data = await res.json();
      setChecks(data?.checks || []);
      setSummary(data?.summary || { total: 0, passed: 0, failed: 0, warnings: 0 });
    } catch {
      setChecks([]);
    } finally {
      setIsLoading(false);
    }
  };

  const runAllChecks = async () => {
    setIsRunning(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/compliance/api/v1/regulatory-compliance/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error("Failed to run compliance checks");
      toast.success("Compliance check completed");
      await load();
    } catch {
      toast.error("Failed to run compliance checks");
    } finally {
      setIsRunning(false);
    }
  };

  useEffect(() => { load(); }, []);

  const filtered = checks.filter(
    (c) => !search || c.name?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileCheck className="w-6 h-6" /> Regulatory Compliance
          </h1>
          <p className="text-muted-foreground mt-1">AML/CFT, KYC, PCI-DSS, and regulatory filing compliance checks</p>
        </div>
        <Button onClick={runAllChecks} disabled={isRunning}>
          {isRunning ? "Running..." : "Run All Checks"}
        </Button>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold">{summary.total}</p><p className="text-sm text-muted-foreground">Total Checks</p></CardContent></Card>
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold text-green-600">{summary.passed}</p><p className="text-sm text-muted-foreground">Passed</p></CardContent></Card>
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold text-red-600">{summary.failed}</p><p className="text-sm text-muted-foreground">Failed</p></CardContent></Card>
        <Card><CardContent className="pt-4 text-center"><p className="text-2xl font-bold text-yellow-600">{summary.warnings}</p><p className="text-sm text-muted-foreground">Warnings</p></CardContent></Card>
      </div>

      <div className="flex items-center gap-2">
        <Search className="w-4 h-4" />
        <Input placeholder="Search checks..." value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-sm" />
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="grid gap-4">
          {filtered.map((c, i) => (
            <Card key={i}>
              <CardContent className="flex items-center justify-between py-4">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${c.status === "passed" ? "bg-green-100" : c.status === "failed" ? "bg-red-100" : "bg-yellow-100"}`}>
                    {c.status === "passed" ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : c.status === "failed" ? (
                      <AlertTriangle className="w-5 h-5 text-red-600" />
                    ) : (
                      <Clock className="w-5 h-5 text-yellow-600" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium">{c.name}</p>
                    <p className="text-sm text-muted-foreground">{c.category} • Last run: {c.lastRun || "Never"}</p>
                    <p className="text-xs text-muted-foreground">{c.description}</p>
                  </div>
                </div>
                <span className={`px-3 py-1 rounded text-xs font-medium ${c.status === "passed" ? "bg-green-100 text-green-700" : c.status === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>
                  {c.status?.toUpperCase()}
                </span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
