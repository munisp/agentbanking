import { Check } from "lucide-react";
import React from "react";

/**
 * OnboardingProgressIndicator
 * Shows current step, percentage completion, and visual step indicators
 */
const OnboardingProgressIndicator = ({ currentStep, totalSteps = 4 }) => {
  const steps = [
    { id: 1, label: "Start" },
    { id: 2, label: "Account" },
    { id: 3, label: "BVN" },
    { id: 4, label: "Address" },
  ];

  const percentage = Math.round(((currentStep - 1) / (totalSteps - 1)) * 100);

  return (
    <div className="w-full space-y-4">
      {/* Progress Bar */}
      <div className="relative">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-600 transition-all duration-500 ease-out"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Step Indicators */}
      <div className="flex justify-between items-center px-1">
        {steps.map((step) => {
          const isCompleted = step.id < currentStep;
          const isCurrent = step.id === currentStep;
          const isPending = step.id > currentStep;

          return (
            <div key={step.id} className="flex flex-col items-center">
              {/* Circle Indicator */}
              <div
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center 
                  text-sm font-semibold transition-all duration-300
                  ${
                    isCompleted
                      ? "bg-green-500 text-white"
                      : isCurrent
                        ? "bg-green-600 text-white shadow-lg shadow-green-200"
                        : "bg-gray-200 text-gray-500"
                  }
                `}
              >
                {isCompleted ? (
                  <Check className="w-5 h-5" />
                ) : (
                  <span>{step.id}</span>
                )}
              </div>

              {/* Label */}
              <span
                className={`
                  text-xs mt-2 font-medium transition-colors
                  ${
                    isCurrent
                      ? "text-green-600"
                      : isCompleted
                        ? "text-green-500"
                        : "text-gray-400"
                  }
                `}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Percentage Display */}
      <div className="text-center">
        <span className="text-sm font-semibold text-gray-700">
          {percentage}% Complete
        </span>
      </div>
    </div>
  );
};

export default OnboardingProgressIndicator;
