import { NativeEventEmitter, NativeModules } from "react-native";

const { NexgoModule } = NativeModules;
const emitter = NexgoModule ? new NativeEventEmitter(NexgoModule) : null;

export const isNexgoAvailable = () => !!NexgoModule;

function requireNexgo(fnName: string): void {
  if (!NexgoModule) {
    throw new Error(
      `Nexgo hardware module is not available on this device (${fnName} called). ` +
        "Ensure the app is built with the Nexgo native module included.",
    );
  }
}

// ─── Types ───────────────────────────────────────

export interface CardInfo {
  cardNo: string; // full PAN
  maskCardNo: string; // e.g. 456789******1234
  expiredDate: string; // MMYY
  serviceCode: string;
  track1: string;
  track2: string;
  track3: string;
  isTrack1Valid: boolean;
  isTrack2Valid: boolean;
  isTrack3Valid: boolean;
  isICC: boolean;
  cardSlot: "ICC1" | "RF" | "SWIPE" | string;
  rfCardType: string;
}

export interface PrintLine {
  text: string;
  fontSize?: 16 | 20 | 24 | 32; // small | normal | large | xlarge
  align?: "LEFT" | "CENTER" | "RIGHT";
  isBold?: boolean;
}

export interface PinEntryResult {
  pinBlock: string; // Hex-encoded encrypted PIN block
  success: boolean;
}

export interface PinInputEvent {
  length: number; // Number of digits entered
}

// ─── Beeper ──────────────────────────────────────

export const beep = (ms = 200): Promise<boolean> => {
  requireNexgo("beep");
  return NexgoModule.beep(ms);
};

// ─── Printer ─────────────────────────────────────

export const initPrinter = (): Promise<boolean> => {
  requireNexgo("initPrinter");
  return NexgoModule.initPrinter();
};

export const getPrinterStatus = (): Promise<number> => {
  requireNexgo("getPrinterStatus");
  return NexgoModule.getPrinterStatus();
};

export const printReceipt = (lines: PrintLine[], feedPixels = 40): Promise<boolean> => {
  requireNexgo("printReceipt");
  return NexgoModule.printReceipt(lines, feedPixels);
};

// ─── Card Reader ──────────────────────────────────

export const searchCard = (timeoutSeconds = 60): Promise<CardInfo> => {
  requireNexgo("searchCard");
  return NexgoModule.searchCard(timeoutSeconds);
};

export const stopCardSearch = (): Promise<boolean> => {
  if (!NexgoModule) return Promise.resolve(false);
  return NexgoModule.stopCardSearch();
};

// ─── PIN Pad ──────────────────────────────────────

/**
 * Get PIN entry from the device's secure PIN pad
 * @param cardNumber - Full or masked card number (last 4 digits will be shown on device)
 * @param mKeyId - Master key ID for PIN encryption (default: 0)
 * @param timeoutSeconds - Timeout in seconds (default: 60)
 * @returns Promise with encrypted PIN block (hex string)
 */
export const getPinEntry = (
  cardNumber: string,
  mKeyId = 0,
  timeoutSeconds = 60,
): Promise<PinEntryResult> => {
  requireNexgo("getPinEntry");
  return NexgoModule.getPinEntry(cardNumber, mKeyId, timeoutSeconds);
};

export const cancelPinEntry = (): Promise<boolean> => {
  if (!NexgoModule) return Promise.resolve(false);
  return NexgoModule.cancelPinEntry();
};

// ─── Events ──────────────────────────────────────

const noopListener = { remove: () => {} };

export const onSwipeIncorrect = (cb: () => void) =>
  emitter?.addListener("onSwipeIncorrect", cb) ?? noopListener;

export const onMultipleCards = (cb: () => void) =>
  emitter?.addListener("onMultipleCards", cb) ?? noopListener;

export const onPinInput = (cb: (event: PinInputEvent) => void) =>
  emitter?.addListener("onPinInput", cb) ?? noopListener;
