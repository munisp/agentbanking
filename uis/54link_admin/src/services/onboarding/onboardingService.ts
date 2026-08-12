/**
 * Platform-admin onboarding service for 54link platform-level admins.
 *
 * Client-side format validation only. Server-side verification of BVN, NIN,
 * phone, and email requires a backend verification endpoint that is not wired
 * for this surface, and there is no backend onboarding submission endpoint.
 * Submission therefore fails closed instead of fabricating a success response.
 */

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
   * Submit onboarding data.
   *
   * Runs client-side format validation, then fails closed: there is no
   * backend onboarding endpoint configured for this admin surface, so the
   * previous implementation's fabricated "submitted successfully" response
   * (which also marked onboarding complete without any server round-trip)
   * has been removed. Callers surface the thrown error to the operator.
   */
  async submitOnboarding(data: OnboardingData): Promise<OnboardingResponse> {
    const validationErrors: ValidationError[] = [];

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

    if (validationErrors.length > 0) {
      return {
        success: false,
        message: "Validation failed. Please correct the errors and try again",
        errors: validationErrors,
      };
    }

    throw new Error(
      "Admin onboarding submission is unavailable: no backend onboarding endpoint is configured. Your data was not submitted.",
    );
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
   * Async phone validation. Client-side format check only — no server-side
   * verification endpoint is wired, so results are reported as unverified
   * instead of simulating network delay and fabricated server verdicts.
   */
  async validatePhoneNumberAsync(phone: string): Promise<ValidationResponse> {
    const clientValidation = this.validatePhoneNumber(phone);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    return { valid: true, verified: false };
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
   * Async BVN validation. Client-side format check only — no server-side
   * verification endpoint is wired, so results are reported as unverified
   * instead of fabricating checksum/registration verdicts.
   */
  async validateBVNAsync(bvn: string): Promise<ValidationResponse> {
    const clientValidation = this.validateBVN(bvn);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    return { valid: true, verified: false };
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
   * Async NIN validation. Client-side format check only — no server-side
   * verification endpoint is wired, so results are reported as unverified
   * instead of fabricating existence/registration verdicts.
   */
  async validateNINAsync(nin: string): Promise<ValidationResponse> {
    const clientValidation = this.validateNIN(nin);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    return { valid: true, verified: false };
  }

  /**
   * Validate email format - Client-side validation
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
   * Async email validation. Client-side format check only — no server-side
   * verification endpoint is wired, so results are reported as unverified
   * instead of fabricating registration/disposable-domain verdicts.
   */
  async validateEmailAsync(email: string): Promise<ValidationResponse> {
    const clientValidation = this.validateEmail(email);
    if (!clientValidation.valid) {
      return clientValidation;
    }

    return { valid: true, verified: false };
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
