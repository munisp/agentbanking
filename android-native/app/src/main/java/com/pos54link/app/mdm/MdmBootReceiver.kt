package com.pos54link.app.mdm

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * 54Link MDM Boot Receiver
 *
 * Automatically re-schedules the MDM HeartbeatWorker after device reboot.
 * Registered in AndroidManifest.xml with:
 *   <receiver android:name=".mdm.MdmBootReceiver" android:exported="true">
 *     <intent-filter>
 *       <action android:name="android.intent.action.BOOT_COMPLETED" />
 *       <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
 *       <action android:name="android.intent.action.LOCKED_BOOT_COMPLETED" />
 *     </intent-filter>
 *   </receiver>
 *
 * Requires: RECEIVE_BOOT_COMPLETED permission in AndroidManifest.xml
 */
class MdmBootReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "MdmBootReceiver"
        private const val WORK_NAME = "mdm_heartbeat_periodic"
    }

    override fun onReceive(context: Context, intent: Intent) {
        val action = intent.action
        Log.i(TAG, "Boot receiver triggered: $action")

        when (action) {
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            "android.intent.action.LOCKED_BOOT_COMPLETED" -> {
                scheduleHeartbeat(context)
            }
        }
    }

    private fun scheduleHeartbeat(context: Context) {
        try {
            val prefs = context.getSharedPreferences("mdm_config", Context.MODE_PRIVATE)
            val isEnrolled = prefs.getBoolean("is_enrolled", false)

            if (!isEnrolled) {
                Log.i(TAG, "Device not enrolled in MDM — skipping heartbeat schedule")
                return
            }

            val intervalMin = prefs.getInt("heartbeat_interval_min", 5).toLong()

            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val heartbeatRequest = PeriodicWorkRequestBuilder<MdmHeartbeatWorker>(
                intervalMin, TimeUnit.MINUTES,
                // Flex period: allow execution within last 1 minute of interval
                minOf(intervalMin, 1L), TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .setBackoffCriteria(
                    BackoffPolicy.EXPONENTIAL,
                    30, TimeUnit.SECONDS
                )
                .addTag("mdm_heartbeat")
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP, // Don't replace if already running
                heartbeatRequest
            )

            Log.i(TAG, "MDM HeartbeatWorker scheduled: every ${intervalMin}min after boot")

        } catch (e: Exception) {
            Log.e(TAG, "Failed to schedule heartbeat after boot", e)
        }
    }
}
