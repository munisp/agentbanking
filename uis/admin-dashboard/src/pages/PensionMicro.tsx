import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { trpc } from "@/lib/trpc";

const statusVariant: Record<string, string> = {
  active: "default",
  dormant: "secondary",
  matured: "outline",
  withdrawn: "outline",
};

export default function PensionMicroPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const statsQuery = trpc.pensionMicro.getStats.useQuery();
  const listQuery = trpc.pensionMicro.list.useQuery({
    limit,
    offset: page * limit,
    search: search || undefined,
  });
  const analyticsQuery = trpc.pensionMicro.analytics.useQuery();
  const healthQuery = trpc.pensionMicro.serviceHealth.useQuery();

  const stats = statsQuery.data;
  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Pension Micro-Contributions</h1>
            <p className="text-muted-foreground">
              Informal sector micro-pension through agents — PenCom compliant
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm">
              Open Account
            </Button>
            <Button variant="outline" size="sm">
              Record Contribution
            </Button>
            <Button variant="outline" size="sm">
              PenCom Report
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Pension Accounts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.totalAccounts ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Contributions (₦)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.totalContributions ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Avg Monthly (₦)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.avgMonthlyContrib ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Withdrawals
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.withdrawalRequests ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
        </div>

        {healthQuery.data && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Service Health
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 flex-wrap">
                {healthQuery.data.services.map(svc => (
                  <Badge
                    key={svc.name}
                    variant={
                      svc.status === "healthy" ? "default" : "destructive"
                    }
                  >
                    {svc.name}: {svc.status}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {analyticsQuery.data && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Analytics by Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4 flex-wrap">
                {Object.entries(analyticsQuery.data.byStatus || {}).map(
                  ([status, cnt]) => (
                    <div key={status} className="text-center">
                      <Badge
                        variant={(statusVariant[status] as any) || "secondary"}
                      >
                        {status}
                      </Badge>
                      <p className="text-lg font-bold mt-1">{String(cnt)}</p>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Records</CardTitle>
              <Input
                placeholder="Search..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="max-w-xs"
              />
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="px-4 py-2 text-left font-medium">
                      Account ID
                    </th>
                    <th className="px-4 py-2 text-left font-medium">
                      Account Holder
                    </th>
                    <th className="px-4 py-2 text-left font-medium">
                      Balance (₦)
                    </th>
                    <th className="px-4 py-2 text-left font-medium">
                      Monthly (₦)
                    </th>
                    <th className="px-4 py-2 text-left font-medium">Status</th>
                    <th className="px-4 py-2 text-left font-medium">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="px-4 py-8 text-center text-muted-foreground"
                      >
                        No records found
                      </td>
                    </tr>
                  ) : (
                    items.map((item: any) => (
                      <tr key={item.id} className="border-b hover:bg-muted/50">
                        <td className="px-4 py-2">
                          {String(item.id ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          {String(item.holderName ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          {String(item.balance ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          {String(item.monthlyContrib ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          <Badge
                            variant={
                              (statusVariant[item.status as string] as any) ||
                              "secondary"
                            }
                          >
                            {String(item.status ?? "\u2014")}
                          </Badge>
                        </td>
                        <td className="px-4 py-2">
                          {String(item.startedAt ?? "\u2014")}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Showing {page * limit + 1}\u2013
                {Math.min((page + 1) * limit, total)} of {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={(page + 1) * limit >= total}
                >
                  Next
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
