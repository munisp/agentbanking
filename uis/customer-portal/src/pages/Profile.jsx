import { ChevronRight, Fingerprint, Lock, Smartphone } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { userApi } from "../utils/api";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const Profile = () => {
  const { user, refreshProfile } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [profileData, setProfileData] = useState({
    name: user?.name || "",
    email: user?.email || "",
    phone: user?.phone || "",
  });

  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name || "",
        email: user.email || "",
        phone: user.phone || "",
      });
    }
  }, [user]);

  const handleSave = async () => {
    if (!user?.keycloakId) return;

    try {
      setIsSaving(true);
      setSaveError(null);

      // Demo mode: simulate save
      if (DEMO_MODE) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        setIsEditing(false);
        setIsSaving(false);
        return;
      }

      await userApi.updateProfile(user.keycloakId, {
        name: profileData.name,
        email: profileData.email,
        phone_number: profileData.phone,
      });

      await refreshProfile();
      setIsEditing(false);
    } catch (error) {
      console.error("Failed to update profile:", error);
      setSaveError(error.message || "Failed to save changes");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
        <button
          onClick={() => (isEditing ? handleSave() : setIsEditing(true))}
          disabled={isSaving}
          className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50"
        >
          {isSaving ? "Saving..." : isEditing ? "Save Changes" : "Edit Profile"}
        </button>
      </div>

      {saveError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
          {saveError}
        </div>
      )}

      <div className="bg-white rounded-lg shadow">
        {/* Profile Header */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center">
            <div className="h-20 w-20 bg-green-600 rounded-full flex items-center justify-center">
              <span className="text-white font-bold text-2xl">
                {user?.name
                  ?.split(" ")
                  .map((n) => n[0])
                  .join("") || "U"}
              </span>
            </div>
            <div className="ml-6">
              <h2 className="text-xl font-semibold text-gray-900">
                {user?.name || "Customer"}
              </h2>
              <p className="text-gray-500">{user?.email}</p>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 mt-2">
                Verified Customer
              </span>
            </div>
          </div>
        </div>

        {/* Profile Details */}
        <div className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Full Name
            </label>
            {isEditing ? (
              <input
                type="text"
                value={profileData.name}
                onChange={(e) =>
                  setProfileData({ ...profileData, name: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-green-500 focus:border-green-500"
              />
            ) : (
              <p className="text-gray-900">{user?.name || "Not set"}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Address
            </label>
            {isEditing ? (
              <input
                type="email"
                value={profileData.email}
                onChange={(e) =>
                  setProfileData({ ...profileData, email: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-green-500 focus:border-green-500"
              />
            ) : (
              <p className="text-gray-900">{user?.email || "Not set"}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Phone Number
            </label>
            {isEditing ? (
              <input
                type="tel"
                value={profileData.phone}
                onChange={(e) =>
                  setProfileData({ ...profileData, phone: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-green-500 focus:border-green-500"
              />
            ) : (
              <p className="text-gray-900">{user?.phone || "Not set"}</p>
            )}
          </div>
        </div>
      </div>

      {/* Security Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Security</h3>
        <div className="space-y-4">
          <button className="w-full flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="flex items-center">
              <Lock className="w-5 h-5 text-gray-400 mr-3" />
              <span className="text-sm font-medium text-gray-700">
                Change Password
              </span>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400" />
          </button>
          <button className="w-full flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="flex items-center">
              <Fingerprint className="w-5 h-5 text-gray-400 mr-3" />
              <span className="text-sm font-medium text-gray-700">
                Two-Factor Authentication
              </span>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400" />
          </button>
          <button className="w-full flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <div className="flex items-center">
              <Smartphone className="w-5 h-5 text-gray-400 mr-3" />
              <span className="text-sm font-medium text-gray-700">
                Manage Devices
              </span>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400" />
          </button>

          {/* PIN Setup Form */}
          <PinSetupSection user={user} />
        </div>
      </div>
    </div>
  );
};

export default Profile;

// PIN Setup Section Component

function PinSetupSection({ user }) {
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [accountNumber, setAccountNumber] = useState("");

  // Fetch account number if not present
  useEffect(() => {
    async function fetchAccount() {
      if (!user?.keycloakId) return;
      try {
        const res = await import("../utils/api").then((m) =>
          m.accountApi.getByKeycloakId(user.keycloakId),
        );
        setAccountNumber(
          res?.account_number || res?.account?.account_number || "",
        );
      } catch {
        setAccountNumber("");
      }
    }
    fetchAccount();
  }, [user?.keycloakId]);

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
        className="w-full py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-semibold"
        disabled={loading || !accountNumber}
      >
        {loading ? "Setting..." : "Set PIN"}
      </button>
    </form>
  );
}
