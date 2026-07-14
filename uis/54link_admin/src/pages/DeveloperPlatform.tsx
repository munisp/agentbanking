import { toast } from 'sonner';
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
// ...existing code...
import type {
  MarketplaceStats,
  PlatformOverview,
} from "@/types/developerPlatform";
import {
  Activity,
  AlertCircle,
  AppWindow,
  Building2,
  // ...existing code...
  DollarSign,
  Shield,
  TrendingUp,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";

export default function DeveloperPlatformDashboard() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platformOverview, setPlatformOverview] =
    useState<PlatformOverview | null>(null);
  const [marketplaceStats, setMarketplaceStats] =
    useState<MarketplaceStats | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Use mock data for now
      setTimeout(() => {
        setPlatformOverview({
          period: "month",
          date_range: {
            start: "2026-01-01",
            end: "2026-01-29",
          },
          metrics: {
            total_api_calls: 5000000,
            successful_calls: 4950000,
            failed_calls: 50000,
            average_latency_ms: 120,
            uptime_percentage: 99.95,
            active_developers: 140,
            new_developers: 10,
            active_apps: 280,
            new_apps: 5,
            total_installations: 12000,
            new_installations: 200,
            gmv: 500000000,
            platform_revenue: 25000000,
          },
          growth: {
            api_calls: 5,
            developers: 2,
            apps: 1,
            revenue: 8.2,
          },
          top_performers: {
            most_popular_apps: [],
            highest_revenue_apps: [],
            most_active_developers: [],
          },
        });
        setMarketplaceStats({
          total_apps: 320,
          published_apps: 250,
          pending_review: 12,
          featured_apps: 5,
          total_installations: 12000,
          active_installations: 11000,
          total_developers: 150,
          active_developers: 140,
          categories: [
            { category: "Payments", app_count: 80, installations: 4000 },
            { category: "Lending", app_count: 50, installations: 2500 },
            { category: "KYC/Compliance", app_count: 30, installations: 1800 },
            { category: "Analytics", app_count: 40, installations: 2000 },
            { category: "Utilities", app_count: 20, installations: 700 },
          ],
          top_apps: [
            {
              app_id: "app1",
              name: "PayLink",
              installations: 1800,
              rating: 4.8,
            },
            {
              app_id: "app2",
              name: "QuickLoan",
              installations: 1500,
              rating: 4.6,
            },
            {
              app_id: "app3",
              name: "KYCPro",
              installations: 1200,
              rating: 4.7,
            },
            {
              app_id: "app4",
              name: "Insight360",
              installations: 1100,
              rating: 4.5,
            },
            {
              app_id: "app5",
              name: "UtilityHub",
              installations: 900,
              rating: 4.4,
            },
          ],
          revenue: {
            monthly_gmv: 500000000,
            platform_fees: 25000000,
            growth_percentage: 8.2,
          },
        });
        setLoading(false);
      }, 500);

      // Uncomment when ready to use real API:
      // const overview = await developerPlatformService.getPlatformOverview({
      //   period: "month",
      // });
      // setPlatformOverview(overview);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load dashboard data";
      setError(message);
      console.error("Error loading dashboard:", err);
      toast.error(message);
      setLoading(false);
    }
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={loadDashboardData} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Developer Platform</h1>
          <p className="text-muted-foreground">
            Manage developers, apps, and marketplace ecosystem
          </p>
        </div>
        <Button onClick={loadDashboardData} variant="outline">
          <Activity className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Key Metrics */}
      {platformOverview && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Developers"
            value={platformOverview.metrics.active_developers}
            icon={Users}
            subtitle="Active developers"
          />
          <StatCard
            title="Organizations"
            value={platformOverview.metrics.total_installations}
            icon={Building2}
            subtitle="Total installations"
          />
          <StatCard
            title="Total Apps"
            value={platformOverview.metrics.active_apps}
            icon={AppWindow}
            subtitle={`${platformOverview.metrics.active_apps} active`}
          />
          <StatCard
            title="Monthly Revenue"
            value={`₦${(platformOverview.metrics.platform_revenue / 100).toLocaleString()}`}
            icon={DollarSign}
            subtitle="This month"
          />
        </div>
      )}

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="developers">Developers</TabsTrigger>
          <TabsTrigger value="apps">Apps</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {platformOverview && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>API Usage</CardTitle>
                  <CardDescription>This month</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {platformOverview.metrics.total_api_calls.toLocaleString()}
                  </div>
                  <p className="text-xs text-muted-foreground">API calls</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Pending Reviews</CardTitle>
                  <CardDescription>Apps awaiting approval</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {/* No pending_reviews in PlatformOverview, so show 0 or placeholder */}
                    0
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Apps in review queue
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Active Apps</CardTitle>
                  <CardDescription>Currently running</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {platformOverview.metrics.active_apps}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    of {platformOverview.metrics.active_apps} total
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="developers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Developer Statistics</CardTitle>
              <CardDescription>Overview of developer activity</CardDescription>
            </CardHeader>
            <CardContent>
              {platformOverview && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">
                      Active Developers
                    </span>
                    <span className="text-2xl font-bold">
                      {platformOverview.metrics.active_developers}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">
                      Total Installations
                    </span>
                    <span className="text-2xl font-bold">
                      {platformOverview.metrics.total_installations}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="apps" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>App Statistics</CardTitle>
              <CardDescription>Overview of application status</CardDescription>
            </CardHeader>
            <CardContent>
              {platformOverview && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Active Apps</span>
                    <span className="text-2xl font-bold">
                      {platformOverview.metrics.active_apps}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Total Apps</span>
                    <span className="text-2xl font-bold">
                      {/* No total_apps in PlatformOverview, so show active_apps as placeholder */}
                      {platformOverview.metrics.active_apps}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Pending Reviews</span>
                    <span className="text-2xl font-bold">0</span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Demo Marketplace Apps Data */}
          {marketplaceStats && (
            <Card>
              <CardHeader>
                <CardTitle>Marketplace Overview (Demo Data)</CardTitle>
                <CardDescription>
                  Key marketplace app stats and top apps
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <div className="mb-2 font-semibold">Categories</div>
                    <ul className="text-sm space-y-1">
                      {marketplaceStats.categories.map((cat) => (
                        <li key={cat.category}>
                          <span className="font-medium">{cat.category}:</span>{" "}
                          {cat.app_count} apps, {cat.installations} installs
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="mb-2 font-semibold">Top Apps</div>
                    <ul className="text-sm space-y-1">
                      {marketplaceStats.top_apps.map((app) => (
                        <li key={app.app_id}>
                          <span className="font-medium">{app.name}</span> —{" "}
                          {app.installations} installs, ⭐ {app.rating}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="mt-4 grid md:grid-cols-3 gap-4">
                  <div>
                    <span className="font-medium">Published Apps:</span>{" "}
                    {marketplaceStats.published_apps}
                  </div>
                  <div>
                    <span className="font-medium">Featured Apps:</span>{" "}
                    {marketplaceStats.featured_apps}
                  </div>
                  <div>
                    <span className="font-medium">Active Installations:</span>{" "}
                    {marketplaceStats.active_installations}
                  </div>
                </div>
                <div className="mt-4">
                  <span className="font-medium">Monthly GMV:</span> ₦
                  {(
                    marketplaceStats.revenue.monthly_gmv / 100
                  ).toLocaleString()}
                  <br />
                  <span className="font-medium">Platform Fees:</span> ₦
                  {(
                    marketplaceStats.revenue.platform_fees / 100
                  ).toLocaleString()}
                  <br />
                  <span className="font-medium">Growth:</span>{" "}
                  {marketplaceStats.revenue.growth_percentage}%
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="activity" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Platform Activity</CardTitle>
              <CardDescription>Recent platform metrics</CardDescription>
            </CardHeader>
            <CardContent>
              {platformOverview && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">
                      Monthly API Calls
                    </span>
                    <span className="text-2xl font-bold">
                      {platformOverview.metrics.total_api_calls.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">Monthly Revenue</span>
                    <span className="text-2xl font-bold">
                      ₦
                      {(
                        platformOverview.metrics.platform_revenue / 100
                      ).toLocaleString()}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
            <Button variant="outline" className="justify-start" asChild>
              <a href="/developer-platform/developers">
                <Users className="mr-2 h-4 w-4" />
                Manage Developers
              </a>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <a href="/developer-platform/organizations">
                <Building2 className="mr-2 h-4 w-4" />
                Organizations
              </a>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <a href="/developer-platform/apps">
                <AppWindow className="mr-2 h-4 w-4" />
                Review Apps
              </a>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <a href="/developer-platform/security">
                <Shield className="mr-2 h-4 w-4" />
                Security Scans
              </a>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <a href="/developer-platform/analytics">
                <TrendingUp className="mr-2 h-4 w-4" />
                Analytics
              </a>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  trend?: number;
}

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
}: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            {subtitle}
            {trend !== undefined && (
              <Badge
                variant={trend > 0 ? "default" : "secondary"}
                className="ml-2 text-xs"
              >
                {trend > 0 ? "+" : ""}
                {trend}%
              </Badge>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function DashboardSkeleton() {
  return (
    <div className="p-6 space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <Skeleton className="h-96" />
    </div>
  );
}
