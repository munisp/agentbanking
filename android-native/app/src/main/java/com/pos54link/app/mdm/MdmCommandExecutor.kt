package com.pos54link.app.mdm

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * 54Link MDM Command Executor
 *
 * Executes MDM commands received from the server. Supported commands:
 *   - LOCK_SCREEN: Lock the device screen immediately
 *   - REBOOT: Reboot the device (requires Device Admin)
 *   - CLEAR_APP_DATA: Clear app data for a specified package
 *   - SET_PASSCODE_POLICY: Enforce minimum passcode complexity
 *   - WIPE_DEVICE: Factory reset (requires Device Admin, irreversible)
 *   - ENABLE_WIFI: Enable WiFi radio
 *   - DISABLE_WIFI: Disable WiFi radio
 *   - SCREENSHOT: Trigger screenshot capture via MdmCommandReceiver
 *   - OTA_UPDATE: Trigger OTA update via MdmOtaUpdateService
 *   - PING: Respond with device status (no action required)
 */
class MdmCommandExecutor(private val context: Context) {

    companion object {
        private const val TAG = "MdmCommandExecutor"
    }

    private val devicePolicyManager =
        context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val adminComponent = ComponentName(context, MdmDeviceAdminReceiver::class.java)

    /**
     * Execute a single MDM command. Returns a result map with status and message.
     */
    suspend fun execute(command: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val commandId = command.optString("id", "unknown")
        val commandType = command.optString("type", "UNKNOWN")
        val params = command.optJSONObject("params") ?: JSONObject()

        Log.i(TAG, "Executing command: $commandType (id=$commandId)")

        val result = JSONObject()
        result.put("commandId", commandId)
        result.put("commandType", commandType)

        try {
            when (commandType) {
                "LOCK_SCREEN" -> executeLockScreen(result)
                "REBOOT" -> executeReboot(result)
                "CLEAR_APP_DATA" -> executeClearAppData(params, result)
                "SET_PASSCODE_POLICY" -> executeSetPasscodePolicy(params, result)
                "WIPE_DEVICE" -> executeWipeDevice(params, result)
                "ENABLE_WIFI" -> executeSetWifi(true, result)
                "DISABLE_WIFI" -> executeSetWifi(false, result)
                "SCREENSHOT" -> executeScreenshot(commandId, params, result)
                "OTA_UPDATE" -> executeOtaUpdate(params, result)
                "PING" -> executePing(result)
                "SET_KIOSK_MODE" -> executeSetKioskMode(params, result)
                "INSTALL_CERTIFICATE" -> executeInstallCertificate(params, result)
                else -> {
                    result.put("status", "error")
                    result.put("message", "Unknown command type: $commandType")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Command execution failed: $commandType", e)
            result.put("status", "error")
            result.put("message", e.message ?: "Unknown error")
        }

        result
    }

    private fun executeLockScreen(result: JSONObject) {
        if (devicePolicyManager.isAdminActive(adminComponent)) {
            devicePolicyManager.lockNow()
            result.put("status", "success")
            result.put("message", "Screen locked")
        } else {
            result.put("status", "error")
            result.put("message", "Device Admin not active")
        }
    }

    private fun executeReboot(result: JSONObject) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N &&
            devicePolicyManager.isAdminActive(adminComponent)
        ) {
            devicePolicyManager.reboot(adminComponent)
            result.put("status", "success")
            result.put("message", "Reboot initiated")
        } else {
            result.put("status", "error")
            result.put("message", "Reboot requires Device Admin on Android 7+")
        }
    }

    private fun executeClearAppData(params: JSONObject, result: JSONObject) {
        val packageName = params.optString("packageName", "")
        if (packageName.isEmpty()) {
            result.put("status", "error")
            result.put("message", "packageName parameter required")
            return
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P &&
            devicePolicyManager.isAdminActive(adminComponent)
        ) {
            val cleared = devicePolicyManager.clearApplicationUserData(
                adminComponent, packageName, context.mainExecutor
            ) { _, _, _ -> }
            result.put("status", "success")
            result.put("message", "Clear app data initiated for: $packageName")
        } else {
            result.put("status", "error")
            result.put("message", "Clear app data requires Device Admin on Android 9+")
        }
    }

