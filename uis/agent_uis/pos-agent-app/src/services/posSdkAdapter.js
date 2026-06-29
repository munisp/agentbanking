import { NativeModules } from "react-native";

const { NexgoModule } = NativeModules;

class PosSdkAdapter {
  constructor() {
    this.customHandlers = {};
    this.localLockState = false;
  }

  normalizeTerminalId(value) {
    if (typeof value !== "string") {
      return "";
    }
    return value.trim();
  }

  async tryNativeGetter(name) {
    const target = NexgoModule?.[name];
    if (typeof target === "function") {
      const value = await target.call(NexgoModule);
      const normalized = this.normalizeTerminalId(value);
      return normalized || null;
    }

    if (typeof target === "string") {
      const normalized = this.normalizeTerminalId(target);
      return normalized || null;
    }

    return null;
  }

  async getPhysicalTerminalId() {
    const candidates = [
      "getPhysicalTerminalId",
      "getTerminalId",
      "getTerminalID",
      "getPosId",
      "getPOSId",
      "getDeviceSerial",
      "getDeviceSn",
      "getSN",
      "getSerialNumber",
      "terminalId",
      "terminalID",
      "deviceSerial",
      "serialNumber",
    ];

    for (const name of candidates) {
      try {
        const value = await this.tryNativeGetter(name);
        if (value) {
          return value;
        }
      } catch (error) {
        continue;
      }
    }

    return null;
  }

  registerHandler(commandType, handler) {
    if (!commandType || typeof handler !== "function") {
      return;
    }
    this.customHandlers[commandType] = handler;
  }

  getCapabilities() {
    return {
      lockTerminal: typeof NexgoModule?.lockTerminal === "function",
      unlockTerminal: typeof NexgoModule?.unlockTerminal === "function",
      rebootTerminal: typeof NexgoModule?.rebootTerminal === "function",
      requestDiagnostics: typeof NexgoModule?.requestDiagnostics === "function",
      remoteWipe: typeof NexgoModule?.remoteWipe === "function",
    };
  }

  async executeCommand(command) {
    const commandType = command?.command_type;
    const params = command?.params ?? {};

    if (!commandType) {
      throw new Error("Invalid command payload: missing command_type");
    }

    if (this.customHandlers[commandType]) {
      return this.customHandlers[commandType](params, command);
    }

    switch (commandType) {
      case "lock_terminal":
        return this.lockTerminal(params);
      case "unlock_terminal":
        return this.unlockTerminal(params);
      case "reboot":
        return this.rebootTerminal(params);
      case "get_diagnostics":
        return this.getDiagnostics(params);
      case "remote_wipe":
        return this.remoteWipe(params);
      case "push_config":
      case "update_apk":
      case "update_firmware":
      case "clear_cache":
      case "enable_offline_mode":
      case "disable_offline_mode":
      case "enable_tamper_protection":
      case "disable_tamper_protection":
      case "rotate_encryption_keys":
      case "push_key_injection":
      case "enable_geofence":
      case "disable_geofence":
      case "screenshot":
      case "log_upload":
        return this.acceptWithoutNativeExecution(commandType, params);
      default:
        throw new Error(`Unsupported MDM command: ${commandType}`);
    }
  }

  async lockTerminal(params = {}) {
    if (typeof NexgoModule?.lockTerminal === "function") {
      await NexgoModule.lockTerminal(params?.reason ?? "mdm_remote_lock");
      this.localLockState = true;
      return { action: "lock_terminal", applied: true, via: "nexgo_sdk" };
    }

    this.localLockState = true;
    return {
      action: "lock_terminal",
      applied: true,
      via: "adapter_fallback",
      note: "Native lockTerminal SDK method not available",
    };
  }

  async unlockTerminal() {
    if (typeof NexgoModule?.unlockTerminal === "function") {
      await NexgoModule.unlockTerminal();
      this.localLockState = false;
      return { action: "unlock_terminal", applied: true, via: "nexgo_sdk" };
    }

    this.localLockState = false;
    return {
      action: "unlock_terminal",
      applied: true,
      via: "adapter_fallback",
      note: "Native unlockTerminal SDK method not available",
    };
  }

  async rebootTerminal() {
    if (typeof NexgoModule?.rebootTerminal === "function") {
      await NexgoModule.rebootTerminal();
      return { action: "reboot", applied: true, via: "nexgo_sdk" };
    }

    return {
      action: "reboot",
      applied: false,
      via: "adapter_fallback",
      note: "Native rebootTerminal SDK method not available",
    };
  }

  async getDiagnostics() {
    if (typeof NexgoModule?.requestDiagnostics === "function") {
      const diagnostics = await NexgoModule.requestDiagnostics();
      return {
        action: "get_diagnostics",
        diagnostics,
        via: "nexgo_sdk",
      };
    }

    return {
      action: "get_diagnostics",
      via: "adapter_fallback",
      diagnostics: {
        sdk: "nexgo",
        local_lock_state: this.localLockState,
        capabilities: this.getCapabilities(),
        timestamp: new Date().toISOString(),
      },
    };
  }

  async remoteWipe() {
    if (typeof NexgoModule?.remoteWipe === "function") {
      await NexgoModule.remoteWipe();
      return { action: "remote_wipe", applied: true, via: "nexgo_sdk" };
    }

    throw new Error(
      "remote_wipe not supported by current POS SDK adapter implementation",
    );
  }

  async acceptWithoutNativeExecution(commandType, params) {
    return {
      action: commandType,
      accepted: true,
      params,
      via: "adapter_placeholder",
      note: "No native execution handler registered yet",
    };
  }
}

export default new PosSdkAdapter();
