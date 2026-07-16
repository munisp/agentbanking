package com.tani1964.posagentapp

import android.os.Build
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod

/**
 * React Native native module that exposes sim-orchestrator lifecycle control
 * to JavaScript. Call start() once when the user logs in; the foreground
 * service keeps the binary alive from that point on.
 */
class SIMOrchestratorModule(private val reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName() = "SIMOrchestratorModule"

    /**
     * Start the orchestrator service.
     *
     * @param agentCode  Agent code from the logged-in user (e.g. "AGT001").
     * @param terminalId Terminal serial number. Pass null to use Build.SERIAL.
     * @param platformUrl 54agent platform base URL.
     * @param apiKey     SIM orchestrator API key.
     */
    @ReactMethod
    fun start(agentCode: String?, terminalId: String?, platformUrl: String?, apiKey: String?) {
        val prefs = reactContext.getSharedPreferences("sim_config", 0).edit()
        agentCode?.let  { prefs.putString("agent_code",   it) }
        platformUrl?.let { prefs.putString("platform_url", it) }
        apiKey?.let     { prefs.putString("api_key",      it) }
        prefs.putString("terminal_id", terminalId ?: Build.SERIAL)
        prefs.apply()

        SIMOrchestratorService.start(reactContext)
    }

    /** Stop the orchestrator service and kill the binary. */
    @ReactMethod
    fun stop() {
        SIMOrchestratorService.stop(reactContext)
    }
}
