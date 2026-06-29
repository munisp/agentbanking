/**
 * Card Reader Service - NextGo N80 Integration
 *
 * Handles card reading from NextGo N80 POS hardware using native SDK:
 * - NFC/Contactless reading (ISO 14443 A/B)
 * - Chip card (EMV) reading
 * - Magnetic stripe reading
 * - Card data extraction and validation
 *
 * NextGo N80 SDK Integration:
 * - Uses React Native bridge to NextGo native modules
 * - Supports EMV Level 1 & 2 transactions
 * - PCI PTS 5.x certified secure card processing
 */

import { NativeEventEmitter, NativeModules, Platform } from "react-native";

// Import NextGo N80 Native Module (only available in dev client/standalone builds)
const { NextGoCardReader, NextGoPrinter } = NativeModules;

// Create event emitter for card reader events
const cardReaderEventEmitter = NextGoCardReader
  ? new NativeEventEmitter(NextGoCardReader)
  : null;

// Check if running in Expo Go (native modules not available)
const isExpoGo = !NextGoCardReader && Platform.OS === "android";
const isSimulationMode = isExpoGo || __DEV__;

if (isExpoGo) {
  console.log("[CardReader] Running in Expo Go - using simulation mode");
  console.log(
    "[CardReader] For real hardware: build a custom dev client or standalone app",
  );
}

/**
 * Card reading modes
 */
export const CardReadingMode = {
  NFC: "nfc", // Contactless/tap
  CHIP: "chip", // EMV chip insert
  SWIPE: "swipe", // Magnetic stripe
  MANUAL: "manual", // Manual entry (fallback)
};

/**
 * Card reading states
 */
export const CardReadingState = {
  IDLE: "idle",
  WAITING: "waiting",
  READING: "reading",
  SUCCESS: "success",
  ERROR: "error",
  CANCELLED: "cancelled",
};

/**
 * Initialize NextGo N80 Card Reader
 * Call this when the app starts or when card reading screen is mounted
 */
export async function initializeCardReader() {
  try {
    // If running in Expo Go or dev mode without native module, use simulation
    if (!NextGoCardReader || isSimulationMode) {
      console.log("[CardReader] Initializing in SIMULATION mode");
      console.log("[CardReader] Device: NextGo N80 (Simulated)");
      console.log("[CardReader] NFC: Enabled (Simulated)");
      console.log("[CardReader] Chip/EMV: Enabled (Simulated)");
      console.log("[CardReader] Magnetic Stripe: Enabled (Simulated)");

      if (isExpoGo) {
        console.log("[CardReader] ⚠️  Running in Expo Go");
        console.log(
          "[CardReader] 💡 For real hardware, build a custom dev client:",
        );
        console.log(
          "[CardReader]    npx expo run:android (on NextGo N80 device)",
        );
      }

      return {
        success: true,
        device: "NextGo N80",
        nfcSupported: true,
        chipSupported: true,
        swipeSupported: true,
        printerAvailable: true,
        fingerprintAvailable: true,
        simulationMode: true,
      };
    }

    console.log("[CardReader] Initializing NextGo N80 hardware...");

    // Initialize the card reader hardware
    const result = await NextGoCardReader.initialize();

    if (!result.success) {
      throw new Error(result.error || "Failed to initialize card reader");
    }

    console.log("[CardReader] Device: NextGo N80 Android POS Terminal");
    console.log(
      "[CardReader] NFC:",
      result.nfcSupported ? "Enabled" : "Disabled",
    );
    console.log(
      "[CardReader] Chip/EMV:",
      result.chipSupported ? "Enabled" : "Disabled",
    );
    console.log(
      "[CardReader] Magnetic Stripe:",
      result.magneticSupported ? "Enabled" : "Disabled",
    );

    return {
      success: true,
      device: "NextGo N80",
      nfcSupported: result.nfcSupported,
      chipSupported: result.chipSupported,
      swipeSupported: result.magneticSupported,
      printerAvailable: result.printerAvailable,
      fingerprintAvailable: result.fingerprintAvailable,
      simulationMode: false,
    };
  } catch (error) {
    console.error("[CardReader] Initialization error:", error);
    return {
      success: false,
      error: error.message,
    };
  }
}

