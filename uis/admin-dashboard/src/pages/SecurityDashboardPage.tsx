// @ts-nocheck
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function SecurityDashboardPage() {
  const { data, isLoading } = trpc.securityHardening.dashboard.useQuery();
  const owasp = trpc.securityHardening.owaspTop10.useQuery();
  const pci = trpc.securityHardening.pciDssCompliance.useQuery();
  const cbn = trpc.securityHardening.cbnCompliance.useQuery();
  const scans = trpc.securityHardening.recentScans.useQuery();
  const runScan = trpc.securityHardening.runScan.useMutation();

  if (isLoading)
    return (
      <div className="p-6 animate-pulse">Loading Security Dashboard...</div>
    );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Security & Compliance Dashboard
          </h1>
          <p className="text-muted-foreground">
            OWASP Top 10, PCI-DSS, CBN compliance, vulnerability management
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-center">
            <div className="text-4xl font-bold text-green-600">
              {data?.overallScore ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">Security Score</div>
          </div>
          <Badge className="text-lg px-3 py-1" variant="default">
            {data?.grade ?? "?"}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Critical Vulns</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {data?.vulnerabilities?.critical ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">OWASP Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.owaspScore ?? 0}/100
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">PCI-DSS Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data?.pciScore ?? 0}/100</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">CBN Compliant</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={data?.cbnCompliant ? "default" : "destructive"}>
              {data?.cbnCompliant ? "Yes" : "No"}
            </Badge>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>OWASP Top 10 Coverage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {(owasp.data?.items || []).map((item: any) => (
              <div
                key={item.id}
                className="flex items-center justify-between p-3 border rounded"
              >
                <div className="flex items-center gap-3">
                  <Badge variant="outline">{item.id}</Badge>
                  <span className="font-medium">{item.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Badge
                    variant={
                      item.status === "mitigated" ? "default" : "secondary"
                    }
                  >
                    {item.status}
                  </Badge>
                  <span className="font-bold text-green-600">
                    {item.score}/100
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>PCI-DSS Compliance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(pci.data?.requirements || []).map((r: any) => (
                <div
                  key={r.requirement}
                  className="flex justify-between text-sm"
                >
                  <span>{r.requirement}</span>
                  <Badge
                    variant={
                      r.status === "compliant"
                        ? "default"
                        : r.status === "n/a"
                          ? "outline"
                          : "destructive"
                    }
                  >
                    {r.score}%
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CBN Regulatory Compliance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(cbn.data?.requirements || []).map((r: any) => (
                <div
                  key={r.requirement}
                  className="flex justify-between text-sm"
                >
                  <span>{r.requirement}</span>
                  <Badge
                    variant={
                      r.status === "compliant" ? "default" : "destructive"
                    }
                  >
                    {r.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Security Scans</CardTitle>
          <div className="flex gap-2">
            {(["SAST", "DAST", "SCA", "Container", "Secrets"] as const).map(
              type => (
                <Button
                  key={type}
                  size="sm"
                  variant="outline"
                  onClick={() => runScan.mutate({ type })}
                >
                  {type}
                </Button>
              )
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Type</th>
                  <th className="text-left p-2">Tool</th>
                  <th className="text-left p-2">Date</th>
                  <th className="text-left p-2">Findings</th>
                  <th className="text-left p-2">Critical</th>
                  <th className="text-left p-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(scans.data?.scans || []).map((s: any) => (
                  <tr key={s.id} className="border-b">
                    <td className="p-2">
                      <Badge variant="outline">{s.type}</Badge>
                    </td>
                    <td className="p-2">{s.tool}</td>
                    <td className="p-2 text-xs">
                      {new Date(s.date).toLocaleString()}
                    </td>
                    <td className="p-2">{s.findings}</td>
                    <td className="p-2 font-bold text-green-600">
                      {s.critical}
                    </td>
                    <td className="p-2">
                      <Badge
                        variant={
                          s.status === "completed" ? "default" : "secondary"
                        }
                      >
                        {s.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
