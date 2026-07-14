import { ArrowLeft, Building2, Check, User } from "lucide-react";
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import OnboardingProgressIndicator from "../../components/OnboardingProgressIndicator.jsx";
import { storage } from "../../utils/storage.js";

const AccountTypeScreen = () => {
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState("");

  useEffect(() => {
    // Load previously selected account type if exists
    const savedType = storage.getAccountType();
    if (savedType) {
      setSelectedType(savedType);
    }
  }, []);

  const accountTypes = [
    {
      id: "individual",
      title: "Individual Account",
      subtitle: "For personal banking needs",
      icon: User,
      features: [
        "Personal wallet account",
        // "Bill payments and transfers",
        // "Loan applications up to ₦5M",
      ],
    },
    // {
    //   id: 'business',
    //   title: 'Business Account',
    //   subtitle: 'For companies and organizations',
    //   icon: Building2,
    //   features: [
    //     'Business banking and payroll',
    //     'LPO financing and invoicing',
    //     'Higher transaction limits',
    //   ],
    // },
  ];

  const handleContinue = () => {
    if (selectedType) {
      // Save account type to localStorage
      storage.saveAccountType(selectedType);

      // Navigate to BVN verification
      navigate("/onboarding/bvn-verification", {
        state: { accountType: selectedType },
      });
    }
  };

  const handleBack = () => {
    navigate("/onboarding/start");
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4">
      <div className="max-w-3xl w-full space-y-6">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center mb-4">
            <div className="h-16 w-16 bg-green-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Building2 className="text-white w-8 h-8" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-gray-900">
            Select Account Type
          </h1>
          <p className="text-gray-600 mt-2">
            Choose the type of account that best fits your needs
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="bg-white rounded-2xl shadow-md p-6">
          <OnboardingProgressIndicator currentStep={2} totalSteps={4} />
        </div>

        {/* Account Type Cards */}
        <div className="space-y-4">
          {accountTypes.map((type) => {
            const Icon = type.icon;
            const isSelected = selectedType === type.id;

            return (
              <button
                key={type.id}
                onClick={() => setSelectedType(type.id)}
                className={`
                  w-full text-left p-6 rounded-2xl border-2 transition-all duration-200
                  ${
                    isSelected
                      ? "border-green-500 bg-green-50 shadow-lg shadow-green-100"
                      : "border-gray-200 bg-white hover:border-green-200 hover:shadow-md"
                  }
                `}
              >
                <div className="flex items-start gap-4">
                  {/* Icon */}
                  <div
                    className={`
                      w-16 h-16 rounded-xl flex items-center justify-center flex-shrink-0
                      ${isSelected ? "bg-green-500" : "bg-gray-100"}
                    `}
                  >
                    <Icon
                      className={`w-8 h-8 ${isSelected ? "text-white" : "text-gray-600"}`}
                    />
                  </div>

                  {/* Content */}
                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <h3 className="text-xl font-bold text-gray-900">
                          {type.title}
                        </h3>
                        <p className="text-sm text-gray-600 mt-1">
                          {type.subtitle}
                        </p>
                      </div>
                      {isSelected && (
                        <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                          <Check className="w-5 h-5 text-white" />
                        </div>
                      )}
                    </div>

                    {/* Features */}
                    <ul className="space-y-2 mt-4">
                      {type.features.map((feature, index) => (
                        <li
                          key={index}
                          className="flex items-center gap-2 text-sm text-gray-700"
                        >
                          <div className="w-1.5 h-1.5 bg-green-500 rounded-full" />
                          {feature}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </button>
            );
          })}
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
          <button
            onClick={handleContinue}
            disabled={!selectedType}
            className="flex-1 py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-green-200"
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccountTypeScreen;
