import {
    Bell,
    Building2,
    Calendar,
    DollarSign,
    Edit2,
    Key,
    Mail,
    MapPin,
    Phone,
    RefreshCw,
    Save,
    Shield,
    User,
    X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { accountApi, agentApi } from "../utils/api";

const Profile = () => {
  const { user, logout, refreshProfile } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [agentProfile, setAgentProfile] = useState(null);
  const [accountDetails, setAccountDetails] = useState(null);
  const [loadingAccount, setLoadingAccount] = useState(false);

  const [profileData, setProfileData] = useState({
    name: user?.name || "",
    email: user?.email || "",
    phone: user?.phone || "",
    address: user?.businessAddress || "",
    agentCode: user?.agentCode || "",
    businessName: user?.businessName || "",
    agentRole: user?.agentRole || "agent",
  });

  const [settings, setSettings] = useState({
    emailNotifications: true,
    smsNotifications: false,
    pushNotifications: true,
    twoFactorAuth: false,
  });

  useEffect(() => {
    const fetchProfile = async () => {
      const keycloakId = user?.keycloakId;
      if (!keycloakId) return;
      try {
        const resp = await agentApi.getAgentByKeycloakId(keycloakId);
        const p = resp.agent ?? resp;
        setAgentProfile(p);
        setProfileData({
          name: p.name ?? `${p.first_name ?? ""} ${p.last_name ?? ""}`.trim(),
          email: p.email ?? user?.email ?? "",
          phone: p.phone_number ?? p.phone ?? user?.phone ?? "",
          address: p.business_address ?? user?.businessAddress ?? "",
          agentCode: p.uin ?? user?.agentCode ?? "",
          businessName: p.business_name ?? user?.businessName ?? "",
          agentRole: p.agent_role ?? user?.agentRole ?? "agent",
        });

        // Fetch account details
        setLoadingAccount(true);
        try {
          const accountResp =
            await accountApi.getAccountByKeycloakId(keycloakId);
          setAccountDetails(accountResp.account ?? accountResp);
        } catch (accountErr) {
          console.error("Account fetch error:", accountErr);
        } finally {
          setLoadingAccount(false);
        }
      } catch (err) {
        console.error("Profile fetch error:", err);
      }
    };
    fetchProfile();
  }, [user]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setProfileData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSettingToggle = (setting) => {
    setSettings((prev) => ({ ...prev, [setting]: !prev[setting] }));
  };

  const handleSave = async () => {
    setSaveError(null);
    setIsSaving(true);
    try {
      const keycloakId = user?.keycloakId;
      if (keycloakId) {
        await agentApi.updateProfile(keycloakId, {
          phone: profileData.phone,
          business_address: profileData.address,
          business_name: profileData.businessName,
        });
        await refreshProfile();
      }
      setIsEditing(false);
    } catch (err) {
      setSaveError(err.message || "Failed to save profile.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setSaveError(null);
  };

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">
            Profile Settings
          </h1>
          <p className="text-gray-600 mt-1">
            Manage your account information and preferences
          </p>
        </div>
        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors"
          >
            <Edit2 className="h-5 w-5 mr-2" />
            Edit Profile
          </button>
        ) : (
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="inline-flex items-center justify-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              {isSaving ? (
                <RefreshCw className="h-5 w-5 mr-2 animate-spin" />
              ) : (
                <Save className="h-5 w-5 mr-2" />
              )}
              {isSaving ? "Saving..." : "Save"}
            </button>
            <button
              onClick={handleCancel}
              className="inline-flex items-center justify-center px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors"
            >
              <X className="h-5 w-5 mr-2" />
              Cancel
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile Information */}
        <div className="lg:col-span-2 space-y-6">
          {" "}
          {saveError && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
              {saveError}
            </div>
          )}{" "}
          {/* Basic Info Card */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 sm:p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Personal Information
              </h2>
            </div>
            <div className="p-4 sm:p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <User className="h-4 w-4 inline mr-1" />
                    Full Name
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={profileData.name}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Building2 className="h-4 w-4 inline mr-1" />
                    Agent Code
                  </label>
                  <input
                    type="text"
                    value={profileData.agentCode}
                    disabled
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-600"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Mail className="h-4 w-4 inline mr-1" />
                    Email Address
                  </label>
                  <input
                    type="email"
                    name="email"
                    value={profileData.email}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Phone className="h-4 w-4 inline mr-1" />
                    Phone Number
                  </label>
                  <input
                    type="tel"
                    name="phone"
                    value={profileData.phone}
                    onChange={handleInputChange}
                    disabled={!isEditing}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <MapPin className="h-4 w-4 inline mr-1" />
                  Address
                </label>
                <input
                  type="text"
                  name="address"
                  value={profileData.address}
                  onChange={handleInputChange}
                  disabled={!isEditing}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50"
                />
              </div>
            </div>
          </div>
          {/* Security Settings */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 sm:p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Security Settings
              </h2>
            </div>
            <div className="p-4 sm:p-6 space-y-4">
              <button className="w-full flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex items-center">
                  <Key className="h-5 w-5 text-gray-600 mr-3" />
                  <div className="text-left">
                    <p className="font-medium text-gray-900">Change Password</p>
                    <p className="text-sm text-gray-500">
                      Update your password regularly
                    </p>
                  </div>
                </div>
                <Edit2 className="h-5 w-5 text-gray-400" />
              </button>

              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <Shield className="h-5 w-5 text-gray-600 mr-3" />
                  <div>
                    <p className="font-medium text-gray-900">
                      Two-Factor Authentication
                    </p>
                    <p className="text-sm text-gray-500">
                      Add an extra layer of security
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => handleSettingToggle("twoFactorAuth")}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    settings.twoFactorAuth ? "bg-blue-600" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      settings.twoFactorAuth ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>
          {/* Notification Preferences */}
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 sm:p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                <Bell className="h-5 w-5 inline mr-2" />
                Notification Preferences
              </h2>
            </div>
            <div className="p-4 sm:p-6 space-y-4">
              {[
                {
                  key: "emailNotifications",
                  label: "Email Notifications",
                  desc: "Receive updates via email",
                },
                {
                  key: "smsNotifications",
                  label: "SMS Notifications",
                  desc: "Get text message alerts",
                },
                {
                  key: "pushNotifications",
                  label: "Push Notifications",
                  desc: "Browser push notifications",
                },
              ].map((setting) => (
                <div
                  key={setting.key}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div>
                    <p className="font-medium text-gray-900">{setting.label}</p>
                    <p className="text-sm text-gray-500">{setting.desc}</p>
                  </div>
                  <button
                    onClick={() => handleSettingToggle(setting.key)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      settings[setting.key] ? "bg-blue-600" : "bg-gray-300"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        settings[setting.key]
                          ? "translate-x-6"
                          : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar Stats */}
        <div className="space-y-6">
          {/* Agent Stats Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-center mb-4">
              <div className="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center">
                <User className="h-12 w-12 text-blue-600" />
              </div>
            </div>
            <h3 className="text-center font-semibold text-gray-900 text-lg">
              {profileData.name}
            </h3>
            <p className="text-center text-sm text-gray-500 mt-1">
              {profileData.agentCode}
            </p>

            <div className="mt-6 space-y-3">
              <div className="flex items-center text-sm">
                <Calendar className="h-4 w-4 text-gray-400 mr-2" />
                <span className="text-gray-600">
                  Joined{" "}
                  {agentProfile?.created_at
                    ? new Date(agentProfile.created_at).toLocaleDateString(
                        "en-GB",
                        { year: "numeric", month: "long", day: "numeric" },
                      )
                    : "—"}
                </span>
              </div>
              <div className="flex items-center text-sm">
                <Building2 className="h-4 w-4 text-gray-400 mr-2" />
                <span className="text-gray-600">
                  {profileData.businessName || "—"}
                </span>
              </div>
              <div className="flex items-center text-sm">
                <Shield className="h-4 w-4 text-gray-400 mr-2" />
                <span className="text-gray-600 capitalize">
                  {agentProfile?.status ?? user?.status ?? "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Agent Info Card */}
          <div className="bg-linear-to-br from-blue-600 to-blue-700 rounded-lg shadow p-6 text-white">
            <h3 className="font-semibold mb-2">Agent Role</h3>
            <p className="text-2xl font-bold capitalize">
              {profileData.agentRole || "—"}
            </p>
            <p className="text-sm text-blue-200 mt-2">
              KYC: {agentProfile?.kyc_verification_status ?? "pending"}
            </p>
          </div>

          {/* Account Details Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-semibold text-gray-900 mb-4">
              <DollarSign className="h-5 w-5 inline mr-2" />
              Account Details
            </h3>
            {loadingAccount ? (
              <div className="text-center py-4">
                <RefreshCw className="h-6 w-6 text-blue-600 animate-spin mx-auto" />
                <p className="text-sm text-gray-500 mt-2">Loading account...</p>
              </div>
            ) : accountDetails ? (
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-gray-500">Account Number</p>
                  <p className="font-mono text-sm font-semibold text-gray-900">
                    {accountDetails.account_number || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Account Name</p>
                  <p className="text-sm font-medium text-gray-900">
                    {accountDetails.name || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Account ID</p>
                  <p className="text-xs font-mono text-gray-700">
                    {accountDetails.entity_id || accountDetails.id || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Status</p>
                  <span
                    className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${
                      accountDetails.status === "active"
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {accountDetails.status || "active"}
                  </span>
                </div>
                {/* PIN Setup Section */}
                <AgentPinSetupSection
                  accountNumber={accountDetails.account_number}
                />
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-sm text-gray-500">No account found</p>
                <p className="text-xs text-gray-400 mt-1">
                  Complete KYC to activate your account
                </p>
              </div>
            )}
          </div>

          {/* Logout Button */}
          <button
            onClick={logout}
            className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
};

// PIN Setup Section Component for Agent
function AgentPinSetupSection({ accountNumber }) {
  const [pin, setPin] = React.useState("");
  const [confirmPin, setConfirmPin] = React.useState("");
  const [status, setStatus] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const handlePinSetup = async (e) => {
    e.preventDefault();
    setStatus(null);
    if (pin.length < 4 || pin !== confirmPin) {
      setStatus({ error: "PINs must match and be at least 4 digits." });
      return;
    }
    setLoading(true);
    try {
      await import("../utils/api").then((m) =>
        m.accountApi.setupPin(accountNumber, pin),
      );
      setStatus({ success: "PIN set successfully." });
      setPin("");
      setConfirmPin("");
    } catch (err) {
      setStatus({ error: err.message || "Failed to set PIN." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="space-y-3 mt-6" onSubmit={handlePinSetup}>
      <h4 className="font-semibold text-gray-800">Set/Update Account PIN</h4>
      {status?.success && (
        <div className="text-green-700 bg-green-50 rounded px-3 py-2">
          {status.success}
        </div>
      )}
      {status?.error && (
        <div className="text-red-700 bg-red-50 rounded px-3 py-2">
          {status.error}
        </div>
      )}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Account Number
        </label>
        <input
          type="text"
          value={accountNumber}
          disabled
          className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          New PIN
        </label>
        <input
          type="password"
          value={pin}
          onChange={(e) => setPin(e.target.value)}
          minLength={4}
          maxLength={6}
          pattern="[0-9]*"
          inputMode="numeric"
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Confirm PIN
        </label>
        <input
          type="password"
          value={confirmPin}
          onChange={(e) => setConfirmPin(e.target.value)}
          minLength={4}
          maxLength={6}
          pattern="[0-9]*"
          inputMode="numeric"
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
          required
        />
      </div>
      <button
        type="submit"
        className="w-full py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-semibold"
        disabled={loading || !accountNumber}
      >
        {loading ? "Setting..." : "Set PIN"}
      </button>
    </form>
  );
}

export default Profile;
