/**
 * Onboarding Data Model
 * Holds all onboarding data across steps and provides validation helpers
 */

export class OnboardingData {
  constructor(data = {}) {
    // Account type
    this.accountType = data.accountType || "";

    // Personal information (from registration)
    this.firstName = data.firstName || "";
    this.lastName = data.lastName || "";
    this.email = data.email || "";
    this.phone = data.phone || "";
    this.password = data.password || "";

    // BVN
    this.bvn = data.bvn || "";
    this.bvnVerified = data.bvnVerified || false;

    // Address
    this.address = data.address || "";
    this.city = data.city || "";
    this.state = data.state || "";
    this.country = data.country || "Nigeria";
    this.postalCode = data.postalCode || "";

    // Documents
    this.documents = data.documents || {};

    // Metadata
    this.currentStep = data.currentStep || 1;
    this.completedSteps = data.completedSteps || [];
  }

  /**
   * Calculate overall completion percentage
   */
  getCompletionPercentage() {
    const totalSteps = 5; // Start, Account Type, BVN, Address, Documents
    return Math.round((this.currentStep / totalSteps) * 100);
  }

  /**
   * Validate account type step
   */
  validateAccountType() {
    return this.accountType !== "";
  }

  /**
   * Validate BVN step (BVN is optional but if provided must be 11 digits)
   */
  validateBVN() {
    if (!this.bvn) return true; // Optional
    return this.bvn.length === 11 && /^\d+$/.test(this.bvn);
  }

  /**
   * Validate address step
   */
  validateAddress() {
    return (
      this.address.trim() !== "" &&
      this.city.trim() !== "" &&
      this.state.trim() !== "" &&
      this.country.trim() !== ""
    );
  }

  /**
   * Validate documents step (at least one document required)
   */
  validateDocuments() {
    return Object.keys(this.documents).length > 0;
  }

  /**
   * Check if all steps are complete
   */
  isComplete() {
    return (
      this.validateAccountType() &&
      this.validateBVN() &&
      this.validateAddress() &&
      this.validateDocuments()
    );
  }

  /**
   * Convert to plain object for storage/API
   */
  toJSON() {
    return {
      accountType: this.accountType,
      firstName: this.firstName,
      lastName: this.lastName,
      email: this.email,
      phone: this.phone,
      password: this.password,
      bvn: this.bvn,
      bvnVerified: this.bvnVerified,
      address: this.address,
      city: this.city,
      state: this.state,
      country: this.country,
      postalCode: this.postalCode,
      documents: this.documents,
      currentStep: this.currentStep,
      completedSteps: this.completedSteps,
    };
  }

  /**
   * Create from stored data
   */
  static fromJSON(json) {
    return new OnboardingData(json);
  }
}

export default OnboardingData;
