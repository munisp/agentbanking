import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const statusVariant: Record<string, string> = {
  confirmed: "default",
  pending: "secondary",
  failed: "destructive",
  processing: "outline",
};

export default function StablecoinRailsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const statsQuery = {data: null, isLoading: false, refetch: () => {}};
  const listQuery = {data: null, isLoading: false, refetch: () => {}};
  const analyticsQuery = {data: null, isLoading: false, refetch: () => {}};
  const healthQuery = {data: null, isLoading: false, refetch: () => {}};

  const stats = statsQuery.data;
  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Stablecoin Rails</h1>
            <p className="text-muted-foreground">
              cNGN stablecoin for instant settlement and cross-border remittance
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm">
              Create Wallet
            </Button>
            <Button variant="outline" size="sm">
              Transfer
            </Button>
            <Button variant="outline" size="sm">
              Mint cNGN
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Wallets
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.totalWallets ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                cNGN Supply
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.circulatingSupply ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Daily Volume (₦)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.dailyVolume ?? "\u2014")}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Peg Deviation
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {String(stats?.pegDeviation ?? "\u2014")}
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
                    <th className="px-4 py-2 text-left font-medium">Txn ID</th>
                    <th className="px-4 py-2 text-left font-medium">From</th>
                    <th className="px-4 py-2 text-left font-medium">To</th>
                    <th className="px-4 py-2 text-left font-medium">
                      Amount (₦)
                    </th>
                    <th className="px-4 py-2 text-left font-medium">Type</th>
                    <th className="px-4 py-2 text-left font-medium">Status</th>
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
                          {String(item.fromWallet ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          {String(item.toWallet ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          {String(item.amount ?? "\u2014")}
                        </td>
                        <td className="px-4 py-2">
                          {String(item.type ?? "\u2014")}
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
