package com.tani1964.posagentapp

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Restarts the SIM orchestrator service automatically after the device reboots.
 * Requires RECEIVE_BOOT_COMPLETED permission in AndroidManifest.xml.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            SIMOrchestratorService.start(context)
        }
    }
}
