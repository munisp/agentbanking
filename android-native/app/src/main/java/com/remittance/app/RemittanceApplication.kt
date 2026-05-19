package com.pos54link.app

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import com.google.firebase.FirebaseApp
import com.google.firebase.crashlytics.FirebaseCrashlytics
import dagger.hilt.android.HiltAndroidApp
import timber.log.Timber
import javax.inject.Inject

@HiltAndroidApp
class RemittanceApplication : Application(), Configuration.Provider {
    
    @Inject
    lateinit var workerFactory: HiltWorkerFactory
    
    override fun onCreate() {
        super.onCreate()
        
        // Initialize Firebase
        FirebaseApp.initializeApp(this)
        
        // Initialize Timber for logging
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        } else {
            // Plant production tree (e.g., Crashlytics tree)
            Timber.plant(CrashlyticsTree())
        }
        
        // Initialize notification channels
        createNotificationChannels()
        
        // Configure Crashlytics
        configureCrashlytics()
        
        Timber.d("RemittanceApplication initialized")
    }
    
    override fun getWorkManagerConfiguration(): Configuration {
        return Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .setMinimumLoggingLevel(if (BuildConfig.DEBUG) android.util.Log.DEBUG else android.util.Log.ERROR)
            .build()
    }
    
    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val notificationManager = getSystemService(NotificationManager::class.java)
            
            // Default notification channel
            val defaultChannel = NotificationChannel(
                getString(R.string.default_notification_channel_id),
                getString(R.string.default_notification_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = "General notifications"
                enableLights(true)
                enableVibration(true)
            }
            
            // Transaction notification channel
            val transactionChannel = NotificationChannel(
                "transaction_notifications",
                "Transaction Notifications",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Notifications for transaction updates"
                enableLights(true)
                enableVibration(true)
            }
            
            // Security notification channel
            val securityChannel = NotificationChannel(
                "security_notifications",
                "Security Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Important security notifications"
                enableLights(true)
                enableVibration(true)
            }
            
            // Promotional notification channel
            val promotionalChannel = NotificationChannel(
                "promotional_notifications",
                "Promotions",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Promotional offers and updates"
            }
            
            notificationManager.createNotificationChannels(
                listOf(
                    defaultChannel,
                    transactionChannel,
                    securityChannel,
                    promotionalChannel
                )
            )
            
            Timber.d("Notification channels created")
        }
    }
    
    private fun configureCrashlytics() {
        FirebaseCrashlytics.getInstance().apply {
            setCrashlyticsCollectionEnabled(!BuildConfig.DEBUG)
            setCustomKey("app_version", BuildConfig.VERSION_NAME)
            setCustomKey("build_type", BuildConfig.BUILD_TYPE)
        }
    }
}

/**
 * Custom Timber tree for production that logs to Crashlytics
 */
class CrashlyticsTree : Timber.Tree() {
    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        if (priority == android.util.Log.VERBOSE || priority == android.util.Log.DEBUG) {
            return
        }
        
        val crashlytics = FirebaseCrashlytics.getInstance()
        
        // Log message to Crashlytics
        crashlytics.log("$tag: $message")
        
        // Log exception if present
        t?.let {
            crashlytics.recordException(it)
        }
    }
}
