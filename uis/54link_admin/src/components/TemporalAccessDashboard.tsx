import CreateGrantForm from "@/components/CreateGrantForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  temporalAccessService,
  type AccessPolicy,
  type Delegation,
  type TemporalGrant,
  type UserSearchResult,
} from "@/services/temporalAccessService";
import {
  Check,
  ChevronsUpDown,
  Clock,
  Plus,
  RefreshCw,
  Shield,
  Users,
  X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { toast } from "sonner";

const TemporalAccessDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState("grants");
  const [grants, setGrants] = useState<TemporalGrant[]>([]);
  const [policies, setPolicies] = useState<AccessPolicy[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreateGrant, setShowCreateGrant] = useState(false);
  const [delegations, setDelegations] = useState<Delegation[]>([]);
  const [showCreatePolicy, setShowCreatePolicy] = useState(false);
  const [showCreateDelegation, setShowCreateDelegation] = useState(false);

  const [policyName, setPolicyName] = useState("");
  const [policyDescription, setPolicyDescription] = useState("");
  const [policyResourceType, setPolicyResourceType] = useState("");
  const [policyPermission, setPolicyPermission] = useState("");
  const [policyPriority, setPolicyPriority] = useState("1");
  const [policyRequireMfa, setPolicyRequireMfa] = useState(false);
  const [policyRequireApproval, setPolicyRequireApproval] = useState(false);

  const [delegationDelegateId, setDelegationDelegateId] = useState("");
  const [delegationDelegateEmail, setDelegationDelegateEmail] = useState("");
  const [delegationPermission, setDelegationPermission] = useState("");
  const [delegationResourceType, setDelegationResourceType] = useState("");
  const [delegationResourceId, setDelegationResourceId] = useState("");
  const [openDelegateSearch, setOpenDelegateSearch] = useState(false);
  const [delegateSearchQuery, setDelegateSearchQuery] = useState("");
  const [delegateSearchResults, setDelegateSearchResults] = useState<
    UserSearchResult[]
  >([]);
  const [searchingDelegate, setSearchingDelegate] = useState(false);

  const tenantId =
    import.meta.env.VITE_TENANT_ID ||
    localStorage.getItem("tenant_id") ||
    "54link";
  const currentUserId = localStorage.getItem("keycloak_id") || "";

  useEffect(() => {
    if (activeTab === "grants") {
      fetchGrants();
    } else if (activeTab === "policies") {
      fetchPolicies();
    } else if (activeTab === "delegations") {
      fetchDelegations();
    }
  }, [activeTab]);

  const fetchGrants = async () => {
    setLoading(true);
    try {
      const data = await temporalAccessService.listGrants(tenantId);
      setGrants(data);
    } catch (error) {
      toast.error("Failed to fetch grants");
    } finally {
      setLoading(false);
    }
  };

  const fetchPolicies = async () => {
    setLoading(true);
    try {
      const data = await temporalAccessService.listPolicies(tenantId);
      setPolicies(data);
    } catch (error) {
      toast.error("Failed to fetch policies");
    } finally {
      setLoading(false);
    }
  };

  const fetchDelegations = async () => {
    if (!currentUserId) return;
    setLoading(true);
    try {
      const data = await temporalAccessService.listDelegations(
        tenantId,
        currentUserId,
      );
      setDelegations(data);
    } catch (error) {
      toast.error("Failed to fetch delegations");
    } finally {
      setLoading(false);
    }
  };

  const revokeGrant = async (grantId: string) => {
    try {
      await temporalAccessService.revokeGrant(grantId, tenantId);
      toast.success("Grant revoked successfully");
      fetchGrants();
    } catch (error) {
      toast.error("Failed to revoke grant");
    }
  };

  const extendGrant = async (grantId: string, duration: string) => {
    try {
      await temporalAccessService.extendGrant(grantId, tenantId, duration);
      toast.success("Grant extended successfully");
      fetchGrants();
    } catch (error) {
      toast.error("Failed to extend grant");
    }
  };

  // const formatDate = (dateStr: string) => {
  //   return new Date(dateStr).toLocaleString();
  // };

  const getResourceIdPlaceholder = (resourceType: string) => {
    const placeholders: Record<string, string> = {
      account: "acc_456",
      transaction: "txn_789",
      loan: "loan_123",
      card: "card_321",
      customer: "cust_555",
      payment: "pay_999",
    };
    return `${placeholders[resourceType] || "resource_id"} (leave empty for all)`;
  };

  // const getStatusBadge = (status: string) => {
  //   const variants: Record<string, string> = {
  //     active: "default",
  //     expired: "secondary",
  //     revoked: "destructive",
  //   };
  //   return (
  //     <Badge variant={variants[status] as any}>{status.toUpperCase()}</Badge>
  //   );
  // };

  const revokeDelegation = async (delegationId: string) => {
    try {
      await temporalAccessService.revokeDelegation(delegationId);
      toast.success("Delegation revoked successfully");
      fetchDelegations();
    } catch (error) {
      toast.error("Failed to revoke delegation");
    }
  };

  const handleDelegateSearch = async (query: string) => {
    setDelegateSearchQuery(query);
    setSearchingDelegate(true);

    try {
      const results = await temporalAccessService.searchUsers(query, tenantId);
      setDelegateSearchResults(results);
    } catch (error) {
      console.error("Error searching users:", error);
      setDelegateSearchResults([]);
    } finally {
      setSearchingDelegate(false);
    }
  };

  const selectDelegate = (user: UserSearchResult) => {
    setDelegationDelegateId(user.keycloak_id);
    setDelegationDelegateEmail(user.email);
    setOpenDelegateSearch(false);
    setDelegateSearchQuery("");
  };

  const handleTogglePolicy = async (policyId: string, enabled: boolean) => {
    try {
      await temporalAccessService.updatePolicy(policyId, { enabled });
      toast.success(`Policy ${enabled ? "enabled" : "disabled"} successfully`);
      fetchPolicies();
    } catch (error) {
      toast.error("Failed to update policy");
    }
  };

  const handleCreatePolicy = async () => {
    if (!policyName || !policyResourceType || !policyPermission) {
      toast.error("Name, resource type, and permission are required");
      return;
    }

    const rules: any[] = [];
    if (policyRequireMfa) {
      rules.push({
        type: "context",
        operator: "equals",
        value: true,
        action: "require_mfa",
      });
    }
    if (policyRequireApproval) {
      rules.push({
        type: "context",
        operator: "equals",
        value: true,
        action: "require_approval",
      });
    }

    try {
      await temporalAccessService.createPolicy({
        tenant_id: tenantId,
        name: policyName,
        description: policyDescription,
        resource_type: policyResourceType,
        permission: policyPermission,
        priority: Number(policyPriority) || 1,
        enabled: true,
        rules,
      });

      toast.success("Policy created successfully");
      setShowCreatePolicy(false);
      setPolicyName("");
      setPolicyDescription("");
      setPolicyResourceType("");
      setPolicyPermission("");
      setPolicyPriority("1");
      setPolicyRequireMfa(false);
      setPolicyRequireApproval(false);
      fetchPolicies();
    } catch (error) {
      toast.error("Failed to create policy");
    }
  };

  const handleCreateDelegation = async () => {
    if (
      !delegationDelegateId ||
      !delegationPermission ||
      !delegationResourceType
    ) {
      toast.error("Delegate, resource type, and permission are required");
      return;
    }

    if (!currentUserId) {
      toast.error("Current user id is missing");
      return;
    }

    try {
      await temporalAccessService.createDelegation({
        tenant_id: tenantId,
        delegator_id: currentUserId,
        delegate_id: delegationDelegateId,
        permission: delegationPermission,
        resource_type: delegationResourceType,
        resource_id: delegationResourceId,
      });

      toast.success("Delegation created successfully");
      setShowCreateDelegation(false);
      setDelegationDelegateId("");
      setDelegationDelegateEmail("");
      setDelegationPermission("");
      setDelegationResourceType("");
      setDelegationResourceId("");
      fetchDelegations();
    } catch (error) {
      toast.error("Failed to create delegation");
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Temporal Access Control</h1>
          <p className="text-gray-600 mt-2">
            Manage time-limited permissions, conditional access, and delegations
          </p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="grants" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Temporal Grants
          </TabsTrigger>
          <TabsTrigger value="policies" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Access Policies
          </TabsTrigger>
          <TabsTrigger value="delegations" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Delegations
          </TabsTrigger>
          {/* <TabsTrigger value="audit" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Audit Log
          </TabsTrigger> */}
        </TabsList>

        <TabsContent value="grants" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Temporal Grants</CardTitle>
                  <CardDescription>
                    Time-limited permissions with conditional access
                  </CardDescription>
                </div>
                <Dialog
                  open={showCreateGrant}
                  onOpenChange={setShowCreateGrant}
                >
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      Create Grant
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-2xl">
                    <CreateGrantForm
                      tenantId={tenantId}
                      onSuccess={() => {
                        setShowCreateGrant(false);
                        fetchGrants();
                      }}
                    />
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <GrantsTable
                grants={grants}
                onRevoke={revokeGrant}
                onExtend={extendGrant}
                loading={loading}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="policies" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Access Policies</CardTitle>
                  <CardDescription>
                    Conditional access rules applied platform-wide
                  </CardDescription>
                </div>
                <Dialog
                  open={showCreatePolicy}
                  onOpenChange={setShowCreatePolicy}
                >
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      Create Policy
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-lg">
                    <DialogHeader>
                      <DialogTitle>Create Access Policy</DialogTitle>
                      <DialogDescription>
                        Define a new conditional access rule for this tenant.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div className="space-y-2">
                        <Label htmlFor="policy-name">Name</Label>
                        <Input
                          id="policy-name"
                          value={policyName}
                          onChange={(e) => setPolicyName(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="policy-description">Description</Label>
                        <Input
                          id="policy-description"
                          value={policyDescription}
                          onChange={(e) => setPolicyDescription(e.target.value)}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="policy-resource-type">
                            Resource Type
                          </Label>
                          <Input
                            id="policy-resource-type"
                            value={policyResourceType}
                            onChange={(e) =>
                              setPolicyResourceType(e.target.value)
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="policy-permission">Permission</Label>
                          <Input
                            id="policy-permission"
                            value={policyPermission}
                            onChange={(e) =>
                              setPolicyPermission(e.target.value)
                            }
                          />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="policy-priority">Priority</Label>
                        <Input
                          id="policy-priority"
                          type="number"
                          min={1}
                          value={policyPriority}
                          onChange={(e) => setPolicyPriority(e.target.value)}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Switch
                            id="policy-require-mfa"
                            checked={policyRequireMfa}
                            onCheckedChange={(v) =>
                              setPolicyRequireMfa(Boolean(v))
                            }
                          />
                          <Label htmlFor="policy-require-mfa">
                            Require MFA
                          </Label>
                        </div>
                        <div className="flex items-center gap-2">
                          <Switch
                            id="policy-require-approval"
                            checked={policyRequireApproval}
                            onCheckedChange={(v) =>
                              setPolicyRequireApproval(Boolean(v))
                            }
                          />
                          <Label htmlFor="policy-require-approval">
                            Require Approval
                          </Label>
                        </div>
                      </div>
                    </div>
                    <DialogFooter className="mt-4">
                      <Button
                        variant="outline"
                        onClick={() => setShowCreatePolicy(false)}
                      >
                        Cancel
                      </Button>
                      <Button onClick={handleCreatePolicy}>Create</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <PoliciesTable
                policies={policies}
                loading={loading}
                onToggle={handleTogglePolicy}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="delegations" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Permission Delegations</CardTitle>
                  <CardDescription>
                    User-to-user permission delegation
                  </CardDescription>
                </div>
                <Dialog
                  open={showCreateDelegation}
                  onOpenChange={setShowCreateDelegation}
                >
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="h-4 w-4 mr-2" />
                      Add Delegation
                    </Button>
                  </DialogTrigger>
                  <DialogContent className="max-w-lg">
                    <DialogHeader>
                      <DialogTitle>Create Delegation</DialogTitle>
                      <DialogDescription>
                        Delegate one of your permissions to another user.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 mt-4">
                      <div className="space-y-2">
                        <Label htmlFor="delegation-delegate-id">
                          Delegate User / Admin
                        </Label>
                        <Popover
                          open={openDelegateSearch}
                          onOpenChange={setOpenDelegateSearch}
                        >
                          <PopoverTrigger asChild>
                            <Button
                              variant="outline"
                              role="combobox"
                              aria-expanded={openDelegateSearch}
                              className="w-full justify-between"
                            >
                              {delegationDelegateEmail || "Search for user..."}
                              <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                            </Button>
                          </PopoverTrigger>
                          <PopoverContent className="w-full p-0">
                            <Command>
                              <CommandInput
                                placeholder="Search by email or ID..."
                                value={delegateSearchQuery}
                                onValueChange={handleDelegateSearch}
                              />
                              <CommandList>
                                <CommandEmpty>
                                  {searchingDelegate
                                    ? "Searching..."
                                    : "No users found"}
                                </CommandEmpty>
                                <CommandGroup>
                                  {delegateSearchResults.map((user) => (
                                    <CommandItem
                                      key={user.id}
                                      value={user.email}
                                      onSelect={() => selectDelegate(user)}
                                    >
                                      <Check
                                        className={`mr-2 h-4 w-4 ${
                                          delegationDelegateId ===
                                          user.keycloak_id
                                            ? "opacity-100"
                                            : "opacity-0"
                                        }`}
                                      />
                                      <div className="flex flex-col">
                                        <span>{user.email}</span>
                                        <span className="text-xs text-muted-foreground">
                                          {user.user_role} • ID:{" "}
                                          {user.keycloak_id}
                                        </span>
                                      </div>
                                    </CommandItem>
                                  ))}
                                </CommandGroup>
                              </CommandList>
                            </Command>
                          </PopoverContent>
                        </Popover>
                        {delegationDelegateId && (
                          <p className="text-sm text-muted-foreground mt-1">
                            Selected: {delegationDelegateEmail} (
                            {delegationDelegateId})
                          </p>
                        )}
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="delegation-resource-type">
                            Resource Type
                          </Label>
                          <Select
                            value={delegationResourceType}
                            onValueChange={setDelegationResourceType}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select resource type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="account">Account</SelectItem>
                              <SelectItem value="transaction">
                                Transaction
                              </SelectItem>
                              <SelectItem value="loan">Loan</SelectItem>
                              <SelectItem value="card">Card</SelectItem>
                              <SelectItem value="customer">Customer</SelectItem>
                              <SelectItem value="payment">Payment</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="delegation-permission">
                            Permission
                          </Label>
                          <Select
                            value={delegationPermission}
                            onValueChange={setDelegationPermission}
                          >
                            <SelectTrigger>
                              <SelectValue placeholder="Select permission" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="view">View</SelectItem>
                              <SelectItem value="approve">Approve</SelectItem>
                              <SelectItem value="modify">Modify</SelectItem>
                              <SelectItem value="delete">Delete</SelectItem>
                              <SelectItem value="initiate">Initiate</SelectItem>
                              <SelectItem value="reject">Reject</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="delegation-resource-id">
                          Resource ID (optional)
                        </Label>
                        <Input
                          id="delegation-resource-id"
                          placeholder={getResourceIdPlaceholder(
                            delegationResourceType,
                          )}
                          value={delegationResourceId}
                          onChange={(e) =>
                            setDelegationResourceId(e.target.value)
                          }
                        />
                      </div>
                    </div>
                    <DialogFooter className="mt-4">
                      <Button
                        variant="outline"
                        onClick={() => setShowCreateDelegation(false)}
                      >
                        Cancel
                      </Button>
                      <Button onClick={handleCreateDelegation}>Create</Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              <DelegationsTable
                delegations={delegations}
                loading={loading}
                onRevoke={revokeDelegation}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Audit Log</CardTitle>
              <CardDescription>
                Full history of grant creation, usage, and revocation
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-gray-500">Audit log viewer coming soon...</p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

const DelegationsTable: React.FC<{
  delegations: Delegation[];
  loading: boolean;
  onRevoke: (id: string) => void;
}> = ({ delegations, loading, onRevoke }) => {
  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (!delegations.length) {
    return (
      <div className="text-center py-8 text-gray-500">No delegations found</div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Delegator</TableHead>
          <TableHead>Delegate</TableHead>
          <TableHead>Permission</TableHead>
          <TableHead>Resource</TableHead>
          <TableHead>Created At</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {delegations.map((d) => (
          <TableRow key={d.id}>
            <TableCell>{d.delegator_id}</TableCell>
            <TableCell>{d.delegate_id}</TableCell>
            <TableCell>
              <Badge variant="outline">{d.permission}</Badge>
            </TableCell>
            <TableCell>
              <div className="text-sm">
                <div className="font-medium">{d.resource_type}</div>
                <div className="text-gray-500 font-mono">{d.resource_id}</div>
              </div>
            </TableCell>
            <TableCell className="text-sm">
              {new Date(d.created_at).toLocaleString()}
            </TableCell>
            <TableCell>
              <Badge variant={d.revoked ? "secondary" : "default"}>
                {d.revoked ? "revoked" : "active"}
              </Badge>
            </TableCell>
            <TableCell>
              <Button
                size="sm"
                variant="destructive"
                disabled={d.revoked}
                onClick={() => onRevoke(d.id)}
              >
                <X className="h-3 w-3 mr-1" />
                Revoke
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

// Grants Table Component
const GrantsTable: React.FC<{
  grants: TemporalGrant[];
  onRevoke: (id: string) => void;
  onExtend: (id: string, duration: string) => void;
  loading: boolean;
}> = ({ grants, onRevoke, onExtend, loading }) => {
  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (grants.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No temporal grants found
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Subject</TableHead>
          <TableHead>Permission</TableHead>
          <TableHead>Resource</TableHead>
          <TableHead>Expires At</TableHead>
          <TableHead>Usage</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {grants.map((grant) => (
          <TableRow key={grant.id}>
            <TableCell className="font-mono text-sm">
              {grant.subject_id}
            </TableCell>
            <TableCell>
              <Badge variant="outline">{grant.permission}</Badge>
            </TableCell>
            <TableCell>
              <div className="text-sm">
                <div className="font-medium">{grant.resource_type}</div>
                <div className="text-gray-500 font-mono">
                  {grant.resource_id}
                </div>
              </div>
            </TableCell>
            <TableCell className="text-sm">
              {new Date(grant.expires_at).toLocaleString()}
            </TableCell>
            <TableCell>
              {grant.usage_count}
              {grant.max_usage && ` / ${grant.max_usage}`}
            </TableCell>
            <TableCell>
              <Badge
                variant={grant.status === "active" ? "default" : "secondary"}
              >
                {grant.status}
              </Badge>
            </TableCell>
            <TableCell>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onExtend(grant.id, "1h")}
                  disabled={grant.status !== "active"}
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  Extend
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => onRevoke(grant.id)}
                  disabled={grant.status !== "active"}
                >
                  <X className="h-3 w-3 mr-1" />
                  Revoke
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

// Policies Table Component
const PoliciesTable: React.FC<{
  policies: AccessPolicy[];
  loading: boolean;
  onToggle: (policyId: string, enabled: boolean) => void;
}> = ({ policies, loading, onToggle }) => {
  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (policies.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No access policies found
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Resource Type</TableHead>
          <TableHead>Permission</TableHead>
          <TableHead>Priority</TableHead>
          <TableHead>Conditions</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {policies.map((policy) => (
          <TableRow key={policy.id}>
            <TableCell>
              <div>
                <div className="font-medium">{policy.name}</div>
                <div className="text-sm text-gray-500">
                  {policy.description}
                </div>
              </div>
            </TableCell>
            <TableCell>
              <Badge variant="outline">{policy.resource_type}</Badge>
            </TableCell>
            <TableCell>{policy.permission}</TableCell>
            <TableCell>{policy.priority}</TableCell>
            <TableCell className="text-sm">
              {policy.rules?.some((rule) => rule.action === "require_mfa") && (
                <Badge variant="secondary" className="mr-1">
                  MFA
                </Badge>
              )}
              {policy.rules?.some(
                (rule) => rule.action === "require_approval",
              ) && <Badge variant="secondary">Approval</Badge>}
            </TableCell>
            <TableCell>
              <Switch
                checked={policy.enabled}
                onCheckedChange={(checked) => onToggle(policy.id, checked)}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

// Create Grant Form Component (continuation in next file)
export default TemporalAccessDashboard;
