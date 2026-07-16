// COMMENTED OUT: Not using API calls for now - using mock data
// import apiClient from '../api';

/**
 * v2.perm `platform` entity roles — for 54link platform-level admins.
 * These map directly to the relations defined in schemas/permify/v2.perm.
 */
export type PlatformRole =
  | "super_admin" // Full platform access
  | "tenant_manager" // Manage tenants
  | "operations_manager" // Platform operations
  | "risk_manager" // Risk & limits oversight
  | "internal_auditor" // View all data & audit
  | "it_admin" // System & feature management
  | "relationship_manager" // Tenant relations
  | "compliance_officer" // Compliance & KYC
  | "support_agent"; // Customer support

export const PLATFORM_ROLE_LABELS: Record<PlatformRole, string> = {
  super_admin: "Super Admin",
  tenant_manager: "Tenant Manager",
  operations_manager: "Operations Manager",
  risk_manager: "Risk Manager",
  internal_auditor: "Internal Auditor",
  it_admin: "IT Admin",
  relationship_manager: "Relationship Manager",
  compliance_officer: "Compliance Officer",
  support_agent: "Support Agent",
};

export const PLATFORM_ROLES = Object.keys(
  PLATFORM_ROLE_LABELS,
) as PlatformRole[];

export interface OnboardingData {
  // Step 1: Personal Information
  name: string;
  email: string;
  phone: string;

  // Step 2: Address
  address: string;
  city: string;
  state: string;
  country: string;
  postalCode?: string;

  // Step 3: Identity Documents
  bvn: string;
  nin: string;

  // Step 4: Platform Role (v2.perm `platform` entity)
  platform_role: PlatformRole;
}

export interface OnboardingResponse {
  success: boolean;
  message: string;
  data?: OnboardingData;
  errors?: ValidationError[];
}

export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationResponse {
  valid: boolean;
  error?: string;
  verified?: boolean; // Whether the value was verified against external service
}

class OnboardingService {
  private readonly ONBOARDING_COMPLETE_KEY = "admin_onboarding_complete";
  private readonly ONBOARDING_DATA_KEY = "admin_onboarding_data";

  /**
   * Check if admin has completed onboarding
   */
  isOnboardingComplete(): boolean {
    const completed = localStorage.getItem(this.ONBOARDING_COMPLETE_KEY);
    return completed === "true";
  }

  /**
   * Mark onboarding as complete
   */
  setOnboardingComplete(): void {
    localStorage.setItem(this.ONBOARDING_COMPLETE_KEY, "true");
  }

  /**
   * Get stored onboarding data
   */
  getOnboardingData(): OnboardingData | null {
    const dataStr = localStorage.getItem(this.ONBOARDING_DATA_KEY);
    if (!dataStr) return null;
    try {
      return JSON.parse(dataStr);
    } catch {
      return null;
    }
  }

  /**
   * Store onboarding data
   */
  setOnboardingData(data: OnboardingData): void {
    localStorage.setItem(this.ONBOARDING_DATA_KEY, JSON.stringify(data));
  }

  /**
   * Submit onboarding data
   * Uses mock data for now, but has placeholder for API call
   */
  async submitOnboarding(data: OnboardingData): Promise<OnboardingResponse> {
    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Mock: Final validation before submission
    const validationErrors: ValidationError[] = [];

    // Validate all fields
    const phoneValidation = await this.validatePhoneNumberAsync(data.phone);
    if (!phoneValidation.valid) {
      validationErrors.push({
        field: "phone",
        message: phoneValidation.error || "Invalid phone number",
      });
    }

    const bvnValidation = await this.validateBVNAsync(data.bvn);
    if (!bvnValidation.valid) {
      validationErrors.push({
        field: "bvn",
        message: bvnValidation.error || "Invalid BVN",
      });
    }

    const ninValidation = await this.validateNINAsync(data.nin);
    if (!ninValidation.valid) {
      validationErrors.push({
        field: "nin",
        message: ninValidation.error || "Invalid NIN",
      });
    }

    const emailValidation = await this.validateEmailAsync(data.email);
    if (!emailValidation.valid) {
      validationErrors.push({
        field: "email",
        message: emailValidation.error || "Invalid email",
      });
    }

    // Mock: Check if BVN and NIN match (they should be for the same person)
    // This is a simplified check - in reality, this would be done server-side
    const bvnCleaned = data.bvn.replace(/\D/g, "");
    const ninCleaned = data.nin.replace(/\D/g, "");

    // Mock: If both are valid format but don't match certain patterns, warn
    // (In reality, this would check against a database)
    if (bvnCleaned.length === 11 && ninCleaned.length === 11) {
      // Mock scenario: BVN and NIN don't match the same person
      const mockMismatchBVN = "12345678901";
      const mockMismatchNIN = "98765432109";

      if (bvnCleaned === mockMismatchBVN && ninCleaned !== mockMismatchNIN) {
        validationErrors.push({
          field: "bvn",
          message:
            "BVN and NIN do not match. Please ensure both belong to the same person",
        });
      }
    }

    // If there are validation errors, return them
    if (validationErrors.length > 0) {
      return {
        success: false,
        message: "Validation failed. Please correct the errors and try again",
        errors: validationErrors,
      };
    }

    // Store data locally
    this.setOnboardingData(data);

    // Mock API call - replace with actual API call when ready
    // TODO: Replace this mock with actual API call
    // const response = await apiClient.post<OnboardingResponse>(
    //   '/admin/onboarding',
    //   data
    // );
    // return response.data;

    // Store data locally
    this.setOnboardingData(data);

    // Mock successful response
    const response = {
      success: true,
      message: "Onboarding data submitted successfully",
      data,
    };

    // Mark onboarding as complete
    this.setOnboardingComplete();

    return response;
  }

