import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { useAuth } from "@/_core/hooks/useAuth";
import { getLoginUrl } from "@/const";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { Users, Gift, TrendingUp, Search } from "lucide-react";

export default function ReferralProgram() {
  const { loading, isAuthenticated } = useAuth();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  const utils = trpc.useUtils();
  const { data, isLoading } = trpc.referrals.list.useQuery({
    page,
    limit: 20,
    status: statusFilter === "all" ? undefined : (statusFilter as any),
    search: search || undefined,
  });
  const { data: stats } = trpc.referrals.stats.useQuery();

  const rewardMutation = trpc.referrals.markRewarded.useMutation({
    onSuccess: () => {
      utils.referrals.list.invalidate();
      utils.referrals.stats.invalidate();
      toast.success("Referral marked as rewarded");
    },
    onError: e => toast.error(e.message),
  });

  if (loading)
    return (
      <div className="flex items-center justify-center h-screen">
        Loading...
      </div>
    );
  if (!isAuthenticated) {
    window.location.href = getLoginUrl();
    return null;
  }

  const statusColor = (s: string) =>
    s === "activated"
      ? "bg-blue-100 text-blue-800"
      : s === "rewarded"
        ? "bg-green-100 text-green-800"
        : s === "expired"
          ? "bg-gray-100 text-gray-600"
          : "bg-yellow-100 text-yellow-800";

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Referral Program
          </h1>
          <p className="text-muted-foreground text-sm">
            Track agent referrals, activations, and reward disbursements
          </p>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Total Referrals", value: stats.total, icon: Users },
              {
                label: "Activated",
                value: stats.activated,
                icon: TrendingUp,
                color: "text-blue-600",
              },
              {
                label: "Rewarded",
                value: stats.rewarded,
                icon: Gift,
                color: "text-green-600",
              },
              {
                label: "Total Rewards (₦)",
                value: `₦${Number(stats.totalRewardAmount ?? 0).toLocaleString()}`,
                icon: Gift,
                color: "text-green-600",
              },
            ].map((s: any) => (
              <Card key={s.label}>
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2">
                    <s.icon
                      className={`w-4 h-4 ${s.color ?? "text-muted-foreground"}`}
                    />
                    <p className="text-xs text-muted-foreground">{s.label}</p>
                  </div>
                  <p className={`text-xl font-bold mt-1 ${s.color ?? ""}`}>
                    {s.value}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <div className="relative flex-1 min-w-48">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search referrer or referee..."
              value={search}
              onChange={e => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <Select
            value={statusFilter}
            onValueChange={v => {
              setStatusFilter(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="activated">Activated</SelectItem>
              <SelectItem value="rewarded">Rewarded</SelectItem>
              <SelectItem value="expired">Expired</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <Card>
          <CardHeader>
            <CardTitle>Referral Records ({data?.total ?? 0})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs">
                    <th className="text-left py-2 px-3">Referrer</th>
                    <th className="text-left py-2 px-3">Referee</th>
                    <th className="text-right py-2 px-3">Reward (₦)</th>
                    <th className="text-left py-2 px-3">Status</th>
                    <th className="text-left py-2 px-3">Activated</th>
                    <th className="text-left py-2 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading && (
                    <tr>
                      <td
                        colSpan={6}
                        className="text-center py-8 text-muted-foreground"
                      >
                        Loading...
                      </td>
                    </tr>
                  )}
                  {!isLoading &&
                    data?.items.map((r: any) => (
                      <tr key={r.id} className="border-b hover:bg-muted/30">
                        <td className="py-2 px-3">
                          <p className="font-medium text-sm">
                            {r.referrerCode}
                          </p>
                        </td>
                        <td className="py-2 px-3">
                          <p className="text-sm">{r.refereeCode ?? "—"}</p>
                          <p className="text-xs text-muted-foreground font-mono">
                            {r.referralCode}
                          </p>
                        </td>
                        <td className="py-2 px-3 text-right font-mono">
                          {r.bonusCash
                            ? `₦${Number(r.bonusCash).toLocaleString()}`
                            : "—"}
                        </td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(r.status)}`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-xs text-muted-foreground">
                          {r.activatedAt
                            ? new Date(r.activatedAt).toLocaleDateString()
                            : "—"}
                        </td>
                        <td className="py-2 px-3">
                          {r.status === "activated" && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs text-green-700 border-green-300"
                              onClick={() =>
                                rewardMutation.mutate({ id: r.id })
                              }
                              disabled={rewardMutation.isPending}
                            >
                              Mark Rewarded
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  {!isLoading && data?.items.length === 0 && (
                    <tr>
                      <td
                        colSpan={6}
                        className="text-center py-8 text-muted-foreground"
                      >
                        No referral records found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {data && data.total > 20 && (
              <div className="flex justify-between items-center pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(p => p - 1)}
                >
                  Previous
                </Button>
                <span className="text-xs text-muted-foreground">
                  Page {page} of {Math.ceil(data.total / 20)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * 20 >= data.total}
                  onClick={() => setPage(p => p + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
