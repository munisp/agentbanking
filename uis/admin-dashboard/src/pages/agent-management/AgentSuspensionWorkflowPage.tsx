import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Ban, Search, UserX, UserCheck, AlertTriangle } from "lucide-react";

export default function AgentSuspensionWorkflowPage() {
  const [search, setSearch] = useState("");
  const data = {data: null, isLoading: false};
  const suspendMut = {mutate: () => toast.success("Feature coming soon"), isPending: false};
  const reinstateMut = {mutate: () => toast.success("Feature coming soon"), isPending: false};
  const agents: any[] = [];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Ban className="w-6 h-6" /> Agent Suspension Workflow
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage agent suspensions, reinstatements, and compliance actions
        </p>
      </div>
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold">0</p>
            <p className="text-sm text-muted-foreground">Total Agents</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-green-600">0</p>
            <p className="text-sm text-muted-foreground">Active</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-red-600">0</p>
            <p className="text-sm text-muted-foreground">Suspended</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-yellow-600">0</p>
            <p className="text-sm text-muted-foreground">Under Review</p>
          </CardContent>
        </Card>
      </div>
      <div className="flex items-center gap-2">
        <Search className="w-4 h-4" />
        <Input
          placeholder="Search agents..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>
      <div className="text-center py-8 text-muted-foreground">
        Connect to live services to view agent suspension data.
      </div>
    </div>
  );
}
