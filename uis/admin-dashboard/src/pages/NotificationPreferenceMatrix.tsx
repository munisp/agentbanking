import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import {
  Bell,
  Mail,
  MessageSquare,
  Smartphone,
  RotateCcw,
  Save,
  Shield,
  AlertTriangle,
  CreditCard,
  Settings,
  FileCheck,
  BarChart3,
  Globe,
} from "lucide-react";

const CATEGORY_META: Record<
  string,
  { label: string; icon: React.ReactNode; description: string }
> = {
  rate_alert: {
    label: "Rate Alerts",
    icon: <BarChart3 className="w-4 h-4" />,
    description: "Exchange rate threshold notifications",
  },
  fraud: {
    label: "Fraud",
    icon: <AlertTriangle className="w-4 h-4" />,
    description: "Fraud detection and resolution alerts",
  },
  transaction: {
    label: "Transactions",
    icon: <CreditCard className="w-4 h-4" />,
    description: "Payment and transfer notifications",
  },
  security: {
    label: "Security",
    icon: <Shield className="w-4 h-4" />,
    description: "Account security and access alerts",
  },
  system: {
    label: "System",
    icon: <Settings className="w-4 h-4" />,
    description: "Platform maintenance and outage alerts",
  },
  settlement: {
    label: "Settlement",
    icon: <FileCheck className="w-4 h-4" />,
    description: "Daily settlement and reconciliation",
  },
  kyc: {
    label: "KYC/KYB",
    icon: <Globe className="w-4 h-4" />,
    description: "Identity verification status updates",
  },
  compliance: {
    label: "Compliance",
    icon: <Shield className="w-4 h-4" />,
    description: "Regulatory compliance alerts",
  },
  general: {
    label: "General",
    icon: <Bell className="w-4 h-4" />,
    description: "General platform notifications",
  },
};

const CHANNEL_META: Record<string, { label: string; icon: React.ReactNode }> = {
  email: { label: "Email", icon: <Mail className="w-4 h-4" /> },
  sms: { label: "SMS", icon: <Smartphone className="w-4 h-4" /> },
  push: { label: "Push", icon: <Bell className="w-4 h-4" /> },
  in_app: { label: "In-App", icon: <MessageSquare className="w-4 h-4" /> },
};

const CATEGORIES = [
  "rate_alert",
  "fraud",
  "transaction",
  "security",
  "system",
  "settlement",
  "kyc",
  "compliance",
  "general",
] as const;
const CHANNELS = ["email", "sms", "push", "in_app"] as const;

