/**
 * SuperAdminPortal.tsx
 *
 * Multi-tenant super admin portal accessible at /super-admin.
 * Uses the tRPC superAdmin router (nested procedures):
 *   - superAdmin.tenants.list
 *   - superAdmin.analytics.overview
 *
 * Role guard: only admin users can access this route.
 */
import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { usePosStore } from "../store/posStore";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  Building2,
  Users,
  Globe,
  Shield,
  BarChart3,
  Activity,
  ChevronLeft,
  Plus,
  Search,
  CheckCircle,
  XCircle,
  Clock,
  Server,
  Database,
  Cpu,
  Wifi,
  Edit,
  RefreshCw,
  FileText,
} from "lucide-react";

const fmt = (n: number | string) =>
  Number(n).toLocaleString("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  });

export default function SuperAdminPortal() {
  const agent = usePosStore(s => s.agent);
  const [, navigate] = useLocation();
  const [tab, setTab] = useState("tenants");
  const [search, setSearch] = useState("");
  const [tenantPage, setTenantPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTenant, setEditTenant] = useState<any>(null);
  const [form, setForm] = useState({
    slug: "",
    name: "",
    contactEmail: "",
    contactPhone: "",
    country: "NGA",
    currency: "NGN",
  });
  const [editForm, setEditForm] = useState({
    name: "",
    status: "active",
    contactEmail: "",
    contactPhone: "",
  });

  // Role guard — only admin
  useEffect(() => {
    if (agent && agent.role !== "admin") {
      navigate("/");
    }
  }, [agent, navigate]);

  const utils = trpc.useUtils();

  const tenantsQuery = trpc.superAdmin.tenants.list.useQuery(
    {
      page: tenantPage,
      limit: 20,
      search: search || undefined,
      status: statusFilter !== "all" ? (statusFilter as any) : undefined,
    },
    { enabled: tab === "tenants", retry: false }
  );
  const analyticsQuery = trpc.superAdmin.analytics.overview.useQuery(
    undefined,
    { enabled: tab === "analytics", retry: false }
  );
  const complianceQ = trpc.superAdmin.compliance.reports.useQuery(
    { page: 1, limit: 20 },
    { enabled: tab === "compliance", retry: false }
  );
  const auditQ = trpc.superAdmin.audit.list.useQuery(
    { page: 1, limit: 50 },
    { enabled: tab === "audit", retry: false }
  );
  const healthQ = trpc.superAdmin.health.overview.useQuery(undefined, {
    enabled: tab === "health",
    retry: false,
  });

  const tenants = tenantsQuery.data?.items ?? [];
  const pStats = analyticsQuery.data ?? {
    tenants: 0,
    agents: 0,
    transactions: 0,
    volume: "0",
    fraudAlerts: 0,
  };

  // Mutations
  const createTenant = trpc.superAdmin.tenants.create.useMutation({
    onSuccess: t => {
      toast.success("Tenant created", {
        description: `${t.name} is now live.`,
      });
      utils.superAdmin.tenants.list.invalidate();
      setCreateOpen(false);
      setForm({
        slug: "",
        name: "",
        contactEmail: "",
        contactPhone: "",
        country: "NGA",
        currency: "NGN",
      });
    },
    onError: e => toast.error("Create failed", { description: e.message }),
  });
  const updateTenant = trpc.superAdmin.tenants.update.useMutation({
    onSuccess: () => {
      toast.success("Tenant updated");
      utils.superAdmin.tenants.list.invalidate();
      setEditTenant(null);
    },
    onError: e => toast.error("Update failed", { description: e.message }),
  });
  const suspendTenant = trpc.superAdmin.tenants.suspend.useMutation({
    onSuccess: () => {
      toast.success("Tenant suspended");
      utils.superAdmin.tenants.list.invalidate();
    },
    onError: e => toast.error("Error", { description: e.message }),
  });
  const activateTenant = trpc.superAdmin.tenants.activate.useMutation({
    onSuccess: () => {
      toast.success("Tenant activated");
      utils.superAdmin.tenants.list.invalidate();
    },
    onError: e => toast.error("Error", { description: e.message }),
  });

  const statusIcon = (status: string) => {
    if (status === "active")
      return <CheckCircle size={12} className="text-green-500" />;
    if (status === "suspended")
      return <XCircle size={12} className="text-red-500" />;
    return <Clock size={12} className="text-yellow-500" />;
  };

  const NAV_ITEMS = [
    { id: "tenants", icon: <Building2 size={14} />, label: "Tenants" },
    { id: "agents", icon: <Users size={14} />, label: "All Agents" },
    { id: "analytics", icon: <BarChart3 size={14} />, label: "Analytics" },
    { id: "compliance", icon: <Shield size={14} />, label: "Compliance" },
    { id: "network", icon: <Globe size={14} />, label: "Network" },
    {
      id: "infrastructure",
      icon: <Server size={14} />,
      label: "Infrastructure",
    },
  ];

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-card border-r border-border flex flex-col">
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Globe size={16} className="text-primary" />
            <div>
              <h1 className="text-xs font-bold text-primary">Super Admin</h1>
              <p className="text-xs text-muted-foreground">Platform Control</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV_ITEMS.map((item: any) => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-colors text-left ${
                tab === item.id
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-border">
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-xs"
            onClick={() => navigate("/")}
          >
            <ChevronLeft size={12} className="mr-1" /> Back to POS
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <div className="sticky top-0 z-10 bg-card border-b border-border px-6 py-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold capitalize">{tab}</h2>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              <Activity size={10} className="mr-1" /> Live
            </Badge>
            <span className="text-xs text-muted-foreground">
              {new Date().toLocaleTimeString()}
            </span>
          </div>
        </div>

        <div className="p-6 space-y-6">
          {/* Platform stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              {
                label: "Tenants",
                value: pStats.tenants,
                icon: <Building2 size={16} />,
              },
              {
                label: "Fraud Alerts",
                value: pStats.fraudAlerts,
                icon: <Shield size={16} />,
              },
              {
                label: "Total Agents",
                value: pStats.agents,
                icon: <Users size={16} />,
              },
              {
                label: "Transactions",
                value: Number(pStats.transactions).toLocaleString(),
                icon: <Activity size={16} />,
              },
              {
                label: "Volume (NGN)",
                value: `₦${Number(pStats.volume).toLocaleString()}`,
                icon: <BarChart3 size={16} />,
              },
            ].map((stat: any) => (
              <Card key={stat.label}>
                <CardContent className="p-3 flex items-center gap-2">
                  <span className="text-primary">{stat.icon}</span>
                  <div>
                    <p className="text-xs text-muted-foreground">
                      {stat.label}
                    </p>
                    <p className="text-sm font-bold">{stat.value}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Tab content */}
          {tab === "tenants" && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Building2 size={14} className="text-primary" /> Tenant
                    Management
                  </CardTitle>
                  <div className="flex gap-2">
                    <Select
                      value={statusFilter}
                      onValueChange={v => {
                        setStatusFilter(v);
                        setTenantPage(1);
                      }}
                    >
                      <SelectTrigger className="h-7 text-xs w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {["all", "trial", "active", "suspended", "churned"].map(
                          s => (
                            <SelectItem
                              key={s}
                              value={s}
                              className="text-xs capitalize"
                            >
                              {s}
                            </SelectItem>
                          )
                        )}
                      </SelectContent>
                    </Select>
                    <Button
                      size="sm"
                      className="text-xs gap-1 h-7"
                      onClick={() => setCreateOpen(true)}
                    >
                      <Plus size={12} /> Add Tenant
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7"
                      onClick={() => tenantsQuery.refetch()}
                    >
                      <RefreshCw
                        size={12}
                        className={
                          tenantsQuery.isFetching ? "animate-spin" : ""
                        }
                      />
                    </Button>
                  </div>
                </div>
                <div className="relative mt-2">
                  <Search
                    size={12}
                    className="absolute left-2.5 top-2.5 text-muted-foreground"
                  />
                  <Input
                    placeholder="Search tenants…"
                    className="pl-7 text-xs h-8"
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                  />
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {tenantsQuery.isLoading ? (
                  <div className="p-4 text-xs text-muted-foreground text-center">
                    Loading tenants…
                  </div>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left p-3 text-muted-foreground font-medium">
                          Tenant
                        </th>
                        <th className="text-left p-3 text-muted-foreground font-medium">
                          Slug
                        </th>
                        <th className="text-left p-3 text-muted-foreground font-medium">
                          Country
                        </th>
                        <th className="text-left p-3 text-muted-foreground font-medium">
                          Status
                        </th>
                        <th className="text-right p-3 text-muted-foreground font-medium">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {tenants.map((t: any) => (
                        <tr
                          key={t.id}
                          className="border-b border-border/50 hover:bg-accent/30"
                        >
                          <td className="p-3 font-medium">{t.name}</td>
                          <td className="p-3 font-mono text-muted-foreground">
                            {t.slug}
                          </td>
                          <td className="p-3">{t.country ?? "NGA"}</td>
                          <td className="p-3">
                            <div className="flex items-center gap-1">
                              {statusIcon(t.status ?? "active")}
                              <span className="capitalize">
                                {t.status ?? "active"}
                              </span>
                            </div>
                          </td>
                          <td className="p-3 text-right">
                            <div className="flex gap-1 justify-end">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-xs h-6 px-2 gap-1"
                                onClick={() => {
                                  setEditTenant(t);
                                  setEditForm({
                                    name: t.name,
                                    status: t.status ?? "active",
                                    contactEmail: t.contactEmail ?? "",
                                    contactPhone: t.contactPhone ?? "",
                                  });
                                }}
                              >
                                <Edit size={10} /> Edit
                              </Button>
                              {(t.status ?? "active") !== "suspended" ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-xs h-6 px-2 text-destructive hover:text-destructive"
                                  onClick={() =>
                                    suspendTenant.mutate({
                                      id: t.id,
                                      reason: "Suspended via super-admin",
                                    })
                                  }
                                  disabled={suspendTenant.isPending}
                                >
                                  <XCircle size={10} />
                                </Button>
                              ) : (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-xs h-6 px-2 text-green-500 hover:text-green-400"
                                  onClick={() =>
                                    activateTenant.mutate({ id: t.id })
                                  }
                                  disabled={activateTenant.isPending}
                                >
                                  <CheckCircle size={10} />
                                </Button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                      {tenants.length === 0 && (
                        <tr>
                          <td
                            colSpan={5}
                            className="p-6 text-center text-muted-foreground"
                          >
                            {search
                              ? "No tenants match your search"
                              : "No tenants yet — add one to get started"}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                )}
              </CardContent>
              {/* Pagination */}
              <div className="flex items-center justify-between px-4 py-2 border-t border-border text-xs text-muted-foreground">
                <span>Total: {tenantsQuery.data?.total ?? 0}</span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-xs"
                    disabled={tenantPage <= 1}
                    onClick={() => setTenantPage(p => p - 1)}
                  >
                    Prev
                  </Button>
                  <span>Page {tenantPage}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-xs"
                    disabled={
                      !tenantsQuery.data ||
                      tenantPage * 20 >= tenantsQuery.data.total
                    }
                    onClick={() => setTenantPage(p => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {tab === "analytics" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Platform Analytics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  {[
                    { label: "Total Tenants", value: pStats.tenants },
                    { label: "Total Agents", value: pStats.agents },
                    {
                      label: "Total Transactions",
                      value: Number(pStats.transactions).toLocaleString(),
                    },
                    {
                      label: "Total Volume (NGN)",
                      value: `₦${Number(pStats.volume).toLocaleString()}`,
                    },
                  ].map((m: any) => (
                    <div key={m.label} className="rounded-lg bg-muted/30 p-3">
                      <p className="text-xs text-muted-foreground">{m.label}</p>
                      <p className="text-sm font-bold">{m.value}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {tab === "compliance" && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Shield size={14} className="text-primary" /> Compliance
                    Reports
                  </CardTitle>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1"
                    onClick={() => complianceQ.refetch()}
                  >
                    <RefreshCw
                      size={11}
                      className={complianceQ.isFetching ? "animate-spin" : ""}
                    />{" "}
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-3 text-muted-foreground">
                        Period
                      </th>
                      <th className="text-left p-3 text-muted-foreground">
                        Generated By
                      </th>
                      <th className="text-left p-3 text-muted-foreground">
                        Created
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {complianceQ.isLoading ? (
                      <tr>
                        <td
                          colSpan={3}
                          className="p-6 text-center text-muted-foreground"
                        >
                          Loading…
                        </td>
                      </tr>
                    ) : (complianceQ.data?.items ?? []).length === 0 ? (
                      <tr>
                        <td
                          colSpan={3}
                          className="p-6 text-center text-muted-foreground"
                        >
                          No compliance reports yet
                        </td>
                      </tr>
                    ) : (
                      (complianceQ.data?.items ?? []).map((r: any) => (
                        <tr
                          key={r.id}
                          className="border-b border-border/50 hover:bg-accent/30"
                        >
                          <td className="p-3">
                            {r.period ??
                              `${new Date(r.periodStart).toLocaleDateString()} – ${new Date(r.periodEnd).toLocaleDateString()}`}
                          </td>
                          <td className="p-3 text-muted-foreground">
                            {r.generatedBy ?? "system"}
                          </td>
                          <td className="p-3 text-muted-foreground">
                            {r.createdAt
                              ? new Date(r.createdAt).toLocaleString()
                              : "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {tab === "network" && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Globe size={14} className="text-primary" /> System Health
                  </CardTitle>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1"
                    onClick={() => healthQ.refetch()}
                  >
                    <RefreshCw
                      size={11}
                      className={healthQ.isFetching ? "animate-spin" : ""}
                    />{" "}
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {healthQ.isLoading ? (
                  <p className="text-xs text-muted-foreground">Checking…</p>
                ) : (
                  <div className="space-y-2">
                    {healthQ.data &&
                      Object.entries(healthQ.data.services ?? {}).map(
                        ([svc, st]: [string, any]) => (
                          <div
                            key={svc}
                            className="flex items-center justify-between py-2 border-b border-border/50 text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <Wifi
                                size={12}
                                className={
                                  st === "up"
                                    ? "text-green-500"
                                    : "text-red-500"
                                }
                              />
                              <span className="capitalize">
                                {svc.replace(/([A-Z])/g, " $1")}
                              </span>
                            </div>
                            <Badge
                              variant={st === "up" ? "default" : "destructive"}
                              className="text-xs"
                            >
                              {st}
                            </Badge>
                          </div>
                        )
                      )}
                    {healthQ.data && (
                      <p className="text-xs text-muted-foreground pt-2">
                        Uptime: {Math.floor((healthQ.data.uptime ?? 0) / 3600)}h{" "}
                        {Math.floor(((healthQ.data.uptime ?? 0) % 3600) / 60)}m
                        · Node {healthQ.data.nodeVersion} ·{" "}
                        {healthQ.data.environment}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {tab === "infrastructure" && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Activity size={14} className="text-primary" /> Audit Log
                  </CardTitle>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1"
                    onClick={() => auditQ.refetch()}
                  >
                    <RefreshCw
                      size={11}
                      className={auditQ.isFetching ? "animate-spin" : ""}
                    />{" "}
                    Refresh
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left p-3 text-muted-foreground">
                        Actor
                      </th>
                      <th className="text-left p-3 text-muted-foreground">
                        Action
                      </th>
                      <th className="text-left p-3 text-muted-foreground">
                        Resource
                      </th>
                      <th className="text-left p-3 text-muted-foreground">
                        Time
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditQ.isLoading ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="p-6 text-center text-muted-foreground"
                        >
                          Loading…
                        </td>
                      </tr>
                    ) : (auditQ.data?.items ?? []).length === 0 ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="p-6 text-center text-muted-foreground"
                        >
                          No audit entries yet
                        </td>
                      </tr>
                    ) : (
                      (auditQ.data?.items ?? []).map((e: any) => (
                        <tr
                          key={e.id}
                          className="border-b border-border/50 hover:bg-accent/30"
                        >
                          <td className="p-3 font-mono">
                            {e.actorId ?? e.agentId ?? "system"}
                          </td>
                          <td className="p-3">{e.action}</td>
                          <td className="p-3 text-muted-foreground">
                            {e.resourceType} #{e.resourceId}
                          </td>
                          <td className="p-3 text-muted-foreground">
                            {e.createdAt
                              ? new Date(e.createdAt).toLocaleString()
                              : "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          {tab === "agents" && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">All Platform Agents</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  Cross-tenant agent view available via the Management Portal at{" "}
                  <button
                    className="text-primary underline"
                    onClick={() => navigate("/management")}
                  >
                    /management
                  </button>
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </main>

      {/* Create Tenant Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {(["name", "slug", "contactEmail", "contactPhone"] as const).map(
              (key: any) => (
                <div key={key}>
                  <Label className="text-xs text-muted-foreground capitalize">
                    {key.replace(/([A-Z])/g, " $1")}
                  </Label>
                  <Input
                    className="mt-1 h-8 text-sm"
                    value={(form as any)[key]}
                    onChange={e =>
                      setForm(f => ({ ...f, [key]: e.target.value }))
                    }
                  />
                </div>
              )
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs text-muted-foreground">
                  Country (ISO3)
                </Label>
                <Input
                  className="mt-1 h-8 text-sm"
                  value={form.country}
                  onChange={e =>
                    setForm(f => ({
                      ...f,
                      country: e.target.value.toUpperCase().slice(0, 3),
                    }))
                  }
                />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">
                  Currency (ISO3)
                </Label>
                <Input
                  className="mt-1 h-8 text-sm"
                  value={form.currency}
                  onChange={e =>
                    setForm(f => ({
                      ...f,
                      currency: e.target.value.toUpperCase().slice(0, 3),
                    }))
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => createTenant.mutate(form as any)}
              disabled={
                createTenant.isPending ||
                !form.slug ||
                !form.name ||
                !form.contactEmail
              }
            >
              {createTenant.isPending ? "Creating…" : "Create Tenant"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Tenant Dialog */}
      <Dialog open={!!editTenant} onOpenChange={o => !o && setEditTenant(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit — {editTenant?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-xs text-muted-foreground">Name</Label>
              <Input
                className="mt-1 h-8 text-sm"
                value={editForm.name}
                onChange={e =>
                  setEditForm(f => ({ ...f, name: e.target.value }))
                }
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">Status</Label>
              <Select
                value={editForm.status}
                onValueChange={v => setEditForm(f => ({ ...f, status: v }))}
              >
                <SelectTrigger className="mt-1 h-8 text-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["trial", "active", "suspended", "churned"].map(s => (
                    <SelectItem
                      key={s}
                      value={s}
                      className="text-xs capitalize"
                    >
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">
                Contact Email
              </Label>
              <Input
                className="mt-1 h-8 text-sm"
                value={editForm.contactEmail}
                onChange={e =>
                  setEditForm(f => ({ ...f, contactEmail: e.target.value }))
                }
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground">
                Contact Phone
              </Label>
              <Input
                className="mt-1 h-8 text-sm"
                value={editForm.contactPhone}
                onChange={e =>
                  setEditForm(f => ({ ...f, contactPhone: e.target.value }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditTenant(null)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                updateTenant.mutate({
                  id: editTenant.id,
                  name: editForm.name,
                  status: editForm.status as any,
                  contactEmail: editForm.contactEmail,
                  contactPhone: editForm.contactPhone,
                })
              }
              disabled={updateTenant.isPending}
            >
              {updateTenant.isPending ? "Saving…" : "Save Changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
