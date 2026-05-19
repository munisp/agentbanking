package com.pos54link.app.analytics

import android.content.Context
import com.google.firebase.analytics.FirebaseAnalytics
import com.google.firebase.remoteconfig.FirebaseRemoteConfig
import io.sentry.Sentry
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.sql.DriverManager
import java.util.*

// MARK: - Comprehensive Analytics with Platform Integration

class ComprehensiveAnalyticsManager(private val context: Context) {
    
    private val firebaseAnalytics = FirebaseAnalytics.getInstance(context)
    private val lakehouseURL = "https://lakehouse.remittance.app/api/v1/events"
    private val middlewareURL = "https://middleware.remittance.app/api/v1/analytics"
    private val eventQueue = mutableListOf<AnalyticsEvent>()
    private val batchSize = 50
    private val client = OkHttpClient()
    
    companion object {
        @Volatile
        private var instance: ComprehensiveAnalyticsManager? = null
        
        fun getInstance(context: Context): ComprehensiveAnalyticsManager {
            return instance ?: synchronized(this) {
                instance ?: ComprehensiveAnalyticsManager(context).also { instance = it }
            }
        }
    }
    
    init {
        startBatchProcessor()
    }
    
    // MARK: - Event Tracking
    
    fun trackEvent(name: String, parameters: Map<String, Any> = emptyMap()) {
        val event = AnalyticsEvent(
            id = UUID.randomUUID().toString(),
            name = name,
            parameters = parameters,
            timestamp = Date(),
            userId = getCurrentUserId(),
            sessionId = getCurrentSessionId(),
            deviceInfo = getDeviceInfo()
        )
        
        // Firebase Analytics
        val bundle = android.os.Bundle()
        parameters.forEach { (key, value) ->
            when (value) {
                is String -> bundle.putString(key, value)
                is Int -> bundle.putInt(key, value)
                is Long -> bundle.putLong(key, value)
                is Double -> bundle.putDouble(key, value)
                is Boolean -> bundle.putBoolean(key, value)
            }
        }
        firebaseAnalytics.logEvent(name, bundle)
        
        // Add to queue
        synchronized(eventQueue) {
            eventQueue.add(event)
            if (eventQueue.size >= batchSize) {
                flushEvents()
            }
        }
    }
    
    // MARK: - User Acquisition
    
    fun trackUserAcquisition(source: String, medium: String, campaign: String) {
        trackEvent("user_acquisition", mapOf(
            "source" to source,
            "medium" to medium,
            "campaign" to campaign,
            "install_date" to System.currentTimeMillis()
        ))
        
        storeAcquisitionData(source, medium, campaign)
    }
    
