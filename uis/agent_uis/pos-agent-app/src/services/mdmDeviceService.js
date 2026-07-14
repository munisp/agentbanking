import * as SecureStore from "expo-secure-store";
import { mdmDeviceApi } from "./apiService";
import locationService from "./locationService";
import { MdmAdapterFactory } from "./mdmAdapter";

const DEFAULT_HEARTBEAT_INTERVAL_MS = 60000;

class MdmDeviceService {
  constructor() {
    this.intervalRef = null;
    this.intervalMs = DEFAULT_HEARTBEAT_INTERVAL_MS;
    this.listeners = [];
    this.isRunning = false;
    this.processedCommandIds = new Set();
    this._adapter = null;
  }

  /** Returns (and caches) the adapter for the current device model */
  async _getAdapter() {
    if (!this._adapter) {
      const modelId = (await SecureStore.getItemAsync("modelId")) ||
        (await SecureStore.getItemAsync("model_id")) ||
        (await SecureStore.getItemAsync("deviceModel")) ||
        "default";
      this._adapter = MdmAdapterFactory.create(modelId);
    }
    return this._adapter;
  }

  normalizeTerminalId(value) {
    if (typeof value !== "string") {
      return "";
    }
    return value.trim();
  }

  addListener(callback) {
    this.listeners.push(callback);
    return () => {
      this.listeners = this.listeners.filter(
        (listener) => listener !== callback,
      );
    };
  }

  notify(event) {
    this.listeners.forEach((listener) => {
      try {
        listener(event);
      } catch (error) {
        console.error("[MDM] Listener error:", error);
      }
    });
  }

  async resolveTerminalContext() {
    const adapter = await this._getAdapter();
    const sdkTerminalId = this.normalizeTerminalId(
      await adapter.getPhysicalTerminalId(),
    );
    const storedTerminalId = this.normalizeTerminalId(
      (await SecureStore.getItemAsync("terminalId")) ||
        (await SecureStore.getItemAsync("terminal_id")),
    );

    if (sdkTerminalId && storedTerminalId && sdkTerminalId !== storedTerminalId) {
      throw new Error(
        `Terminal identity mismatch (sdk=${sdkTerminalId}, stored=${storedTerminalId})`,
      );
    }

    const terminalId = sdkTerminalId || storedTerminalId;

    const modelId =
      (await SecureStore.getItemAsync("modelId")) ||
      (await SecureStore.getItemAsync("model_id")) ||
      (await SecureStore.getItemAsync("deviceModel"));

    return { terminalId, modelId };
  }

  async buildHeartbeatPayload(overrides = {}) {
    let latitude = null;
    let longitude = null;

    try {
      const location = await locationService.getCurrentLocation();
      latitude = location?.latitude ?? null;
      longitude = location?.longitude ?? null;
    } catch (error) {
      // Location may be unavailable; heartbeat can still proceed.
    }

    const apkVersion =
      overrides.apk_version ||
      (await SecureStore.getItemAsync("apkVersion")) ||
      (await SecureStore.getItemAsync("apk_version")) ||
      "unknown";

    const firmwareVersion =
      overrides.firmware_version ||
      (await SecureStore.getItemAsync("firmwareVersion")) ||
      (await SecureStore.getItemAsync("firmware_version")) ||
      "unknown";

    return {
      battery_level: overrides.battery_level ?? null,
      signal_strength: overrides.signal_strength ?? null,
      apk_version: apkVersion,
      firmware_version: firmwareVersion,
      latitude: overrides.latitude ?? latitude,
      longitude: overrides.longitude ?? longitude,
      tamper_status: overrides.tamper_status || "ok",
    };
  }

  async heartbeatOnce(heartbeatOverrides = {}) {
    const { terminalId } = await this.resolveTerminalContext();
    if (!terminalId) {
      throw new Error(
        "No physical terminal ID found (SDK or terminalId/terminal_id secure storage)",
      );
    }

    const payload = await this.buildHeartbeatPayload(heartbeatOverrides);
    const heartbeat = await mdmDeviceApi.sendHeartbeat(terminalId, payload);

    this.notify({ type: "heartbeat", payload: heartbeat });
    return heartbeat;
  }

