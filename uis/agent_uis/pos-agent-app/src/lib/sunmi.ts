import { NativeEventEmitter, NativeModules } from "react-native";

const { SunmiModule } = NativeModules;
const emitter = SunmiModule ? new NativeEventEmitter(SunmiModule) : null;

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CardInfo {
  cardNo: string;       // full PAN
  maskCardNo: string;   // e.g. 456789******1234
  expiredDate: string;  // MMYY
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
  fontSize?: 16 | 20 | 24 | 32;
  align?: "LEFT" | "CENTER" | "RIGHT";
  isBold?: boolean;
}

export interface PinEntryResult {
  pinBlock: string;
  success: boolean;
}

export interface PinInputEvent {
  length: number;
}

// ─── Availability ─────────────────────────────────────────────────────────────

export const isSunmiAvailable = () => !!SunmiModule;

function requireSunmi(fnName: string): void {
  if (!SunmiModule) {
    throw new Error(
      `Sunmi hardware module is not available on this device (${fnName} called). ` +
        "Ensure the app is built with the SunmiModule native module included.",
    );
  }else {
    console.log(`[Sunmi] ${fnName} called and SunmiModule is available.`);
  }
}

// ─── Beeper ───────────────────────────────────────────────────────────────────

export const beep = (ms = 200): Promise<boolean> => {
  requireSunmi("beep");
  return SunmiModule.beep(ms);
};

// ─── Printer ──────────────────────────────────────────────────────────────────

export const initPrinter = (): Promise<boolean> => {
  requireSunmi("initPrinter");
  return SunmiModule.initPrinter();
};

export const getPrinterStatus = (): Promise<number> => {
  requireSunmi("getPrinterStatus");
  return SunmiModule.getPrinterStatus();
};

export const printReceipt = (lines: PrintLine[], feedPixels = 40): Promise<boolean> => {
  requireSunmi("printReceipt");
  return SunmiModule.printReceipt(lines, feedPixels);
};

// ─── Card Reader ──────────────────────────────────────────────────────────────

export const searchCard = async (timeoutSeconds = 60): Promise<CardInfo> => {
  console.log(`[Sunmi] searchCard called with timeout: ${timeoutSeconds} seconds`);

  requireSunmi("searchCard");
  return SunmiModule.searchCard(timeoutSeconds);
};

export const stopCardSearch = (): Promise<boolean> => {
  if (!SunmiModule) return Promise.resolve(false);
  return SunmiModule.stopCardSearch();
};

// ─── PIN Pad ──────────────────────────────────────────────────────────────────

export const getPinEntry = (
  cardNumber: string,
  mKeyId = 0,
  timeoutSeconds = 60,
): Promise<PinEntryResult> => {
  requireSunmi("getPinEntry");
  return SunmiModule.getPinEntry(cardNumber, mKeyId, timeoutSeconds);
};

export const cancelPinEntry = (): Promise<boolean> => {
  if (!SunmiModule) return Promise.resolve(false);
  return SunmiModule.cancelPinEntry();
};

// ─── Events ───────────────────────────────────────────────────────────────────

const noopListener = { remove: () => {} };

export const onSwipeIncorrect = (cb: () => void) =>
  emitter?.addListener("onSwipeIncorrect", cb) ?? noopListener;

export const onMultipleCards = (cb: () => void) =>
  emitter?.addListener("onMultipleCards", cb) ?? noopListener;

export const onPinInput = (cb: (event: PinInputEvent) => void) =>
  emitter?.addListener("onPinInput", cb) ?? noopListener;
