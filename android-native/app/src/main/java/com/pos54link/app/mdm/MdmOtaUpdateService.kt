package com.pos54link.app.mdm

import android.app.IntentService
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.FileProvider
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * 54Link MDM OTA Update Service
 *
 * Downloads an APK from the given URL and triggers the Android PackageInstaller.
 * On Android 8+, uses FileProvider to share the APK file with the installer.
 * On managed/kiosk devices with INSTALL_PACKAGES permission, the install is silent.
 *
 * Triggered by MdmCommandReceiver when an UPDATE command is received.
 */
@Suppress("DEPRECATION")
class MdmOtaUpdateService : IntentService("MdmOtaUpdateService") {

    companion object {
        private const val TAG = "MdmOtaUpdateService"
        private const val NOTIFICATION_CHANNEL_ID = "mdm_ota_updates"
        private const val NOTIFICATION_ID = 54001
    }

    override fun onHandleIntent(intent: Intent?) {
        val downloadUrl = intent?.getStringExtra("downloadUrl") ?: return
        Log.i(TAG, "Starting OTA update from: $downloadUrl")

        createNotificationChannel()
        showProgressNotification("Downloading update...")

        try {
            val apkFile = downloadApk(downloadUrl)
            showProgressNotification("Installing update...")
            installApk(apkFile)
            Log.i(TAG, "OTA update APK installed successfully")
        } catch (e: Exception) {
            Log.e(TAG, "OTA update failed", e)
            showErrorNotification("Update failed: ${e.message}")
        }
    }

    private fun downloadApk(downloadUrl: String): File {
        val apkFile = File(cacheDir, "54link_update_${System.currentTimeMillis()}.apk")
        val url = URL(downloadUrl)
        val conn = url.openConnection() as HttpURLConnection
        try {
            conn.connectTimeout = 30_000
            conn.readTimeout = 60_000
            conn.connect()

            val totalBytes = conn.contentLength.toLong()
            var downloadedBytes = 0L

            conn.inputStream.use { input ->
                FileOutputStream(apkFile).use { output ->
                    val buffer = ByteArray(8192)
                    var bytesRead: Int
                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                        downloadedBytes += bytesRead
                        if (totalBytes > 0) {
                            val progress = (downloadedBytes * 100 / totalBytes).toInt()
                            showProgressNotification("Downloading update... $progress%")
                        }
                    }
                }
            }
        } finally {
            conn.disconnect()
        }
        Log.i(TAG, "APK downloaded to ${apkFile.absolutePath} (${apkFile.length()} bytes)")
        return apkFile
    }

    private fun installApk(apkFile: File) {
        val apkUri: Uri = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            FileProvider.getUriForFile(
                this,
                "${packageName}.fileprovider",
                apkFile,
            )
        } else {
            Uri.fromFile(apkFile)
        }

        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(apkUri, "application/vnd.android.package-archive")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
        }
        startActivity(installIntent)
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                "MDM OTA Updates",
                NotificationManager.IMPORTANCE_LOW,
            ).apply {
                description = "54Link device management update notifications"
            }
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(channel)
        }
    }

    private fun showProgressNotification(message: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notification = NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("54Link MDM Update")
            .setContentText(message)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        nm.notify(NOTIFICATION_ID, notification)
    }

    private fun showErrorNotification(message: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val notification = NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle("54Link MDM Update Failed")
            .setContentText(message)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        nm.notify(NOTIFICATION_ID, notification)
    }
}
