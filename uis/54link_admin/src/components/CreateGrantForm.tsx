import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { DialogHeader, DialogTitle } from "@/components/ui/dialog";
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
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  temporalAccessService,
  type UserSearchResult,
} from "@/services/temporalAccessService";
import { Check, ChevronsUpDown, Plus, X } from "lucide-react";
import React, { useState } from "react";
import { toast } from "sonner";

interface CreateGrantFormProps {
  tenantId: string;
  onSuccess: () => void;
}

const CreateGrantForm: React.FC<CreateGrantFormProps> = ({
  tenantId,
  onSuccess,
}) => {
  const [formData, setFormData] = useState({
    subject_id: "",
    subject_email: "",
    permission: "view",
    resource_type: "account",
    resource_id: "",
    duration: "30m",
    reason: "",
    max_usage: 0,
  });

  const [conditions, setConditions] = useState({
    require_mfa: false,
    require_liveness: false,
    ip_whitelist: [] as string[],
    device_ids: [] as string[],
  });

  const [newIP, setNewIP] = useState("");
  const [newDeviceID, setNewDeviceID] = useState("");
  const [openUserSearch, setOpenUserSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<UserSearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const handleUserSearch = async (query: string) => {
    setSearchQuery(query);
    setSearching(true);

    try {
      const results = await temporalAccessService.searchUsers(query, tenantId);
      setSearchResults(results);
    } catch (error) {
      console.error("Error searching users:", error);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const selectUser = (user: UserSearchResult) => {
    setFormData({
      ...formData,
      subject_id: user.keycloak_id,
      subject_email: user.email,
    });
    setOpenUserSearch(false);
    setSearchQuery("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.subject_id) {
      toast.error("Please select a user");
      return;
    }

    try {
      await temporalAccessService.createGrant({
        tenant_id: tenantId,
        subject_id: formData.subject_id,
        subject_type: "user",
        permission: formData.permission,
        resource_type: formData.resource_type,
        resource_id: formData.resource_id,
        duration: formData.duration,
        reason: formData.reason,
        max_usage: formData.max_usage || undefined,
        conditions: {
          ip_whitelist:
            conditions.ip_whitelist.length > 0
              ? conditions.ip_whitelist
              : undefined,
          device_ids:
            conditions.device_ids.length > 0
              ? conditions.device_ids
              : undefined,
          require_mfa: conditions.require_mfa,
          require_liveness: conditions.require_liveness,
        },
      });

      toast.success("Temporal grant created successfully");

      onSuccess();
    } catch (error) {
      toast.error("Failed to create grant");
    }
  };

  const addIP = () => {
    if (newIP && !conditions.ip_whitelist.includes(newIP)) {
      setConditions({
        ...conditions,
        ip_whitelist: [...conditions.ip_whitelist, newIP],
      });
      setNewIP("");
    }
  };

  const removeIP = (ip: string) => {
    setConditions({
      ...conditions,
      ip_whitelist: conditions.ip_whitelist.filter((i) => i !== ip),
    });
  };

  const addDeviceID = () => {
    if (newDeviceID && !conditions.device_ids.includes(newDeviceID)) {
      setConditions({
        ...conditions,
        device_ids: [...conditions.device_ids, newDeviceID],
      });
      setNewDeviceID("");
    }
  };

  const removeDeviceID = (id: string) => {
    setConditions({
      ...conditions,
      device_ids: conditions.device_ids.filter((d) => d !== id),
    });
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>Create Temporal Grant</DialogTitle>
      </DialogHeader>

      <form onSubmit={handleSubmit} className="space-y-6 mt-4">
        {/* Basic Information */}
        <div className="space-y-4">
          <div>
            <Label htmlFor="subject">User / Admin</Label>
            <Popover open={openUserSearch} onOpenChange={setOpenUserSearch}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={openUserSearch}
                  className="w-full justify-between"
                >
                  {formData.subject_email || "Search for user..."}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-full p-0">
                <Command>
                  <CommandInput
                    placeholder="Search by email or ID..."
                    value={searchQuery}
                    onValueChange={handleUserSearch}
                  />
                  <CommandList>
                    <CommandEmpty>
                      {searching ? "Searching..." : "No users found"}
                    </CommandEmpty>
                    <CommandGroup>
                      {searchResults.map((user) => (
                        <CommandItem
                          key={user.id}
                          value={user.email}
                          onSelect={() => selectUser(user)}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              formData.subject_id === user.keycloak_id
                                ? "opacity-100"
                                : "opacity-0",
                            )}
                          />
                          <div className="flex flex-col">
                            <span>{user.email}</span>
                            <span className="text-xs text-muted-foreground">
                              {user.user_role} • ID: {user.keycloak_id}
                            </span>
                          </div>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            {formData.subject_id && (
              <p className="text-sm text-muted-foreground mt-1">
                Selected: {formData.subject_email} ({formData.subject_id})
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="resource_type">Resource Type</Label>
              <Select
                value={formData.resource_type}
                onValueChange={(value) =>
                  setFormData({ ...formData, resource_type: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="account">Account</SelectItem>
                  <SelectItem value="transaction">Transaction</SelectItem>
                  <SelectItem value="loan">Loan</SelectItem>
                  <SelectItem value="card">Card</SelectItem>
                  <SelectItem value="customer">Customer</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="resource_id">Resource ID</Label>
              <Input
                id="resource_id"
                placeholder="acc_456 (leave empty for all)"
                value={formData.resource_id}
                onChange={(e) =>
                  setFormData({ ...formData, resource_id: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="permission">Permission</Label>
              <Select
                value={formData.permission}
                onValueChange={(value) =>
                  setFormData({ ...formData, permission: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="view">View</SelectItem>
                  <SelectItem value="edit">Edit</SelectItem>
                  <SelectItem value="transact">Transact</SelectItem>
                  <SelectItem value="approve">Approve</SelectItem>
                  <SelectItem value="audit">Audit</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="duration">Duration</Label>
              <Select
                value={formData.duration}
                onValueChange={(value) =>
                  setFormData({ ...formData, duration: value })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15m">15 minutes</SelectItem>
                  <SelectItem value="30m">30 minutes</SelectItem>
                  <SelectItem value="1h">1 hour</SelectItem>
                  <SelectItem value="4h">4 hours</SelectItem>
                  <SelectItem value="8h">8 hours</SelectItem>
                  <SelectItem value="24h">24 hours</SelectItem>
                  <SelectItem value="7d">7 days</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div>
            <Label htmlFor="max_usage">Max Usage Count (0 = unlimited)</Label>
            <Input
              id="max_usage"
              type="number"
              min="0"
              value={formData.max_usage}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  max_usage: parseInt(e.target.value),
                })
              }
            />
          </div>

          <div>
            <Label htmlFor="reason">Reason</Label>
            <Textarea
              id="reason"
              placeholder="Explain why this grant is needed..."
              value={formData.reason}
              onChange={(e) =>
                setFormData({ ...formData, reason: e.target.value })
              }
              required
            />
          </div>
        </div>

        {/* Conditions */}
        <div className="space-y-4 border-t pt-4">
          <h3 className="font-semibold">Access Conditions</h3>

          <div className="flex items-center justify-between">
            <Label htmlFor="require_mfa">Require MFA</Label>
            <Switch
              id="require_mfa"
              checked={conditions.require_mfa}
              onCheckedChange={(checked) =>
                setConditions({ ...conditions, require_mfa: checked })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="require_liveness">Require Biometric Liveness</Label>
            <Switch
              id="require_liveness"
              checked={conditions.require_liveness}
              onCheckedChange={(checked) =>
                setConditions({ ...conditions, require_liveness: checked })
              }
            />
          </div>

          {/* IP Whitelist */}
          <div>
            <Label>IP Whitelist (CIDR notation supported)</Label>
            <div className="flex gap-2 mt-2">
              <Input
                placeholder="192.168.1.0/24 or 10.0.0.1"
                value={newIP}
                onChange={(e) => setNewIP(e.target.value)}
                onKeyPress={(e) =>
                  e.key === "Enter" && (e.preventDefault(), addIP())
                }
              />
              <Button type="button" onClick={addIP} size="sm">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {conditions.ip_whitelist.map((ip) => (
                <Badge key={ip} variant="secondary">
                  {ip}
                  <button
                    type="button"
                    onClick={() => removeIP(ip)}
                    className="ml-2"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>

          {/* Device IDs */}
          <div>
            <Label>Allowed Device IDs</Label>
            <div className="flex gap-2 mt-2">
              <Input
                placeholder="device_abc123"
                value={newDeviceID}
                onChange={(e) => setNewDeviceID(e.target.value)}
                onKeyPress={(e) =>
                  e.key === "Enter" && (e.preventDefault(), addDeviceID())
                }
              />
              <Button type="button" onClick={addDeviceID} size="sm">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {conditions.device_ids.map((id) => (
                <Badge key={id} variant="secondary">
                  {id}
                  <button
                    type="button"
                    onClick={() => removeDeviceID(id)}
                    className="ml-2"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button type="submit">Create Grant</Button>
        </div>
      </form>
    </>
  );
};

export default CreateGrantForm;