  async pollPendingCommands() {
    const { terminalId } = await this.resolveTerminalContext();
    if (!terminalId) {
      throw new Error(
        "No physical terminal ID found (SDK or terminalId/terminal_id secure storage)",
      );
    }

    const response = await mdmDeviceApi.getPendingCommands(terminalId);
    const commands = Array.isArray(response?.commands) ? response.commands : [];

    if (commands.length > 0) {
      this.notify({ type: "pending_commands", payload: commands });
      await this.executePendingCommands(commands, terminalId);
    }

    return response;
  }

  async executePendingCommands(commands, terminalId) {
    for (const command of commands) {
      const commandId = command?.command_id;
      const commandType = command?.command_type;
      const commandTerminalId = this.normalizeTerminalId(command?.terminal_id);

      if (commandTerminalId && commandTerminalId !== terminalId) {
        this.notify({
          type: "command_execution_skipped",
          payload: {
            command,
            reason: `terminal mismatch: local=${terminalId} command=${commandTerminalId}`,
          },
        });
        continue;
      }

      if (!commandId || this.processedCommandIds.has(commandId)) {
        continue;
      }

      this.processedCommandIds.add(commandId);

      try {
        this.notify({ type: "command_execution_started", payload: command });
        const adapter = await this._getAdapter();
        const result = await adapter.executeCommand(command);

        await this.updateCommandStatus(
          commandId,
          "executed",
          JSON.stringify(result ?? { ok: true }),
          terminalId,
        );

        this.notify({
          type: "command_execution_success",
          payload: { command, result },
        });
      } catch (error) {
        await this.updateCommandStatus(
          commandId,
          "failed",
          error?.message || `Execution failed for ${commandType || "unknown"}`,
          terminalId,
        );

        this.notify({
          type: "command_execution_failed",
          payload: {
            command,
            error:
              error?.message ||
              `Execution failed for ${commandType || "unknown"}`,
          },
        });
      }
    }
  }

  async completeProvisioning(apkVersion, firmwareVersion) {
    const { terminalId } = await this.resolveTerminalContext();
    if (!terminalId) {
      throw new Error(
        "No physical terminal ID found (SDK or terminalId/terminal_id secure storage)",
      );
    }

    return mdmDeviceApi.completeProvisioning(terminalId, {
      apk_version: apkVersion,
      firmware_version: firmwareVersion,
    });
  }

  async reportTamperAlert(alertType, severity, details) {
    const { terminalId } = await this.resolveTerminalContext();
    if (!terminalId) {
      throw new Error(
        "No physical terminal ID found (SDK or terminalId/terminal_id secure storage)",
      );
    }

    return mdmDeviceApi.sendTamperAlert(terminalId, {
      alert_type: alertType,
      severity,
      details,
    });
  }

  async fetchLatestApk() {
    const { modelId } = await this.resolveTerminalContext();
    if (!modelId) {
      throw new Error(
        "No model ID found (modelId/model_id missing in secure storage)",
      );
    }

    return mdmDeviceApi.getLatestApkByModel(modelId);
  }

  async updateCommandStatus(
    commandId,
    status,
    result,
    terminalIdOverride = null,
  ) {
    const { terminalId } = await this.resolveTerminalContext();

    return mdmDeviceApi.updateCommandStatus(commandId, {
      terminal_id: terminalIdOverride || terminalId,
      status,
      result,
    });
  }

  async heartbeatAndPoll() {
    const heartbeat = await this.heartbeatOnce();
    const pending = await this.pollPendingCommands();
    return { heartbeat, pending };
  }

  start(options = {}) {
    if (this.isRunning) {
      return;
    }

    this.intervalMs = options.intervalMs || DEFAULT_HEARTBEAT_INTERVAL_MS;
    const runCycle = async () => {
      try {
        await this.heartbeatAndPoll();
      } catch (error) {
        this.notify({
          type: "error",
          payload: error?.message || "MDM sync failed",
        });
      }
    };

    runCycle();
    this.intervalRef = setInterval(runCycle, this.intervalMs);
    this.isRunning = true;
  }

  stop() {
    if (this.intervalRef) {
      clearInterval(this.intervalRef);
      this.intervalRef = null;
    }
    this.isRunning = false;
  }
}

export default new MdmDeviceService();
