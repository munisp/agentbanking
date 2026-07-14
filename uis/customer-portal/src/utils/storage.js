/**
 * Local Storage Helper for Onboarding Data
 */

const ONBOARDING_KEY = "onboarding_data";
const ONBOARDING_ACCOUNT_TYPE = "onboarding_account_type";
const ONBOARDING_BVN = "onboarding_bvn";

export const storage = {
  /**
   * Save onboarding data to localStorage
   */
  saveOnboardingData(data) {
    try {
      localStorage.setItem(ONBOARDING_KEY, JSON.stringify(data));
      return true;
    } catch (error) {
      console.error("Error saving onboarding data:", error);
      return false;
    }
  },

  /**
   * Get onboarding data from localStorage
   */
  getOnboardingData() {
    try {
      const data = localStorage.getItem(ONBOARDING_KEY);
      return data ? JSON.parse(data) : null;
    } catch (error) {
      console.error("Error getting onboarding data:", error);
      return null;
    }
  },

  /**
   * Clear onboarding data
   */
  clearOnboardingData() {
    try {
      localStorage.removeItem(ONBOARDING_KEY);
      localStorage.removeItem(ONBOARDING_ACCOUNT_TYPE);
      localStorage.removeItem(ONBOARDING_BVN);
      return true;
    } catch (error) {
      console.error("Error clearing onboarding data:", error);
      return false;
    }
  },

  /**
   * Save account type
   */
  saveAccountType(accountType) {
    try {
      localStorage.setItem(ONBOARDING_ACCOUNT_TYPE, accountType);
      return true;
    } catch (error) {
      console.error("Error saving account type:", error);
      return false;
    }
  },

  /**
   * Get account type
   */
  getAccountType() {
    try {
      return localStorage.getItem(ONBOARDING_ACCOUNT_TYPE);
    } catch (error) {
      console.error("Error getting account type:", error);
      return null;
    }
  },

  /**
   * Save BVN
   */
  saveBVN(bvn) {
    try {
      if (bvn) {
        localStorage.setItem(ONBOARDING_BVN, bvn);
      } else {
        localStorage.removeItem(ONBOARDING_BVN);
      }
      return true;
    } catch (error) {
      console.error("Error saving BVN:", error);
      return false;
    }
  },

  /**
   * Get BVN
   */
  getBVN() {
    try {
      return localStorage.getItem(ONBOARDING_BVN);
    } catch (error) {
      console.error("Error getting BVN:", error);
      return null;
    }
  },
};

export default storage;
