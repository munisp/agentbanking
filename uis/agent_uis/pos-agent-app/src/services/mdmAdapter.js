/**
 * MDM Adapter — per-device-type command execution layer.
 *
 * Usage:
 *   const adapter = MdmAdapterFactory.create(deviceModel);
 *   await adapter.executeCommand({ command_type: "reboot", params: {} });
 *
 * To add a new device type:
 *   1. Create a class extending MdmAdapterBase
 *   2. Override only the methods your SDK supports natively
 *   3. Register the model key(s) in MdmAdapterFactory.create()
 */

import { NativeModules } from "react-native";

const { NexgoModule, PaxModule, NewlandModule, SunmiModule } = NativeModules;

// ─────────────────────────────────────────────────────────────────────────────
// Base adapter — defines the contract and safe fallbacks for all device types
// ─────────────────────────────────────────────────────────────────────────────

class MdmAdapterBase {
  constructor(deviceModel) {
    this.deviceModel = deviceModel;
    this.localLockState = false;
    this._customHandlers = {};
  }

  /** Register a custom handler for a command type at runtime */
  registerHandler(commandType, handler) {
    if (commandType && typeof handler === "function") {
      this._customHandlers[commandType] = handler;
    }
  }

  /** Dispatch a command to the right method */
  async executeCommand(command) {
    const { command_type: type, params = {} } = command ?? {};
    if (!type) throw new Error("Missing command_type");

    if (this._customHandlers[type]) {
      return this._customHandlers[type](params, command);
    }

    switch (type) {
      case "lock_terminal":           return this.lockTerminal(params);
      case "unlock_terminal":         return this.unlockTerminal(params);
      case "reboot":                  return this.rebootTerminal(params);
      case "factory_reset":           return this.factoryReset(params);
      case "get_diagnostics":         return this.getDiagnostics(params);
      case "remote_wipe":             return this.remoteWipe(params);
      case "screenshot":              return this.screenshot(params);
      case "clear_cache":             return this.clearCache(params);
      case "log_upload":              return this.logUpload(params);
      case "update_apk":              return this.updateApk(params);
      case "update_firmware":         return this.updateFirmware(params);
      case "push_config":             return this.pushConfig(params);
      case "enable_geofence":         return this.enableGeofence(params);
      case "disable_geofence":        return this.disableGeofence(params);
      case "enable_offline_mode":     return this.setOfflineMode(true, params);
      case "disable_offline_mode":    return this.setOfflineMode(false, params);
      case "enable_tamper_protection":  return this.setTamperProtection(true, params);
      case "disable_tamper_protection": return this.setTamperProtection(false, params);
      case "rotate_encryption_keys":  return this.rotateEncryptionKeys(params);
      case "push_key_injection":      return this.pushKeyInjection(params);
      default:
        throw new Error(`Unsupported MDM command for ${this.deviceModel}: ${type}`);
    }
  }

  /** What this adapter can execute natively (override in subclass) */
  getCapabilities() {
    return {
      lockTerminal: false,
      unlockTerminal: false,
      rebootTerminal: false,
      factoryReset: false,
      getDiagnostics: false,
      remoteWipe: false,
      screenshot: false,
      clearCache: false,
      updateApk: false,
      updateFirmware: false,
    };
  }

  async getPhysicalTerminalId() {
    return null;
  }

  // ── Default implementations (safe fallbacks) ────────────────────────────

  async lockTerminal(_params) {
    this.localLockState = true;
    return this._accepted("lock_terminal", "adapter_fallback");
  }

  async unlockTerminal(_params) {
    this.localLockState = false;
    return this._accepted("unlock_terminal", "adapter_fallback");
  }

  async rebootTerminal(_params) {
    return this._pending("reboot");
  }

  async factoryReset(_params) {
    return this._pending("factory_reset");
  }

  async getDiagnostics(_params) {
    return {
      action: "get_diagnostics",
      via: "adapter_fallback",
      diagnostics: {
        device_model: this.deviceModel,
        local_lock_state: this.localLockState,
        capabilities: this.getCapabilities(),
        timestamp: new Date().toISOString(),
      },
    };
  }

  async remoteWipe(_params) {
    throw new Error(`remote_wipe not supported on ${this.deviceModel}`);
  }