/**
 * Start listening for card tap/insert using NextGo N80 hardware
 * @param {Function} onCardDetected - Callback when card is detected
 * @param {Function} onError - Callback for errors
 * @param {string} mode - Reading mode (nfc, chip, swipe)
 * @param {number} timeout - Timeout in seconds (default: 60)
 */
export async function startCardReading(
  onCardDetected,
  onError,
  mode = CardReadingMode.NFC,
  timeout = 60,
) {
  console.log(`[CardReader] Starting ${mode} card reading...`);

  try {
    // Use simulation if native module not available
    if (!NextGoCardReader || isSimulationMode) {
      console.log("[CardReader] Using simulation mode");
      return {
        success: true,
        mode,
        message: getModeMessage(mode),
        simulationMode: true,
      };
    }

    // Setup event listeners for card detection
    const cardDetectedSubscription = cardReaderEventEmitter?.addListener(
      "onCardDetected",
      (cardData) => {
        console.log("[CardReader] Card detected:", cardData);
        if (onCardDetected) {
          onCardDetected(parseCardData(cardData));
        }
      },
    );

    const errorSubscription = cardReaderEventEmitter?.addListener(
      "onCardReadError",
      (error) => {
        console.error("[CardReader] Card read error:", error);
        if (onError) {
          onError(new Error(error.message));
        }
      },
    );

    // Request card reading based on mode
    const readConfig = {
      mode,
      timeout,
      enableBeep: true,
      enableVibration: true,
    };

    const result = await NextGoCardReader.startReading(readConfig);

    if (!result.success) {
      throw new Error(result.error || "Failed to start card reading");
    }

    return {
      success: true,
      mode,
      message: getModeMessage(mode),
      subscriptions: { cardDetectedSubscription, errorSubscription },
    };
  } catch (error) {
    console.error("[CardReader] Reading error:", error);
    if (onError) {
      onError(error);
    }
    return {
      success: false,
      error: error.message,
    };
  }
}

/**
 * Get user message for reading mode
 */
function getModeMessage(mode) {
  switch (mode) {
    case CardReadingMode.NFC:
      return "Tap your card on the NextGo N80 reader";
    case CardReadingMode.CHIP:
      return "Insert your card into the chip reader";
    case CardReadingMode.SWIPE:
      return "Swipe your card through the reader";
    default:
      return "Please present your card";
  }
}

/**
 * Stop card reading on NextGo N80
 */
export async function stopCardReading() {
  try {
    if (!NextGoCardReader || isSimulationMode) {
      console.log("[CardReader] Stopped card reading (simulation)");
      return { success: true };
    }

    await NextGoCardReader.cancelReading();

    console.log("[CardReader] Stopped card reading");
    return { success: true };
  } catch (error) {
    console.error("[CardReader] Error stopping reader:", error);
    return { success: false, error: error.message };
  }
}

/**
 * Parse raw card data from NextGo SDK into a standardized format
 * @param {Object} rawCardData
 */
