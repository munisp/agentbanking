package com.pos54link.app.mdm

import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * 54Link MDM Device Admin Receiver
 *
 * Required for WIPE and LOCK MDM commands. Must be declared in AndroidManifest.xml
 * with android.app.action.DEVICE_ADMIN_ENABLED intent filter and
 * android:permission="android.permission.BIND_DEVICE_ADMIN".
 *
 * The device admin policy XML (res/xml/mdm_device_admin.xml) must declare:
 *   <uses-policies>
 *     <wipe-data />
 *     <force-lock />
 *     <encrypted-storage />
 *     <disable-camera />
 *   </uses-policies>
 *
 * To activate device admin, the MDM enrollment flow launches:
 *   Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN)
 *     .putExtra(DevicePolicyManager.EXTRA_DEVICE_ADMIN, componentName)
 *     .putExtra(DevicePolicyManager.EXTRA_ADD_EXPLANATION, "Required for remote management")
 */
class MdmDeviceAdminReceiver : DeviceAdminReceiver() {

    companion object {
        private const val TAG = "MdmDeviceAdminReceiver"
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device admin enabled — MDM WIPE and LOCK commands are now active")
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device admin disabled — WIPE and LOCK commands will no longer work")
        // Notify MDM server that admin was revoked
        val prefs = context.getSharedPreferences("mdm_config", Context.MODE_PRIVATE)
        val serverUrl = prefs.getString("server_url", "https://54link.manus.space") ?: return
        val deviceToken = prefs.getString("device_token", null) ?: return

        // Fire-and-forget notification to server
        Thread {
            try {
                val url = java.net.URL("$serverUrl/api/trpc/mdm.reportAdminRevoked")
                val conn = url.openConnection() as java.net.HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("Authorization", "Bearer $deviceToken")
                conn.connectTimeout = 5_000
                conn.doOutput = true
                java.io.OutputStreamWriter(conn.outputStream).use {
                    it.write("{\"json\":{\"reason\":\"admin_disabled\"}}")
                }
                conn.responseCode
                conn.disconnect()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to notify server of admin revocation", e)
            }
        }.start()
    }

    override fun onPasswordChanged(context: Context, intent: Intent) {
        super.onPasswordChanged(context, intent)
        Log.i(TAG, "Device password changed")
    }

    override fun onPasswordFailed(context: Context, intent: Intent) {
        super.onPasswordFailed(context, intent)
        Log.w(TAG, "Device password attempt failed")
    }

    override fun onPasswordSucceeded(context: Context, intent: Intent) {
        super.onPasswordSucceeded(context, intent)
        Log.i(TAG, "Device password succeeded")
    }
}
