// @ts-nocheck
/**
 * GeofencingTab.tsx
 * Admin Panel tab for managing geofence zones, assigning agents to zones,
 * viewing compliance reports, and reviewing geofence violation alerts.
 *
 * Features:
 * - Zone type selector (8 types matching platform geofencing service)
 * - Circle geometry (lat/lng/radius) OR Polygon geometry (GeoJSON coordinates)
 * - Platform proxy integration via geofencing.createZone / updateZone
 * - Compliance reports, location history, agent assignment
 */
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import {
  MapPin,
  Plus,
  Trash2,
  RefreshCw,
  FileText,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Hexagon,
  Circle,
} from "lucide-react";

// ─── Zone types (matches platform geofencing service — 8 types) ──────────────
const ZONE_TYPES = [
  {
    value: "AGENT_OPERATING_AREA",
    label: "Agent Operating Area",
    description: "Primary area where agent is authorised to transact",
  },
  {
    value: "MERCHANT_DELIVERY_ZONE",
    label: "Merchant Delivery Zone",
    description: "Zone for merchant delivery agents",
  },
  {
    value: "RESTRICTED_ZONE",
    label: "Restricted Zone",
    description: "Area where agent is NOT allowed to transact",
  },
  {
    value: "HIGH_RISK_AREA",
    label: "High Risk Area",
    description: "Elevated fraud monitoring and stricter velocity limits",
  },
  {
    value: "PREMIUM_ZONE",
    label: "Premium Zone",
    description: "High-value area with elevated commission rates",
  },
  {
    value: "MARKET_ZONE",
    label: "Market Zone",
    description: "High-density market area with relaxed velocity limits",
  },
  {
    value: "CAMPUS_ZONE",
    label: "Campus Zone",
    description: "University or campus area",
  },
  {
    value: "INDUSTRIAL_ZONE",
    label: "Industrial Zone",
    description: "Industrial estate or factory area",
  },
] as const;

type ZoneTypeValue = (typeof ZONE_TYPES)[number]["value"];

