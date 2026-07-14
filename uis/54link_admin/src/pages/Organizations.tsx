import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// ...existing code...
import type {
    Organization,
} from "@/types/developerPlatform";
import { AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Use mock data for now
    setLoading(true);
    setTimeout(() => {
      setOrganizations([
        {
          id: "org-1",
          name: "Acme Corp",
          legal_name: "Acme Corporation",
          country: "NG",
          kyb_status: "verified",
          tier_level: "enterprise",
          total_developers: 1,
          total_apps: 2,
          monthly_revenue: 100000,
          status: "active",
          created_at: new Date().toISOString(),
        },
      ]);
      setLoading(false);
    }, 500);
  }, []); // Fixed: removed undefined 'filters' and 'page' from dependencies

  const loadOrganizations = async () => {
    try {
      setLoading(true);
      setError(null);
      // Use mock data for now
      setTimeout(() => {
        setOrganizations([
          {
            id: "org-1",
            name: "Acme Corp",
            legal_name: "Acme Corporation",
            country: "NG",
            kyb_status: "verified",
            tier_level: "enterprise",
            total_developers: 1,
            total_apps: 2,
            monthly_revenue: 100000,
            status: "active",
            created_at: new Date().toISOString(),
          },
        ]);
        setLoading(false);
      }, 500);
      // Uncomment when ready to use real API:
      // const response = await developerPlatformService.listOrganizations();
      // setOrganizations(response.organizations);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load organizations";
      setError(message);
      setLoading(false);
    }
  };

  if (loading) return <div className="p-6">Loading organizations...</div>;
  if (error)
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={loadOrganizations} className="mt-4">
          Retry
        </Button>
      </div>
    );

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold mb-4">Organizations</h1>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {organizations.map((org) => (
          <Card key={org.id}>
            <CardHeader>
              <CardTitle>{org.name}</CardTitle>
              <div className="flex gap-2 mt-2">
                <Badge variant="secondary">{org.country}</Badge>
                <Badge variant="outline">{org.kyb_status}</Badge>
                <Badge variant="outline">{org.tier_level}</Badge>
                <Badge
                  variant={org.status === "active" ? "default" : "destructive"}
                >
                  {org.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground mb-2">
                Legal: {org.legal_name}
              </div>
              <div className="text-sm">
                Apps: {org.total_apps} | Developers: {org.total_developers}
              </div>
              <div className="text-sm">
                Revenue: ₦{(org.monthly_revenue / 100).toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                Created: {new Date(org.created_at).toLocaleDateString()}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
