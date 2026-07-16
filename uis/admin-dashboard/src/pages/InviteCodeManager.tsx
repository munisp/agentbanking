import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  ArrowLeft,
  Ban,
  Copy,
  Key,
  Loader2,
  Plus,
  RefreshCw,
  Ticket,
} from "lucide-react";

export default function InviteCodeManager() {
  const [codeType, setCodeType] = useState<"one_time" | "multi_use">(
    "one_time"
  );
  const [maxUses, setMaxUses] = useState(1);
  const [partnerName, setPartnerName] = useState("");
  const [partnerEmail, setPartnerEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [search, setSearch] = useState("");

  const stats = trpc.inviteCodes.stats.useQuery();
  const codesList = trpc.inviteCodes.list.useQuery({
    status: filterStatus ? (filterStatus as any) : undefined,
    search: search || undefined,
  });

  const generateCode = trpc.inviteCodes.generate.useMutation({
    onSuccess: data => {
      toast.success(`Invite code generated: ${data.code}`);
      navigator.clipboard.writeText(data.code);
      setPartnerName("");
      setPartnerEmail("");
      setNotes("");
      codesList.refetch();
      stats.refetch();
    },
    onError: err => toast.error(err.message),
  });

  const revokeCode = trpc.inviteCodes.revoke.useMutation({
    onSuccess: () => {
      toast.success("Code revoked");
      codesList.refetch();
      stats.refetch();
    },
  });

  const s = stats.data;

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b bg-card/50 backdrop-blur sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => window.history.back()}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Ticket className="h-5 w-5 text-primary" />
          <span className="font-bold">Invite Code Management</span>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold">{s?.total ?? 0}</p>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-green-500">
                {s?.active ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Active</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-blue-500">{s?.used ?? 0}</p>
              <p className="text-xs text-muted-foreground">Used</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-amber-500">
                {s?.expired ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Expired</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 text-center">
              <p className="text-2xl font-bold text-red-500">
                {s?.revoked ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Revoked</p>
            </CardContent>
          </Card>
        </div>

        {/* Generate new code */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5" /> Generate Invite Code
            </CardTitle>
            <CardDescription>Create a new partner invite code</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label>Code Type</Label>
                <select
                  value={codeType}
                  onChange={e => setCodeType(e.target.value as any)}
                  className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                >
                  <option value="one_time">One-Time Use</option>
                  <option value="multi_use">Multi-Use</option>
                </select>
              </div>
              {codeType === "multi_use" && (
                <div>
                  <Label>Max Uses</Label>
                  <Input
                    type="number"
                    value={maxUses}
                    onChange={e => setMaxUses(Number(e.target.value))}
                    min={1}
                    max={1000}
                  />
                </div>
              )}
              <div>
                <Label>Partner Name</Label>
                <Input
                  value={partnerName}
                  onChange={e => setPartnerName(e.target.value)}
                  placeholder="Acme Corp"
                />
              </div>
              <div>
                <Label>Partner Email</Label>
                <Input
                  type="email"
                  value={partnerEmail}
                  onChange={e => setPartnerEmail(e.target.value)}
                  placeholder="partner@acme.com"
                />
              </div>
              <div className="md:col-span-2">
                <Label>Notes</Label>
                <Input
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  placeholder="Internal notes about this partner..."
                />
              </div>
            </div>
            <Button
              onClick={() =>
                generateCode.mutate({
                  type: codeType,
                  maxUses: codeType === "multi_use" ? maxUses : 1,
                  partnerName: partnerName || undefined,
                  partnerEmail: partnerEmail || undefined,
                  notes: notes || undefined,
                })
              }
              className="mt-4"
              disabled={generateCode.isPending}
            >
              {generateCode.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Plus className="h-4 w-4 mr-2" />
              )}
              Generate Code
            </Button>
          </CardContent>
        </Card>

        {/* Codes list */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>All Invite Codes</CardTitle>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => codesList.refetch()}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex gap-3 mt-2">
              <Input
                placeholder="Search codes or partners..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="max-w-xs"
              />
              <select
                value={filterStatus}
                onChange={e => setFilterStatus(e.target.value)}
                className="h-10 rounded-md border bg-background px-3 text-sm"
              >
                <option value="">All Status</option>
                <option value="active">Active</option>
                <option value="used">Used</option>
                <option value="expired">Expired</option>
                <option value="revoked">Revoked</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {codesList.data?.items && codesList.data.items.length > 0 ? (
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2">Code</th>
                      <th className="text-left px-4 py-2">Type</th>
                      <th className="text-left px-4 py-2">Partner</th>
                      <th className="text-left px-4 py-2">Uses</th>
                      <th className="text-left px-4 py-2">Status</th>
                      <th className="text-left px-4 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {codesList.data.items.map((c: any) => (
                      <tr key={c.id} className="border-t">
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-2">
                            <code className="font-mono text-xs bg-muted px-2 py-1 rounded">
                              {c.code}
                            </code>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={() => {
                                navigator.clipboard.writeText(c.code);
                                toast.success("Copied!");
                              }}
                            >
                              <Copy className="h-3 w-3" />
                            </Button>
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          <Badge variant="outline">
                            {c.type === "one_time" ? "One-Time" : "Multi-Use"}
                          </Badge>
                        </td>
                        <td className="px-4 py-2">
                          <div>
                            <p className="font-medium">
                              {c.partnerName || "-"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {c.partnerEmail || ""}
                            </p>
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          {c.usedCount}/{c.maxUses}
                        </td>
                        <td className="px-4 py-2">
                          <Badge
                            variant={
                              c.status === "active"
                                ? "default"
                                : c.status === "used"
                                  ? "secondary"
                                  : c.status === "revoked"
                                    ? "destructive"
                                    : "outline"
                            }
                          >
                            {c.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-2">
                          {c.status === "active" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => revokeCode.mutate({ id: c.id })}
                              className="text-destructive"
                            >
                              <Ban className="h-3 w-3 mr-1" /> Revoke
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No invite codes generated yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
