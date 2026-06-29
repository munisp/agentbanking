import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

const STEPS = [
  { id: 1, title: "Welcome", description: "Get started with 54agent banking" },
  {
    id: 2,
    title: "Personal Info",
    description: "Tell us a bit more about you",
  },
  { id: 3, title: "Address", description: "Where are you located?" },
  { id: 4, title: "KYC Verification", description: "Verify your identity" },
  { id: 5, title: "Done", description: "You're ready to go!" },
];

const Onboarding = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [personalData, setPersonalData] = useState({
    date_of_birth: "",
    gender: "",
    occupation: "",
  });

  const [addressData, setAddressData] = useState({
    address: "",
    city: "",
    state: "",
    postal_code: "",
  });

  const handlePersonalChange = (e) => {
    setPersonalData({ ...personalData, [e.target.name]: e.target.value });
  };

  const handleAddressChange = (e) => {
    setAddressData({ ...addressData, [e.target.name]: e.target.value });
  };

  const handleNext = () => {
    if (currentStep < STEPS.length) setCurrentStep((s) => s + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep((s) => s - 1);
  };

  const handleSave = async (e) => {
    e?.preventDefault();
    setIsSubmitting(true);
    await new Promise((r) => setTimeout(r, 700));
    setIsSubmitting(false);
    handleNext();
  };

  const progressPercent = ((currentStep - 1) / (STEPS.length - 1)) * 100;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-xl w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-3">
            <div className="h-14 w-14 bg-green-600 rounded-2xl flex items-center justify-center shadow-lg">
              <span className="text-white font-bold text-xl">AB</span>
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Account Setup</h1>
          <p className="text-sm text-gray-500 mt-1">
            Step {currentStep} of {STEPS.length}:{" "}
            {STEPS[currentStep - 1].description}
          </p>
        </div>

        {/* Progress Bar */}
        <div className="bg-gray-200 rounded-full h-2">
          <div
            className="bg-green-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Step Dots */}
        <div className="flex justify-between px-1">
          {STEPS.map((step) => (
            <div key={step.id} className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                  step.id < currentStep
                    ? "bg-green-500 text-white"
                    : step.id === currentStep
                      ? "bg-green-600 text-white"
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
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                <span className="text-4xl">🏦</span>
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  Welcome to 54agent!
                </h2>
                <p className="text-sm text-gray-600 mt-2 leading-relaxed">
                  Your account has been created. Let's complete your profile so
                  you can access all banking features and transact seamlessly
                  with your local agent.
                </p>
              </div>
              <ul className="text-left space-y-2 text-sm text-gray-700">
                {[
                  "Complete your personal profile",
                  "Add your home address",
                  "Verify your identity (KYC)",
                  "Access your digital wallet",
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs font-bold">
                      {i + 1}
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
              <button
                onClick={handleNext}
                className="w-full py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors"
              >
                Get Started
              </button>
            </div>
          )}

          {/* Step 2: Personal Info */}
          {currentStep === 2 && (
            <form onSubmit={handleSave} className="space-y-5">
              <h2 className="text-lg font-bold text-gray-900">
                Personal Information
              </h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date of Birth
                </label>
                <input
                  name="date_of_birth"
                  type="date"
                  required
                  value={personalData.date_of_birth}
                  onChange={handlePersonalChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Gender
                </label>
                <select
                  name="gender"
                  value={personalData.gender}
                  onChange={handlePersonalChange}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  <option value="">Select gender</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="prefer_not_to_say">Prefer not to say</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Occupation
                </label>
                <input
                  name="occupation"
                  type="text"
                  value={personalData.occupation}
                  onChange={handlePersonalChange}
                  placeholder="e.g. Teacher, Trader, Nurse"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
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
                  className="flex-1 py-2.5 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 disabled:opacity-50 text-sm"
                >
                  {isSubmitting ? "Saving..." : "Continue"}
                </button>
              </div>
            </form>
          )}

          {/* Step 3: Address */}
          {currentStep === 3 && (
            <div className="space-y-5">
              <h2 className="text-lg font-bold text-gray-900">Home Address</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Street Address
                </label>
                <input
                  name="address"
                  type="text"
                  required
                  value={addressData.address}
                  onChange={handleAddressChange}
                  placeholder="45 Adeola Odeku Street"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
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
                    value={addressData.city}
                    onChange={handleAddressChange}
                    placeholder="Lagos"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
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
                    value={addressData.state}
                    onChange={handleAddressChange}
                    placeholder="Lagos"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Postal Code
                </label>
                <input
                  name="postal_code"
                  type="text"
                  value={addressData.postal_code}
                  onChange={handleAddressChange}
                  placeholder="100001"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
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
                  className="flex-1 py-2.5 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 text-sm"
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
                Identity Verification
              </h2>
              <p className="text-sm text-gray-600 leading-relaxed">
                To keep your account secure and compliant, we need to verify
                your identity. This takes only a few minutes.
              </p>
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-left text-sm text-yellow-800 space-y-1">
                <p className="font-semibold">You will need:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>
                    Government-issued ID (NIN slip, Voter's Card, Passport)
                  </li>
                  <li>A clear front-facing selfie</li>
                  <li>Your BVN or NIN number</li>
                </ul>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleBack}
                  className="flex-1 py-2.5 border border-gray-300 text-gray-700 rounded-xl font-medium hover:bg-gray-50 text-sm"
                >
                  Back
                </button>
                <button
                  onClick={handleSave}
                  disabled={isSubmitting}
                  className="flex-1 py-2.5 bg-yellow-500 text-white font-semibold rounded-xl hover:bg-yellow-600 disabled:opacity-50 text-sm"
                >
                  {isSubmitting ? "Loading..." : "Start Verification"}
                </button>
              </div>
            </div>
          )}

          {/* Step 5: Done */}
          {currentStep === 5 && (
            <div className="space-y-6 text-center">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                <span className="text-4xl">✅</span>
              </div>
              <h2 className="text-xl font-bold text-gray-900">
                You're All Set!
              </h2>
              <p className="text-sm text-gray-600 leading-relaxed">
                Your profile is complete and your verification is underway. You
                can now explore your account while verification is processed in
                the background.
              </p>
              <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-800 text-left">
                <p className="font-semibold">You can now:</p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>View your account balance</li>
                  <li>Browse agent storefronts</li>
                  <li>Receive money transfers</li>
                </ul>
              </div>
              <button
                onClick={() => navigate("/")}
                className="w-full py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 text-sm"
              >
                Go to Dashboard
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
