/**
 * FraudRulesTab — admin view of the platform's fraud-detection rules.
 * Lists the rules returned by the fraud-rules endpoint and allows
 * toggling a rule's enabled state.
 */

import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ShieldAlert } from "lucide-react";

interface FraudRule {
  id: string;
  name: string;
  description?: string;
  severity?: string;
  threshold?: number;
  enabled: boolean;
}

export function FraudRulesTab() {
  const rulesQuery = trpc.fraud?.rules?.list?.useQuery?.() as
    | { data?: FraudRule[]; isLoading?: boolean; refetch?: () => void }
    | undefined;
  const toggleMut = trpc.fraud?.rules?.toggle?.useMutation?.({
    onSuccess: () => rulesQuery?.refetch?.(),
  }) as { mutate?: (vars: { id: string; enabled: boolean }) => void } | undefined;

  const rules = rulesQuery?.data ?? [];
  const [search, setSearch] = useState("");

  const filtered = rules.filter(
    r =>
      !search ||
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5" />
          Fraud Detection Rules
        </CardTitle>
        <CardDescription>
          Rules evaluated by the real-time fraud engine. Disabling a rule stops
          it from generating alerts.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Input
          placeholder="Search rules…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-sm"
        />
        {rulesQuery?.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading rules…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No fraud rules configured.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Rule</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Threshold</TableHead>
                <TableHead>Enabled</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map(rule => (
                <TableRow key={rule.id}>
                  <TableCell>
                    <div className="font-medium">{rule.name}</div>
                    {rule.description && (
                      <div className="text-xs text-muted-foreground">
                        {rule.description}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    {rule.severity && (
                      <Badge variant="outline">{rule.severity}</Badge>
                    )}
                  </TableCell>
                  <TableCell>{rule.threshold ?? "—"}</TableCell>
                  <TableCell>
                    <Switch
                      checked={rule.enabled}
                      onCheckedChange={enabled =>
                        toggleMut?.mutate?.({ id: rule.id, enabled })
                      }
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {rules.length > 0 && (
          <Button variant="outline" onClick={() => rulesQuery?.refetch?.()}>
            Refresh
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default FraudRulesTab;
