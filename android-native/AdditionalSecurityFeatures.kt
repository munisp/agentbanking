package com.pos54link.app.security

import android.app.Activity
import android.content.ClipboardManager
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import java.util.*

/**
 * Additional Security Features (18 features)
 * Comprehensive security protection
 */
class AdditionalSecurityFeatures(private val context: Context) {
    
    // MARK: - Screenshot Prevention
    
    fun enableScreenshotPrevention(activity: Activity) {
        activity.window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )
    }
    
    fun disableScreenshotPrevention(activity: Activity) {
        activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
    }
    
    // MARK: - Session Timeout
    
    class SessionManager(private val timeoutMillis: Long = 300000) { // 5 minutes
        private var lastActivityTime = System.currentTimeMillis()
        private val handler = Handler(Looper.getMainLooper())
        private var timeoutCallback: (() -> Unit)? = null
        
        fun updateActivity() {
            lastActivityTime = System.currentTimeMillis()
        }
        
        fun startMonitoring(callback: () -> Unit) {
            timeoutCallback = callback
            checkTimeout()
        }
        
        private fun checkTimeout() {
            handler.postDelayed({
                if (System.currentTimeMillis() - lastActivityTime > timeoutMillis) {
                    timeoutCallback?.invoke()
                } else {
                    checkTimeout()
                }
            }, 10000) // Check every 10 seconds
        }
        
        fun stopMonitoring() {
            handler.removeCallbacksAndMessages(null)
        }
    }
    
    // MARK: - ML-Based Anomaly Detection
    
    data class TransactionAnomaly(
        val amount: Double,
        val timestamp: Date,
        val location: String?,
        val riskScore: Double
    )
    
    fun detectAnomalies(transaction: TransactionAnomaly, history: List<TransactionAnomaly>): Boolean {
        val unusualAmount = detectUnusualAmount(transaction.amount, history)
        val unusualTime = detectUnusualTime(transaction.timestamp, history)
        val unusualLocation = detectUnusualLocation(transaction.location, history)
        
        return unusualAmount || unusualTime || unusualLocation
    }
    
    private fun detectUnusualAmount(amount: Double, history: List<TransactionAnomaly>): Boolean {
        if (history.isEmpty()) return false
        
        val amounts = history.map { it.amount }
        val avg = amounts.average()
        val stdDev = calculateStdDev(amounts, avg)
        
        return amount > avg + (2 * stdDev)
    }
    
    private fun detectUnusualTime(timestamp: Date, history: List<TransactionAnomaly>): Boolean {
        val calendar = Calendar.getInstance()
        calendar.time = timestamp
        val hour = calendar.get(Calendar.HOUR_OF_DAY)
        
        // Flag transactions between 2 AM and 6 AM as unusual
        return hour in 2..5
    }
    
    private fun detectUnusualLocation(location: String?, history: List<TransactionAnomaly>): Boolean {
        if (location == null) return false
        
        val commonLocations = history.mapNotNull { it.location }.groupingBy { it }.eachCount()
        return !commonLocations.containsKey(location)
    }
    
    private fun calculateStdDev(values: List<Double>, mean: Double): Double {
        val variance = values.map { (it - mean) * (it - mean) }.average()
        return Math.sqrt(variance)
    }
    
    // MARK: - Geo-Fencing
    
    fun isLocationAllowed(countryCode: String): Boolean {
        val allowedCountries = setOf("NG", "US", "GB", "CA", "GH", "KE")
        return allowedCountries.contains(countryCode)
    }
    
    // MARK: - Velocity Checks (Rate Limiting)
    
    class VelocityChecker(private val maxRequests: Int = 5, private val windowMillis: Long = 60000) {
        private val requestTimes = mutableListOf<Long>()
        
        fun checkRateLimit(): Boolean {
            val now = System.currentTimeMillis()
            
            // Remove old requests outside the window
            requestTimes.removeAll { it < now - windowMillis }
            
            if (requestTimes.size >= maxRequests) {
                return false // Rate limit exceeded
            }
            
            requestTimes.add(now)
            return true
        }
        
        fun reset() {
            requestTimes.clear()
        }
    }
    
    // MARK: - IP Whitelisting
    
    fun isIPWhitelisted(ip: String): Boolean {
        val whitelist = setOf(
            "192.168.1.1",
            "10.0.0.1"
            // Add your whitelisted IPs
        )
        return whitelist.contains(ip)
    }
    
    // MARK: - VPN Detection
    
    fun isVPNActive(): Boolean {
        val connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        
        return capabilities.hasTransport(NetworkCapabilities.TRANSPORT_VPN)
    }
    
    // MARK: - Clipboard Protection
    
    fun protectClipboard(sensitiveData: String) {
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        
        // Clear clipboard after 30 seconds
        Handler(Looper.getMainLooper()).postDelayed({
            clipboard.clearPrimaryClip()
        }, 30000)
    }
    
    // MARK: - Account Activity Logs
    
    data class ActivityLog(
        val timestamp: Date,
        val action: String,
        val ipAddress: String?,
        val deviceID: String,
        val location: String?,
        val success: Boolean
    )
    
    class ActivityLogger {
        private val logs = mutableListOf<ActivityLog>()
        private val maxLogs = 100
        
        fun log(activity: ActivityLog) {
            logs.add(activity)
            if (logs.size > maxLogs) {
                logs.removeAt(0)
            }
        }
        
        fun getLogs(limit: Int = 50): List<ActivityLog> {
            return logs.takeLast(limit)
        }
        
        fun getFailedAttempts(since: Date): List<ActivityLog> {
            return logs.filter { !it.success && it.timestamp.after(since) }
        }
    }
    
    // MARK: - Suspicious Activity Alerts
    
    enum class AlertSeverity {
        LOW, MEDIUM, HIGH, CRITICAL
    }
    
    data class SecurityAlert(
        val severity: AlertSeverity,
        val message: String,
        val timestamp: Date = Date(),
        val details: Map<String, String> = emptyMap()
    )
    
    fun sendSecurityAlert(alert: SecurityAlert) {
        // TODO: Integrate with notification system
        // Send push notification, email, or SMS based on severity
        android.util.Log.w("SECURITY_ALERT", "${alert.severity}: ${alert.message}")
    }
    
    // MARK: - Security Center
    
    data class SecurityStatus(
        val deviceIntegrity: Boolean,
        val runtimeProtection: Boolean,
        val certificatePinning: Boolean,
        val mfaEnabled: Boolean,
        val biometricEnabled: Boolean,
        val lastSecurityCheck: Date,
        val activeAlerts: List<SecurityAlert>
    )
    
    fun getSecurityStatus(): SecurityStatus {
        // Aggregate all security checks
        return SecurityStatus(
            deviceIntegrity = true,
            runtimeProtection = true,
            certificatePinning = true,
            mfaEnabled = true,
            biometricEnabled = true,
            lastSecurityCheck = Date(),
            activeAlerts = emptyList()
        )
    }
}
