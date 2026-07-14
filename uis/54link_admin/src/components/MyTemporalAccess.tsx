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
    type Delegation,
    type TemporalGrant,
} from "@/services/temporalAccessService";
import { Clock, RefreshCw, Shield, Users } from "lucide-react";
import React, { useEffect, useState } from "react";
import { toast } from "sonner";

const MyTemporalAccess: React.FC = () => {
  const [activeTab, setActiveTab] = useState("grants");
  const [myGrants, setMyGrants] = useState<TemporalGrant[]>([]);
  const [myDelegations, setMyDelegations] = useState<Delegation[]>([]);
  const [loading, setLoading] = useState(false);

  const tenantId =
    import.meta.env.VITE_TENANT_ID ||
    localStorage.getItem("tenant_id") ||
    "54link";
  const currentUserId = localStorage.getItem("keycloak_id") || "";

  useEffect(() => {
    if (currentUserId) {
      fetchMyAccess();
    }
  }, [currentUserId]);

  const fetchMyAccess = async () => {
    setLoading(true);
    try {
      // Fetch grants for this user
      const grants = await temporalAccessService.listUserGrants(tenantId);
      setMyGrants(Array.isArray(grants) ? grants : []);

      // Fetch delegations to this user (pass user ID as fallback if backend needs it)
      const delegations = await temporalAccessService.listDelegations(tenantId);
      setMyDelegations(Array.isArray(delegations) ? delegations : []);
    } catch (error) {
      toast.error("Failed to fetch permissions");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const formatDuration = (expiresAt: string) => {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diffMs = expiry.getTime() - now.getTime();

    if (diffMs <= 0) return "Expired";

    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `${diffMins}m remaining`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h remaining`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d remaining`;
  };

  const checkPermission = async (
    permission: string,
    resourceType: string,
    resourceId: string = "",
  ) => {
    try {
      const result = await temporalAccessService.checkAccess({
        tenant_id: tenantId,
        subject_id: currentUserId,
        permission,
        resource_type: resourceType,
        resource_id: resourceId,
        context: {},
      });

      if (result.allowed) {
        let message = "✅ Permission granted";
        toast.success(message);
      } else {
        toast.error(`❌ Permission denied: ${result.reason || "No access"}`);
      }
    } catch (error) {
      toast.error("Failed to check permission");
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">My Temporal Access</h1>
          <p className="text-gray-600 mt-2">
            View your time-limited permissions and delegated access
          </p>
        </div>
        <Button onClick={fetchMyAccess} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="grants" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            My Grants ({myGrants.filter((g) => g.status === "active").length})
          </TabsTrigger>
          <TabsTrigger value="delegations" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Delegated to Me ({myDelegations.filter((d) => !d.revoked).length})
          </TabsTrigger>
          <TabsTrigger value="check" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Check Permission
          </TabsTrigger>
        </TabsList>

        <TabsContent value="grants" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Active Temporal Grants</CardTitle>
              <CardDescription>
                Time-limited permissions granted to you
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8">Loading...</div>
              ) : myGrants.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No temporal grants found
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Permission</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Expires In</TableHead>
                      <TableHead>Usage</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Conditions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {myGrants.map((grant) => (
                      <TableRow key={grant.id}>
                        <TableCell>
                          <Badge variant="default">{grant.permission}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div className="font-medium">
                              {grant.resource_type}
                            </div>
                            {grant.resource_id && (
                              <div className="text-gray-500 font-mono">
                                {grant.resource_id}
                              </div>
                            )}
                            {!grant.resource_id && (
                              <div className="text-gray-500 italic">
                                All resources
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div
                              className={
                                grant.status === "active"
                                  ? "font-medium text-green-600"
                                  : "text-gray-500"
                              }
                            >
                              {formatDuration(grant.expires_at)}
                            </div>
                            <div className="text-xs text-gray-500">
                              {formatDate(grant.expires_at)}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {grant.usage_count}
                          {grant.max_usage && ` / ${grant.max_usage}`}
                          {!grant.max_usage && " / unlimited"}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              grant.status === "active"
                                ? "default"
                                : "secondary"
                            }
                          >
                            {grant.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">
                          {grant.conditions?.require_mfa && (
                            <Badge variant="outline" className="mr-1">
                              MFA
                            </Badge>
                          )}
                          {grant.conditions?.require_liveness && (
                            <Badge variant="outline" className="mr-1">
                              Liveness
                            </Badge>
                          )}
                          {grant.conditions?.ip_whitelist &&
                            grant.conditions.ip_whitelist.length > 0 && (
                              <Badge variant="outline" className="mr-1">
                                IP Restricted
                              </Badge>
                            )}
                          {!grant.conditions?.require_mfa &&
                            !grant.conditions?.require_liveness &&
                            (!grant.conditions?.ip_whitelist ||
                              grant.conditions.ip_whitelist.length === 0) && (
                              <span className="text-gray-400">None</span>
                            )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="delegations" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Delegated Permissions</CardTitle>
              <CardDescription>
                Permissions delegated to you by other users
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8">Loading...</div>
              ) : myDelegations.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No delegations found
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Delegated By</TableHead>
                      <TableHead>Permission</TableHead>
                      <TableHead>Resource</TableHead>
                      <TableHead>Granted At</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {myDelegations.map((delegation) => (
                      <TableRow key={delegation.id}>
                        <TableCell className="font-mono text-sm">
                          {delegation.delegator_id}
                        </TableCell>
                        <TableCell>
                          <Badge variant="default">
                            {delegation.permission}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="text-sm">
                            <div className="font-medium">
                              {delegation.resource_type}
                            </div>
                            {delegation.resource_id && (
                              <div className="text-gray-500 font-mono">
                                {delegation.resource_id}
                              </div>
                            )}
                            {!delegation.resource_id && (
                              <div className="text-gray-500 italic">
                                All resources
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm">
                          {formatDate(delegation.created_at)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              delegation.revoked ? "secondary" : "default"
                            }
                          >
                            {delegation.revoked ? "Revoked" : "Active"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="check" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Check My Permissions</CardTitle>
              <CardDescription>
                Test if you have permission to perform specific actions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PermissionChecker
                currentUserId={currentUserId}
                tenantId={tenantId}
                onCheck={checkPermission}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

const PermissionChecker: React.FC<{
  currentUserId: string;
  tenantId: string;
  onCheck: (
    permission: string,
    resourceType: string,
    resourceId: string,
  ) => void;
}> = ({ currentUserId, tenantId, onCheck }) => {
  const [permission, setPermission] = useState("approve");
  const [resourceType, setResourceType] = useState("loan");
  const [resourceId, setResourceId] = useState("");
  console.log(currentUserId,tenantId)

  const handleCheck = () => {
    if (!permission || !resourceType) {
      toast.error("Permission and resource type are required");
      return;
    }
    onCheck(permission, resourceType, resourceId);
  };

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-900">
              Quick Permission Check
            </h3>
            <p className="text-sm text-blue-700 mt-1">
              Enter the action you want to perform and we'll check if you have
              the necessary permissions (grants, delegations, or policies).
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Permission</label>
          <select
            className="w-full p-2 border rounded"
            value={permission}
            onChange={(e) => setPermission(e.target.value)}
          >
            <option value="approve">Approve</option>
            <option value="view">View</option>
            <option value="modify">Modify</option>
            <option value="delete">Delete</option>
            <option value="initiate">Initiate</option>
            <option value="reject">Reject</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Resource Type</label>
          <select
            className="w-full p-2 border rounded"
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
          >
            <option value="loan">Loan</option>
            <option value="account">Account</option>
            <option value="transaction">Transaction</option>
            <option value="payment">Payment</option>
            <option value="card">Card</option>
            <option value="customer">Customer</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Resource ID (optional)</label>
          <input
            type="text"
            className="w-full p-2 border rounded"
            placeholder="loan_123"
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
          />
        </div>
      </div>

      <Button onClick={handleCheck} className="w-full">
        <Shield className="h-4 w-4 mr-2" />
        Check Permission
      </Button>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="font-medium text-sm mb-2">What gets checked:</h4>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>✓ Temporal grants assigned to you</li>
          <li>✓ Permissions delegated to you</li>
          <li>✓ Access policies requiring MFA or approval</li>
          <li>✓ Your base permissions from Permify</li>
        </ul>
      </div>
    </div>
  );
};

export default MyTemporalAccess;
