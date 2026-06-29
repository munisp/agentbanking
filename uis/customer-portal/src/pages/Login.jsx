import { AlertCircle, ShieldAlert, ShieldCheck, X } from "lucide-react";
import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logo from "../assets/logo.png";
import { useAuth } from "../hooks/useAuth";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const Login = () => {
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [loginError, setLoginError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showKycModal, setShowKycModal] = useState(false);
  const [kycUrl, setKycUrl] = useState(null);
  const navigate = useNavigate();
  const { login, logout, isAuthenticated } = useAuth();

  // Redirect if already authenticated (but not when the KYC modal is blocking)
  React.useEffect(() => {
    if (isAuthenticated && !showKycModal) {
      navigate("/");
    }
  }, [isAuthenticated, showKycModal, navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError(null);
    setIsSubmitting(true);

    try {
      const userData = await login(loginForm);
      // Check KYC verification status before granting dashboard access
      if (userData?.kycStatus && userData.kycStatus !== "verified") {
        setKycUrl(userData.kycVerificationUrl || null);
        setShowKycModal(true);
      } else {
        navigate("/");
      }
    } catch (error) {
      setLoginError(error.message || "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKycLogout = async () => {
    sessionStorage.removeItem("kyc_acknowledged");
    await logout();
    setShowKycModal(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      {/* KYC Verification Modal */}
      {showKycModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-8 space-y-6 relative">
            {/* Close / logout */}
            <button
              onClick={handleKycLogout}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>

            {/* Icon */}
            <div className="flex justify-center">
              <div className="w-16 h-16 bg-orange-500 rounded-full flex items-center justify-center">
                <ShieldAlert className="w-8 h-8 text-white" />
              </div>
            </div>

            {/* Title */}
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold text-gray-900">
                KYC Verification Required
              </h2>
              <p className="text-gray-500 text-sm">
                To comply with regulatory requirements, you must complete
                identity verification before accessing your account.
              </p>
            </div>

            {/* Info boxes */}
            <div className="space-y-3">
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-blue-900">
                    Why KYC is Required
                  </p>
                  <p className="text-sm text-blue-700 mt-1">
                    KYC helps us protect your account and ensure CBN compliance
                    across all banking operations.
                  </p>
                </div>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex gap-3">
                <ShieldCheck className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-semibold text-green-900">
                    Quick &amp; Simple Process
                  </p>
                  <p className="text-sm text-green-700 mt-1">
                    Verification only takes a few minutes. Visit your profile to
                    submit the required documents.
                  </p>
                </div>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex gap-3">
              <button
                onClick={handleKycLogout}
                className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-colors text-sm"
              >
                Logout
              </button>
              <button
                onClick={() => {
                  // Mark KYC as acknowledged in sessionStorage so the global
                  // App.jsx gate doesn't re-block immediately after redirect
                  sessionStorage.setItem("kyc_acknowledged", "true");
                  setShowKycModal(false);
                  if (kycUrl) {
                    window.open(kycUrl, "_blank", "noopener,noreferrer");
                  } else {
                    navigate("/profile");
                  }
                }}
                className="flex-1 py-3 bg-green-600 text-white rounded-xl font-semibold hover:bg-green-700 transition-colors text-sm flex items-center justify-center gap-2"
              >
                <ShieldCheck className="w-4 h-4" />
                Complete KYC
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="max-w-md w-full space-y-8">
        <div>
          <div className="flex justify-center">
            <img
              src={logo}
              alt="Area Konnect by Fidelity"
              className="h-20 w-auto object-contain"
            />
          </div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Customer Portal
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Sign in to manage your account
          </p>
        </div>

        {DEMO_MODE && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 px-4 py-3 rounded-md text-sm">
            <p className="font-semibold">🛠️ Demo Mode Active</p>
            <p className="mt-1">
              Click "Quick Demo Login" to enter without credentials
            </p>
          </div>
        )}

        {loginError && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
            {loginError}
          </div>
        )}

        {DEMO_MODE && (
          <button
            onClick={handleLogin}
            disabled={isSubmitting}
            className="w-full flex justify-center py-3 px-4 border-2 border-green-600 text-sm font-semibold rounded-md text-green-600 bg-green-50 hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? "Logging in..." : "🚀 Quick Demo Login"}
          </button>
        )}

        <form className="mt-8 space-y-6" onSubmit={handleLogin}>
          <div className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700"
              >
                Email address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required={!DEMO_MODE}
                value={loginForm.email}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, email: e.target.value })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label
                htmlFor="password"
                className="block text-sm font-medium text-gray-700"
              >
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required={!DEMO_MODE}
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-green-500 focus:border-green-500 sm:text-sm"
                placeholder="Enter your password"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                className="h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded"
              />
              <label
                htmlFor="remember-me"
                className="ml-2 block text-sm text-gray-900"
              >
                Remember me
              </label>
            </div>

            <div className="text-sm">
              <a
                href="#"
                className="font-medium text-green-600 hover:text-green-500"
              >
                Forgot password?
              </a>
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
            >
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </div>
        </form>

        <p className="mt-4 text-center text-sm text-gray-600">
          Don't have an account?{" "}
          <Link
            to="/signup"
            className="font-medium text-green-600 hover:text-green-500"
          >
            Create one here
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