  async screenshot(_params) {
    return this._accepted("screenshot", "adapter_fallback");
  }

  async clearCache(_params) {
    return this._accepted("clear_cache", "adapter_fallback");
  }

  async logUpload(_params) {
    return this._accepted("log_upload", "adapter_fallback");
  }

  async updateApk(params) {
    return this._accepted("update_apk", "adapter_fallback", params);
  }

  async updateFirmware(params) {
    return this._accepted("update_firmware", "adapter_fallback", params);
  }

  async pushConfig(params) {
    return this._accepted("push_config", "adapter_fallback", params);
  }

  async enableGeofence(params) {
    return this._accepted("enable_geofence", "adapter_fallback", params);
  }

  async disableGeofence(_params) {
    return this._accepted("disable_geofence", "adapter_fallback");
  }

  async setOfflineMode(enable, _params) {
    return this._accepted(enable ? "enable_offline_mode" : "disable_offline_mode", "adapter_fallback");
  }

  async setTamperProtection(enable, _params) {
    return this._accepted(
      enable ? "enable_tamper_protection" : "disable_tamper_protection",
      "adapter_fallback",
    );
  }

  async rotateEncryptionKeys(_params) {
    return this._accepted("rotate_encryption_keys", "adapter_fallback");
  }

  async pushKeyInjection(params) {
    return this._accepted("push_key_injection", "adapter_fallback", params);
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  _accepted(action, via, params) {
    return { action, accepted: true, via, ...(params ? { params } : {}) };
  }

  _pending(action) {
    return { action, applied: false, via: "adapter_fallback", note: "No native SDK available" };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Nexgo adapter — HorizonPay K11, Topwise T11 Pro, Newland N750, etc.
// ─────────────────────────────────────────────────────────────────────────────

class NexgoAdapter extends MdmAdapterBase {
  getCapabilities() {
    return {
      lockTerminal: typeof NexgoModule?.lockTerminal === "function",
      unlockTerminal: typeof NexgoModule?.unlockTerminal === "function",
      rebootTerminal: typeof NexgoModule?.rebootTerminal === "function",
      factoryReset: false,
      getDiagnostics: typeof NexgoModule?.requestDiagnostics === "function",
      remoteWipe: typeof NexgoModule?.remoteWipe === "function",
      screenshot: false,
      clearCache: false,
      updateApk: false,
      updateFirmware: false,
    };
  }

  async getPhysicalTerminalId() {
    const candidates = [
      "getPhysicalTerminalId", "getTerminalId", "getTerminalID",
      "getPosId", "getPOSId", "getDeviceSerial", "getDeviceSn",
      "getSN", "getSerialNumber", "terminalId", "terminalID",
      "deviceSerial", "serialNumber",
    ];
    for (const name of candidates) {
      try {
        const target = NexgoModule?.[name];
        const value = typeof target === "function"
          ? await target.call(NexgoModule)
          : target;
        const normalized = typeof value === "string" ? value.trim() : null;
        if (normalized) return normalized;
      } catch {
        continue;
      }
    }
    return null;
  }

  async lockTerminal(params = {}) {
    if (typeof NexgoModule?.lockTerminal === "function") {
      await NexgoModule.lockTerminal(params?.reason ?? "mdm_remote_lock");
      this.localLockState = true;
      return { action: "lock_terminal", applied: true, via: "nexgo_sdk" };
    }
    return super.lockTerminal(params);
  }

  async unlockTerminal(params) {
    if (typeof NexgoModule?.unlockTerminal === "function") {
      await NexgoModule.unlockTerminal();
      this.localLockState = false;
      return { action: "unlock_terminal", applied: true, via: "nexgo_sdk" };
    }
    return super.unlockTerminal(params);
  }

  async rebootTerminal(params) {
    if (typeof NexgoModule?.rebootTerminal === "function") {
      await NexgoModule.rebootTerminal();
      return { action: "reboot", applied: true, via: "nexgo_sdk" };
    }
    return super.rebootTerminal(params);
  }

  async getDiagnostics(params) {
    if (typeof NexgoModule?.requestDiagnostics === "function") {
      const diagnostics = await NexgoModule.requestDiagnostics();
      return { action: "get_diagnostics", diagnostics, via: "nexgo_sdk" };
    }
    return super.getDiagnostics(params);
  }

  async remoteWipe(params) {
    if (typeof NexgoModule?.remoteWipe === "function") {
      await NexgoModule.remoteWipe();
      return { action: "remote_wipe", applied: true, via: "nexgo_sdk" };
    }
    throw new Error("remote_wipe not available on this Nexgo device");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// PAX adapter — PAX A920 MAX, PAX A8900 (PAXSTORE SDK)
// ─────────────────────────────────────────────────────────────────────────────

class PaxAdapter extends MdmAdapterBase {
  getCapabilities() {
    return {
      lockTerminal: typeof PaxModule?.lockDevice === "function",
      unlockTerminal: typeof PaxModule?.unlockDevice === "function",
      rebootTerminal: typeof PaxModule?.rebootDevice === "function",
      factoryReset: typeof PaxModule?.factoryReset === "function",
      getDiagnostics: typeof PaxModule?.getDiagnosticInfo === "function",
      remoteWipe: typeof PaxModule?.remoteWipe === "function",
      screenshot: typeof PaxModule?.captureScreen === "function",
      clearCache: typeof PaxModule?.clearAppCache === "function",
      updateApk: typeof PaxModule?.installApk === "function",
      updateFirmware: typeof PaxModule?.updateFirmware === "function",
    };
  }

  async getPhysicalTerminalId() {
    try {
      if (typeof PaxModule?.getSerialNumber === "function") {
        const sn = await PaxModule.getSerialNumber();
        return sn?.trim() || null;
      }
      if (typeof PaxModule?.getTerminalId === "function") {
        const tid = await PaxModule.getTerminalId();
        return tid?.trim() || null;
      }
    } catch {}
    return null;
  }

  async lockTerminal(params = {}) {
    if (typeof PaxModule?.lockDevice === "function") {
      await PaxModule.lockDevice(params?.reason ?? "mdm_remote_lock");
      this.localLockState = true;
      return { action: "lock_terminal", applied: true, via: "pax_sdk" };
    }
    return super.lockTerminal(params);
  }

  async unlockTerminal(params) {
    if (typeof PaxModule?.unlockDevice === "function") {
      await PaxModule.unlockDevice();
      this.localLockState = false;
      return { action: "unlock_terminal", applied: true, via: "pax_sdk" };
    }
    return super.unlockTerminal(params);
  }

  async rebootTerminal(params) {
    if (typeof PaxModule?.rebootDevice === "function") {
      await PaxModule.rebootDevice();
      return { action: "reboot", applied: true, via: "pax_sdk" };
    }
    return super.rebootTerminal(params);
  }

  async factoryReset(params) {
    if (typeof PaxModule?.factoryReset === "function") {
      await PaxModule.factoryReset();
      return { action: "factory_reset", applied: true, via: "pax_sdk" };
    }
    return super.factoryReset(params);
  }

  async getDiagnostics(params) {
    if (typeof PaxModule?.getDiagnosticInfo === "function") {
      const diagnostics = await PaxModule.getDiagnosticInfo();
      return { action: "get_diagnostics", diagnostics, via: "pax_sdk" };
    }
    return super.getDiagnostics(params);
  }

  async remoteWipe(params) {
    if (typeof PaxModule?.remoteWipe === "function") {
      await PaxModule.remoteWipe();
      return { action: "remote_wipe", applied: true, via: "pax_sdk" };
    }
    throw new Error("remote_wipe not available on this PAX device");
  }

  async screenshot(params) {
    if (typeof PaxModule?.captureScreen === "function") {
      const result = await PaxModule.captureScreen();
      return { action: "screenshot", applied: true, via: "pax_sdk", result };
    }
    return super.screenshot(params);
  }

  async clearCache(params) {
    if (typeof PaxModule?.clearAppCache === "function") {
      await PaxModule.clearAppCache();
      return { action: "clear_cache", applied: true, via: "pax_sdk" };
    }
    return super.clearCache(params);
  }

  async updateApk(params) {
    if (typeof PaxModule?.installApk === "function" && params?.apk_url) {
      await PaxModule.installApk(params.apk_url);
      return { action: "update_apk", applied: true, via: "pax_sdk" };
    }
    return super.updateApk(params);
  }

  async updateFirmware(params) {
    if (typeof PaxModule?.updateFirmware === "function" && params?.firmware_url) {
      await PaxModule.updateFirmware(params.firmware_url);
      return { action: "update_firmware", applied: true, via: "pax_sdk" };
    }
    return super.updateFirmware(params);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Newland adapter — N910, N910 Pro, ME30SU (PayDroid / mPOS)
// ─────────────────────────────────────────────────────────────────────────────

class NewlandAdapter extends MdmAdapterBase {
  getCapabilities() {
    return {
      lockTerminal: typeof NewlandModule?.lockTerminal === "function",
      unlockTerminal: typeof NewlandModule?.unlockTerminal === "function",
      rebootTerminal: typeof NewlandModule?.reboot === "function",
      factoryReset: typeof NewlandModule?.factoryReset === "function",
      getDiagnostics: typeof NewlandModule?.getSystemInfo === "function",
      remoteWipe: false,
      screenshot: false,
      clearCache: typeof NewlandModule?.clearCache === "function",
      updateApk: typeof NewlandModule?.installPackage === "function",
      updateFirmware: false,
    };
  }

  async getPhysicalTerminalId() {
    try {
      if (typeof NewlandModule?.getSerialNo === "function") {
        const sn = await NewlandModule.getSerialNo();
        return sn?.trim() || null;
      }
      if (typeof NewlandModule?.getSN === "function") {
        const sn = await NewlandModule.getSN();
        return sn?.trim() || null;
      }
    } catch {}
    return null;
  }

  async lockTerminal(params = {}) {
    if (typeof NewlandModule?.lockTerminal === "function") {
      await NewlandModule.lockTerminal(params?.reason ?? "mdm_remote_lock");
      this.localLockState = true;
      return { action: "lock_terminal", applied: true, via: "newland_sdk" };
    }
    return super.lockTerminal(params);
  }

  async unlockTerminal(params) {
    if (typeof NewlandModule?.unlockTerminal === "function") {
      await NewlandModule.unlockTerminal();
      this.localLockState = false;
      return { action: "unlock_terminal", applied: true, via: "newland_sdk" };
    }
    return super.unlockTerminal(params);
  }

  async rebootTerminal(params) {
    if (typeof NewlandModule?.reboot === "function") {
      await NewlandModule.reboot();
      return { action: "reboot", applied: true, via: "newland_sdk" };
    }
    return super.rebootTerminal(params);
  }

  async factoryReset(params) {
    if (typeof NewlandModule?.factoryReset === "function") {
      await NewlandModule.factoryReset();
      return { action: "factory_reset", applied: true, via: "newland_sdk" };
    }
    return super.factoryReset(params);
  }

  async getDiagnostics(params) {
    if (typeof NewlandModule?.getSystemInfo === "function") {
      const diagnostics = await NewlandModule.getSystemInfo();
      return { action: "get_diagnostics", diagnostics, via: "newland_sdk" };
    }
    return super.getDiagnostics(params);
  }

  async clearCache(params) {
    if (typeof NewlandModule?.clearCache === "function") {
      await NewlandModule.clearCache();
      return { action: "clear_cache", applied: true, via: "newland_sdk" };
    }
    return super.clearCache(params);
  }

  async updateApk(params) {
    if (typeof NewlandModule?.installPackage === "function" && params?.apk_url) {
      await NewlandModule.installPackage(params.apk_url);
      return { action: "update_apk", applied: true, via: "newland_sdk" };
    }
    return super.updateApk(params);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Factory — maps MDM model IDs to the right adapter
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Sunmi adapter — Sunmi System Services SDK (P-series handhelds)
// ─────────────────────────────────────────────────────────────────────────────

class SunmiAdapter extends MdmAdapterBase {
  constructor(deviceModel) {
    super(deviceModel);
    this._module = SunmiModule;
  }

  getCapabilities() {
    return {
      lockTerminal: typeof SunmiModule?.lockScreen === "function",
      unlockTerminal: typeof SunmiModule?.unlockScreen === "function",
      rebootTerminal: typeof SunmiModule?.rebootDevice === "function",
      factoryReset: typeof SunmiModule?.factoryReset === "function",
      getDiagnostics: typeof SunmiModule?.getDeviceInfo === "function",
      clearCache: typeof SunmiModule?.clearAppCache === "function",
      updateApk: typeof SunmiModule?.silentInstall === "function",
    };
  }

  async getPhysicalTerminalId() {
    const candidates = ["getSerialNo", "getSerial", "getDeviceSN", "getSN"];
    for (const method of candidates) {
      try {
        if (typeof SunmiModule?.[method] === "function") {
          const sn = await SunmiModule[method]();
          if (sn?.trim()) return sn.trim();
        }
      } catch {}
    }
    return null;
  }

  async lockTerminal(params = {}) {
    if (typeof SunmiModule?.lockScreen === "function") {
      await SunmiModule.lockScreen();
      this.localLockState = true;
      return { action: "lock_terminal", applied: true, via: "sunmi_sdk" };
    }
    return super.lockTerminal(params);
  }

  async unlockTerminal(params) {
    if (typeof SunmiModule?.unlockScreen === "function") {
      await SunmiModule.unlockScreen();
      this.localLockState = false;
      return { action: "unlock_terminal", applied: true, via: "sunmi_sdk" };
    }
    return super.unlockTerminal(params);
  }

  async rebootTerminal(params) {
    if (typeof SunmiModule?.rebootDevice === "function") {
      await SunmiModule.rebootDevice();
      return { action: "reboot", applied: true, via: "sunmi_sdk" };
    }
    return super.rebootTerminal(params);
  }

  async factoryReset(params) {
    if (typeof SunmiModule?.factoryReset === "function") {
      await SunmiModule.factoryReset();
      return { action: "factory_reset", applied: true, via: "sunmi_sdk" };
    }
    return super.factoryReset(params);
  }

  async getDiagnostics(params) {
    if (typeof SunmiModule?.getDeviceInfo === "function") {
      const info = await SunmiModule.getDeviceInfo();
      return { action: "get_diagnostics", diagnostics: info, via: "sunmi_sdk" };
    }
    return super.getDiagnostics(params);
  }

  async clearCache(params) {
    if (typeof SunmiModule?.clearAppCache === "function") {
      await SunmiModule.clearAppCache();
      return { action: "clear_cache", applied: true, via: "sunmi_sdk" };
    }
    return super.clearCache(params);
  }

  async updateApk(params) {
    if (typeof SunmiModule?.silentInstall === "function") {
      await SunmiModule.silentInstall(params.download_url || params.apk_path);
      return { action: "update_apk", applied: true, via: "sunmi_sdk" };
    }
    return super.updateApk(params);
  }
}

const MDM_MODEL_ADAPTER_MAP = {
  // PAX devices
  pax_a920_max: "pax",
  pax_a8900: "pax",
  // Newland PayDroid / mPOS
  newland_n910: "newland",
  newland_n910_pro: "newland",
  newland_me30su: "newland",
  // Nexgo-compatible (AOSP full/compact/mini+keypad)
  newland_n750: "nexgo",
  horizonpay_k11: "nexgo",
  horizonpay_k11_lite: "nexgo",
  topwise_t11_pro: "nexgo",
  topwise_mp45p: "nexgo",
  // Sunmi P-series
  sunmi_p1: "sunmi",
  sunmi_p2: "sunmi",
  sunmi_p2_pro: "sunmi",
  sunmi_p3: "sunmi",
};

export class MdmAdapterFactory {
  /**
   * Create the right adapter for a given MDM model ID.
   * Falls back to NexgoAdapter if the model isn't in the map.
   */
  static create(mdmModelId) {
    const adapterType = MDM_MODEL_ADAPTER_MAP[mdmModelId?.toLowerCase()] ?? "nexgo";
    switch (adapterType) {
      case "pax":     return new PaxAdapter(mdmModelId);
      case "newland": return new NewlandAdapter(mdmModelId);
      case "sunmi":   return new SunmiAdapter(mdmModelId);
      case "nexgo":
      default:        return new NexgoAdapter(mdmModelId);
    }
  }
}

export { MdmAdapterBase, NexgoAdapter, PaxAdapter, NewlandAdapter, SunmiAdapter };

// Default export: NexgoAdapter for backwards compatibility with existing imports
export default new NexgoAdapter("default");
