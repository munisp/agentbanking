import {
    AlertCircle,
    ArrowLeft,
    CheckCircle,
    Loader,
    Shield,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import OnboardingProgressIndicator from "../../components/OnboardingProgressIndicator.jsx";
import { storage } from "../../utils/storage.js";

const BvnVerificationScreen = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [bvn, setBvn] = useState("");
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationMessage, setVerificationMessage] = useState("");
  const [bvnIsValid, setBvnIsValid] = useState(null);
  const [accountType, setAccountType] = useState("");

  useEffect(() => {
    // Get account type from state or storage
    const type = location.state?.accountType || storage.getAccountType();
    setAccountType(type);

    // Load previously entered BVN if exists
    const savedBvn = storage.getBVN();
    if (savedBvn) {
      setBvn(savedBvn);
    }
  }, [location]);

  const validateBvn = async (value) => {
    if (value.length !== 11) {
      setBvnIsValid(null);
      setVerificationMessage("");
      return;
    }

    setIsVerifying(true);
    setVerificationMessage("");
    setBvnIsValid(null);

    try {
      // Simulate BVN verification API call
      // In production, replace with actual verification service
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Mock validation - check if BVN is all digits
      const isValid = /^\d{11}$/.test(value);

      setBvnIsValid(isValid);
      setVerificationMessage(
        isValid
          ? "BVN verified successfully"
          : "Invalid BVN format. Please check and try again.",
      );
    } catch (error) {
      setBvnIsValid(false);
      setVerificationMessage("Verification failed. Please try again.");
    } finally {
      setIsVerifying(false);
    }
  };

  const handleBvnChange = (e) => {
    const value = e.target.value.replace(/\D/g, "").slice(0, 11);
    setBvn(value);

    // Auto-verify when 11 digits entered
    if (value.length === 11) {
      validateBvn(value);
    } else {
      setBvnIsValid(null);
      setVerificationMessage("");
    }
  };

  const handleContinue = () => {
    // Save BVN to localStorage (BVN is optional, so we allow continue even if empty)
    if (bvn) {
      storage.saveBVN(bvn);
    } else {
      storage.saveBVN(null);
    }

    // Navigate to address verification
    navigate("/onboarding/address-verification", {
      state: { accountType },
    });
  };

  const handleBack = () => {
    navigate("/onboarding/account-type");
  };

  const handleSkip = () => {
    // Clear BVN and continue
    storage.saveBVN(null);
    navigate("/onboarding/address-verification", {
      state: { accountType },
    });
  };

  const canContinue = !bvn || (bvn.length === 11 && bvnIsValid);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-2xl w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 bg-green-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Shield className="text-white w-8 h-8" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">BVN Verification</h1>
          <p className="text-gray-600 mt-2">
            Enter your Bank Verification Number for compliance
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <OnboardingProgressIndicator currentStep={3} totalSteps={4} />
        </div>

        {/* BVN Info Banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex gap-3">
            <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-blue-900 font-medium mb-1">
                Why do we need your BVN?
              </p>
              <p className="text-sm text-blue-800">
                The Central Bank of Nigeria (CBN) requires BVN for all banking
                accounts to ensure compliance and security. Your BVN is
                encrypted and stored securely.
              </p>
            </div>
          </div>
        </div>

        {/* BVN Input Form */}
        <div className="bg-white rounded-2xl shadow-md p-8">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bank Verification Number (BVN)
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={bvn}
                  onChange={handleBvnChange}
                  placeholder="12345678901"
                  maxLength={11}
                  className={`
                    w-full px-4 py-3 border-2 rounded-xl text-lg
                    focus:outline-none focus:ring-2 transition-all
                    ${
                      bvnIsValid === true
                        ? "border-green-500 focus:ring-green-200"
                        : bvnIsValid === false
                          ? "border-red-500 focus:ring-red-200"
                          : "border-gray-300 focus:ring-green-200 focus:border-green-500"
                    }
                  `}
                />
                {/* Input Status Icon */}
                {isVerifying && (
                  <div className="absolute right-4 top-1/2 transform -translate-y-1/2">
                    <Loader className="w-5 h-5 text-gray-400 animate-spin" />
                  </div>
                )}
                {!isVerifying && bvnIsValid === true && (
                  <div className="absolute right-4 top-1/2 transform -translate-y-1/2">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                  </div>
                )}
                {!isVerifying && bvnIsValid === false && (
                  <div className="absolute right-4 top-1/2 transform -translate-y-1/2">
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  </div>
                )}
              </div>
              <div className="flex justify-between items-center mt-2">
                <p className="text-xs text-gray-500">{bvn.length}/11 digits</p>
                {verificationMessage && (
                  <p
                    className={`text-sm font-medium ${
                      bvnIsValid ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {verificationMessage}
                  </p>
                )}
              </div>
            </div>

            {/* <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
              <p className="text-sm text-yellow-900">
                <strong>Note:</strong> You can skip this step and provide your
                BVN later. However, some features may be limited until your BVN
                is verified.
              </p>
            </div> */}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-4">
          <button
            onClick={handleBack}
            className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-colors flex items-center justify-center gap-2"
          >
            <ArrowLeft className="w-5 h-5" />
            Back
          </button>
          {!bvn && (
            <button
              onClick={handleSkip}
              className="flex-1 py-3 border-2 border-yellow-300 text-yellow-700 rounded-xl font-semibold hover:bg-yellow-50 transition-colors"
            >
              Skip for Now
            </button>
          )}
          <button
            onClick={handleContinue}
            disabled={!canContinue}
            className="flex-1 py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-200"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
};

export default BvnVerificationScreen;