function parseCardData(rawCardData) {
  try {
    // NextGo SDK returns standardized EMV card data
    const cardNumber = rawCardData.pan || rawCardData.cardNumber || "";
    const cardLast4 = cardNumber.slice(-4);

    return {
      cardId: rawCardData.cardId || `CARD-${Date.now()}`,
      cardNumber: maskCardNumber(cardNumber),
      cardLast4,
      cardholderName:
        rawCardData.cardholderName || rawCardData.holderName || "CARDHOLDER",
      expiryDate: rawCardData.expiryDate || rawCardData.expiry || "",
      cardType: rawCardData.cardType || detectCardType(cardNumber),
      bank: rawCardData.issuerBank || rawCardData.bank || "Unknown Bank",
      accountNumber: rawCardData.accountNumber || "",
      track2Data: rawCardData.track2 || "",
      emvData: rawCardData.emvTags || {},
      readMethod: rawCardData.readMethod || "unknown",
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error("[CardReader] Error parsing card data:", error);
    throw error;
  }
}

/**
 * Mask card number for security (show only last 4 digits)
 */
function maskCardNumber(cardNumber) {
  if (!cardNumber || cardNumber.length < 4) return "****";
  const last4 = cardNumber.slice(-4);
  const masked = "*".repeat(cardNumber.length - 4) + last4;
  return masked;
}

/**
 * Detect card type from card number
 * @param {string} cardNumber
 */
function detectCardType(cardNumber) {
  if (!cardNumber) return "UNKNOWN";

  const number = cardNumber.replace(/\s/g, "");

  // Visa
  if (/^4/.test(number)) return "VISA";

  // Mastercard
  if (/^5[1-5]/.test(number) || /^2[2-7]/.test(number)) return "MASTERCARD";

  // Verve (Nigerian)
  if (/^506[01]/.test(number) || /^650[0-9]/.test(number)) return "VERVE";

  // American Express
  if (/^3[47]/.test(number)) return "AMEX";

  return "UNKNOWN";
}

/**
 * Read card using NextGo N80 hardware
 * This is a promise-based wrapper for easier integration
 *
 * @param {string} mode - Reading mode (nfc, chip, swipe)
 * @param {number} timeout - Timeout in seconds
 * @returns {Promise<Object>} Card data
 */
export async function readCard(mode = CardReadingMode.NFC, timeout = 60) {
  // If in simulation mode (Expo Go), use simulated reading
  if (!NextGoCardReader || isSimulationMode) {
    return simulateCardRead(mode, timeout);
  }

  return new Promise((resolve, reject) => {
    let timeoutHandle;
    let subscriptions = null;

    const cleanup = () => {
      if (timeoutHandle) clearTimeout(timeoutHandle);
      if (subscriptions) {
        subscriptions.cardDetectedSubscription?.remove();
        subscriptions.errorSubscription?.remove();
      }
    };

    // Setup timeout
    timeoutHandle = setTimeout(() => {
      cleanup();
      stopCardReading();
      reject(new Error("Card reading timeout"));
    }, timeout * 1000);

    // Start reading
    startCardReading(
      // onCardDetected
      (cardData) => {
        cleanup();
        resolve({
          success: true,
          mode,
          cardData: {
            ...cardData,
            readMethod: mode,
            timestamp: new Date().toISOString(),
          },
        });
      },
      // onError
      (error) => {
        cleanup();
        reject(error);
      },
      mode,
      timeout,
    )
      .then((result) => {
        if (result.success) {
          subscriptions = result.subscriptions;
        } else {
          cleanup();
          reject(new Error(result.error));
        }
      })
      .catch((error) => {
        cleanup();
        reject(error);
      });
  });
}

/**
 * Simulate card reading for development/testing (Expo Go)
 * @param {string} mode - Reading mode
 * @param {number} timeout - Timeout in seconds
 */
async function simulateCardRead(mode = CardReadingMode.NFC, timeout = 60) {
  console.log(`[CardReader] Simulating ${mode} card read...`);

  // Simulate reading delay (realistic timing)
  await new Promise((resolve) =>
    setTimeout(resolve, mode === CardReadingMode.NFC ? 800 : 1500),
  );

  // Generate realistic test card data
  const testCards = [
    {
      cardId: "CARD-" + Math.random().toString(36).substr(2, 9).toUpperCase(),
      cardNumber: "5060990000000001", // Verve test card
      cardLast4: "0001",
      cardholderName: "TEST CUSTOMER",
      expiryDate: "12/28",
      cardType: "VERVE",
      bank: "First Bank",
      accountNumber: "1234567890",
    },
    {
      cardId: "CARD-" + Math.random().toString(36).substr(2, 9).toUpperCase(),
      cardNumber: "4111111111111111", // Visa test card
      cardLast4: "1111",
      cardholderName: "JOHN DOE",
      expiryDate: "06/27",
      cardType: "VISA",
      bank: "GTBank",
      accountNumber: "0987654321",
    },
    {
      cardId: "CARD-" + Math.random().toString(36).substr(2, 9).toUpperCase(),
      cardNumber: "5399838383838381", // Mastercard test card
      cardLast4: "8381",
      cardholderName: "JANE SMITH",
      expiryDate: "09/26",
      cardType: "MASTERCARD",
      bank: "Zenith Bank",
      accountNumber: "5555666677",
    },
  ];

  // Randomly select a test card
  const cardData = testCards[Math.floor(Math.random() * testCards.length)];

  return {
    success: true,
    mode,
    cardData: {
      ...cardData,
      readMethod: mode,
      timestamp: new Date().toISOString(),
      simulated: true,
    },
  };
}

/**
 * Validate card data
 * @param {Object} cardData
 */
export function validateCardData(cardData) {
  const errors = [];

  if (!cardData.cardNumber || cardData.cardNumber.length < 13) {
    errors.push("Invalid card number");
  }

  if (!cardData.cardholderName) {
    errors.push("Cardholder name required");
  }

  if (!cardData.expiryDate) {
    errors.push("Expiry date required");
  } else {
    // Check if card is expired
    const [month, year] = cardData.expiryDate.split("/");
    const expiry = new Date(2000 + parseInt(year), parseInt(month) - 1);
    const now = new Date();

    if (expiry < now) {
      errors.push("Card has expired");
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

/**
 * Get NextGo N80 card reader status
 * Check if card reader hardware is available and working
 */
export async function getCardReaderStatus() {
  try {
    if (!NextGoCardReader || isSimulationMode) {
      // Return simulated status for Expo Go
      return {
        available: true,
        device: "NextGo N80",
        manufacturer: "NextGo",
        model: "N80",
        serialNumber: "SIM-" + Date.now(),
        nfcEnabled: true,
        chipReaderEnabled: true,
        swipeReaderEnabled: true,
        printerEnabled: true,
        fingerprintEnabled: true,
        batteryLevel: 85,
        firmwareVersion: "2.4.1",
        androidVersion: "9.0",
        networkType: "4G",
        lastHealthCheck: new Date().toISOString(),
        simulationMode: true,
      };
    }

    const status = await NextGoCardReader.getDeviceStatus();

    return {
      available: status.available,
      device: "NextGo N80",
      manufacturer: "NextGo",
      model: "N80",
      serialNumber: status.serialNumber || "Unknown",
      nfcEnabled: status.nfcEnabled,
      chipReaderEnabled: status.chipEnabled,
      swipeReaderEnabled: status.magneticEnabled,
      printerEnabled: status.printerEnabled,
      fingerprintEnabled: status.fingerprintEnabled,
      batteryLevel: status.batteryLevel,
      firmwareVersion: status.firmwareVersion,
      androidVersion: status.androidVersion,
      networkType: status.networkType,
      lastHealthCheck: new Date().toISOString(),
      simulationMode: false,
    };
  } catch (error) {
    console.error("[CardReader] Status check error:", error);
    return {
      available: false,
      error: error.message,
    };
  }
}

/**
 * Cleanup NextGo N80 card reader resources
 * Call this when unmounting card reading screens
 */
export async function cleanupCardReader() {
  try {
    await stopCardReading();

    if (NextGoCardReader && !isSimulationMode) {
      await NextGoCardReader.cleanup();
    }

    console.log("[CardReader] Cleanup complete");
    return { success: true };
  } catch (error) {
    console.error("[CardReader] Cleanup error:", error);
    return { success: false, error: error.message };
  }
}