// ─── Zone List ────────────────────────────────────────────────────────────────
function ZoneList() {
  const utils = trpc.useUtils();
  const [showCreate, setShowCreate] = useState(false);
  const [geometryMode, setGeometryMode] = useState<"circle" | "polygon">(
    "circle"
  );
  const [form, setForm] = useState({
    name: "",
    description: "",
    zoneType: "AGENT_OPERATING_AREA" as ZoneTypeValue,
    latitude: "",
    longitude: "",
    radiusMetres: "500",
    polygonCoordinates: "",
    state: "",
    lga: "",
    alertOnEntry: false,
    alertOnExit: true,
  });

  const {
    data: zones,
    isLoading,
    refetch,
  } = trpc.geofencing.listZones.useQuery();

  const createZone = trpc.geofencing.createZone.useMutation({
    onSuccess: () => {
      toast.success(`Zone "${form.name}" created and is now active.`);
      setShowCreate(false);
      setForm({
        name: "",
        description: "",
        zoneType: "AGENT_OPERATING_AREA",
        latitude: "",
        longitude: "",
        radiusMetres: "500",
        polygonCoordinates: "",
        state: "",
        lga: "",
        alertOnEntry: false,
        alertOnExit: true,
      });
      setGeometryMode("circle");
      utils.geofencing.listZones.invalidate();
    },
    onError: e => toast.error(e.message),
  });

  const deleteZone = trpc.geofencing.deleteZone.useMutation({
    onSuccess: () => {
      toast.success("Zone deleted.");
      utils.geofencing.listZones.invalidate();
    },
    onError: e => toast.error(e.message),
  });

  const toggleZone = trpc.geofencing.updateZone.useMutation({
    onSuccess: () => utils.geofencing.listZones.invalidate(),
  });

  const handleCreate = () => {
    let polygonCoords: [number, number][][] | undefined;
    if (geometryMode === "polygon") {
      try {
        const parsed = JSON.parse(form.polygonCoordinates);
        if (!Array.isArray(parsed)) throw new Error("Must be an array");
        polygonCoords = parsed;
      } catch {
        toast.error(
          "Invalid polygon coordinates. Must be a valid JSON array of [lng, lat] pairs."
        );
        return;
      }
    }
    createZone.mutate({
      name: form.name,
      description: form.description || undefined,
      zoneType: form.zoneType,
      ...(geometryMode === "circle"
        ? {
            latitude: parseFloat(form.latitude),
            longitude: parseFloat(form.longitude),
            radiusMetres: parseInt(form.radiusMetres, 10),
          }
        : {
            polygonCoordinates: polygonCoords,
          }),
      state: form.state || undefined,
      lga: form.lga || undefined,
      alertOnEntry: form.alertOnEntry,
      alertOnExit: form.alertOnExit,
    });
  };

  const isCreateDisabled =
    createZone.isPending ||
    !form.name ||
    (geometryMode === "circle"
      ? !form.latitude || !form.longitude
      : !form.polygonCoordinates);

  const zoneTypeMeta = (value: string) =>
    ZONE_TYPES.find(z => z.value === value);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Geofence Zones
        </h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5 mr-1" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="h-3.5 w-3.5 mr-1" /> New Zone
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading zones…</div>
      ) : !zones?.length ? (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <MapPin className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No geofence zones configured.
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Create a zone to restrict where agents can process transactions.
          </p>
        </div>
      ) : (
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Zone Name</th>
                <th className="text-left px-3 py-2 font-medium">Type</th>
                <th className="text-left px-3 py-2 font-medium">Geometry</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-left px-3 py-2 font-medium">Created By</th>
                <th className="text-left px-3 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {zones.map(zone => {
                const isPolygon = !!(zone as any).polygonCoordinates;
                const meta = zoneTypeMeta(
                  (zone as any).zoneType ?? "AGENT_OPERATING_AREA"
                );
                return (
                  <tr
                    key={zone.id}
                    className="border-t hover:bg-muted/30 transition-colors"
                  >
                    <td className="px-3 py-2 font-medium">
                      <div>{zone.name}</div>
                      {zone.description && (
                        <div className="text-xs text-muted-foreground">
                          {zone.description}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="outline" className="text-xs">
                        {meta?.label ?? "Operating Area"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {isPolygon ? (
                        <span className="flex items-center gap-1">
                          <Hexagon className="h-3 w-3" /> Polygon
                        </span>
                      ) : (
                        <span className="flex items-center gap-1">
                          <Circle className="h-3 w-3" /> Circle ·{" "}
                          {(zone.radiusMetres ?? 0) >= 1000
                            ? `${((zone.radiusMetres ?? 0) / 1000).toFixed(1)} km`
                            : `${zone.radiusMetres ?? 0} m`}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant={zone.isActive ? "default" : "secondary"}>
                        {zone.isActive ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {zone.createdBy ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() =>
                            toggleZone.mutate({
                              id: zone.id,
                              isActive: !zone.isActive,
                            })
                          }
                        >
                          {zone.isActive ? "Disable" : "Enable"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                          onClick={() => {
                            if (
                              confirm(
                                `Delete zone "${zone.name}"? This cannot be undone.`
                              )
                            ) {
                              deleteZone.mutate({ id: zone.id });
                            }
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Zone Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Geofence Zone</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            {/* Zone Name */}
            <div>
              <Label>Zone Name *</Label>
              <Input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="e.g. Lagos Island Branch"
              />
            </div>
            {/* Description */}
            <div>
              <Label>Description</Label>
              <Input
                value={form.description}
                onChange={e =>
                  setForm(f => ({ ...f, description: e.target.value }))
                }
                placeholder="Optional description"
              />
            </div>
            {/* Zone Type */}
            <div>
              <Label>Zone Type *</Label>
              <Select
                value={form.zoneType}
                onValueChange={v =>
                  setForm(f => ({ ...f, zoneType: v as ZoneTypeValue }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select zone type" />
                </SelectTrigger>
                <SelectContent>
                  {ZONE_TYPES.map(zt => (
                    <SelectItem key={zt.value} value={zt.value}>
                      <div>
                        <div className="font-medium">{zt.label}</div>
                        <div className="text-xs text-muted-foreground">
                          {zt.description}
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {/* Geometry Mode Toggle */}
            <div>
              <Label>Geometry Type *</Label>
              <div className="flex gap-2 mt-1">
                <Button
                  type="button"
                  size="sm"
                  variant={geometryMode === "circle" ? "default" : "outline"}
                  onClick={() => setGeometryMode("circle")}
                  className="flex-1"
                >
                  <Circle className="h-3.5 w-3.5 mr-1" /> Circle
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={geometryMode === "polygon" ? "default" : "outline"}
                  onClick={() => setGeometryMode("polygon")}
                  className="flex-1"
                >
                  <Hexagon className="h-3.5 w-3.5 mr-1" /> Polygon
                </Button>
              </div>
            </div>
            {/* Circle geometry */}
            {geometryMode === "circle" && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Latitude *</Label>
                    <Input
                      value={form.latitude}
                      onChange={e =>
                        setForm(f => ({ ...f, latitude: e.target.value }))
                      }
                      placeholder="6.4550"
                      type="number"
                      step="0.00001"
                    />
                  </div>
                  <div>
                    <Label>Longitude *</Label>
                    <Input
                      value={form.longitude}
                      onChange={e =>
                        setForm(f => ({ ...f, longitude: e.target.value }))
                      }
                      placeholder="3.3841"
                      type="number"
                      step="0.00001"
                    />
                  </div>
                </div>
                <div>
                  <Label>Radius (metres) *</Label>
                  <Input
                    value={form.radiusMetres}
                    onChange={e =>
                      setForm(f => ({ ...f, radiusMetres: e.target.value }))
                    }
                    type="number"
                    min="50"
                    max="100000"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Min 50 m · Max 100 km. Typical branch: 200–500 m.
                  </p>
                </div>
              </>
            )}
            {/* Polygon geometry */}
            {geometryMode === "polygon" && (
              <div>
                <Label>Polygon Coordinates (GeoJSON) *</Label>
                <Textarea
                  value={form.polygonCoordinates}
                  onChange={e =>
                    setForm(f => ({ ...f, polygonCoordinates: e.target.value }))
                  }
                  rows={5}
                  placeholder={`[[3.3841, 6.4550], [3.3900, 6.4550], [3.3900, 6.4600], [3.3841, 6.4600], [3.3841, 6.4550]]`}
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground mt-1">
                  Enter a JSON array of [longitude, latitude] coordinate pairs.
                  First and last point must be the same to close the polygon.
                </p>
              </div>
            )}
            {/* Optional metadata */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>State</Label>
                <Input
                  value={form.state}
                  onChange={e =>
                    setForm(f => ({ ...f, state: e.target.value }))
                  }
                  placeholder="e.g. Lagos"
                />
              </div>
              <div>
                <Label>LGA</Label>
                <Input
                  value={form.lga}
                  onChange={e => setForm(f => ({ ...f, lga: e.target.value }))}
                  placeholder="e.g. Lagos Island"
                />
              </div>
            </div>
            {/* Alert settings */}
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.alertOnEntry}
                  onChange={e =>
                    setForm(f => ({ ...f, alertOnEntry: e.target.checked }))
                  }
                  className="rounded"
                />
                Alert on Entry
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.alertOnExit}
                  onChange={e =>
                    setForm(f => ({ ...f, alertOnExit: e.target.checked }))
                  }
                  className="rounded"
                />
                Alert on Exit
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button disabled={isCreateDisabled} onClick={handleCreate}>
              {createZone.isPending ? "Creating…" : "Create Zone"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── Compliance Reports ───────────────────────────────────────────────────────
function ComplianceReports() {
  const {
    data: reports,
    isLoading,
    refetch,
  } = trpc.geofencing.listComplianceReports.useQuery({ limit: 12 });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Compliance Reports
        </h3>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-3.5 w-3.5 mr-1" /> Refresh
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Weekly security compliance reports are generated every Monday at 08:00
        UTC and stored here.
      </p>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">Loading reports…</div>
      ) : !reports?.length ? (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <FileText className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No compliance reports yet.
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            The first report will be generated next Monday at 08:00 UTC.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map(report => {
            const start = new Date(
              report.periodStart ?? Date.now()
            ).toLocaleDateString("en-NG", { dateStyle: "medium" });
            const end = new Date(
              report.periodEnd ?? Date.now()
            ).toLocaleDateString("en-NG", { dateStyle: "medium" });
            return (
              <Card key={report.id} className="border">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-medium">
                        {start} — {end}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {report.totalAlerts} total alerts · {report.highAlerts}{" "}
                        high · {report.escalatedAlerts} escalated
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {report.totalAlerts === 0 ? (
                        <CheckCircle className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-amber-500" />
                      )}
                      {report.pdfUrl && (
                        <a
                          href={report.pdfUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-blue-500 hover:underline flex items-center gap-1"
                        >
                          <FileText className="h-3 w-3" /> PDF
                        </a>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Location History ─────────────────────────────────────────────────────────
function LocationHistory() {
  const [deviceId, setDeviceId] = useState("");
  const [searched, setSearched] = useState<number | null>(null);
  const { data, isLoading } = trpc.geofencing.getLocationHistory.useQuery(
    { deviceId: searched!, limit: 50 },
    { enabled: searched !== null }
  );

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-foreground">
        Terminal Location History
      </h3>
      <div className="flex gap-2">
        <Input
          value={deviceId}
          onChange={e => setDeviceId(e.target.value)}
          placeholder="Device ID (number)"
          type="number"
          className="max-w-xs"
        />
        <Button
          size="sm"
          onClick={() => setSearched(parseInt(deviceId, 10))}
          disabled={!deviceId}
        >
          Search
        </Button>
      </div>

      {isLoading && (
        <div className="text-sm text-muted-foreground">Loading…</div>
      )}
      {data && data.length === 0 && (
        <div className="text-sm text-muted-foreground">
          No location history found for this agent.
        </div>
      )}
      {data && data.length > 0 && (
        <div className="rounded-md border overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-3 py-2 font-medium">Time</th>
                <th className="text-left px-3 py-2 font-medium">Coordinates</th>
                <th className="text-left px-3 py-2 font-medium">Accuracy</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((loc: any) => (
                <tr key={loc.id} className="border-t hover:bg-muted/30">
                  <td className="px-3 py-2 font-mono">
                    {new Date(loc.recordedAt).toLocaleString("en-NG")}
                  </td>
                  <td className="px-3 py-2 font-mono">
                    {parseFloat(loc.latitude).toFixed(5)},{" "}
                    {parseFloat(loc.longitude).toFixed(5)}
                  </td>
                  <td className="px-3 py-2">
                    {loc.accuracy ? `±${loc.accuracy}m` : "—"}
                  </td>
                  <td className="px-3 py-2">
                    {loc.withinZone ? (
                      <span className="flex items-center gap-1 text-emerald-600">
                        <CheckCircle className="h-3 w-3" /> In Zone
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-red-500">
                        <XCircle className="h-3 w-3" /> Out of Zone
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Geofencing Stats ─────────────────────────────────────────────────────────
function GeofencingStats() {
  const { data: stats } = trpc.geofencing.stats.useQuery();

  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {[
        {
          label: "Active Zones",
          value: stats.activeZones,
          icon: <Shield className="h-4 w-4" />,
          color: "text-emerald-400",
        },
        {
          label: "Agent Assignments",
          value: stats.agentAssignments,
          icon: <CheckCircle className="h-4 w-4" />,
          color: "text-amber-400",
        },
        {
          label: "Violations (24h)",
          value: stats.violations24h,
          icon: <AlertTriangle className="h-4 w-4" />,
          color: "text-red-400",
        },
      ].map(s => (
        <Card key={s.label} className="border">
          <CardContent className="pt-4 pb-3">
            <div className={`flex items-center gap-2 mb-1 ${s.color}`}>
              {s.icon}
              <span className="text-xs text-muted-foreground">{s.label}</span>
            </div>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value ?? 0}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ─── Main GeofencingTab ───────────────────────────────────────────────────────
export function GeofencingTab() {
  const [activeSection, setActiveSection] = useState<
    "zones" | "reports" | "history"
  >("zones");

  return (
    <div className="space-y-6">
      <GeofencingStats />

      {/* Section tabs */}
      <div className="flex gap-2 border-b pb-2">
        {(["zones", "reports", "history"] as const).map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md capitalize transition-colors ${
              activeSection === s
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            {s === "zones"
              ? "Zones"
              : s === "reports"
                ? "Compliance Reports"
                : "Location History"}
          </button>
        ))}
      </div>

      {activeSection === "zones" && <ZoneList />}
      {activeSection === "reports" && <ComplianceReports />}
      {activeSection === "history" && <LocationHistory />}
    </div>
  );
}
