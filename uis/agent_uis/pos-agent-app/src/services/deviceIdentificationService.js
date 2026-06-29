import * as SecureStore from "expo-secure-store";
import { MdmAdapterFactory } from "./mdmAdapter";
import { mdmDeviceApi } from "./apiService";

// ─── Test Mode ───────────────────────────────────────────────────────────────
// Set EXPO_PUBLIC_TEST_MODE=true in .env.local for development only.
// Must be false (or unset) in all production builds.
const TEST_MODE = process.env.EXPO_PUBLIC_TEST_MODE === "true";

const TEST_DEVICE = {
  terminal_id: process.env.EXPO_PUBLIC_TEST_TERMINAL_ID || "POS-DEV-PLACEHOLDER",
  model_id: process.env.EXPO_PUBLIC_TEST_MODEL_ID || "unknown",
  serial_number: process.env.EXPO_PUBLIC_TEST_SERIAL || "PLACEHOLDER",
  agent_id: process.env.EXPO_PUBLIC_TEST_AGENT_ID || "",
  apk_version: "0.0.0-dev",
  firmware_version: "0.0.0-dev",
  state: "development",
};
// ─────────────────────────────────────────────────────────────────────────────

const SERIAL_SDK_METHODS = [
  "getSerialNumber", "getSerial", "getSN", "getDeviceSerial",
  "getTerminalSerial", "getDeviceSN", "readSerialNumber",
];

async function readSerialFromHardware(adapter) {
  const mod = adapter._module;
  if (!mod) return null;
  for (const method of SERIAL_SDK_METHODS) {
    try {
      if (typeof mod[method] === "function") {
        const sn = await mod[method]();
        if (sn && typeof sn === "string" && sn.trim().length > 0) return sn.trim();
      }
    } catch {}
  }
  return null;
}

class DeviceIdentificationService {
  /**
   * Called once at app startup (after auth). Reads the physical serial number
   * from the hardware SDK, looks it up in MDM, then writes terminal context
   * into SecureStore so all other services can read it.
   *
   * Safe to call multiple times — skips if already identified this session.
   */
  async identify() {
    try {
      if (!TEST_MODE) {
        // Use a cached result within the same app session
        const cached = await SecureStore.getItemAsync("terminalId");
        if (cached) return;
      }

      let device;

      if (TEST_MODE) {
        console.log("[DeviceID] TEST MODE — using mock device identity");
        device = TEST_DEVICE;
      } else {
        const candidates = ["sunmi_p2", "nexgo_aosp_full", "pax_a920_max", "newland_n910"];
        let serialNumber = null;

        for (const modelId of candidates) {
          const adapter = MdmAdapterFactory.create(modelId);
          serialNumber = await readSerialFromHardware(adapter);
          if (serialNumber) break;
        }

        if (!serialNumber) {
          console.warn("[DeviceID] Could not read serial from hardware SDK");
          return;
        }

        device = await mdmDeviceApi.getDeviceBySerial(serialNumber);
        if (!device || !device.terminal_id) {
          console.warn("[DeviceID] Serial not found in MDM:", serialNumber);
          return;
        }
      }

      // Persist everything services need
      await Promise.all([
        SecureStore.setItemAsync("terminalId", device.terminal_id),
        SecureStore.setItemAsync("modelId", device.model_id || ""),
        SecureStore.setItemAsync("serialNumber", device.serial_number || ""),
        SecureStore.setItemAsync("apkVersion", device.apk_version || ""),
        SecureStore.setItemAsync("firmwareVersion", device.firmware_version || ""),
        SecureStore.setItemAsync("deviceState", device.state || ""),
        SecureStore.setItemAsync("agentId", device.agent_id || ""),
      ]);

      console.log(`[DeviceID] Identified: ${device.terminal_id} (${device.model_id}, SN: ${device.serial_number}, APK: ${device.apk_version})`);
    } catch (err) {
      // Non-fatal — device still works, just won't have MDM context
      console.warn("[DeviceID] Identification failed:", err?.message || err);
    }
  }

  /** Returns the stored device identity without triggering a new lookup. */
  async getStoredIdentity() {
    const [terminalId, modelId, serialNumber, apkVersion, firmwareVersion, deviceState] =
      await Promise.all([
        SecureStore.getItemAsync("terminalId"),
        SecureStore.getItemAsync("modelId"),
        SecureStore.getItemAsync("serialNumber"),
        SecureStore.getItemAsync("apkVersion"),
        SecureStore.getItemAsync("firmwareVersion"),
        SecureStore.getItemAsync("deviceState"),
      ]);
    return { terminalId, modelId, serialNumber, apkVersion, firmwareVersion, deviceState };
  }
}

export default new DeviceIdentificationService();
