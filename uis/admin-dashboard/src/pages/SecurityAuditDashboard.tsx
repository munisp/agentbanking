// @ts-nocheck
// SecurityAuditDashboard — Sprint 76
// PBAC evaluation, vulnerability scanning, DDoS status, file integrity, backups
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Shield,
  AlertTriangle,
  CheckCircle,
  Lock,
  Server,
  Database,
} from "lucide-react";

export default function SecurityAuditDashboard() {
  const [subject, setSubject] = useState("agent-001");
  const [role, setRole] = useState("agent");
  const [resource, setResource] = useState("transaction:cash_in");
  const [action, setAction] = useState("create");

  const scan = trpc.securityAudit.runSecurityScan.useQuery();
  const policies = trpc.securityAudit.getPolicies.useQuery();
  const fileIntegrity = trpc.securityAudit.getFileIntegrity.useQuery();
  const backups = trpc.securityAudit.getBackupStatus.useQuery();
  const ddos = trpc.securityAudit.getDDoSStatus.useQuery();
  const auditChain = trpc.securityAudit.getAuditChain.useQuery({ limit: 20 });
  const pbacResult = trpc.securityAudit.evaluateAccess.useQuery({
    subject,
    subjectRole: role,
    resource,
    action,
  });

  return (
    <DashboardLayout>
      <div className="container py-6 space-y-6">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-red-500" />
          <div>
            <h1 className="text-2xl font-bold">Security Audit Dashboard</h1>
            <p className="text-muted-foreground">
              PBAC, vulnerability scanning, DDoS shield, file integrity, backups
            </p>
          </div>
        </div>

        {/* Security Score */}
        {scan.data && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6 text-center">
                <div
                  className="text-4xl font-bold"
                  style={{
                    color:
                      scan.data.securityScore >= 90
                        ? "#22c55e"
                        : scan.data.securityScore >= 70
                          ? "#eab308"
                          : "#ef4444",
                  }}
                >
                  {scan.data.grade}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  Security Grade
                </p>
                <p className="text-lg font-semibold">
                  {scan.data.securityScore}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <CheckCircle className="h-8 w-8 text-green-500 mx-auto" />
                <p className="text-2xl font-bold mt-2">{scan.data.passed}</p>
                <p className="text-sm text-muted-foreground">Checks Passed</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <AlertTriangle className="h-8 w-8 text-yellow-500 mx-auto" />
                <p className="text-2xl font-bold mt-2">{scan.data.failed}</p>
                <p className="text-sm text-muted-foreground">Checks Failed</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <Lock className="h-8 w-8 text-red-500 mx-auto" />
                <p className="text-2xl font-bold mt-2">
                  {scan.data.criticalIssues}
                </p>
                <p className="text-sm text-muted-foreground">Critical Issues</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* PBAC Tester */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" /> PBAC Access Evaluator
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Input
                placeholder="Subject"
                value={subject}
                onChange={e => setSubject(e.target.value)}
              />
              <Input
                placeholder="Role"
                value={role}
                onChange={e => setRole(e.target.value)}
              />
              <Input
                placeholder="Resource"
                value={resource}
                onChange={e => setResource(e.target.value)}
              />
              <Input
                placeholder="Action"
                value={action}
                onChange={e => setAction(e.target.value)}
              />
            </div>
            {pbacResult.data && (
              <div
                className="p-4 rounded-lg"
                style={{
                  backgroundColor: pbacResult.data.allowed
                    ? "rgba(34,197,94,0.1)"
                    : "rgba(239,68,68,0.1)",
                }}
              >
                <Badge
                  variant={pbacResult.data.allowed ? "default" : "destructive"}
                >
                  {pbacResult.data.allowed ? "ALLOWED" : "DENIED"}
                </Badge>
                <p className="text-sm mt-2">{pbacResult.data.reason}</p>
                {pbacResult.data.policyName && (
                  <p className="text-xs text-muted-foreground">
                    Policy: {pbacResult.data.policyName}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* DDoS Shield */}
        {ddos.data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" /> DDoS Shield Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <p className="text-sm text-muted-foreground">
                    Total Requests
                  </p>
                  <p className="text-xl font-bold">
                    {ddos.data.totalRequests.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Blocked</p>
                  <p className="text-xl font-bold text-red-500">
                    {ddos.data.blockedRequests.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Block Rate</p>
                  <p className="text-xl font-bold">{ddos.data.blockRate}%</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Active Blocks</p>
                  <p className="text-xl font-bold">{ddos.data.activeBlocks}</p>
                </div>
              </div>
              <div className="space-y-2">
                {ddos.data.topThreats.map((t: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-muted/50"
                  >
                    <span className="font-mono text-sm">{t.ip}</span>
                    <Badge
                      variant={
                        t.severity === "critical" ? "destructive" : "secondary"
                      }
                    >
                      {t.type}
                    </Badge>
                    <Badge variant={t.blocked ? "default" : "outline"}>
                      {t.blocked ? "Blocked" : "Monitoring"}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* File Integrity & Backups */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {fileIntegrity.data && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Database className="h-5 w-5" /> File Integrity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-green-500 mb-3">
                  {fileIntegrity.data.integrityScore}% Integrity
                </p>
                <div className="space-y-1">
                  {fileIntegrity.data.files.map((f: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="font-mono truncate max-w-[200px]">
                        {f.path}
                      </span>
                      <Badge
                        variant={f.status === "ok" ? "default" : "destructive"}
                      >
                        {f.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
          {backups.data && (
            <Card>
              <CardHeader>
                <CardTitle>Backup Status</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {backups.data.slice(0, 5).map((b: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-sm p-2 rounded bg-muted/50"
                    >
                      <span className="font-mono">{b.id}</span>
                      <span>{(b.sizeBytes / 1e6).toFixed(0)} MB</span>
                      <Badge variant={b.verified ? "default" : "destructive"}>
                        {b.verified ? "Verified" : "Unverified"}
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Vulnerability Scan Results */}
        {scan.data && (
          <Card>
            <CardHeader>
              <CardTitle>Vulnerability Scan Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {scan.data.results.map((r: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-muted/50"
                  >
                    <div className="flex items-center gap-2">
                      {r.mitigated ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                      )}
                      <span className="text-sm font-medium">{r.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          r.severity === "critical"
                            ? "destructive"
                            : r.severity === "high"
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {r.severity}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        CVSS {r.cvss}
                      </span>
                      <Badge variant={r.mitigated ? "default" : "destructive"}>
                        {r.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Audit Chain */}
        {auditChain.data && (
          <Card>
            <CardHeader>
              <CardTitle>
                Audit Chain ({auditChain.data.chainValid ? "Valid" : "TAMPERED"}
                )
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {auditChain.data.entries.map((e: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-sm p-2 rounded bg-muted/50"
                  >
                    <span className="font-mono text-xs">{e.hash}</span>
                    <span>
                      {e.actor} ({e.role})
                    </span>
                    <span>{e.action}</span>
                    <span className="text-muted-foreground">{e.resource}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Policies */}
        {policies.data && (
          <Card>
            <CardHeader>
              <CardTitle>PBAC Policies ({policies.data.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {policies.data.map((p: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-muted/50"
                  >
                    <div>
                      <span className="font-medium text-sm">{p.name}</span>
                      <span className="text-xs text-muted-foreground ml-2">
                        Priority: {p.priority}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          p.effect === "allow" ? "default" : "destructive"
                        }
                      >
                        {p.effect}
                      </Badge>
                      <Badge variant={p.enabled ? "default" : "outline"}>
                        {p.enabled ? "Active" : "Disabled"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
