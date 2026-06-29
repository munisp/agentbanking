import { Building2, FileCheck, MapPin, Shield, User } from "lucide-react";
import React, { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import OnboardingProgressIndicator from "../../components/OnboardingProgressIndicator.jsx";

const OnboardingStartScreen = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Mark that user has seen onboarding screen
    localStorage.setItem("onboarding_seen", "true");
  }, []);

  const features = [
    {
      icon: User,
      title: "Select Account Type",
      description: "Choose Individual or Business account",
    },
    {
      icon: Shield,
      title: "Enter BVN",
      description: "Provide your Bank Verification Number",
    },
    {
      icon: MapPin,
      title: "Address Details",
      description: "Provide your address information",
    },
    {
      icon: FileCheck,
      title: "Upload Documents",
      description: "Upload identity verification documents",
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-2xl w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-20 w-20 bg-green-600 rounded-3xl flex items-center justify-center shadow-xl shadow-green-200">
              <Building2 className="text-white w-10 h-10" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mt-4">
            Welcome to 54agent Agent Banking
          </h1>
          <p className="text-gray-600 mt-3 text-lg">
            Complete your account setup to unlock all features and ensure CBN
            compliance.
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <OnboardingProgressIndicator currentStep={1} totalSteps={4} />
        </div>

        {/* Steps Overview */}
        <div className="bg-white rounded-2xl shadow-md p-8">
          <h2 className="text-xl font-bold text-gray-900 mb-6">
            What to Expect
          </h2>
          <div className="space-y-4">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div
                  key={index}
                  className="flex items-start gap-4 p-4 rounded-xl hover:bg-gray-50 transition-colors"
                >
                  <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Icon className="w-6 h-6 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900 mb-1">
                      {index + 1}. {feature.title}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {feature.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="space-y-4">
          <button
            onClick={() => navigate("/onboarding/account-type")}
            className="w-full py-4 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors shadow-lg shadow-green-200 text-lg"
          >
            Get Started
          </button>

          <div className="text-center">
            <Link
              to="/login"
              className="text-green-600 font-medium hover:underline"
            >
              Already have an account? Sign in
            </Link>
          </div>
        </div>

        {/* Footer Note */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex gap-3">
            <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-blue-900">
                <strong>Secure & Compliant:</strong> All information is
                encrypted and stored securely in compliance with CBN
                regulations.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OnboardingStartScreen;
