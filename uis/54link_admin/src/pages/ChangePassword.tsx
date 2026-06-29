import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useTenantBranding } from "@/contexts/TenantBrandingContext";
import { authService } from "@/services/auth/authService";
import { Eye, EyeOff, KeyRound } from "lucide-react";
import { useState } from "react";
import { useLocation } from "wouter";

export default function ChangePassword() {
  const [, setLocation] = useLocation();
  const { primaryColor } = useTenantBranding();
  const secondaryColor = primaryColor;

  const [formData, setFormData] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [show, setShow] = useState({ current: false, newPw: false, confirm: false });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (formData.newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }
    if (formData.newPassword !== formData.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await authService.changePassword(
        formData.currentPassword,
        formData.newPassword,
        formData.confirmPassword,
      );
      setSuccess("Password changed successfully. Redirecting...");
      setTimeout(() => setLocation("/"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setLoading(false);
    }
  };

  const field = (
    key: "currentPassword" | "newPassword" | "confirmPassword",
    label: string,
    showKey: "current" | "newPw" | "confirm",
    hint?: string,
  ) => (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-gray-700 uppercase tracking-wide">
        {label}
      </label>
      <div className="relative">
        <input
          type={show[showKey] ? "text" : "password"}
          value={formData[key]}
          onChange={(e) => setFormData({ ...formData, [key]: e.target.value })}
          className="w-full px-4 py-3 pr-12 border-2 border-gray-200 rounded-lg focus:border-transparent transition-all focus:outline-none focus:ring-2"
          style={{ "--tw-ring-color": primaryColor } as React.CSSProperties}
          required
          minLength={key !== "currentPassword" ? 8 : undefined}
        />
        <button
          type="button"
          onClick={() => setShow({ ...show, [showKey]: !show[showKey] })}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors"
        >
          {show[showKey] ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
        </button>
      </div>
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      style={{
        background: `linear-gradient(135deg, ${primaryColor}08 0%, ${secondaryColor}08 25%, ${primaryColor}05 50%, ${secondaryColor}12 100%)`,
      }}
    >
      <div
        className="absolute inset-0 opacity-30 pointer-events-none"
        style={{
          background: `radial-gradient(circle at 20% 50%, ${primaryColor}15 0%, transparent 50%), radial-gradient(circle at 80% 80%, ${secondaryColor}15 0%, transparent 50%)`,
        }}
      />

      <Card
        className="w-full max-w-md relative z-10 shadow-2xl backdrop-blur-sm border-0"
        style={{ backgroundColor: "rgba(255,255,255,0.95)" }}
      >
        <div
          className="absolute top-0 left-0 right-0 h-1.5 rounded-t-lg"
          style={{ background: `linear-gradient(90deg, ${primaryColor}, ${secondaryColor})` }}
        />

        <div className="p-8">
          <div className="text-center mb-8">
            <div
              className="mx-auto w-16 h-16 rounded-full flex items-center justify-center mb-4"
              style={{ backgroundColor: `${primaryColor}15` }}
            >
              <KeyRound className="h-8 w-8" style={{ color: primaryColor }} />
            </div>
            <h1 className="text-2xl font-bold text-gray-800 mb-1">Change Password</h1>
            <p className="text-sm text-gray-500">Update your account password</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded-lg text-sm font-medium">
                {error}
              </div>
            )}
            {success && (
              <div className="bg-green-50 border-l-4 border-green-500 text-green-700 px-4 py-3 rounded-lg text-sm font-medium">
                {success}
              </div>
            )}

            {field("currentPassword", "Current Password", "current")}
            {field("newPassword", "New Password", "newPw", "Must be at least 8 characters")}
            {field("confirmPassword", "Confirm New Password", "confirm")}

            <div className="flex gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                className="flex-1 py-3"
                onClick={() => setLocation("/")}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                className="flex-1 py-3 text-white font-semibold"
                style={{ backgroundColor: primaryColor }}
                disabled={loading}
              >
                {loading ? "Updating..." : "Update Password"}
              </Button>
            </div>
          </form>

          <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
            <p className="font-semibold mb-1">Security Tips</p>
            <ul className="list-disc list-inside space-y-0.5 text-xs">
              <li>Use uppercase, lowercase, numbers &amp; symbols</li>
              <li>Never reuse passwords across services</li>
              <li>Change your password regularly</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
