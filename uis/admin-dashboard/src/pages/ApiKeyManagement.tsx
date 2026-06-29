/**
 * API Key Management — Create, revoke, and monitor API keys for developer integrations
 * Wired to developer.listApiKeys, createApiKey, revokeApiKey
 */
import { useState, useMemo } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Key,
  Search,
  Plus,
  Trash2,
  Eye,
  EyeOff,
  Copy,
  Shield,
} from "lucide-react";
import { toast } from "sonner";

export default function ApiKeyManagement() {
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState({
    name: "",
    environment: "sandbox",
    permissions: "read",
  });
  const [revealedKeys, setRevealedKeys] = useState<Set<number>>(new Set());

  const apiKeys = trpc.devPortal.listKeys.useQuery(undefined, { retry: false });
  const createKey = trpc.devPortal.createKey.useMutation({
    onSuccess: () => {
      toast.success("API key created");
      apiKeys.refetch();
      setShowCreate(false);
      setNewKey({ name: "", environment: "sandbox", permissions: "read" });
    },
    onError: (e: any) => toast.error("Failed: " + e.message),
  });
  const revokeKey = trpc.devPortal.revokeKey.useMutation({
    onSuccess: () => {
      toast.success("API key revoked");
      apiKeys.refetch();
    },
    onError: (e: any) => toast.error("Failed: " + e.message),
  });

  const rawKeys = apiKeys.data;
  const keys: any[] = Array.isArray(rawKeys) ? rawKeys : (rawKeys?.keys ?? []);
  const filtered = useMemo(() => {
    if (!search) return keys;
    const q = search.toLowerCase();
    return keys.filter(
      (k: any) =>
        k.name?.toLowerCase().includes(q) ||
        k.keyPrefix?.toLowerCase().includes(q)
    );
  }, [keys, search]);

  const toggleReveal = (id: number) => {
    setRevealedKeys(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast.success("API key copied to clipboard");
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Key className="w-6 h-6 text-yellow-400" /> API Key Management
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Create and manage API keys for third-party integrations
          </p>
        </div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild>
            <Button
              size="sm"
              className="bg-yellow-600 hover:bg-yellow-700 text-white"
            >
              <Plus className="w-3 h-3 mr-1" /> New API Key
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-slate-900 border-slate-700 text-white">
            <DialogHeader>
              <DialogTitle>Create API Key</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400">Key Name</label>
                <Input
                  value={newKey.name}
                  onChange={e =>
                    setNewKey(p => ({ ...p, name: e.target.value }))
                  }
                  className="bg-slate-800 border-slate-700 text-white"
                  placeholder="e.g., Mobile App Production"
                />
              </div>
              <div>
                <label className="text-xs text-slate-400">Environment</label>
                <Select
                  value={newKey.environment}
                  onValueChange={v =>
                    setNewKey(p => ({ ...p, environment: v }))
                  }
                >
                  <SelectTrigger className="bg-slate-800 border-slate-700 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700">
                    <SelectItem value="sandbox">Sandbox</SelectItem>
                    <SelectItem value="production">Production</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-slate-400">Permissions</label>
                <Select
                  value={newKey.permissions}
                  onValueChange={v =>
                    setNewKey(p => ({ ...p, permissions: v }))
                  }
                >
                  <SelectTrigger className="bg-slate-800 border-slate-700 text-white">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-slate-800 border-slate-700">
                    <SelectItem value="read">Read Only</SelectItem>
                    <SelectItem value="write">Read + Write</SelectItem>
                    <SelectItem value="admin">Full Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                className="border-slate-700 text-slate-400"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </Button>
              <Button
                className="bg-yellow-600 hover:bg-yellow-700 text-white"
                onClick={() => createKey.mutate({ name: newKey.name })}
                disabled={!newKey.name || createKey.isPending}
              >
                {createKey.isPending ? "Creating..." : "Create Key"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <Card className="bg-slate-900/50 border-slate-700">
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-white">{keys.length}</div>
            <div className="text-xs text-slate-500">Total Keys</div>
          </CardContent>
        </Card>
        <Card className="bg-slate-900/50 border-slate-700">
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-green-400">
              {keys.filter((k: any) => k.isActive !== false).length}
            </div>
            <div className="text-xs text-slate-500">Active</div>
          </CardContent>
        </Card>
        <Card className="bg-slate-900/50 border-slate-700">
          <CardContent className="p-4 text-center">
            <div className="text-2xl font-bold text-red-400">
              {keys.filter((k: any) => k.isActive === false).length}
            </div>
            <div className="text-xs text-slate-500">Revoked</div>
          </CardContent>
        </Card>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search API keys..."
          className="pl-9 bg-slate-800 border-slate-700 text-white"
        />
      </div>

      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-white">
            API Keys ({filtered.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Key</th>
                <th className="px-3 py-2 text-center">Environment</th>
                <th className="px-3 py-2 text-center">Status</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {filtered.map((k: any) => (
                <tr key={k.id} className="hover:bg-slate-800/40">
                  <td className="px-3 py-2.5 text-white font-medium">
                    {k.name}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-slate-400">
                    {revealedKeys.has(k.id)
                      ? (k.keyValue ?? k.keyPrefix + "...")
                      : (k.keyPrefix ?? "54lk") + "••••••••"}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${k.environment === "production" ? "border-red-600 text-red-400" : "border-blue-600 text-blue-400"}`}
                    >
                      {k.environment ?? "sandbox"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <Badge
                      variant="outline"
                      className={`text-[10px] ${k.isActive !== false ? "border-green-600 text-green-400" : "border-slate-600 text-slate-400"}`}
                    >
                      {k.isActive !== false ? "Active" : "Revoked"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5 text-slate-500">
                    {k.createdAt
                      ? new Date(k.createdAt).toLocaleDateString()
                      : "-"}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <div className="flex gap-1 justify-center">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 text-blue-400"
                        onClick={() => toggleReveal(k.id)}
                      >
                        {revealedKeys.has(k.id) ? (
                          <EyeOff className="w-3 h-3" />
                        ) : (
                          <Eye className="w-3 h-3" />
                        )}
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-6 w-6 text-slate-400"
                        onClick={() => copyKey(k.keyValue ?? k.keyPrefix)}
                      >
                        <Copy className="w-3 h-3" />
                      </Button>
                      {k.isActive !== false && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 text-red-400"
                          onClick={() => {
                            if (confirm(`Revoke key "${k.name}"?`))
                              revokeKey.mutate({ keyId: k.id });
                          }}
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-3 py-8 text-center text-slate-600"
                  >
                    {apiKeys.isLoading ? "Loading..." : "No API keys found"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
