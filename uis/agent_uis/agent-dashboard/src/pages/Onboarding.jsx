import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

const STEPS = [
  { id: 1, title: "Welcome", description: "Get started as a 54agent" },
  { id: 2, title: "Business Info", description: "Tell us about your business" },
  { id: 3, title: "Location", description: "Where is your business located?" },
  { id: 4, title: "KYC Verification", description: "Verify your identity" },
  { id: 5, title: "Done", description: "You're all set!" },
];

const Onboarding = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [businessData, setBusinessData] = useState({
    business_name: "",
    business_type: "",
    business_address: "",
    city: "",
    state: "",
    lga: "",
    postal_code: "",
  });

  const handleChange = (e) => {
    setBusinessData({ ...businessData, [e.target.name]: e.target.value });
  };

  const handleNext = () => {
    if (currentStep < STEPS.length) setCurrentStep((s) => s + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep((s) => s - 1);
  };

  const handleSubmitBusiness = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    // In production: PATCH /agent-service/agent/{keycloak_id}/onboarding
    await new Promise((r) => setTimeout(r, 800));
    setIsSubmitting(false);
    handleNext();
  };

  const handleStartKYC = async () => {
    setIsSubmitting(true);
    // In production: trigger KYC verification URL
    await new Promise((r) => setTimeout(r, 800));
    setIsSubmitting(false);
    handleNext();
  };

  const progressPercent = ((currentStep - 1) / (STEPS.length - 1)) * 100;

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center py-12 px-4">
      <div className="max-w-2xl w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-3">
            <div className="h-14 w-14 bg-blue-600 rounded-2xl flex items-center justify-center shadow-lg">
              <span className="text-white font-bold text-xl">AG</span>
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Agent Onboarding</h1>
          <p className="text-sm text-gray-500 mt-1">
            Step {currentStep} of {STEPS.length}:{" "}
            {STEPS[currentStep - 1].description}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="bg-white rounded-full h-2 shadow-inner">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Step indicators */}
        <div className="flex justify-between px-1">
          {STEPS.map((step) => (
            <div key={step.id} className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                  step.id < currentStep
                    ? "bg-green-500 text-white"
                    : step.id === currentStep
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-500"
                }`}
              >
                {step.id < currentStep ? "✓" : step.id}
              </div>
              <span className="text-xs text-gray-500 mt-1 hidden sm:block">
                {step.title}
              </span>
            </div>
          ))}
        </div>

        {/* Step Content */}
        <div className="bg-white rounded-2xl shadow-md p-8">
          {/* Step 1: Welcome */}
          {currentStep === 1 && (
            <div className="text-center space-y-6">
              <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
                <span className="text-4xl">👋</span>
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  Welcome to 54agent!
                </h2>
                <p className="text-gray-600 mt-2 text-sm leading-relaxed">
                  We're excited to have you on board. Complete this quick setup
                  to activate your agent account and start processing
                  transactions for your customers.
                </p>
              </div>
              <ul className="text-left space-y-3 text-sm text-gray-700">
                {[
                  "Register your business details",
                  "Set your business location",
                  "Complete KYC identity verification",
                  "Get approved and go live",
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="w-5 h-5 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">
                      {i + 1}
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
              <button
                onClick={handleNext}
                className="w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 transition-colors"
              >
                Get Started
              </button>
            </div>
          )}

          {/* Step 2: Business Info */}
          {currentStep === 2 && (
            <form onSubmit={handleSubmitBusiness} className="space-y-5">
              <h2 className="text-lg font-bold text-gray-900">
                Business Information
              </h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Name
                </label>
                <input
                  name="business_name"
                  type="text"
                  required
                  value={businessData.business_name}
                  onChange={handleChange}
                  placeholder="e.g. Tani Ventures"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Business Type
                </label>
                <select
                  name="business_type"
                  value={businessData.business_type}
                  onChange={handleChange}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Select type</option>
                  <option value="retail">Retail Store</option>
                  <option value="pharmacy">Pharmacy</option>
                  <option value="supermarket">Supermarket</option>
                  <option value="electronics">Electronics</option>
                  <option value="food_beverage">Food &amp; Beverage</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleBack}
                  className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl font-medium hover:bg-gray-50 text-sm"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex-1 py-2.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 disabled:opacity-50 text-sm"
                >
                  {isSubmitting ? "Saving..." : "Continue"}
                </button>
              </div>
            </form>
          )}

          {/* Step 3: Location */}
          {currentStep === 3 && (
            <div className="space-y-5">
              <h2 className="text-lg font-bold text-gray-900">
                Business Location
              </h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Street Address
                </label>
                <input
                  name="business_address"
                  type="text"
                  required
                  value={businessData.business_address}
                  onChange={handleChange}
                  placeholder="123 Market Street"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    City
                  </label>
                  <input
                    name="city"
                    type="text"
                    required
                    value={businessData.city}
                    onChange={handleChange}
                    placeholder="Lagos"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    State
                  </label>
                  <input
                    name="state"
                    type="text"
                    required
                    value={businessData.state}
                    onChange={handleChange}
                    placeholder="Lagos"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    LGA
                  </label>
                  <input
                    name="lga"
                    type="text"
                    value={businessData.lga}
                    onChange={handleChange}
                    placeholder="Ikeja"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Postal Code
                  </label>
                  <input
                    name="postal_code"
                    type="text"
                    value={businessData.postal_code}
                    onChange={handleChange}
                    placeholder="100001"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleBack}
                  className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl font-medium hover:bg-gray-50 text-sm"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={handleNext}
                  className="flex-1 py-2.5 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 text-sm"
                >
                  Continue
                </button>
              </div>
            </div>
          )}

          {/* Step 4: KYC */}
          {currentStep === 4 && (
            <div className="space-y-6 text-center">
              <div className="w-20 h-20 bg-yellow-100 rounded-full flex items-center justify-center mx-auto">
                <span className="text-4xl">🪪</span>
              </div>
              <h2 className="text-lg font-bold text-gray-900">
                Identity Verification (KYC)
              </h2>
              <p className="text-sm text-gray-600 leading-relaxed">
                We need to verify your identity before activating your account.
                Click the button below to start KYC verification. You will need
                your NIN / BVN and a valid government-issued ID.
              </p>
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-left text-sm text-blue-800 space-y-1">
                <p className="font-semibold">What you'll need:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>National ID or International Passport</li>
                  <li>A clear selfie / face photo</li>
                  <li>Your BVN or NIN number</li>
                </ul>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleBack}
                  className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl font-medium hover:bg-gray-50 text-sm"
                >
                  Back
                </button>
                <button
                  type="button"
                  onClick={handleStartKYC}
                  disabled={isSubmitting}
                  className="flex-1 py-2.5 bg-yellow-500 text-white font-semibold rounded-xl hover:bg-yellow-600 disabled:opacity-50 text-sm"
                >
                  {isSubmitting ? "Initiating..." : "Start KYC Verification"}
                </button>
              </div>
            </div>
          )}

          {/* Step 5: Done */}
          {currentStep === 5 && (
            <div className="space-y-6 text-center">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                <span className="text-4xl">🎉</span>
              </div>
              <h2 className="text-xl font-bold text-gray-900">
                Onboarding Complete!
              </h2>
              <p className="text-sm text-gray-600 leading-relaxed">
                Your application has been submitted. Our team will review and
                approve your agent account within 1–2 business days. You'll
                receive an email notification once approved.
              </p>
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-800">
                <p className="font-semibold">What happens next?</p>
                <ol className="list-decimal list-inside mt-2 space-y-1 text-left">
                  <li>Our team reviews your KYC documents</li>
                  <li>Account gets approved and activated</li>
                  <li>You receive confirmation email</li>
                  <li>Start accepting transactions!</li>
                </ol>
              </div>
              <button
                onClick={() => navigate("/login")}
                className="w-full py-3 bg-blue-600 text-white font-semibold rounded-xl hover:bg-blue-700 text-sm"
              >
                Go to Login
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
