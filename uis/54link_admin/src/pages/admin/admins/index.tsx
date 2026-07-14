import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Calendar,
    CheckCircle,
    Edit2,
    Loader2,
    Mail,
    MoreVertical,
    Phone,
    Search,
    Shield,
    Trash2,
    UserPlus,
    XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import CascadingAddressDropdown from "../../../components/shared/CascadingAddressDropdown";
import { useTenantBranding } from "../../../contexts/TenantBrandingContext";
import {
    createAdmin,
    getAdmins,
    suspendAdmin,
    unsuspendAdmin,
} from "../../../services/admin/adminService";

// Platform role options (v2.perm `platform` entity named roles)
const PLATFORM_ROLES = [
  { value: "support_agent", label: "Support Agent" },
  { value: "relationship_manager", label: "Relationship Manager" },
  { value: "operations_manager", label: "Operations Manager" },
  { value: "risk_manager", label: "Risk Manager" },
  { value: "compliance_officer", label: "Compliance Officer" },
  { value: "internal_auditor", label: "Internal Auditor" },
  { value: "it_admin", label: "IT Admin" },
  { value: "tenant_manager", label: "Tenant Manager" },
  { value: "super_admin", label: "Super Admin" },
];

type Admin = {
  id: string;
  name: string;
  email: string;
  phone: string;
  access_level: string;
  role?: string;
  platform_role?: string;
  status: "active" | "inactive";
  createdAt: string | Date;
  lastLogin?: string | Date;
  permissions: string[];
  uin?: string;
  firstName?: string;
  lastName?: string;
  tenantId?: string;
  keycloakId?: string;
  isVerified?: boolean;
  isSuspended?: boolean;
  country?: string;
  state?: string;
  city?: string;
};

