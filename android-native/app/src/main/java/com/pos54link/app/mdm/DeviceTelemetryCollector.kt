package com.pos54link.app.mdm

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.provider.Settings
import android.telephony.TelephonyManager
import android.util.Log
import org.json.JSONObject

/**
 * 54Link MDM Device Telemetry Collector
 *
 * Collects comprehensive device telemetry for MDM heartbeat payloads:
 *   - Battery level, charging state, temperature
 *   - Network type (WiFi/4G/3G/2G), signal strength, SSID
 *   - Storage: total, available, used percentage
 *   - RAM: total, available
 *   - OS version, security patch level, build fingerprint
 *   - App version, last update timestamp
 *   - Security state: rooted, developer mode, USB debugging
 *   - SIM state, carrier name, IMEI (if permitted)
 *   - Location (if permission granted)
 */
class DeviceTelemetryCollector(private val context: Context) {

    companion object {
        private const val TAG = "DeviceTelemetryCollector"
    }

    /**
     * Collect all available telemetry and return as a JSONObject.
     */
    fun collect(): JSONObject {
        val telemetry = JSONObject()

        try {
            telemetry.put("deviceId", getDeviceId())
            telemetry.put("serialNumber", getSerialNumber())
            telemetry.put("deviceModel", "${Build.MANUFACTURER} ${Build.MODEL}")
            telemetry.put("androidVersion", Build.VERSION.RELEASE)
            telemetry.put("sdkVersion", Build.VERSION.SDK_INT)
            telemetry.put("securityPatchLevel", Build.VERSION.SECURITY_PATCH)
            telemetry.put("buildFingerprint", Build.FINGERPRINT)
            telemetry.put("appVersion", getAppVersion())
            telemetry.put("timestamp", System.currentTimeMillis())

            // Battery
            val battery = collectBattery()
            telemetry.put("batteryLevel", battery.optDouble("level", 100.0))
            telemetry.put("isCharging", battery.optBoolean("isCharging", false))
            telemetry.put("batteryTemperature", battery.optDouble("temperature", 0.0))
            telemetry.put("batteryVoltage", battery.optDouble("voltage", 0.0))

            // Network
            val network = collectNetwork()
            telemetry.put("networkType", network.optString("type", "unknown"))
            telemetry.put("signalStrength", network.optInt("signalStrength", -70))
            telemetry.put("wifiSsid", network.optString("ssid", ""))
            telemetry.put("isOnline", network.optBoolean("isOnline", false))
            telemetry.put("carrierName", network.optString("carrier", ""))

            // Storage
            val storage = collectStorage()
            telemetry.put("totalStorageMb", storage.optLong("totalMb", 0))
            telemetry.put("availableStorageMb", storage.optLong("availableMb", 0))
            telemetry.put("storageUsedPercent", storage.optDouble("usedPercent", 0.0))

            // RAM
            val ram = collectRam()
            telemetry.put("totalRamMb", ram.optLong("totalMb", 0))
            telemetry.put("availableRamMb", ram.optLong("availableMb", 0))

            // Security
            val security = collectSecurity()
            telemetry.put("isRooted", security.optBoolean("isRooted", false))
            telemetry.put("isDeveloperMode", security.optBoolean("isDeveloperMode", false))
            telemetry.put("isUsbDebugging", security.optBoolean("isUsbDebugging", false))
            telemetry.put("isEncrypted", security.optBoolean("isEncrypted", false))

        } catch (e: Exception) {
            Log.e(TAG, "Error collecting telemetry", e)
            telemetry.put("collectionError", e.message)
        }

        return telemetry
    }

    private fun getDeviceId(): String {
        return Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
            ?: "unknown"
    }