  /**
   * Validate phone number (Nigerian format) - Client-side validation
   */
  validatePhoneNumber(phone: string): { valid: boolean; error?: string } {
    // Remove all non-digit characters
    const cleaned = phone.replace(/\D/g, "");

    // Nigerian phone number validation
    // Should be 11 digits starting with 0, or 13 digits starting with +234
    if (cleaned.length === 11 && cleaned.startsWith("0")) {
      return { valid: true };
    }

    if (cleaned.length === 13 && cleaned.startsWith("234")) {
      return { valid: true };
    }

    if (cleaned.length === 10 && !cleaned.startsWith("0")) {
      return { valid: true };
    }

    return {
      valid: false,
      error:
        "Please enter a valid Nigerian phone number (e.g., 08012345678 or +2348012345678)",
    };
  }

  /**
   * Mock API validation for phone number
   * Simulates server-side validation with network delay
   */
  async validatePhoneNumberAsync(phone: string): Promise<ValidationResponse> {
    // First do client-side validation
    const clientValidation = this.validatePhoneNumber(phone);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 800));

    const cleaned = phone.replace(/\D/g, "");

    // Mock invalid phone numbers that would fail server validation
    const invalidPhones = [
      "08000000000", // All zeros
      "08011111111", // All ones
      "08012345678", // Mock: This number is already registered
      "08123456789", // Mock: This number is blocked
    ];

    if (invalidPhones.includes(cleaned)) {
      if (cleaned === "08012345678") {
        return {
          valid: false,
          error: "This phone number is already registered with another account",
          verified: true,
        };
      }
      if (cleaned === "08123456789") {
        return {
          valid: false,
          error: "This phone number has been blocked. Please contact support",
          verified: true,
        };
      }
      return {
        valid: false,
        error: "Invalid phone number format. Please check and try again",
        verified: true,
      };
    }

    // Mock: Check if phone starts with valid Nigerian prefixes
    const validPrefixes = [
      "080",
      "081",
      "082",
      "083",
      "070",
      "071",
      "090",
      "091",
    ];
    const prefix = cleaned.substring(0, 3);

    if (!validPrefixes.includes(prefix)) {
      return {
        valid: false,
        error:
          "Invalid phone number prefix. Please use a valid Nigerian mobile number",
        verified: true,
      };
    }

    // Valid phone number
    return {
      valid: true,
      verified: true,
    };
  }

  /**
   * Validate BVN (Bank Verification Number) - Client-side validation
   */
  validateBVN(bvn: string): { valid: boolean; error?: string } {
    // Remove all non-digit characters
    const cleaned = bvn.replace(/\D/g, "");

    // BVN should be exactly 11 digits
    if (cleaned.length === 11) {
      return { valid: true };
    }

    return {
      valid: false,
      error: "BVN must be exactly 11 digits",
    };
  }

  /**
   * Mock API validation for BVN
   * Simulates server-side validation with network delay
   */
  async validateBVNAsync(bvn: string): Promise<ValidationResponse> {
    // First do client-side validation
    const clientValidation = this.validateBVN(bvn);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 1000));

    const cleaned = bvn.replace(/\D/g, "");

    // Mock invalid BVNs that would fail server validation
    const invalidBVNs = [
      "00000000000", // All zeros
      "11111111111", // All ones
      "22222222222", // All twos
      "12345678901", // Sequential - invalid checksum
      "98765432109", // Reverse sequential - invalid checksum
    ];

    if (invalidBVNs.includes(cleaned)) {
      return {
        valid: false,
        error: "Invalid BVN. The provided BVN does not exist or is invalid",
        verified: true,
      };
    }

    // Mock: Check BVN checksum (simplified validation)
    // Real BVNs have a checksum algorithm, but we'll simulate with a simple check
    const digits = cleaned.split("").map(Number);
    const sum = digits.reduce((acc, digit) => acc + digit, 0);

    // Mock: If sum is too low or too high, it's likely invalid
    if (sum < 20 || sum > 90) {
      return {
        valid: false,
        error: "Invalid BVN format. Please verify your BVN and try again",
        verified: true,
      };
    }

    // Mock: Some BVNs are already registered
    const registeredBVNs = ["12345678901", "98765432109"];
    if (registeredBVNs.includes(cleaned)) {
      return {
        valid: false,
        error: "This BVN is already registered with another account",
        verified: true,
      };
    }

    // Valid BVN
    return {
      valid: true,
      verified: true,
    };
  }

  /**
   * Validate NIN (National Identification Number) - Client-side validation
   */
  validateNIN(nin: string): { valid: boolean; error?: string } {
    // Remove all non-digit characters
    const cleaned = nin.replace(/\D/g, "");

    // NIN should be exactly 11 digits
    if (cleaned.length === 11) {
      return { valid: true };
    }

    return {
      valid: false,
      error: "NIN must be exactly 11 digits",
    };
  }

  /**
   * Mock API validation for NIN
   * Simulates server-side validation with network delay
   */
  async validateNINAsync(nin: string): Promise<ValidationResponse> {
    // First do client-side validation
    const clientValidation = this.validateNIN(nin);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 1200));

    const cleaned = nin.replace(/\D/g, "");

    // Mock invalid NINs that would fail server validation
    const invalidNINs = [
      "00000000000", // All zeros
      "11111111111", // All ones
      "22222222222", // All twos
      "12345678901", // Sequential - invalid format
      "98765432109", // Reverse sequential - invalid format
    ];

    if (invalidNINs.includes(cleaned)) {
      return {
        valid: false,
        error: "Invalid NIN. The provided NIN does not exist or is invalid",
        verified: true,
      };
    }

    // Mock: Check NIN format (NINs typically start with specific patterns)
    // Real NINs have specific validation rules, but we'll simulate
    const firstDigit = cleaned[0];

    // Mock: NINs typically don't start with 0
    if (firstDigit === "0") {
      return {
        valid: false,
        error: "Invalid NIN format. Please verify your NIN and try again",
        verified: true,
      };
    }

    // Mock: Some NINs are already registered
    const registeredNINs = ["12345678901", "98765432109"];
    if (registeredNINs.includes(cleaned)) {
      return {
        valid: false,
        error: "This NIN is already registered with another account",
        verified: true,
      };
    }

    // Mock: Check if NIN matches BVN (they should match for the same person)
    // This would be checked during final submission, not during individual field validation

    // Valid NIN
    return {
      valid: true,
      verified: true,
    };
  }

  /**
   * Mock validation for email format
   */
  validateEmail(email: string): { valid: boolean; error?: string } {
    if (!email.trim()) {
      return {
        valid: false,
        error: "Email is required",
      };
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      return {
        valid: false,
        error: "Please enter a valid email address",
      };
    }

    // Check for common invalid patterns
    if (email.includes("..") || email.startsWith(".") || email.endsWith(".")) {
      return {
        valid: false,
        error: "Invalid email format",
      };
    }

    return { valid: true };
  }

  /**
   * Mock API validation for email
   * Simulates server-side validation with network delay
   */
  async validateEmailAsync(email: string): Promise<ValidationResponse> {
    // First do client-side validation
    const clientValidation = this.validateEmail(email);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    // Simulate API call delay
    await new Promise((resolve) => setTimeout(resolve, 600));

    // Mock: Check if email is already registered
    const registeredEmails = ["test@example.com", "admin@test.com"];
    if (registeredEmails.includes(email.toLowerCase())) {
      return {
        valid: false,
        error: "This email address is already registered",
        verified: true,
      };
    }

    // Mock: Check for disposable email domains
    const disposableDomains = [
      "tempmail.com",
      "throwaway.email",
      "10minutemail.com",
    ];
    const domain = email.split("@")[1]?.toLowerCase();
    if (domain && disposableDomains.includes(domain)) {
      return {
        valid: false,
        error:
          "Disposable email addresses are not allowed. Please use a permanent email address",
        verified: true,
      };
    }

    // Valid email
    return {
      valid: true,
      verified: true,
    };
  }

  /**
   * Reset onboarding (for testing purposes)
   */
  resetOnboarding(): void {
    localStorage.removeItem(this.ONBOARDING_COMPLETE_KEY);
    localStorage.removeItem(this.ONBOARDING_DATA_KEY);
  }
}

// Export singleton instance
export const onboardingService = new OnboardingService();
export default onboardingService;
