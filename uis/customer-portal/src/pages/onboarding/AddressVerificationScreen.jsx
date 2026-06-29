import { AlertCircle, ArrowLeft, Loader, MapPin } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import OnboardingProgressIndicator from "../../components/OnboardingProgressIndicator.jsx";
import { orchestratorApi } from "../../utils/api.js";
import { storage } from "../../utils/storage.js";

const AddressVerificationScreen = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [accountType, setAccountType] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [formData, setFormData] = useState({
    address: "",
    city: "",
    state: "",
    country: "Nigeria",
    postalCode: "",
  });

  // Nigerian states
  const nigerianStates = [
    "Abia",
    "Adamawa",
    "Akwa Ibom",
    "Anambra",
    "Bauchi",
    "Bayelsa",
    "Benue",
    "Borno",
    "Cross River",
    "Delta",
    "Ebonyi",
    "Edo",
    "Ekiti",
    "Enugu",
    "FCT",
    "Gombe",
    "Imo",
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Kogi",
    "Kwara",
    "Lagos",
    "Nasarawa",
    "Niger",
    "Ogun",
    "Ondo",
    "Osun",
    "Oyo",
    "Plateau",
    "Rivers",
    "Sokoto",
    "Taraba",
    "Yobe",
    "Zamfara",
  ];

  useEffect(() => {
    // Get account type from state or storage
    const type = location.state?.accountType || storage.getAccountType();
    setAccountType(type);

    // Load previously saved address data if exists
    const savedData = storage.getOnboardingData();
    if (savedData) {
      setFormData({
        address: savedData.address || "",
        city: savedData.city || "",
        state: savedData.state || "",
        country: savedData.country || "Nigeria",
        postalCode: savedData.postalCode || "",
      });
    }
  }, [location]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleContinue = async () => {
    if (!formData.address || !formData.city || !formData.state) return;

    setSubmitError("");
    setIsSubmitting(true);

    try {
      // Merge address data with existing onboarding data
      const onboardingData = storage.getOnboardingData() || {};
      const updatedData = { ...onboardingData, ...formData, accountType };
      storage.saveOnboardingData(updatedData);

      const bvn = storage.getBVN();

      const customerData = {
        firstName: updatedData.firstName || "",
        lastName: updatedData.lastName || "",
        email: updatedData.email || "",
        phone: updatedData.phone || "",
        password: updatedData.password || "",
        uin: bvn || "",
        address: updatedData.address || "",
        city: updatedData.city || "",
        state: updatedData.state || "",
        postalCode: updatedData.postalCode || "",
      };

      await orchestratorApi.registerCustomer(customerData);

      storage.clearOnboardingData();
      navigate("/onboarding/completion", { state: { accountType } });
    } catch (error) {
      console.error("Error creating customer:", error);
      setSubmitError(
        error.message || "Account creation failed. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBack = () => {
    navigate("/onboarding/bvn-verification");
  };

  const isFormValid =
    formData.address.trim() &&
    formData.city.trim() &&
    formData.state.trim() &&
    formData.country.trim();

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-2xl w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 bg-green-600 rounded-2xl flex items-center justify-center shadow-lg">
              <MapPin className="text-white w-8 h-8" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">
            Address Verification
          </h1>
          <p className="text-gray-600 mt-2">
            Provide your current residential address
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <OnboardingProgressIndicator currentStep={4} totalSteps={4} />
        </div>

        {/* Address Form */}
        <div className="bg-white rounded-2xl shadow-md p-8">
          <form className="space-y-5">
            {/* Street Address */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Street Address <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="address"
                value={formData.address}
                onChange={handleChange}
                placeholder="Enter your house address"
                required
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-all"
              />
            </div>

            {/* Country */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Country <span className="text-red-500">*</span>
              </label>
              <select
                name="country"
                value={formData.country}
                onChange={handleChange}
                required
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-all bg-white"
              >
                <option value="Nigeria">Nigeria</option>
                <option value="Ghana">Ghana</option>
                <option value="Kenya">Kenya</option>
                <option value="South Africa">South Africa</option>
              </select>
            </div>

            {/* State */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                State <span className="text-red-500">*</span>
              </label>
              {formData.country === "Nigeria" ? (
                <select
                  name="state"
                  value={formData.state}
                  onChange={handleChange}
                  required
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-all bg-white"
                >
                  <option value="">Select State</option>
                  {nigerianStates.map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  name="state"
                  value={formData.state}
                  onChange={handleChange}
                  placeholder="Enter your state/province"
                  required
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-all"
                />
              )}
            </div>

            {/* City */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                City <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="city"
                value={formData.city}
                onChange={handleChange}
                placeholder="Enter your city"
                required
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-all"
              />
            </div>

            {/* Postal Code */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Postal Code
              </label>
              <input
                type="text"
                name="postalCode"
                value={formData.postalCode}
                onChange={handleChange}
                placeholder="Enter postal code"
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-500 transition-all"
              />
            </div>
          </form>
        </div>

        {/* Error Message */}
        {submitError && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex gap-3 items-start">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{submitError}</p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-4">
          <button
            onClick={handleBack}
            disabled={isSubmitting}
            className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowLeft className="w-5 h-5" />
            Back
          </button>
          <button
            onClick={handleContinue}
            disabled={!isFormValid || isSubmitting}
            className="flex-1 py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-200 flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Creating Account…
              </>
            ) : (
              "Create Account"
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AddressVerificationScreen;