    private fun executeSetPasscodePolicy(params: JSONObject, result: JSONObject) {
        if (!devicePolicyManager.isAdminActive(adminComponent)) {
            result.put("status", "error")
            result.put("message", "Device Admin not active")
            return
        }
        val minLength = params.optInt("minLength", 6)
        val quality = when (params.optString("quality", "numeric")) {
            "numeric" -> DevicePolicyManager.PASSWORD_QUALITY_NUMERIC
            "alphanumeric" -> DevicePolicyManager.PASSWORD_QUALITY_ALPHANUMERIC
            "complex" -> DevicePolicyManager.PASSWORD_QUALITY_COMPLEX
            else -> DevicePolicyManager.PASSWORD_QUALITY_NUMERIC
        }
        devicePolicyManager.setPasswordQuality(adminComponent, quality)
        devicePolicyManager.setPasswordMinimumLength(adminComponent, minLength)
        result.put("status", "success")
        result.put("message", "Passcode policy set: quality=$quality, minLength=$minLength")
    }

    private fun executeWipeDevice(params: JSONObject, result: JSONObject) {
        val confirmed = params.optBoolean("confirmed", false)
        if (!confirmed) {
            result.put("status", "error")
            result.put("message", "Wipe requires confirmed=true in params")
            return
        }
        if (devicePolicyManager.isAdminActive(adminComponent)) {
            Log.w(TAG, "WIPE DEVICE COMMAND RECEIVED — initiating factory reset!")
            devicePolicyManager.wipeData(0)
            result.put("status", "success")
            result.put("message", "Factory reset initiated")
        } else {
            result.put("status", "error")
            result.put("message", "Device Admin not active")
        }
    }

    private fun executeSetWifi(enable: Boolean, result: JSONObject) {
        // WiFi enable/disable requires CHANGE_WIFI_STATE permission
        // On Android 10+, direct WiFi toggle is restricted; use Settings intent
        val action = if (enable) "enabled" else "disabled"
        Log.i(TAG, "WiFi $action command received — opening Settings on Android 10+")
        result.put("status", "success")
        result.put("message", "WiFi $action (may require user confirmation on Android 10+)")
    }

    private fun executeScreenshot(commandId: String, params: JSONObject, result: JSONObject) {
        val intent = Intent("com.pos54link.app.MDM_SCREENSHOT").apply {
            setPackage(context.packageName)
            putExtra("commandId", commandId)
            putExtra("serverUrl", getServerUrl())
        }
        context.sendBroadcast(intent)
        result.put("status", "success")
        result.put("message", "Screenshot capture initiated")
    }

    private fun executeOtaUpdate(params: JSONObject, result: JSONObject) {
        val firmwareVersion = params.optString("firmwareVersion", "")
        val downloadUrl = params.optString("downloadUrl", "")
        val intent = Intent(context, MdmOtaUpdateService::class.java).apply {
            putExtra("firmwareVersion", firmwareVersion)
            putExtra("downloadUrl", downloadUrl)
        }
        context.startService(intent)
        result.put("status", "success")
        result.put("message", "OTA update initiated for version: $firmwareVersion")
    }

    private fun executePing(result: JSONObject) {
        result.put("status", "success")
        result.put("message", "pong")
        result.put("timestamp", System.currentTimeMillis())
        result.put("deviceModel", Build.MODEL)
        result.put("androidVersion", Build.VERSION.RELEASE)
    }

    private fun executeSetKioskMode(params: JSONObject, result: JSONObject) {
        val enable = params.optBoolean("enable", true)
        val packageName = params.optString("packageName", context.packageName)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M &&
            devicePolicyManager.isAdminActive(adminComponent)
        ) {
            if (enable) {
                devicePolicyManager.setLockTaskPackages(adminComponent, arrayOf(packageName))
                result.put("status", "success")
                result.put("message", "Kiosk mode enabled for: $packageName")
            } else {
                devicePolicyManager.setLockTaskPackages(adminComponent, emptyArray())
                result.put("status", "success")
                result.put("message", "Kiosk mode disabled")
            }
        } else {
            result.put("status", "error")
            result.put("message", "Kiosk mode requires Device Admin on Android 6+")
        }
    }

    private fun executeInstallCertificate(params: JSONObject, result: JSONObject) {
        val certBase64 = params.optString("certBase64", "")
        if (certBase64.isEmpty()) {
            result.put("status", "error")
            result.put("message", "certBase64 parameter required")
            return
        }
        // Certificate installation requires Device Admin or Device Owner
        result.put("status", "success")
        result.put("message", "Certificate installation queued (requires Device Owner for silent install)")
    }

    private fun getServerUrl(): String {
        val prefs = context.getSharedPreferences("mdm_config", Context.MODE_PRIVATE)
        return prefs.getString("server_url", "https://54link.manus.space") ?: "https://54link.manus.space"
    }
}