export default function NotificationPreferenceMatrix() {
  const [agentId] = useState(1);
  const [pendingChanges, setPendingChanges] = useState<Map<string, boolean>>(
    new Map()
  );

  // @ts-ignore Sprint 85
  const matrixQuery = trpc.production.prefMatrix.getMatrix.useQuery({
    agentId,
  });
  // @ts-ignore Sprint 85
  const bulkUpdate = trpc.production.prefMatrix.bulkUpdate.useMutation({
    onSuccess: () => {
      toast.success("Preferences saved");
      setPendingChanges(new Map());
      matrixQuery.refetch();
    },
    onError: () => toast.error("Failed to save preferences"),
  });
  // @ts-ignore Sprint 85
  const resetMut = trpc.production.prefMatrix.resetToDefaults.useMutation({
    onSuccess: () => {
      toast.success("Reset to defaults");
      setPendingChanges(new Map());
      matrixQuery.refetch();
    },
  });

  const matrix = matrixQuery.data;

  function getValue(cat: string, ch: string): boolean {
    const key = `${cat}:${ch}`;
    if (pendingChanges.has(key)) return pendingChanges.get(key)!;
    return matrix?.[cat]?.[ch] ?? false;
  }

  function toggle(cat: string, ch: string) {
    const key = `${cat}:${ch}`;
    const current = getValue(cat, ch);
    setPendingChanges(prev => {
      const n = new Map(prev);
      n.set(key, !current);
      return n;
    });
  }

  function saveAll() {
    const updates = Array.from(pendingChanges.entries()).map(
      ([key, enabled]) => {
        const [category, channel] = key.split(":");
        return {
          category: category as (typeof CATEGORIES)[number],
          channel: channel as (typeof CHANNELS)[number],
          enabled,
        };
      }
    );
    if (updates.length === 0) {
      toast.info("No changes to save");
      return;
    }
    bulkUpdate.mutate({ agentId, updates });
  }

  function toggleColumn(ch: string) {
    const allOn = CATEGORIES.every(cat => getValue(cat, ch));
    const newVal = !allOn;
    setPendingChanges(prev => {
      const n = new Map(prev);
      for (const cat of CATEGORIES) n.set(`${cat}:${ch}`, newVal);
      return n;
    });
  }

  function toggleRow(cat: string) {
    const allOn = CHANNELS.every(ch => getValue(cat, ch));
    const newVal = !allOn;
    setPendingChanges(prev => {
      const n = new Map(prev);
      for (const ch of CHANNELS) n.set(`${cat}:${ch}`, newVal);
      return n;
    });
  }

  const enabledCount = CATEGORIES.reduce(
    (sum: any, cat: any) =>
      sum +
      CHANNELS.reduce((s: any, ch: any) => s + (getValue(cat, ch) ? 1 : 0), 0),
    0
  );
  const totalCount = CATEGORIES.length * CHANNELS.length;

  return (
    <DashboardLayout>
      <div className="container max-w-5xl py-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Notification Preferences</h1>
            <p className="text-muted-foreground mt-1">
              Configure which notifications you receive and how they are
              delivered
            </p>
          </div>
          <div className="flex gap-2">
            <Badge variant="outline">
              {enabledCount}/{totalCount} enabled
            </Badge>
            {pendingChanges.size > 0 && (
              <Badge variant="secondary">{pendingChanges.size} unsaved</Badge>
            )}
          </div>
        </div>

        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Delivery Channel Matrix</CardTitle>
                <CardDescription>
                  Toggle delivery channels for each notification category
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => resetMut.mutate({ agentId })}
                  disabled={resetMut.isPending}
                >
                  <RotateCcw className="w-4 h-4 mr-1" /> Reset
                </Button>
                <Button
                  size="sm"
                  onClick={saveAll}
                  disabled={pendingChanges.size === 0 || bulkUpdate.isPending}
                >
                  <Save className="w-4 h-4 mr-1" /> Save{" "}
                  {pendingChanges.size > 0 && `(${pendingChanges.size})`}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {matrixQuery.isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 9 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-12 bg-muted animate-pulse rounded"
                  />
                ))}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-2 font-medium text-sm w-[280px]">
                        Category
                      </th>
                      {CHANNELS.map(ch => (
                        <th key={ch} className="text-center py-3 px-4">
                          <button
                            onClick={() => toggleColumn(ch)}
                            className="flex flex-col items-center gap-1 mx-auto hover:opacity-70 transition-opacity"
                          >
                            {CHANNEL_META[ch].icon}
                            <span className="text-xs font-medium">
                              {CHANNEL_META[ch].label}
                            </span>
                          </button>
                        </th>
                      ))}
                      <th className="text-center py-3 px-2 text-xs text-muted-foreground">
                        All
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {CATEGORIES.map(cat => {
                      const meta = CATEGORY_META[cat];
                      const rowEnabled = CHANNELS.filter(ch =>
                        getValue(cat, ch)
                      ).length;
                      return (
                        <tr
                          key={cat}
                          className="border-b last:border-0 hover:bg-muted/30 transition-colors"
                        >
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-2">
                              <div className="p-1.5 rounded bg-muted">
                                {meta.icon}
                              </div>
                              <div>
                                <div className="font-medium text-sm">
                                  {meta.label}
                                </div>
                                <div className="text-xs text-muted-foreground">
                                  {meta.description}
                                </div>
                              </div>
                            </div>
                          </td>
                          {CHANNELS.map(ch => (
                            <td key={ch} className="text-center py-3 px-4">
                              <Switch
                                checked={getValue(cat, ch)}
                                onCheckedChange={() => toggle(cat, ch)}
                              />
                            </td>
                          ))}
                          <td className="text-center py-3 px-2">
                            <button
                              onClick={() => toggleRow(cat)}
                              className="text-xs text-muted-foreground hover:text-foreground"
                            >
                              {rowEnabled}/{CHANNELS.length}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const n = new Map<string, boolean>();
                for (const cat of ["fraud", "security", "compliance"])
                  for (const ch of CHANNELS) n.set(`${cat}:${ch}`, true);
                setPendingChanges(n);
              }}
            >
              Enable all critical alerts
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const n = new Map<string, boolean>();
                for (const cat of CATEGORIES) n.set(`${cat}:sms`, false);
                setPendingChanges(n);
              }}
            >
              Disable all SMS
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                const n = new Map<string, boolean>();
                for (const cat of CATEGORIES)
                  for (const ch of CHANNELS) n.set(`${cat}:${ch}`, true);
                setPendingChanges(n);
              }}
            >
              Enable everything
            </Button>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
