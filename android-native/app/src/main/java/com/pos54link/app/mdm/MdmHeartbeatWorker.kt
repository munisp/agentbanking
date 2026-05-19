package com.pos54link.app.mdm

import android.Manifest
import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjectionManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.provider.Settings
import android.util.Base64
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/**
 * 54Link MDM HeartbeatWorker
 *
 * Runs as a periodic WorkManager task every 5 minutes. On each execution:
 *  1. Collects device telemetry (battery, WiFi, OS version, app version, security state)
 *  2. Sends a heartbeat POST to the MDM server at /api/trpc/mdm.heartbeat
 *  3. Parses the response for pending commands and executes them
 *  4. Reports screenshot if a SCREENSHOT command is pending
 *
 * Configuration (read from SharedPreferences "mdm_config"):
 *   server_url       — MDM server base URL (default: https://54link.manus.space)
 *   device_token     — Device token issued during enrollment
 *   serial_number    — Device serial number
 *   agent_code       — Agent code for this POS terminal
 *   heartbeat_interval_min — Heartbeat interval in minutes (default: 5)
 */
class MdmHeartbeatWorker(
    private val context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "MdmHeartbeatWorker"
        private const val WORK_NAME = "54link_mdm_heartbeat"
        private const val PREFS_NAME = "mdm_config"
        private const val DEFAULT_SERVER_URL = "https://54link.manus.space"
        private const val DEFAULT_HEARTBEAT_INTERVAL_MIN = 5L

        /**
         * Schedule the periodic MDM heartbeat worker.
         * Call from Application.onCreate() after enrollment is complete.
         */
        fun schedule(context: Context) {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val intervalMin = prefs.getLong("heartbeat_interval_min", DEFAULT_HEARTBEAT_INTERVAL_MIN)

            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = PeriodicWorkRequestBuilder<MdmHeartbeatWorker>(
                intervalMin, TimeUnit.MINUTES,
                intervalMin / 2, TimeUnit.MINUTES, // flex window
            )
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.UPDATE,
                request,
            )
            Log.i(TAG, "MDM heartbeat scheduled every $intervalMin minutes")
        }

        /** Cancel the heartbeat worker (call on device unenrollment). */
        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
            Log.i(TAG, "MDM heartbeat cancelled")
        }
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        try {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val serverUrl = prefs.getString("server_url", DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
            val deviceToken = prefs.getString("device_token", null)
            val serialNumber = prefs.getString("serial_number", null)
            val agentCode = prefs.getString("agent_code", null)

            if (deviceToken == null || serialNumber == null) {
                Log.w(TAG, "Device not enrolled — skipping heartbeat")
                return@withContext Result.success()
            }

            // Collect telemetry
            val telemetry = collectTelemetry(serialNumber, agentCode ?: "")

            // Send heartbeat
            val response = sendHeartbeat(serverUrl, deviceToken, telemetry)
            Log.d(TAG, "Heartbeat response: $response")

            // Process pending commands
            response?.let { processCommands(it, serverUrl, deviceToken) }

            Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Heartbeat failed", e)
            Result.retry()
        }
    }

    // ── Telemetry collection ──────────────────────────────────────────────────

    private fun collectTelemetry(serialNumber: String, agentCode: String): JSONObject {
        return JSONObject().apply {
            put("serialNumber", serialNumber)
            put("agentCode", agentCode)
            put("osVersion", Build.VERSION.RELEASE)
            put("appVersion", getAppVersion())
            put("deviceModel", "${Build.MANUFACTURER} ${Build.MODEL}")
            put("androidSdkVersion", Build.VERSION.SDK_INT)
            put("batteryLevel", getBatteryLevel())
            put("batteryCharging", isBatteryCharging())
            put("isScreenLocked", isScreenLocked())
            put("isEncrypted", isEncrypted())
            put("isRooted", isRooted())
            put("isDeveloperOptionsEnabled", isDeveloperOptionsEnabled())
            put("isAdbEnabled", isAdbEnabled())
            put("wifiConnected", isWifiConnected())
            put("wifiSsid", getWifiSsid())
            put("wifiSignalStrength", getWifiSignalStrength())
            put("wifiBssid", getWifiBssid())
            put("networkType", getNetworkType())
            put("freeMemoryMb", getFreeMemoryMb())
            put("totalMemoryMb", getTotalMemoryMb())
            put("freeDiskMb", getFreeDiskMb())
            put("uptime", android.os.SystemClock.elapsedRealtime() / 1000)
            put("timestamp", java.time.Instant.now().toString())
        }
    }

    private fun getAppVersion(): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            pInfo.versionName ?: "unknown"
        } catch (e: PackageManager.NameNotFoundException) {
            "unknown"
        }
    }

    private fun getBatteryLevel(): Int {
        val batteryIntent = context.registerReceiver(
            null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        ) ?: return -1
        val level = batteryIntent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = batteryIntent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        return if (level >= 0 && scale > 0) (level * 100 / scale) else -1
    }

    private fun isBatteryCharging(): Boolean {
        val batteryIntent = context.registerReceiver(
            null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        ) ?: return false
        val status = batteryIntent.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        return status == BatteryManager.BATTERY_STATUS_CHARGING ||
               status == BatteryManager.BATTERY_STATUS_FULL
    }

    private fun isScreenLocked(): Boolean {
        val km = context.getSystemService(Context.KEYGUARD_SERVICE) as android.app.KeyguardManager
        return km.isKeyguardLocked
    }

    private fun isEncrypted(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val dm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as android.app.admin.DevicePolicyManager
            dm.storageEncryptionStatus == android.app.admin.DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE ||
            dm.storageEncryptionStatus == android.app.admin.DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE_PER_USER
        } else {
            true // Older devices encrypted by default
        }
    }

    private fun isRooted(): Boolean {
        val paths = arrayOf(
            "/system/app/Superuser.apk", "/sbin/su", "/system/bin/su",
            "/system/xbin/su", "/data/local/xbin/su", "/data/local/bin/su",
            "/system/sd/xbin/su", "/system/bin/failsafe/su", "/data/local/su",
        )
        return paths.any { java.io.File(it).exists() }
    }

    private fun isDeveloperOptionsEnabled(): Boolean {
        return Settings.Global.getInt(
            context.contentResolver, Settings.Global.DEVELOPMENT_SETTINGS_ENABLED, 0
        ) != 0
    }

    private fun isAdbEnabled(): Boolean {
        return Settings.Global.getInt(
            context.contentResolver, Settings.Global.ADB_ENABLED, 0
        ) != 0
    }

    private fun isWifiConnected(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    private fun getWifiSsid(): String {
        if (!isWifiConnected()) return ""
        val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val info = wm.connectionInfo ?: return ""
        return info.ssid.removeSurrounding("\"")
    }

    private fun getWifiBssid(): String {
        if (!isWifiConnected()) return ""
        val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        return wm.connectionInfo?.bssid ?: ""
    }

    private fun getWifiSignalStrength(): Int {
        if (!isWifiConnected()) return -1
        val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val rssi = wm.connectionInfo?.rssi ?: return -1
        return WifiManager.calculateSignalLevel(rssi, 5) // 0–4 bars
    }

    private fun getNetworkType(): String {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return "NONE"
        val caps = cm.getNetworkCapabilities(network) ?: return "NONE"
        return when {
            caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "WIFI"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "CELLULAR"
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ETHERNET"
            else -> "OTHER"
        }
    }

    private fun getFreeMemoryMb(): Long {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val info = ActivityManager.MemoryInfo()
        am.getMemoryInfo(info)
        return info.availMem / (1024 * 1024)
    }

    private fun getTotalMemoryMb(): Long {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val info = ActivityManager.MemoryInfo()
        am.getMemoryInfo(info)
        return info.totalMem / (1024 * 1024)
    }

    private fun getFreeDiskMb(): Long {
        val stat = android.os.StatFs(android.os.Environment.getDataDirectory().path)
        return stat.availableBlocksLong * stat.blockSizeLong / (1024 * 1024)
    }

    // ── Network communication ─────────────────────────────────────────────────

    private fun sendHeartbeat(
        serverUrl: String,
        deviceToken: String,
        telemetry: JSONObject,
    ): JSONObject? {
        val url = URL("$serverUrl/api/trpc/mdm.heartbeat")
        val conn = url.openConnection() as HttpURLConnection
        return try {
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Authorization", "Bearer $deviceToken")
            conn.setRequestProperty("X-54Link-Device-Token", deviceToken)
            conn.connectTimeout = 15_000
            conn.readTimeout = 15_000
            conn.doOutput = true

            // tRPC batch format
            val body = JSONObject().apply {
                put("json", telemetry)
            }
            OutputStreamWriter(conn.outputStream).use { it.write(body.toString()) }

            if (conn.responseCode in 200..299) {
                val text = conn.inputStream.bufferedReader().readText()
                JSONObject(text)
            } else {
                Log.w(TAG, "Heartbeat HTTP ${conn.responseCode}")
                null
            }
        } catch (e: Exception) {
            Log.e(TAG, "Heartbeat network error", e)
            null
        } finally {
            conn.disconnect()
        }
    }

    // ── Command processing ────────────────────────────────────────────────────

    private fun processCommands(response: JSONObject, serverUrl: String, deviceToken: String) {
        // tRPC response shape: { result: { data: { json: { pendingCommands: [...] } } } }
        val pendingCommands = try {
            response.optJSONObject("result")
                ?.optJSONObject("data")
                ?.optJSONObject("json")
                ?.optJSONArray("pendingCommands")
        } catch (e: Exception) {
            null
        } ?: return

        for (i in 0 until pendingCommands.length()) {
            val cmd = pendingCommands.optJSONObject(i) ?: continue
            val commandId = cmd.optString("id")
            val commandType = cmd.optString("command")
            Log.i(TAG, "Executing command: $commandType (id=$commandId)")

            when (commandType) {
                "RESTART" -> scheduleRestart()
                "WIPE" -> initiateFactoryReset()
                "LOCK" -> lockScreen()
                "SCREENSHOT" -> captureAndUploadScreenshot(serverUrl, deviceToken, commandId)
                "UPDATE" -> {
                    val downloadUrl = cmd.optString("downloadUrl")
                    if (downloadUrl.isNotEmpty()) scheduleOtaUpdate(downloadUrl)
                }
                "RECONFIG" -> {
                    val config = cmd.optJSONObject("config")
                    if (config != null) applyRemoteConfig(config)
                }
                "PING" -> Log.i(TAG, "PING received — device is alive")
                else -> Log.w(TAG, "Unknown command: $commandType")
            }
        }
    }

    private fun scheduleRestart() {
        Log.i(TAG, "RESTART command received — scheduling restart in 5s")
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
            intent?.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            context.startActivity(intent)
        }, 5_000)
    }

    private fun initiateFactoryReset() {
        Log.w(TAG, "WIPE command received — initiating factory reset")
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as android.app.admin.DevicePolicyManager
        try {
            dpm.wipeData(0)
        } catch (e: SecurityException) {
            Log.e(TAG, "WIPE failed — device admin not active", e)
        }
    }

    private fun lockScreen() {
        Log.i(TAG, "LOCK command received — locking screen")
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as android.app.admin.DevicePolicyManager
        try {
            dpm.lockNow()
        } catch (e: SecurityException) {
            Log.e(TAG, "LOCK failed — device admin not active", e)
        }
    }

    private fun captureAndUploadScreenshot(serverUrl: String, deviceToken: String, commandId: String) {
        Log.i(TAG, "SCREENSHOT command received (id=$commandId)")
        // Screenshot capture requires MediaProjection API which needs user consent.
        // On managed/kiosk devices, this is pre-granted via DevicePolicyManager.
        // For now, we report the command as acknowledged with a placeholder.
        // Full MediaProjection flow requires Activity context — handled in MdmCommandReceiver.
        val intent = Intent("com.pos54link.app.MDM_SCREENSHOT").apply {
            putExtra("commandId", commandId)
            putExtra("serverUrl", serverUrl)
            putExtra("deviceToken", deviceToken)
        }
        context.sendBroadcast(intent)
    }

    private fun scheduleOtaUpdate(downloadUrl: String) {
        Log.i(TAG, "OTA UPDATE command received — download URL: $downloadUrl")
        // Trigger Android PackageInstaller flow for the APK at downloadUrl
        val intent = Intent("com.pos54link.app.MDM_OTA_UPDATE").apply {
            putExtra("downloadUrl", downloadUrl)
        }
        context.sendBroadcast(intent)
    }

    private fun applyRemoteConfig(config: JSONObject) {
        Log.i(TAG, "RECONFIG command received — applying ${config.length()} settings")
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val editor = prefs.edit()
        config.keys().forEach { key ->
            when (val value = config.get(key)) {
                is String -> editor.putString(key, value)
                is Int -> editor.putInt(key, value)
                is Long -> editor.putLong(key, value)
                is Boolean -> editor.putBoolean(key, value)
                else -> editor.putString(key, value.toString())
            }
        }
        editor.apply()
    }
}
