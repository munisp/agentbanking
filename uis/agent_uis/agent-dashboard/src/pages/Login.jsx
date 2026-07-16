import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logo from "../assets/logo.png";
import { useTenant } from "../contexts/TenantContext";
import { useAuth } from "../hooks/useAuth";

const Login = () => {
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [loginError, setLoginError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();
  const { name, logoUrl, isLoading: isTenantLoading } = useTenant();

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate("/");
    }
  }, [isAuthenticated, navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError(null);

    // Wait for tenant config to load
    if (isTenantLoading) {
      setLoginError("Loading tenant configuration...");
      return;
    }

    setIsSubmitting(true);

    try {
      await login(loginForm);
      navigate("/");
    } catch (error) {
      const message =
        error?.response?.data?.detail?.message ||
        (typeof error?.response?.data?.detail === "string"
          ? error.response.data.detail
          : null) ||
        error?.response?.data?.message ||
        error?.message ||
        "Login failed";

      setLoginError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-primary-900 to-gray-800 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div
          className="absolute w-96 h-96 rounded-full blur-3xl -top-48 -left-48 animate-pulse"
          style={{ backgroundColor: "rgba(0, 79, 113, 0.2)" }}
        ></div>
        <div
          className="absolute w-96 h-96 rounded-full blur-3xl -bottom-48 -right-48"
          style={{
            backgroundColor: "rgba(228, 191, 48, 0.2)",
            animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
            animationDelay: "1s",
          }}
        ></div>
      </div>

      <div
        className="w-full max-w-md p-8 relative z-10 rounded-2xl shadow-2xl"
        style={{
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255, 255, 255, 0.2)",
        }}
      >
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <img src={logoUrl || logo} alt={name} className="h-16 w-auto object-contain" />
          </div>
          {name && (
            <h1
              className="text-3xl font-bold"
              style={{
                background: "linear-gradient(to right, var(--tenant-primary-color,#002082), var(--tenant-secondary-color,#6CC049))",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              {name}
            </h1>
          )}
          <p className="text-gray-600 mt-2">Agent Banking Platform</p>
        </div>

        {loginError && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm text-center">
            {loginError}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Email Address
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={loginForm.email}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, email: e.target.value })
                }
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="you@example.com"
                style={{ outline: "none" }}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-3 h-5 w-5 text-gray-400" />
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
                className="w-full pl-10 pr-12 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                placeholder="••••••••"
                style={{ outline: "none" }}
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5" />
                ) : (
                  <Eye className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting || isTenantLoading}
            className="w-full text-white py-3 rounded-xl font-semibold shadow-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            style={{
              backgroundColor: "var(--tenant-primary-color,#002082)",
            }}
            onMouseEnter={(e) => {
              if (!isSubmitting && !isTenantLoading) {
                e.currentTarget.style.backgroundColor = "var(--tenant-primary-color,#003F5A)";
                e.currentTarget.style.boxShadow =
                  "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)";
                e.currentTarget.style.transform = "translateY(-2px)";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = "var(--tenant-primary-color,#002082)";
              e.currentTarget.style.boxShadow =
                "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            {isTenantLoading
              ? "Loading..."
              : isSubmitting
                ? "Signing in..."
                : "Sign In"}
          </button>
        </form>

        <div className="mt-6 text-center">
          <Link
            to="/signup"
            className="inline-flex items-center justify-center w-full py-3 rounded-xl font-semibold border border-gray-300 text-gray-700 hover:bg-gray-50 transition-all"
          >
            Create an Agent Account
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Login;
