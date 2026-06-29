import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { orchestratorApi } from "../utils/api";

const SignUp = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
    phone: "",
    uin: "",
    password: "",
    confirm_password: "",
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (formData.password !== formData.confirm_password) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await orchestratorApi.registerAgent({
        firstName: formData.first_name,
        lastName: formData.last_name,
        email: formData.email,
        phone: formData.phone,
        uin: formData.uin,
        password: formData.password,
      });
      // After successful registration, redirect to onboarding
      navigate("/onboarding");
    } catch (err) {
      setError(err.message || "Registration failed. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8"
      style={{
        background:
          "linear-gradient(to bottom right, rgba(0, 79, 113, 0.05), rgba(0, 79, 113, 0.15)",
      }}
    >
      <div className="max-w-md w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-[var(--tenant-primary-color,#004F71)] rounded-2xl flex items-center justify-center shadow-lg">
              <span className="text-white font-bold text-2xl">AG</span>
            </div>
          </div>
          <h2 className="mt-4 text-3xl font-extrabold text-gray-900">
            Create Agent Account
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium hover:underline"
              style={{ color: "var(--tenant-primary-color,#004F71)" }}
            >
              Sign in
            </Link>
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm">
            {error}
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          className="bg-white shadow-md rounded-2xl p-8 space-y-5"
        >
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                First Name
              </label>
              <input
                name="first_name"
                type="text"
                required
                value={formData.first_name}
                onChange={handleChange}
                placeholder="John"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Last Name
              </label>
              <input
                name="last_name"
                type="text"
                required
                value={formData.last_name}
                onChange={handleChange}
                placeholder="Doe"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email Address
            </label>
            <input
              name="email"
              type="email"
              required
              value={formData.email}
              onChange={handleChange}
              placeholder="you@example.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Phone Number
            </label>
            <input
              name="phone"
              type="tel"
              required
              value={formData.phone}
              onChange={handleChange}
              placeholder="+234 800 000 0000"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              NIN / BVN (UIN)
            </label>
            <input
              name="uin"
              type="text"
              required
              value={formData.uin}
              onChange={handleChange}
              placeholder="Enter your NIN or BVN"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              name="password"
              type="password"
              required
              value={formData.password}
              onChange={handleChange}
              placeholder="Minimum 8 characters"
              minLength={8}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Confirm Password
            </label>
            <input
              name="confirm_password"
              type="password"
              required
              value={formData.confirm_password}
              onChange={handleChange}
              placeholder="Re-enter password"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3 px-4 bg-[var(--tenant-primary-color,#004F71)] text-white font-semibold rounded-lg hover:bg-[var(--tenant-primary-color,#003F5A)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            {isSubmitting ? "Creating Account..." : "Create Agent Account"}
          </button>

          <p className="text-xs text-gray-500 text-center">
            By creating an account you agree to our{" "}
            <span
              className="cursor-pointer hover:underline"
              style={{ color: "var(--tenant-primary-color,#004F71)" }}
            >
              Terms of Service
            </span>{" "}
            and{" "}
            <span
              className="cursor-pointer hover:underline"
              style={{ color: "var(--tenant-primary-color,#004F71)" }}
            >
              Privacy Policy
            </span>
            .
          </p>
        </form>
      </div>
    </div>
  );
};

export default SignUp;
