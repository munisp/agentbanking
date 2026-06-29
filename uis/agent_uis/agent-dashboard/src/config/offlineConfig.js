/**
 * Offline Transactions Configuration
 * Customize offline behavior to match your requirements
 */

export const OFFLINE_CONFIG = {
  // Database Configuration
  DATABASE: {
    // IndexedDB database name
    NAME: "54AgentBank",
    // Database version (increment to trigger migration)
    VERSION: 1,
  },

  // Storage Configuration
  STORAGE: {
    // Maximum number of transactions to keep in storage
    MAX_TRANSACTIONS: 1000,
    // Clear transactions older than this (in days)
    CLEAR_AFTER_DAYS: 30,
    // Storage quota warning threshold (in KB)
    WARNING_THRESHOLD_KB: 50000,
  },

  // Sync Configuration
  SYNC: {
    // Maximum number of retry attempts
    MAX_RETRIES: 3,
    // Base delay for exponential backoff (in ms)
    BASE_DELAY_MS: 5000,
    // Batch size for batch sync operations
    BATCH_SIZE: 5,
    // Delay between batches (in ms)
    BATCH_DELAY_MS: 1000,
    // Request timeout (in ms)
    TIMEOUT_MS: 30000,
    // Auto-sync on online (set false to require manual sync)
    AUTO_SYNC_ON_ONLINE: true,
    // Delay before auto-sync after coming online (in ms)
    AUTO_SYNC_DELAY_MS: 2000,
  },

  // Network Configuration
  NETWORK: {
    // Minimum RTT to consider as unstable connection (in ms)
    UNSTABLE_RTT_THRESHOLD_MS: 400,
    // Connection types considered unstable
    UNSTABLE_CONNECTION_TYPES: ["2g", "3g", "slow-2g"],
    // Check network status interval (in ms)
    STATUS_CHECK_INTERVAL_MS: 5000,
  },

  // Transaction Configuration
  TRANSACTION: {
    // Transaction expiry time (in days)
    EXPIRY_DAYS: 7,
    // Transactions to automatically sync (empty = sync all)
    AUTO_SYNC_TYPES: [
      // uncomment to auto-sync only certain types:
      // "cash_in",
      // "cash_out",
      // "transfer"
    ],
    // Transaction types that require manual verification before sync
    REQUIRE_VERIFICATION: [
      // "remittance_send",
      // "bill_payment"
    ],
  },

  // UI Configuration
  UI: {
    // Show transaction queue by default
    SHOW_QUEUE_BY_DEFAULT: false,
    // Show transaction details in queue
    SHOW_TRANSACTION_DETAILS: true,
    // Enable animated status indicators
    ANIMATE_STATUS: true,
    // Show pending count in header
    SHOW_PENDING_COUNT: true,
    // Toast notification position
    TOAST_POSITION: "bottom-right",
  },

  // Feature Flags
  FEATURES: {
    // Enable offline transactions globally
    ENABLED: true,
    // Enable background sync (Service Worker)
    BACKGROUND_SYNC: false,
    // Enable conflict resolution for parallel edits
    CONFLICT_RESOLUTION: false,
    // Enable analytics tracking
    ANALYTICS: false,
    // Enable push notifications on sync completion
    PUSH_NOTIFICATIONS: false,
  },

  // Logging Configuration
  LOGGING: {
    // Enable debug logging
    DEBUG: process.env.NODE_ENV === "development",
    // Log level: 'error', 'warn', 'info', 'debug'
    LEVEL: "info",
    // Send logs to external service
    REMOTE_LOGGING: false,
    // Remote logging endpoint
    REMOTE_LOGGING_URL: null,
  },
};

/**
 * Get configuration value with fallback to default
 * Usage: getConfig('SYNC.MAX_RETRIES')
 */
export function getConfig(path) {
  const keys = path.split(".");
  let value = OFFLINE_CONFIG;

  for (const key of keys) {
    if (value && typeof value === "object" && key in value) {
      value = value[key];
    } else {
      console.warn(`Configuration path not found: ${path}`);
      return undefined;
    }
  }

  return value;
}

/**
 * Override configuration value
 * Usage: setConfig('SYNC.MAX_RETRIES', 5)
 */
export function setConfig(path, value) {
  const keys = path.split(".");
  const lastKey = keys.pop();
  let obj = OFFLINE_CONFIG;

  for (const key of keys) {
    if (!(key in obj)) {
      obj[key] = {};
    }
    obj = obj[key];
  }

  obj[lastKey] = value;
  console.log(`Configuration updated: ${path} = ${value}`);
}

/**
 * Get all configuration
 */
export function getAllConfig() {
  return { ...OFFLINE_CONFIG };
}

/**
 * Reset configuration to defaults
 */
export function resetConfig() {
  // This would need to be implemented by re-importing
  location.reload();
}

/**
 * Validate configuration
 */
export function validateConfig() {
  const errors = [];

  // Validate SYNC configuration
  if (OFFLINE_CONFIG.SYNC.MAX_RETRIES < 1) {
    errors.push("SYNC.MAX_RETRIES must be at least 1");
  }

  if (OFFLINE_CONFIG.SYNC.BASE_DELAY_MS < 100) {
    errors.push("SYNC.BASE_DELAY_MS should be at least 100ms");
  }

  if (OFFLINE_CONFIG.SYNC.BATCH_SIZE < 1) {
    errors.push("SYNC.BATCH_SIZE must be at least 1");
  }

  // Validate STORAGE configuration
  if (OFFLINE_CONFIG.STORAGE.MAX_TRANSACTIONS < 10) {
    errors.push("STORAGE.MAX_TRANSACTIONS should be at least 10");
  }

  // Validate NETWORK configuration
  if (OFFLINE_CONFIG.NETWORK.UNSTABLE_RTT_THRESHOLD_MS < 100) {
    errors.push("NETWORK.UNSTABLE_RTT_THRESHOLD_MS should be at least 100ms");
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Pretty print configuration
 */
export function printConfig() {
  console.group("📋 Offline Transactions Configuration");
  Object.entries(OFFLINE_CONFIG).forEach(([section, config]) => {
    console.group(section);
    Object.entries(config).forEach(([key, value]) => {
      console.log(`  ${key}: ${JSON.stringify(value)}`);
    });
    console.groupEnd();
  });
  console.groupEnd();
}

export default OFFLINE_CONFIG;