    private fun storeAcquisitionData(source: String, medium: String, campaign: String) {
        GlobalScope.launch(Dispatchers.IO) {
            try {
                val connection = DriverManager.getConnection(
                    "jdbc:postgresql://postgres.remittance.app:5432/remittance_analytics",
                    "analytics_user",
                    System.getenv("POSTGRES_PASSWORD") ?: ""
                )
                
                val sql = "INSERT INTO user_acquisition (user_id, source, medium, campaign, created_at) VALUES (?, ?, ?, ?, NOW())"
                val statement = connection.prepareStatement(sql)
                statement.setString(1, getCurrentUserId())
                statement.setString(2, source)
                statement.setString(3, medium)
                statement.setString(4, campaign)
                statement.executeUpdate()
                
                connection.close()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
    
    // MARK: - Feature Adoption
    
    fun trackFeatureUsage(featureName: String, firstTime: Boolean = false) {
        trackEvent("feature_used", mapOf(
            "feature_name" to featureName,
            "first_time" to firstTime
        ))
    }
    
    // MARK: - Session Tracking
    
    fun startSession() {
        val sessionId = UUID.randomUUID().toString()
        val prefs = context.getSharedPreferences("analytics", Context.MODE_PRIVATE)
        prefs.edit()
            .putString("current_session_id", sessionId)
            .putLong("session_start_time", System.currentTimeMillis())
            .apply()
        
        trackEvent("session_start", mapOf("session_id" to sessionId))
    }
    
    fun endSession() {
        val prefs = context.getSharedPreferences("analytics", Context.MODE_PRIVATE)
        val startTime = prefs.getLong("session_start_time", 0)
        val duration = System.currentTimeMillis() - startTime
        
        trackEvent("session_end", mapOf(
            "session_id" to getCurrentSessionId(),
            "duration" to duration
        ))
    }
    
    // MARK: - Lakehouse Integration
    
    private fun sendToLakehouse(event: String, data: Map<String, Any>) {
        GlobalScope.launch(Dispatchers.IO) {
            try {
                val json = JSONObject().apply {
                    put("event", event)
                    put("data", JSONObject(data))
                    put("timestamp", System.currentTimeMillis())
                    put("user_id", getCurrentUserId())
                }
                
                val body = json.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(lakehouseURL)
                    .post(body)
                    .addHeader("Authorization", "Bearer ${getLakehouseToken()}")
                    .build()
                
                client.newCall(request).execute()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
    
    // MARK: - Batch Processing
    
    private fun startBatchProcessor() {
        GlobalScope.launch(Dispatchers.IO) {
            while (true) {
                delay(60000) // 1 minute
                flushEvents()
            }
        }
    }
    
    private fun flushEvents() {
        val eventsToSend = synchronized(eventQueue) {
            val events = eventQueue.toList()
            eventQueue.clear()
            events
        }
        
        if (eventsToSend.isEmpty()) return
        
        sendToMiddleware(eventsToSend)
    }
    
    private fun sendToMiddleware(events: List<AnalyticsEvent>) {
        GlobalScope.launch(Dispatchers.IO) {
            try {
                val jsonArray = JSONArray()
                events.forEach { event ->
                    jsonArray.put(JSONObject(event.toDictionary()))
                }
                
                val body = jsonArray.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(middlewareURL)
                    .post(body)
                    .build()
                
                client.newCall(request).execute()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
    
    // MARK: - Helper Methods
    
    private fun getCurrentUserId(): String {
        val prefs = context.getSharedPreferences("analytics", Context.MODE_PRIVATE)
        return prefs.getString("user_id", "anonymous") ?: "anonymous"
    }
    
    private fun getCurrentSessionId(): String {
        val prefs = context.getSharedPreferences("analytics", Context.MODE_PRIVATE)
        return prefs.getString("current_session_id", "unknown") ?: "unknown"
    }
    
    private fun getDeviceInfo(): Map<String, Any> {
        return mapOf(
            "model" to android.os.Build.MODEL,
            "os_version" to android.os.Build.VERSION.RELEASE,
            "app_version" to context.packageManager.getPackageInfo(context.packageName, 0).versionName
        )
    }
    
    private fun getLakehouseToken(): String {
        return System.getenv("LAKEHOUSE_TOKEN") ?: ""
    }
}

data class AnalyticsEvent(
    val id: String,
    val name: String,
    val parameters: Map<String, Any>,
    val timestamp: Date,
    val userId: String,
    val sessionId: String,
    val deviceInfo: Map<String, Any>
) {
    fun toDictionary(): Map<String, Any> {
        return mapOf(
            "id" to id,
            "name" to name,
            "parameters" to parameters,
            "timestamp" to timestamp.time,
            "user_id" to userId,
            "session_id" to sessionId,
            "device_info" to deviceInfo
        )
    }
}

// MARK: - A/B Testing

class ABTestingManager(private val context: Context) {
    private val remoteConfig = FirebaseRemoteConfig.getInstance()
    
    fun initialize() {
        remoteConfig.setConfigSettingsAsync(
            com.google.firebase.remoteconfig.FirebaseRemoteConfigSettings.Builder()
                .setMinimumFetchIntervalInSeconds(3600)
                .build()
        )
        
        remoteConfig.setDefaultsAsync(mapOf(
            "onboarding_variant" to "control",
            "button_color" to "#007AFF",
            "pricing_variant" to "monthly"
        ))
        
        remoteConfig.fetchAndActivate()
    }
    
    fun getVariant(experiment: String): String {
        return remoteConfig.getString(experiment)
    }
}

// MARK: - Revenue Tracking with TigerBeetle

class RevenueTrackingManager {
    private val tigerBeetleURL = "https://tigerbeetle.remittance.app/api/v1/revenue"
    private val client = OkHttpClient()
    
    fun trackTransaction(amount: Double, currency: String, type: String) {
        GlobalScope.launch(Dispatchers.IO) {
            try {
                val json = JSONObject().apply {
                    put("id", UUID.randomUUID().toString())
                    put("amount", amount)
                    put("currency", currency)
                    put("type", type)
                    put("timestamp", System.currentTimeMillis())
                }
                
                val body = json.toString().toRequestBody("application/json".toMediaType())
                val request = Request.Builder()
                    .url(tigerBeetleURL)
                    .post(body)
                    .build()
                
                client.newCall(request).execute()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
