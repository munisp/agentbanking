import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Landmark, Users, FileText, TrendingUp } from "lucide-react";

export default function PensionCollectionPage() {
  const [tab, setTab] = useState<"contributions" | "pfas" | "employers">(
    "contributions"
  );
  // @ts-ignore Sprint 85
  const contributions = trpc.pensionCollection.history.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const pfas = trpc.pensionCollection.pfas.useQuery();
  // @ts-ignore Sprint 85
  const employers = trpc.pensionCollection.history.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const analytics = trpc.pensionCollection.analytics.useQuery();

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Pension Collection</h1>
          <p className="text-muted-foreground">
            Pension contribution collection for PFAs — employee and employer
            contributions per PenCom guidelines
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Collected
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                NGN {(analytics.data?.totalVolume ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Contributions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.totalContributions ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Commission
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                NGN {(analytics.data?.totalCommission ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Active PFAs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {pfas.data?.pfas?.length ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="flex gap-2">
          <Button
            variant={tab === "contributions" ? "default" : "outline"}
            onClick={() => setTab("contributions")}
          >
            <FileText className="h-4 w-4 mr-1" />
            Contributions
          </Button>
          <Button
            variant={tab === "pfas" ? "default" : "outline"}
            onClick={() => setTab("pfas")}
          >
            <Landmark className="h-4 w-4 mr-1" />
            PFAs
          </Button>
          <Button
            variant={tab === "employers" ? "default" : "outline"}
            onClick={() => setTab("employers")}
          >
            <Users className="h-4 w-4 mr-1" />
            Employers
          </Button>
        </div>

        {tab === "contributions" && (
          <Card>
            <CardHeader>
              <CardTitle>Recent Contributions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">RSA PIN</th>
                      <th className="text-left p-2">Contributor</th>
                      <th className="text-left p-2">PFA</th>
                      <th className="text-left p-2">Type</th>
                      <th className="text-right p-2">Employee</th>
                      <th className="text-right p-2">Employer</th>
                      <th className="text-left p-2">Period</th>
                      <th className="text-left p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {contributions.data?.contributions?.map((c: any) => (
                      <tr key={c.id} className="border-b">
                        <td className="p-2 font-mono text-xs">{c.rsaPin}</td>
                        <td className="p-2">{c.contributorName}</td>
                        <td className="p-2">{c.pfaName}</td>
                        <td className="p-2">
                          <Badge>{c.type}</Badge>
                        </td>
                        <td className="p-2 text-right">
                          NGN {c.employeeAmount?.toLocaleString()}
                        </td>
                        <td className="p-2 text-right">
                          NGN {c.employerAmount?.toLocaleString()}
                        </td>
                        <td className="p-2 text-xs">{c.period}</td>
                        <td className="p-2">
                          <Badge
                            variant={
                              c.status === "remitted"
                                ? "default"
                                : c.status === "collected"
                                  ? "secondary"
                                  : "destructive"
                            }
                          >
                            {c.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "pfas" && (
          <Card>
            <CardHeader>
              <CardTitle>Pension Fund Administrators</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {pfas.data?.pfas?.map((p: any) => (
                  <div key={p.id} className="border rounded p-3">
                    <p className="font-bold">{p.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {p.code} &bull; License: {p.licenseNo}
                    </p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs">
                        {p.contributorCount} contributors
                      </span>
                      <Badge variant={p.active ? "default" : "secondary"}>
                        {p.active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "employers" && (
          <Card>
            <CardHeader>
              <CardTitle>Registered Employers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Employer</th>
                      <th className="text-left p-2">RC Number</th>
                      <th className="text-right p-2">Employees</th>
                      <th className="text-right p-2">Total Contributed</th>
                      <th className="text-left p-2">Compliance</th>
                      <th className="text-left p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {employers.data?.contributions?.map((e: any) => (
                      <tr key={e.id} className="border-b">
                        <td className="p-2">{e.name}</td>
                        <td className="p-2 font-mono text-xs">{e.rcNumber}</td>
                        <td className="p-2 text-right">{e.employeeCount}</td>
                        <td className="p-2 text-right font-bold">
                          NGN {e.totalContributed?.toLocaleString()}
                        </td>
                        <td className="p-2">
                          <Badge
                            variant={e.compliant ? "default" : "destructive"}
                          >
                            {e.compliant ? "Compliant" : "Non-Compliant"}
                          </Badge>
                        </td>
                        <td className="p-2">
                          <Badge variant={e.active ? "default" : "secondary"}>
                            {e.active ? "Active" : "Inactive"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
