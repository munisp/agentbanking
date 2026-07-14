import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    ArrowLeft,
    ArrowRight,
    Check,
    MapPin,
    Shield,
    User,
} from "lucide-react";
import { useEffect, useState } from "react";
// import { Card } from '@/components/ui/card';
import { useTenantBranding } from "@/contexts/TenantBrandingContext";
import { useAuth } from "@/services/auth";
import {
    onboardingService,
    PLATFORM_ROLE_LABELS,
    PLATFORM_ROLES,
    type OnboardingData,
} from "@/services/onboarding";
import { useLocation } from "wouter";

const steps = [
  { id: 1, title: "Personal Information", icon: User },
  { id: 2, title: "Address", icon: MapPin },
  { id: 3, title: "Identity Verification", icon: Shield },
];

export default function AdminOnboarding() {
  const [, setLocation] = useLocation();
  const { user } = useAuth();
  const { primaryColor, secondaryColor, name, logoUrl } = useTenantBranding();
  const [currentStep, setCurrentStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formData, setFormData] = useState<OnboardingData>({
    name: "",
    email: user?.email || "",
    phone: "",
    address: "",
    city: "",
    state: "",
    country: "Nigeria",
    postalCode: "",
    bvn: "",
    nin: "",
    platform_role: "support_agent", // Default to Support Agent
  });

  // Validation errors (allow 'submit' key)
  const [errors, setErrors] = useState<
    Partial<Record<keyof OnboardingData | "submit", string>>
  >({});

  // Validation loading states
  const [validating, setValidating] = useState<
    Partial<Record<keyof OnboardingData, boolean>>
  >({});

  // Load existing data if available
  useEffect(() => {
    const existingData = onboardingService.getOnboardingData();
    if (existingData) {
      setFormData(existingData);
    }
  }, []);

  // Set email from user if available
  useEffect(() => {
    if (user?.email && !formData.email) {
      setFormData((prev) => ({ ...prev, email: user.email }));
    }
  }, [user?.email, formData.email]);

  const validateStep1 = async (): Promise<boolean> => {
    const newErrors: Partial<Record<keyof OnboardingData, string>> = {};

    if (!formData.name.trim()) {
      newErrors.name = "Name is required";
    }

    // Validate email with async validation
    if (!formData.email.trim()) {
      newErrors.email = "Email is required";
    } else {
      setValidating((prev) => ({ ...prev, email: true }));
      try {
        const emailValidation = await onboardingService.validateEmailAsync(
          formData.email,
        );
        if (!emailValidation.valid) {
          newErrors.email = emailValidation.error;
        }
      } catch {
        newErrors.email = "Failed to validate email. Please try again";
      } finally {
        setValidating((prev) => ({ ...prev, email: false }));
      }
    }

    // Validate phone with async validation
    if (!formData.phone.trim()) {
      newErrors.phone = "Phone number is required";
    } else {
      setValidating((prev) => ({ ...prev, phone: true }));
      try {
        const phoneValidation =
          await onboardingService.validatePhoneNumberAsync(formData.phone);
        if (!phoneValidation.valid) {
          newErrors.phone = phoneValidation.error;
        }
      } catch {
        newErrors.phone = "Failed to validate phone number. Please try again";
      } finally {
        setValidating((prev) => ({ ...prev, phone: false }));
      }
    }

    // Validate platform role
    if (!formData.platform_role) {
      newErrors.platform_role = "Platform role is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = (): boolean => {
    const newErrors: Partial<Record<keyof OnboardingData, string>> = {};

    if (!formData.address.trim()) {
      newErrors.address = "Address is required";
    }

    if (!formData.city.trim()) {
      newErrors.city = "City is required";
    }

    if (!formData.state.trim()) {
      newErrors.state = "State is required";
    }

    if (!formData.country.trim()) {
      newErrors.country = "Country is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep3 = async (): Promise<boolean> => {
    const newErrors: Partial<Record<keyof OnboardingData, string>> = {};

    // Validate BVN with async validation
    if (!formData.bvn.trim()) {
      newErrors.bvn = "BVN is required";
    } else {
      setValidating((prev) => ({ ...prev, bvn: true }));
      try {
        const bvnValidation = await onboardingService.validateBVNAsync(
          formData.bvn,
        );
        if (!bvnValidation.valid) {
          newErrors.bvn = bvnValidation.error;
        }
      } catch {
        newErrors.bvn = "Failed to validate BVN. Please try again";
      } finally {
        setValidating((prev) => ({ ...prev, bvn: false }));
      }
    }

    // Validate NIN with async validation
    if (!formData.nin.trim()) {
      newErrors.nin = "NIN is required";
    } else {
      setValidating((prev) => ({ ...prev, nin: true }));
      try {
        const ninValidation = await onboardingService.validateNINAsync(
          formData.nin,
        );
        if (!ninValidation.valid) {
          newErrors.nin = ninValidation.error;
        }
      } catch {
        newErrors.nin = "Failed to validate NIN. Please try again";
      } finally {
        setValidating((prev) => ({ ...prev, nin: false }));
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const nextStep = async () => {
    let isValid = false;

    if (currentStep === 1) {
      isValid = await validateStep1();
    } else if (currentStep === 2) {
      isValid = validateStep2();
    }

    if (isValid && currentStep < 3) {
      setCurrentStep(currentStep + 1);
      setErrors({});
    }
  };

  const prevStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
      setErrors({});
    }
  };

  const handleSubmit = async () => {
    // Validate step 3 first
    const isValid = await validateStep3();
    if (!isValid) {
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await onboardingService.submitOnboarding(formData);

      // Check if there are validation errors from the API
      if (!response.success && response.errors) {
        const apiErrors: Partial<Record<keyof OnboardingData, string>> = {};
        response.errors.forEach((error) => {
          apiErrors[error.field as keyof OnboardingData] = error.message;
        });
        setErrors(apiErrors);
        setIsSubmitting(false);
        return;
      }

      // Navigate to KYC screen (onboarding is already marked as complete in the service)
      setLocation("/kyc");
    } catch {
      setErrors({
        submit: "Failed to submit onboarding data. Please try again.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateField = (field: keyof OnboardingData, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value || (field === "platform_role" ? "support_agent" : ""),
    }));
    // Clear error for this field when user starts typing
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Personal Information
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Let's start with your basic information
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <Label htmlFor="name">Full Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => updateField("name", e.target.value)}
                  placeholder="Enter your full name"
                  className={errors.name ? "border-red-500" : ""}
                />
                {errors.name && (
                  <p className="text-sm text-red-500 mt-1">{errors.name}</p>
                )}
              </div>

              <div>
                <Label htmlFor="email">Email Address *</Label>
                <div className="relative">
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => updateField("email", e.target.value)}
                    placeholder="Enter your email"
                    className={errors.email ? "border-red-500" : ""}
                    disabled={!!user?.email || validating.email}
                  />
                  {validating.email && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <div
                        className="w-4 h-4 border-2 border-gray-300 rounded-full animate-spin"
                        style={{ borderTopColor: primaryColor }}
                      />
                    </div>
                  )}
                </div>
                {user?.email && (
                  <p className="text-sm text-gray-500 mt-1">
                    This is your login email address
                  </p>
                )}
                {errors.email && (
                  <p className="text-sm text-red-500 mt-1">{errors.email}</p>
                )}
              </div>

              <div>
                <Label htmlFor="phone">Phone Number *</Label>
                <div className="relative">
                  <Input
                    id="phone"
                    type="tel"
                    value={formData.phone}
                    onChange={(e) => updateField("phone", e.target.value)}
                    placeholder="08012345678 or +2348012345678"
                    className={errors.phone ? "border-red-500" : ""}
                    disabled={validating.phone}
                  />
                  {validating.phone && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <div
                        className="w-4 h-4 border-2 border-gray-300 rounded-full animate-spin"
                        style={{ borderTopColor: primaryColor }}
                      />
                    </div>
                  )}
                </div>
                {errors.phone && (
                  <p className="text-sm text-red-500 mt-1">{errors.phone}</p>
                )}
                <p className="text-sm text-gray-500 mt-1">
                  Enter a valid Nigerian phone number
                </p>
              </div>

              <div>
                <Label htmlFor="platform_role">Platform Role *</Label>
                <select
                  id="platform_role"
                  value={formData.platform_role}
                  onChange={(e) => updateField("platform_role", e.target.value)}
                  className={`w-full mt-1 p-2 rounded border ${errors.platform_role ? "border-red-500" : "border-input"}`}
                >
                  {PLATFORM_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {PLATFORM_ROLE_LABELS[role]}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Defines what this admin can do on the 54link platform.
                </p>
                {errors.platform_role && (
                  <p className="text-sm text-red-500 mt-1">
                    {errors.platform_role}
                  </p>
                )}
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Address Information
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Please provide your residential address
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <Label htmlFor="address">Street Address *</Label>
                <Input
                  id="address"
                  value={formData.address}
                  onChange={(e) => updateField("address", e.target.value)}
                  placeholder="Enter your street address"
                  className={errors.address ? "border-red-500" : ""}
                />
                {errors.address && (
                  <p className="text-sm text-red-500 mt-1">{errors.address}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="city">City *</Label>
                  <Input
                    id="city"
                    value={formData.city}
                    onChange={(e) => updateField("city", e.target.value)}
                    placeholder="Enter your city"
                    className={errors.city ? "border-red-500" : ""}
                  />
                  {errors.city && (
                    <p className="text-sm text-red-500 mt-1">{errors.city}</p>
                  )}
                </div>

                <div>
                  <Label htmlFor="state">State *</Label>
                  <Input
                    id="state"
                    value={formData.state}
                    onChange={(e) => updateField("state", e.target.value)}
                    placeholder="Enter your state"
                    className={errors.state ? "border-red-500" : ""}
                  />
                  {errors.state && (
                    <p className="text-sm text-red-500 mt-1">{errors.state}</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="country">Country *</Label>
                  <Input
                    id="country"
                    value={formData.country}
                    onChange={(e) => updateField("country", e.target.value)}
                    placeholder="Enter your country"
                    className={errors.country ? "border-red-500" : ""}
                  />
                  {errors.country && (
                    <p className="text-sm text-red-500 mt-1">
                      {errors.country}
                    </p>
                  )}
                </div>

                <div>
                  <Label htmlFor="postalCode">Postal Code</Label>
                  <Input
                    id="postalCode"
                    value={formData.postalCode}
                    onChange={(e) => updateField("postalCode", e.target.value)}
                    placeholder="Enter postal code (optional)"
                  />
                </div>
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Identity Verification
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Please provide your BVN and NIN for verification
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <Label htmlFor="bvn">Bank Verification Number (BVN) *</Label>
                <div className="relative">
                  <Input
                    id="bvn"
                    type="text"
                    value={formData.bvn}
                    onChange={(e) =>
                      updateField("bvn", e.target.value.replace(/\D/g, ""))
                    }
                    placeholder="Enter your 11-digit BVN"
                    maxLength={11}
                    className={errors.bvn ? "border-red-500" : ""}
                    disabled={validating.bvn}
                  />
                  {validating.bvn && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <div
                        className="w-4 h-4 border-2 border-gray-300 rounded-full animate-spin"
                        style={{ borderTopColor: primaryColor }}
                      />
                    </div>
                  )}
                </div>
                {errors.bvn && (
                  <p className="text-sm text-red-500 mt-1">{errors.bvn}</p>
                )}
                <p className="text-sm text-gray-500 mt-1">
                  Enter your 11-digit BVN
                </p>
              </div>

              <div>
                <Label htmlFor="nin">
                  National Identification Number (NIN) *
                </Label>
                <div className="relative">
                  <Input
                    id="nin"
                    type="text"
                    value={formData.nin}
                    onChange={(e) =>
                      updateField("nin", e.target.value.replace(/\D/g, ""))
                    }
                    placeholder="Enter your 11-digit NIN"
                    maxLength={11}
                    className={errors.nin ? "border-red-500" : ""}
                    disabled={validating.nin}
                  />
                  {validating.nin && (
                    <div className="absolute right-3 top-1/2 -translate-y-1/2">
                      <div
                        className="w-4 h-4 border-2 border-gray-300 rounded-full animate-spin"
                        style={{ borderTopColor: primaryColor }}
                      />
                    </div>
                  )}
                </div>
                {errors.nin && (
                  <p className="text-sm text-red-500 mt-1">{errors.nin}</p>
                )}
                <p className="text-sm text-gray-500 mt-1">
                  Enter your 11-digit NIN
                </p>
              </div>

              {errors.submit && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg text-sm">
                  {errors.submit}
                </div>
              )}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`,
      }}
    >
      {/* Header with Logo */}
      <div className="w-full py-6 px-4 border-b border-gray-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm">
        <div className="max-w-4xl mx-auto flex items-center gap-4">
          {logoUrl && (
            <img
              src={logoUrl}
              alt={`${name} logo`}
              className="w-12 h-12 rounded object-contain"
            />
          )}
          <div>
            <h1 className="text-2xl font-bold" style={{ color: primaryColor }}>
              {name}
            </h1>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Admin Onboarding
            </p>
          </div>
        </div>
      </div>

      <div className="flex-1 container py-8">
        {/* Progress Steps */}
        <div className="mb-12">
          <div className="max-w-5xl mx-auto px-4">
            <div className="relative flex items-center justify-between">
              {/* Progress line background */}
              <div
                className="absolute top-6 left-0 right-0 h-1 z-0"
                style={{
                  background: `linear-gradient(to right, ${secondaryColor} 0%, ${secondaryColor} ${((currentStep - 1) / (steps.length - 1)) * 100}%, #e5e7eb ${((currentStep - 1) / (steps.length - 1)) * 100}%, #e5e7eb 100%)`,
                }}
              />

              {/* Steps */}
              {steps.map((step) => {
                const Icon = step.icon;
                const isCompleted = step.id < currentStep;
                const isCurrent = step.id === currentStep;
                const isUpcoming = step.id > currentStep;

                return (
                  <div
                    key={step.id}
                    className="relative z-10 flex flex-col items-center flex-1"
                  >
                    {/* Step circle */}
                    <div
                      className={`relative w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 shadow-lg ${
                        isCompleted
                          ? "text-white scale-110"
                          : isCurrent
                            ? "text-white scale-110 ring-4"
                            : "bg-white dark:bg-slate-800 text-gray-400 border-2 border-gray-300 dark:border-slate-600"
                      }`}
                      style={
                        isCompleted || isCurrent
                          ? {
                              backgroundColor: isCompleted
                                ? secondaryColor
                                : primaryColor,
                            }
                          : {}
                      }
                    >
                      {isCompleted ? (
                        <Check className="w-7 h-7" />
                      ) : (
                        <Icon
                          className={`w-6 h-6 ${isCurrent ? "animate-pulse" : ""}`}
                        />
                      )}
                      {/* Step number badge for upcoming steps */}
                      {isUpcoming && (
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-gray-300 dark:bg-slate-600 text-gray-600 dark:text-gray-400 text-xs font-bold rounded-full flex items-center justify-center">
                          {step.id}
                        </span>
                      )}
                    </div>

                    {/* Step label */}
                    <div className="mt-4 text-center max-w-30">
                      <p
                        className={`text-sm font-semibold transition-colors ${
                          isCurrent
                            ? ""
                            : isCompleted
                              ? "text-gray-700 dark:text-gray-300"
                              : "text-gray-500 dark:text-gray-500"
                        }`}
                        style={isCurrent ? { color: primaryColor } : {}}
                      >
                        {step.title}
                      </p>
                      {isCurrent && (
                        <div
                          className="mt-1 h-1 w-8 rounded-full mx-auto"
                          style={{ backgroundColor: primaryColor }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="max-w-5xl mx-auto px-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-gray-200 dark:border-slate-700 overflow-hidden">
            {/* Step indicator header */}
            <div
              className="px-8 py-6 border-b border-gray-200 dark:border-slate-700"
              style={{
                background: `linear-gradient(135deg, ${primaryColor}08, ${secondaryColor}08)`,
              }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                    Step {currentStep} of {steps.length}
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {steps[currentStep - 1]?.title}
                  </p>
                </div>
                <div
                  className="px-4 py-2 rounded-full text-sm font-semibold text-white"
                  style={{ backgroundColor: primaryColor }}
                >
                  {Math.round((currentStep / steps.length) * 100)}% Complete
                </div>
              </div>
            </div>

            {/* Form content */}
            <div className="p-8">{renderStepContent()}</div>

            {/* Navigation Buttons */}
            <div className="px-8 py-6 border-t border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-900/50">
              <div className="flex justify-between items-center">
                <Button
                  variant="outline"
                  onClick={prevStep}
                  disabled={currentStep === 1}
                  className="flex items-center gap-2 min-w-30"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Previous
                </Button>

                <div className="flex gap-2">
                  {steps.map((step) => (
                    <div
                      key={step.id}
                      className={`w-2 h-2 rounded-full transition-all ${
                        step.id === currentStep
                          ? "w-8"
                          : step.id < currentStep
                            ? "opacity-100"
                            : "opacity-30"
                      }`}
                      style={{
                        backgroundColor:
                          step.id <= currentStep ? primaryColor : "#d1d5db",
                      }}
                    />
                  ))}
                </div>

                {currentStep < 3 ? (
                  <Button
                    onClick={nextStep}
                    className="flex items-center gap-2 min-w-30 text-white hover:opacity-90 transition-opacity"
                    style={{ backgroundColor: primaryColor || "#2563eb" }}
                  >
                    Next
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                ) : (
                  <Button
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="flex items-center gap-2 min-w-45 text-white hover:opacity-90 transition-opacity disabled:opacity-50"
                    style={{
                      backgroundColor:
                        secondaryColor || primaryColor || "#2563eb",
                    }}
                  >
                    {isSubmitting ? "Submitting..." : "Complete Onboarding"}
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