export default function AdminManagement() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAddingAdmin, setIsAddingAdmin] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [verificationDialog, setVerificationDialog] = useState<{
    open: boolean;
    link: string | null;
  }>({ open: false, link: null });
  const [selectedAdmin, setSelectedAdmin] = useState<Admin | null>(null);
  const [filterRole, setFilterRole] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    uin: "",
    password: "",
    firstName: "",
    lastName: "",
    country: "",
    state: "",
    city: "",
    platform_role: "support_agent",
    role: "viewer" as Admin["role"],
    status: "active" as Admin["status"],
    permissions: [] as string[],
  });

  // Fetch admins from API
  useEffect(() => {
    setLoading(true);
    getAdmins()
      .then((data) => {
        // If response is { message, admins: [...] }
        const adminsRaw = data.admins || data;
        setAdmins(
          adminsRaw.map((admin: any) => ({
            id: admin.id,
            name: [admin.first_name, admin.last_name].filter(Boolean).join(" "),
            email: admin.email,
            phone: admin.phone,
            role: "admin", // or use admin.role if available
            status: admin.is_suspended ? "inactive" : "active",
            platform_role: admin.platform_role || "support_agent",
            createdAt: admin.created_at
              ? new Date(admin.created_at)
              : new Date(),
            lastLogin: admin.last_login
              ? new Date(admin.last_login)
              : undefined,
            permissions: [], // fill if available
            uin: admin.uin,
            tenantId: admin.tenant_id,
            keycloakId: admin.keycloak_id,
            isVerified: admin.is_verified,
            isSuspended: admin.is_suspended,
          })),
        );
      })
      .catch(() => setAdmins([]))
      .finally(() => setLoading(false));
  }, []);

  const handleAddAdmin = async () => {
    setIsAddingAdmin(true);
    // Split name into firstName and lastName if not provided
    let firstName = formData.firstName;
    let lastName = formData.lastName;
    if (!firstName || !lastName) {
      const [first, ...rest] = formData.name.split(" ");
      firstName = first;
      lastName = rest.join(" ");
    }
    const payload = {
      email: formData.email,
      firstName,
      lastName,
      phone: formData.phone,
      uin: formData.uin,
      password: formData.password,
      platformRole: formData.platform_role || "support_agent",
    };
    try {
      const response = await createAdmin(payload);
      // Refresh admin list
      const data = await getAdmins();
      const adminsRaw = data.admins || data;
      setAdmins(
        adminsRaw.map((admin: any) => ({
          ...admin,
          createdAt: admin.createdAt ? new Date(admin.createdAt) : new Date(),
          lastLogin: admin.lastLogin ? new Date(admin.lastLogin) : undefined,
        })),
      );
      setIsAddDialogOpen(false);
      resetForm();
      // Show verification link dialog
      setVerificationDialog({
        open: true,
        link: response.verification || null,
      });
    } catch (e) {
      alert(`Failed to create admin.${e}`);
    } finally {
      setIsAddingAdmin(false);
    }
    {
      /* Verification Link Dialog */
    }
    <Dialog
      open={verificationDialog.open}
      onOpenChange={(open) => setVerificationDialog((v) => ({ ...v, open }))}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Admin Created</DialogTitle>
          <DialogDescription>
            The admin was created successfully. Please share the verification
            link below with the new admin to complete their onboarding:
          </DialogDescription>
        </DialogHeader>
        {verificationDialog.link && (
          <div className="mt-4">
            <a
              href={verificationDialog.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline break-all"
            >
              {verificationDialog.link}
            </a>
          </div>
        )}
        <DialogFooter>
          <Button
            onClick={() => setVerificationDialog({ open: false, link: null })}
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>;
  };

  const handleEditAdmin = () => {
    if (!selectedAdmin) return;
    setAdmins(
      admins.map((admin) =>
        admin.id === selectedAdmin.id ? { ...admin, ...formData } : admin,
      ),
    );
    setIsEditDialogOpen(false);
    setSelectedAdmin(null);
    resetForm();
  };

  const handleDeleteAdmin = (adminId: string) => {
    if (confirm("Are you sure you want to delete this admin?")) {
      setAdmins(admins.filter((admin) => admin.id !== adminId));
    }
  };

  const handleToggleStatus = async (adminId: string) => {
    const admin = admins.find((a) => a.id === adminId);
    if (!admin) return;
    setLoading(true);
    try {
      if (admin.status === "active") {
        await suspendAdmin(adminId);
      } else {
        await unsuspendAdmin(adminId);
      }
      // Refresh list
      const data = await getAdmins();
      setAdmins(
        data.map((admin: any) => ({
          ...admin,
          createdAt: admin.createdAt ? new Date(admin.createdAt) : new Date(),
          lastLogin: admin.lastLogin ? new Date(admin.lastLogin) : undefined,
        })),
      );
    } catch (e) {
      // Optionally show error
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      email: "",
      phone: "",
      uin: "",
      password: "",
      firstName: "",
      lastName: "",
      country: "",
      state: "",
      city: "",
      platform_role: "support_agent",
      role: "viewer",
      status: "active",
      permissions: [],
    });
  };

  const openEditDialog = (admin: Admin) => {
    setSelectedAdmin(admin);
    const [firstName, ...lastNameParts] = admin.name.split(" ");
    setFormData({
      name: admin.name,
      email: admin.email,
      phone: admin.phone,
      uin: admin.uin || "",
      password: "",
      firstName: admin.firstName || firstName || "",
      lastName: admin.lastName || lastNameParts.join(" ") || "",
      country: admin.country || "",
      state: admin.state || "",
      city: admin.city || "",
      platform_role: admin.platform_role || "support_agent",
      role: admin.role,
      status: admin.status,
      permissions: admin.permissions,
    });
    setIsEditDialogOpen(true);
  };

  const filteredAdmins = admins.filter((admin) => {
    const name = admin.name || "";
    const email = admin.email || "";
    const matchesSearch =
      name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = filterRole === "all" || admin.role === filterRole;
    const matchesStatus =
      filterStatus === "all" || admin.status === filterStatus;
    return matchesSearch && matchesRole && matchesStatus;
  });

  const getRoleBadge = (role: Admin["role"]) => {
    switch (role) {
      case "super_admin":
        return (
          <Badge className="bg-purple-600 hover:bg-purple-700">
            Super Admin
          </Badge>
        );
      case "admin":
        return (
          <Badge
            style={{ backgroundColor: primaryColor }}
            className="hover:opacity-90"
          >
            Admin
          </Badge>
        );
      case "viewer":
        return <Badge className="bg-gray-600 hover:bg-gray-700">Viewer</Badge>;
    }
  };

  const stats = {
    total: admins.length,
    active: admins.filter((a) => a.status === "active").length,
    superAdmins: admins.filter((a) => a.role === "super_admin").length,
    recentlyAdded: admins.filter((a) => {
      const createdAt =
        a.createdAt instanceof Date ? a.createdAt : new Date(a.createdAt);
      const daysDiff =
        (new Date().getTime() - createdAt.getTime()) / (1000 * 60 * 60 * 24);
      return daysDiff <= 30;
    }).length,
  };

  return (
    <div
      className="min-h-screen dark:from-slate-900 dark:to-slate-800"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`,
      }}
    >
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8" style={{ color: primaryColor }} />
              <div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
                  Admin Management
                </h1>
                <p className="text-slate-600 dark:text-slate-400 mt-1">
                  Manage administrator accounts and permissions
                </p>
              </div>
            </div>
            <Button
              onClick={() => setIsAddDialogOpen(true)}
              className="text-white hover:opacity-90"
              style={{ backgroundColor: primaryColor }}
            >
              <UserPlus className="w-4 h-4 mr-2" />
              Add Admin
            </Button>
          </div>
        </div>
      </div>

      <div className="container py-8 space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Total Admins
                </p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
                  {stats.total}
                </p>
              </div>
              <Shield
                className="w-12 h-12 opacity-20"
                style={{ color: primaryColor }}
              />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Active
                </p>
                <p className="text-3xl font-bold text-green-600 mt-2">
                  {stats.active}
                </p>
              </div>
              <CheckCircle className="w-12 h-12 text-green-600 opacity-20" />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Super Admins
                </p>
                <p className="text-3xl font-bold text-purple-600 mt-2">
                  {stats.superAdmins}
                </p>
              </div>
              <Shield className="w-12 h-12 text-purple-600 opacity-20" />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Added (30d)
                </p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
                  {stats.recentlyAdded}
                </p>
              </div>
              <Calendar className="w-12 h-12 text-orange-600 opacity-20" />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-50">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  type="text"
                  placeholder="Search admins..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <Select value={filterRole} onValueChange={setFilterRole}>
              <SelectTrigger className="w-45">
                <SelectValue placeholder="Filter by role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                {PLATFORM_ROLES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-45">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>

            <div className="text-sm text-slate-600 dark:text-slate-400">
              {loading
                ? "Loading admins..."
                : `Showing ${filteredAdmins.length} of ${admins.length} admins`}
            </div>
          </div>
        </div>

        {/* Admin List */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-50 dark:bg-slate-700 border-b border-slate-200 dark:border-slate-600">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Admin
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Contact
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Access Level
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Last Login
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {filteredAdmins.map((admin) => (
                  <tr
                    key={admin.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-700/50"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div
                          className="w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold"
                          style={{ backgroundColor: primaryColor }}
                        >
                          {(admin.name || "")
                            .split(" ")
                            .map((n) => n[0])
                            .join("")
                            .toUpperCase()}
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900 dark:text-white">
                            {admin.name}
                          </p>
                          <p className="text-sm text-slate-600 dark:text-slate-400">
                            ID: {admin.id}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-sm text-slate-900 dark:text-white">
                          <Mail className="w-4 h-4 text-slate-400" />
                          {admin.email}
                        </div>
                        <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                          <Phone className="w-4 h-4 text-slate-400" />
                          {admin.phone}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">{getRoleBadge(admin.role)}</td>
                    <td className="px-6 py-4">
                      {(() => {
                        const role = admin.platform_role || "support_agent";
                        const found = PLATFORM_ROLES.find(
                          (r) => r.value === role,
                        );
                        return (
                          <Badge className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                            {found ? found.label : role}
                          </Badge>
                        );
                      })()}
                    </td>
                    <td className="px-6 py-4">
                      {admin.status === "active" ? (
                        <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Active
                        </Badge>
                      ) : (
                        <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                          <XCircle className="w-3 h-3 mr-1" />
                          Inactive
                        </Badge>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                      {admin.lastLogin
                        ? admin.lastLogin.toLocaleString()
                        : "Never"}
                    </td>
                    <td className="px-6 py-4">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => openEditDialog(admin)}
                          >
                            <Edit2 className="w-4 h-4 mr-2" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleToggleStatus(admin.id)}
                          >
                            {admin.status === "active" ? (
                              <>
                                <XCircle className="w-4 h-4 mr-2" />
                                Deactivate
                              </>
                            ) : (
                              <>
                                <CheckCircle className="w-4 h-4 mr-2" />
                                Activate
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleDeleteAdmin(admin.id)}
                            className="text-red-600"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Add Admin Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="sm:max-w-125">
          <DialogHeader>
            <DialogTitle>Add New Admin</DialogTitle>
            <DialogDescription>
              Create a new administrator account with specific roles and
              permissions.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                placeholder="John Doe"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="uin">NIN</Label>
              <Input
                id="uin"
                value={formData.uin}
                onChange={(e) =>
                  setFormData({ ...formData, uin: e.target.value })
                }
                placeholder="0123456789"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData({ ...formData, password: e.target.value })
                }
                placeholder="Password"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                placeholder="john.doe@54link-dev.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                value={formData.phone}
                onChange={(e) =>
                  setFormData({ ...formData, phone: e.target.value })
                }
                placeholder="+234 801 234 5678"
              />
            </div>
            <div className="grid gap-2">
              <Label>Address</Label>
              <CascadingAddressDropdown
                country={formData.country}
                state={formData.state}
                city={formData.city}
                onCountryChange={(value) =>
                  setFormData({ ...formData, country: value })
                }
                onStateChange={(value) =>
                  setFormData({ ...formData, state: value })
                }
                onCityChange={(value) =>
                  setFormData({ ...formData, city: value })
                }
                primaryColor={primaryColor}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="platform_role">Platform Role</Label>
              <Select
                value={formData.platform_role}
                onValueChange={(value) =>
                  setFormData({ ...formData, platform_role: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select platform role" />
                </SelectTrigger>
                <SelectContent>
                  {PLATFORM_ROLES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsAddDialogOpen(false)}
              disabled={isAddingAdmin}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddAdmin}
              disabled={isAddingAdmin}
              className="text-white hover:opacity-90"
              style={{ backgroundColor: primaryColor }}
            >
              {isAddingAdmin ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Adding...
                </>
              ) : (
                "Add Admin"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Admin Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="sm:max-w-125">
          <DialogHeader>
            <DialogTitle>Edit Admin</DialogTitle>
            <DialogDescription>
              Update administrator account details and permissions.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="edit-name">Full Name</Label>
              <Input
                id="edit-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-email">Email</Label>
              <Input
                id="edit-email"
                type="email"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-phone">Phone</Label>
              <Input
                id="edit-phone"
                value={formData.phone}
                onChange={(e) =>
                  setFormData({ ...formData, phone: e.target.value })
                }
              />
            </div>
            <div className="grid gap-2">
              {" "}
              <Label>Address</Label>
              <CascadingAddressDropdown
                country={formData.country}
                state={formData.state}
                city={formData.city}
                onCountryChange={(value) =>
                  setFormData({ ...formData, country: value })
                }
                onStateChange={(value) =>
                  setFormData({ ...formData, state: value })
                }
                onCityChange={(value) =>
                  setFormData({ ...formData, city: value })
                }
                primaryColor={primaryColor}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-platform_role">Platform Role</Label>
              <Select
                value={formData.platform_role}
                onValueChange={(value) =>
                  setFormData({ ...formData, platform_role: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select platform role" />
                </SelectTrigger>
                <SelectContent>
                  {PLATFORM_ROLES.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              {" "}
              <Label htmlFor="edit-role">Role</Label>
              <Select
                value={formData.role}
                onValueChange={(value) =>
                  setFormData({ ...formData, role: value as Admin["role"] })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">Viewer</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="super_admin">Super Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="edit-status">Status</Label>
              <Select
                value={formData.status}
                onValueChange={(value) =>
                  setFormData({ ...formData, status: value as Admin["status"] })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsEditDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleEditAdmin}
              className="text-white hover:opacity-90"
              style={{ backgroundColor: primaryColor }}
            >
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
