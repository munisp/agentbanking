package com.pos54link.app.mdm

import android.content.Context
import android.os.Build
import android.provider.Settings
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * 54Link MDM Enrollment Manager
 *
 * Handles device enrollment via QR code token scan:
 *  1. Agent scans QR code containing an enrollment token
 *  2. Device sends serial number + token to /api/trpc/mdm.completeEnrollment
 *  3. Server validates token and returns a persistent deviceToken
 *  4. deviceToken is stored in SharedPreferences and used for all subsequent heartbeats
 *
 * Enrollment state is persisted in SharedPreferences "mdm_config".
 */
class MdmEnrollmentManager(private val context: Context) {

    companion object {
        private const val TAG = "MdmEnrollmentManager"
        private const val PREFS_NAME = "mdm_config"
        private const val DEFAULT_SERVER_URL = "https://54link.manus.space"
    }

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    /** Returns true if the device has a valid enrollment token. */
    val isEnrolled: Boolean
        get() = prefs.getString("device_token", null) != null

    /** Returns the stored device token, or null if not enrolled. */
    val deviceToken: String?
        get() = prefs.getString("device_token", null)

    /** Returns the stored serial number. */
    val serialNumber: String
        get() = prefs.getString("serial_number", getDeviceSerial()) ?: getDeviceSerial()

    /**
     * Enroll this device using a QR code enrollment token.
     *
     * @param enrollmentToken The token scanned from the QR code
     * @param agentCode The agent code for this POS terminal
     * @param serverUrl Optional server URL override
     * @return EnrollmentResult with success/error details
     */
    suspend fun enroll(
        enrollmentToken: String,
        agentCode: String,
        serverUrl: String = DEFAULT_SERVER_URL,
    ): EnrollmentResult = withContext(Dispatchers.IO) {
        try {
            val serial = getDeviceSerial()
            val body = JSONObject().apply {
                put("json", JSONObject().apply {
                    put("enrollmentToken", enrollmentToken)
                    put("serialNumber", serial)
                    put("agentCode", agentCode)
                    put("deviceModel", "${Build.MANUFACTURER} ${Build.MODEL}")
                    put("osVersion", Build.VERSION.RELEASE)
                    put("androidId", getAndroidId())
                })
            }

            val url = URL("$serverUrl/api/trpc/mdm.completeEnrollment")
            val conn = url.openConnection() as HttpURLConnection
            try {
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.connectTimeout = 15_000
                conn.readTimeout = 15_000
                conn.doOutput = true
                OutputStreamWriter(conn.outputStream).use { it.write(body.toString()) }

                if (conn.responseCode !in 200..299) {
                    val error = conn.errorStream?.bufferedReader()?.readText() ?: "HTTP ${conn.responseCode}"
                    return@withContext EnrollmentResult.Failure("Server error: $error")
                }

                val response = JSONObject(conn.inputStream.bufferedReader().readText())
                val deviceToken = response
                    .optJSONObject("result")
                    ?.optJSONObject("data")
                    ?.optJSONObject("json")
                    ?.optString("deviceToken")

                if (deviceToken.isNullOrEmpty()) {
                    return@withContext EnrollmentResult.Failure("No device token in response")
                }

                // Persist enrollment state
                prefs.edit()
                    .putString("device_token", deviceToken)
                    .putString("serial_number", serial)
                    .putString("agent_code", agentCode)
                    .putString("server_url", serverUrl)
                    .putLong("enrolled_at", System.currentTimeMillis())
                    .apply()

                // Start heartbeat worker
                MdmHeartbeatWorker.schedule(context)

                Log.i(TAG, "Device enrolled successfully: serial=$serial")
                EnrollmentResult.Success(deviceToken)

            } finally {
                conn.disconnect()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Enrollment failed", e)
            EnrollmentResult.Failure(e.message ?: "Unknown error")
        }
    }

    /** Unenroll this device — clears stored token and cancels heartbeat worker. */
    fun unenroll() {
        MdmHeartbeatWorker.cancel(context)
        prefs.edit()
            .remove("device_token")
            .remove("serial_number")
            .remove("agent_code")
            .remove("enrolled_at")
            .apply()
        Log.i(TAG, "Device unenrolled")
    }

    private fun getDeviceSerial(): String {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // On Android 10+, serial requires READ_PRIVILEGED_PHONE_STATE
            // Fall back to ANDROID_ID for non-privileged apps
            getAndroidId()
        } else {
            @Suppress("DEPRECATION")
            Build.SERIAL.takeIf { it != Build.UNKNOWN } ?: getAndroidId()
        }
    }

    private fun getAndroidId(): String {
        return Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
            ?: "unknown"
    }
}

/** Result of an enrollment attempt. */
sealed class EnrollmentResult {
    data class Success(val deviceToken: String) : EnrollmentResult()
    data class Failure(val error: String) : EnrollmentResult()
}