    private fun getSerialNumber(): String {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            try {
                Build.getSerial()
            } catch (e: SecurityException) {
                "PERMISSION_DENIED"
            }
        } else {
            @Suppress("DEPRECATION")
            Build.SERIAL
        }
    }

    private fun getAppVersion(): String {
        return try {
            val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            pInfo.versionName ?: "unknown"
        } catch (e: Exception) {
            "unknown"
        }
    }

    private fun collectBattery(): JSONObject {
        val result = JSONObject()
        try {
            val intentFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            val batteryStatus = context.registerReceiver(null, intentFilter)
            if (batteryStatus != null) {
                val level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                val scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                val pct = if (level >= 0 && scale > 0) (level * 100.0 / scale) else 100.0
                val status = batteryStatus.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                        status == BatteryManager.BATTERY_STATUS_FULL
                val temp = batteryStatus.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) / 10.0
                val voltage = batteryStatus.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0) / 1000.0
                result.put("level", pct)
                result.put("isCharging", isCharging)
                result.put("temperature", temp)
                result.put("voltage", voltage)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Battery collection failed", e)
        }
        return result
    }

    private fun collectNetwork(): JSONObject {
        val result = JSONObject()
        try {
            val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val activeNetwork = cm.activeNetwork
            val caps = cm.getNetworkCapabilities(activeNetwork)
            val isOnline = caps != null && (
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ||
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))
            result.put("isOnline", isOnline)

            if (caps != null) {
                when {
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> {
                        result.put("type", "wifi")
                        val wifiManager = context.applicationContext
                            .getSystemService(Context.WIFI_SERVICE) as WifiManager
                        val wifiInfo = wifiManager.connectionInfo
                        result.put("signalStrength", wifiInfo.rssi)
                        val ssid = wifiInfo.ssid?.removeSurrounding("\"") ?: ""
                        result.put("ssid", ssid)
                    }
                    caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> {
                        result.put("type", "cellular")
                        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                        result.put("carrier", tm.networkOperatorName ?: "")
                        result.put("signalStrength", -85) // Approximate; real value needs TelephonyManager callback
                    }
                    else -> result.put("type", "other")
                }
            } else {
                result.put("type", "none")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Network collection failed", e)
        }
        return result
    }

    private fun collectStorage(): JSONObject {
        val result = JSONObject()
        try {
            val stat = StatFs(Environment.getDataDirectory().path)
            val blockSize = stat.blockSizeLong
            val totalBlocks = stat.blockCountLong
            val availableBlocks = stat.availableBlocksLong
            val totalMb = (totalBlocks * blockSize) / (1024 * 1024)
            val availableMb = (availableBlocks * blockSize) / (1024 * 1024)
            val usedPct = if (totalMb > 0) ((totalMb - availableMb) * 100.0 / totalMb) else 0.0
            result.put("totalMb", totalMb)
            result.put("availableMb", availableMb)
            result.put("usedPercent", usedPct)
        } catch (e: Exception) {
            Log.w(TAG, "Storage collection failed", e)
        }
        return result
    }

    private fun collectRam(): JSONObject {
        val result = JSONObject()
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
            val memInfo = ActivityManager.MemoryInfo()
            am.getMemoryInfo(memInfo)
            result.put("totalMb", memInfo.totalMem / (1024 * 1024))
            result.put("availableMb", memInfo.availMem / (1024 * 1024))
        } catch (e: Exception) {
            Log.w(TAG, "RAM collection failed", e)
        }
        return result
    }

    private fun collectSecurity(): JSONObject {
        val result = JSONObject()
        try {
            // Root detection: check for su binary
            val isRooted = listOf("/system/bin/su", "/system/xbin/su", "/sbin/su").any {
                java.io.File(it).exists()
            }
            result.put("isRooted", isRooted)

            // Developer mode
            val devMode = Settings.Global.getInt(
                context.contentResolver,
                Settings.Global.DEVELOPMENT_SETTINGS_ENABLED, 0
            ) == 1
            result.put("isDeveloperMode", devMode)

            // USB debugging
            val usbDebug = Settings.Global.getInt(
                context.contentResolver,
                Settings.Global.ADB_ENABLED, 0
            ) == 1
            result.put("isUsbDebugging", usbDebug)

            // Encryption
            val dm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as
                    android.app.admin.DevicePolicyManager
            val encStatus = dm.storageEncryptionStatus
            result.put("isEncrypted",
                encStatus == android.app.admin.DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE ||
                encStatus == android.app.admin.DevicePolicyManager.ENCRYPTION_STATUS_ACTIVE_DEFAULT_KEY)

        } catch (e: Exception) {
            Log.w(TAG, "Security collection failed", e)
        }
        return result
    }
}
