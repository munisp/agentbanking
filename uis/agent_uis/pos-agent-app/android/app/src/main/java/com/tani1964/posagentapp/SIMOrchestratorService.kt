package com.tani1964.posagentapp

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import java.io.File
import java.io.FileOutputStream

/**
 * Android foreground service that runs the sim-orchestrator Rust binary as a
 * child process. Keeps the binary alive (auto-restarts on crash), survives
 * app backgrounding, and shows a persistent low-priority notification as
 * required by Android for foreground services.
 *
 * The binary is bundled in src/main/assets/sim-orchestrator and is copied to
 * the app's private filesDir on every start (idempotent).
 */
class SIMOrchestratorService : Service() {

    companion object {
        private const val TAG            = "SIMOrchestrator"
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID     = "sim_orchestrator_channel"
        private const val BINARY_NAME    = "sim-orchestrator"
        private const val PREFS_NAME     = "sim_config"

        fun start(context: Context) {
            val intent = Intent(context, SIMOrchestratorService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, SIMOrchestratorService::class.java))
        }
    }

    private var process: Process? = null
    private var monitorThread: Thread? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification("Starting…"))
        startOrchestrator()
        return START_STICKY // Android restarts this service if it's killed
    }

    override fun onDestroy() {
        monitorThread?.interrupt()
        process?.destroy()
        super.onDestroy()
    }

    // ── Binary management ────────────────────────────────────────────────────

    private fun deployBinary(): File? {
        val dest = File(filesDir, BINARY_NAME)
        return try {
            assets.open(BINARY_NAME).use { input ->
                FileOutputStream(dest).use { output -> input.copyTo(output) }
            }
            dest.setExecutable(true, false)
            Log.i(TAG, "Binary deployed → ${dest.absolutePath}")
            dest
        } catch (e: Exception) {
            Log.e(TAG, "Failed to deploy binary", e)
            null
        }
    }

    // ── Orchestrator process ─────────────────────────────────────────────────

    private fun startOrchestrator() {
        val binary = deployBinary() ?: run { stopSelf(); return }

        val prefs      = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val agentCode  = prefs.getString("agent_code",  "AGT001")  ?: "AGT001"
        val terminalId = prefs.getString("terminal_id", Build.SERIAL) ?: Build.SERIAL
        val platformUrl = prefs.getString("platform_url", "https://api.54agent.io") ?: "https://api.54agent.io"
        val apiKey      = prefs.getString("api_key", "54agent-sim-orchestrator-default-key") ?: "54agent-sim-orchestrator-default-key"

        monitorThread = Thread {
            while (!Thread.currentThread().isInterrupted) {
                try {
                    Log.i(TAG, "Launching sim-orchestrator (agent=$agentCode terminal=$terminalId)")
                    updateNotification("Running · $agentCode")

                    process = ProcessBuilder(binary.absolutePath)
                        .redirectErrorStream(true)
                        .apply {
                            environment().apply {
                                put("SIM_AGENT_CODE",           agentCode)
                                put("SIM_TERMINAL_ID",          terminalId)
                                put("PLATFORM_API_URL",         platformUrl)
                                put("SIM_API_KEY",              apiKey)
                                put("RUST_LOG",                 "info")
                                put("SIM_PROBE_INTERVAL_SECS",  "30")
                                put("SIM_RELAY_FLUSH_SECS",     "60")
                                put("SIM_WATCHDOG_ENABLED",     "true")
                            }
                        }
                        .start()

                    // Pipe stdout/stderr to logcat
                    process!!.inputStream.bufferedReader().use { reader ->
                        reader.forEachLine { Log.i(TAG, it) }
                    }

                    val code = process!!.waitFor()
                    Log.w(TAG, "sim-orchestrator exited (code=$code) — restarting in 5 s")
                    updateNotification("Restarting…")
                    Thread.sleep(5_000)

                } catch (e: InterruptedException) {
                    Log.i(TAG, "Monitor thread interrupted — stopping")
                    break
                } catch (e: Exception) {
                    Log.e(TAG, "Orchestrator error", e)
                    try { Thread.sleep(5_000) } catch (_: InterruptedException) { break }
                }
            }
        }.also { it.isDaemon = true; it.start() }
    }

    // ── Notification ─────────────────────────────────────────────────────────

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "SIM Orchestrator",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Monitors SIM signal quality and performs automatic carrier failover"
                setShowBadge(false)
            }
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification(status: String): Notification {
        val tapIntent = packageManager.getLaunchIntentForPackage(packageName)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, tapIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("SIM Orchestrator")
            .setContentText(status)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setSilent(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification(status: String) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(status))
    }
}
