/**
 * simOrchestratorManager
 *
 * JS bridge to the native Android SIMOrchestratorModule.
 * Call start() once after the agent logs in; the foreground service keeps
 * the binary alive from that point on (survives backgrounding and reboots).
 *
 * On non-Android platforms (iOS dev, web) all calls are no-ops.
 */

import { NativeModules, Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const { SIMOrchestratorModule } = NativeModules;
const isAndroid = Platform.OS === "android";

const simOrchestratorManager = {
  /**
   * Start the orchestrator foreground service.
   * Reads agent config from SecureStore so it's always in sync with the
   * logged-in user.
   */
  async start() {
    if (!isAndroid || !SIMOrchestratorModule) return;

    const [agentCode, terminalId] = await Promise.all([
      SecureStore.getItemAsync("agentCode").catch(() => null),
      SecureStore.getItemAsync("terminalId").catch(() => null),
    ]);

    SIMOrchestratorModule.start(
      agentCode  || "AGT001",
      terminalId || null,          // falls back to Build.SERIAL in Kotlin
      "https://api.54agent.io",
      "54agent-sim-orchestrator-default-key",
    );
  },

  /** Stop the orchestrator service (call on logout). */
  stop() {
    if (!isAndroid || !SIMOrchestratorModule) return;
    SIMOrchestratorModule.stop();
  },
};

export default simOrchestratorManager;
