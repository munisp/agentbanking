package com.pos54link.app.sim

import android.content.Context
import android.os.Build
import android.telephony.SubscriptionInfo
import android.telephony.SubscriptionManager
import android.telephony.TelephonyManager
import android.telephony.SignalStrength
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

/**
 * SimSlotManager — Dual/Multi-SIM management for POS terminals.
 *
 * Uses Android SubscriptionManager API to:
 *   1. Enumerate all active SIM slots (physical + eSIM)
 *   2. Read per-slot carrier name, MCC/MNC, signal strength, ICCID
 *   3. Set preferred data SIM for transaction routing
 *   4. Monitor SIM state changes via broadcast receiver
 *   5. Score each SIM slot for intelligent failover decisions
 *
 * Requires: READ_PHONE_STATE permission (runtime + manifest)
 */
class SimSlotManager(private val context: Context) {

    companion object {
        private const val TAG = "SimSlotManager"

        // Nigerian MNO MCC/MNC codes
        val NIGERIAN_CARRIERS = mapOf(
            "62130" to CarrierInfo("MTN", "MTN Nigeria", "mtn"),
            "62120" to CarrierInfo("MTN", "MTN Nigeria", "mtn"),
            "62160" to CarrierInfo("MTN", "MTN Nigeria", "mtn"),
            "62150" to CarrierInfo("GLO", "Globacom", "glo"),
            "62140" to CarrierInfo("AIRTEL", "Airtel Nigeria", "airtel"),
            "62127" to CarrierInfo("AIRTEL", "Airtel Nigeria", "airtel"),
            "62125" to CarrierInfo("AIRTEL", "Airtel Nigeria", "airtel"),
            "62122" to CarrierInfo("9MOBILE", "9mobile (Etisalat)", "9mobile"),
            "62160" to CarrierInfo("9MOBILE", "9mobile (Etisalat)", "9mobile"),
        )

        // Scoring weights for SIM selection
        const val WEIGHT_SIGNAL = 0.30
        const val WEIGHT_LATENCY = 0.25
        const val WEIGHT_PACKET_LOSS = 0.20
        const val WEIGHT_RELIABILITY = 0.15
        const val WEIGHT_COST = 0.10
    }

    data class CarrierInfo(val code: String, val name: String, val slug: String)

    data class SimSlotInfo(
        val slotIndex: Int,
        val subscriptionId: Int,
        val iccid: String,
        val carrierName: String,
        val carrierCode: String,
        val mccMnc: String,
        val isActive: Boolean,
        val isDataPreferred: Boolean,
        val signalStrengthDbm: Int,
        val networkType: String,
        val isRoaming: Boolean,
        val score: Int
    )

    // Per-slot reliability tracking (persisted via SharedPreferences)
    private val slotReliability = ConcurrentHashMap<Int, SlotReliabilityStats>()

    data class SlotReliabilityStats(
        var totalTransactions: Long = 0,
        var successfulTransactions: Long = 0,
        var avgLatencyMs: Double = 0.0,
        var lastFailureTimestamp: Long = 0,
        var consecutiveFailures: Int = 0
    ) {
        val successRate: Double get() = if (totalTransactions > 0) successfulTransactions.toDouble() / totalTransactions else 0.5
    }

    init {
        loadReliabilityStats()
    }

    /**
     * Enumerate all available SIM slots with full metadata.
     */
    fun getAvailableSlots(): List<SimSlotInfo> {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP_MR1) {
            return emptyList()
        }

        val subscriptionManager = context.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE) as? SubscriptionManager
            ?: return emptyList()

        val activeSubscriptions: List<SubscriptionInfo> = try {
            subscriptionManager.activeSubscriptionInfoList ?: emptyList()
        } catch (e: SecurityException) {
            Log.w(TAG, "READ_PHONE_STATE permission not granted", e)
            return emptyList()
        }

        val defaultDataSubId = SubscriptionManager.getDefaultDataSubscriptionId()

        return activeSubscriptions.map { sub ->
            val tm = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
                    createForSubscriptionId(sub.subscriptionId)
            } else {
                context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            }

            val mccMnc = "${sub.mcc}${sub.mnc}"
            val carrierInfo = NIGERIAN_CARRIERS[mccMnc]
            val signalDbm = getSignalStrengthForSlot(sub.simSlotIndex)
            val networkType = getNetworkTypeName(tm)
            val reliability = slotReliability[sub.simSlotIndex] ?: SlotReliabilityStats()
            val score = computeSlotScore(signalDbm, reliability, networkType)

            SimSlotInfo(
                slotIndex = sub.simSlotIndex,
                subscriptionId = sub.subscriptionId,
                iccid = sub.iccId ?: "",
                carrierName = carrierInfo?.name ?: sub.carrierName?.toString() ?: "Unknown",
                carrierCode = carrierInfo?.code ?: sub.carrierName?.toString()?.uppercase() ?: "UNKNOWN",
                mccMnc = mccMnc,
                isActive = true,
                isDataPreferred = sub.subscriptionId == defaultDataSubId,
                signalStrengthDbm = signalDbm,
                networkType = networkType,
                isRoaming = try { tm.isNetworkRoaming } catch (_: Exception) { false },
                score = score
            )
        }
    }

    /**
     * Get the best SIM slot for a given transaction type.
     * Financial transactions prefer reliability over signal strength.
     */
    fun getBestSlotForTransaction(transactionType: String): SimSlotInfo? {
        val slots = getAvailableSlots()
        if (slots.isEmpty()) return null

        return when (transactionType) {
            "financial", "payment", "transfer", "settlement" -> {
                // Financial transactions: prioritize reliability + low latency
                slots.maxByOrNull { slot ->
                    val reliability = slotReliability[slot.slotIndex] ?: SlotReliabilityStats()
                    (reliability.successRate * 40) +
                    (normalizeSignal(slot.signalStrengthDbm) * 25) +
                    (normalizeLatency(reliability.avgLatencyMs) * 25) +
                    (networkTypeBonus(slot.networkType) * 10)
                }
            }
            else -> {
                // Non-financial: use standard score (signal-weighted)
                slots.maxByOrNull { it.score }
            }
        }
    }

    /**
     * Switch the preferred data SIM to the given slot.
     * Returns true if the switch was successful.
     */
    fun switchDataSim(targetSlotIndex: Int): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP_MR1) return false

        val subscriptionManager = context.getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE) as? SubscriptionManager
            ?: return false

        val targetSub = try {
            subscriptionManager.activeSubscriptionInfoList?.find { it.simSlotIndex == targetSlotIndex }
        } catch (e: SecurityException) {
            Log.e(TAG, "Cannot access subscription info", e)
            return false
        }

        if (targetSub == null) {
            Log.w(TAG, "No active subscription in slot $targetSlotIndex")
            return false
        }

        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // Android 10+: Use SubscriptionManager.setDefaultDataSubId (requires carrier privileges or MODIFY_PHONE_STATE)
                SubscriptionManager.setDefaultDataSubId(targetSub.subscriptionId)
                Log.i(TAG, "Switched data SIM to slot $targetSlotIndex (subId=${targetSub.subscriptionId})")
                true
            } else {
                Log.w(TAG, "Programmatic SIM switching requires Android 10+")
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to switch data SIM to slot $targetSlotIndex", e)
            false
        }
    }

    /**
     * Record a transaction result for reliability tracking.
     */
    fun recordTransactionResult(slotIndex: Int, success: Boolean, latencyMs: Long) {
        val stats = slotReliability.getOrPut(slotIndex) { SlotReliabilityStats() }
        stats.totalTransactions++
        if (success) {
            stats.successfulTransactions++
            stats.consecutiveFailures = 0
            // Exponential moving average for latency
            stats.avgLatencyMs = if (stats.totalTransactions <= 1) {
                latencyMs.toDouble()
            } else {
                stats.avgLatencyMs * 0.8 + latencyMs * 0.2
            }
        } else {
            stats.lastFailureTimestamp = System.currentTimeMillis()
            stats.consecutiveFailures++
        }
        saveReliabilityStats()
    }

    /**
     * Collect SIM telemetry as JSON for the probe payload.
     */
    fun collectTelemetry(): JSONObject {
        val result = JSONObject()
        val slotsArray = JSONArray()
        val slots = getAvailableSlots()

        for (slot in slots) {
            val slotJson = JSONObject().apply {
                put("slotIndex", slot.slotIndex)
                put("subscriptionId", slot.subscriptionId)
                put("iccid", slot.iccid)
                put("carrierName", slot.carrierName)
                put("carrierCode", slot.carrierCode)
                put("mccMnc", slot.mccMnc)
                put("isDataPreferred", slot.isDataPreferred)
                put("signalStrengthDbm", slot.signalStrengthDbm)
                put("networkType", slot.networkType)
                put("isRoaming", slot.isRoaming)
                put("score", slot.score)
            }
            slotsArray.put(slotJson)
        }

        result.put("slots", slotsArray)
        result.put("slotCount", slots.size)
        result.put("preferredSlot", slots.firstOrNull { it.isDataPreferred }?.slotIndex ?: -1)
        result.put("bestSlotForFinancial", getBestSlotForTransaction("financial")?.slotIndex ?: -1)
        result.put("timestamp", System.currentTimeMillis())

        return result
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private fun getSignalStrengthForSlot(slotIndex: Int): Int {
        return try {
            val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val ss = tm.signalStrength
                ss?.level?.let { level ->
                    // Convert 0-4 level to approximate dBm
                    when (level) {
                        4 -> -60
                        3 -> -70
                        2 -> -80
                        1 -> -90
                        else -> -100
                    }
                } ?: -85
            } else {
                -85 // Default approximate value for older Android
            }
        } catch (e: Exception) {
            -85
        }
    }

    private fun getNetworkTypeName(tm: TelephonyManager): String {
        return try {
            when (tm.dataNetworkType) {
                TelephonyManager.NETWORK_TYPE_LTE -> "4G"
                TelephonyManager.NETWORK_TYPE_NR -> "5G"
                TelephonyManager.NETWORK_TYPE_HSDPA, TelephonyManager.NETWORK_TYPE_HSUPA,
                TelephonyManager.NETWORK_TYPE_HSPA, TelephonyManager.NETWORK_TYPE_HSPAP -> "3G"
                TelephonyManager.NETWORK_TYPE_EDGE, TelephonyManager.NETWORK_TYPE_GPRS -> "2G"
                TelephonyManager.NETWORK_TYPE_CDMA, TelephonyManager.NETWORK_TYPE_EVDO_0 -> "3G"
                else -> "unknown"
            }
        } catch (e: Exception) {
            "unknown"
        }
    }

    private fun computeSlotScore(signalDbm: Int, reliability: SlotReliabilityStats, networkType: String): Int {
        val signalScore = normalizeSignal(signalDbm) * WEIGHT_SIGNAL
        val latencyScore = normalizeLatency(reliability.avgLatencyMs) * WEIGHT_LATENCY
        val lossScore = (1.0 - (reliability.consecutiveFailures.coerceAtMost(5) / 5.0)) * WEIGHT_PACKET_LOSS * 100
        val reliabilityScore = reliability.successRate * WEIGHT_RELIABILITY * 100
        val networkBonus = networkTypeBonus(networkType) * WEIGHT_COST

        return (signalScore + latencyScore + lossScore + reliabilityScore + networkBonus).toInt().coerceIn(0, 100)
    }

    private fun normalizeSignal(dbm: Int): Double {
        // Map -120..-50 dBm to 0..100
        return ((dbm + 120).toDouble() / 70.0 * 100).coerceIn(0.0, 100.0)
    }

    private fun normalizeLatency(avgMs: Double): Double {
        // Lower latency = higher score. Map 0..2000ms to 100..0
        return (100.0 - (avgMs / 20.0)).coerceIn(0.0, 100.0)
    }

    private fun networkTypeBonus(type: String): Double {
        return when (type) {
            "5G" -> 100.0
            "4G" -> 80.0
            "3G" -> 40.0
            "2G" -> 10.0
            else -> 20.0
        }
    }

    private fun loadReliabilityStats() {
        try {
            val prefs = context.getSharedPreferences("sim_reliability", Context.MODE_PRIVATE)
            for (i in 0..3) {
                val total = prefs.getLong("slot_${i}_total", 0)
                if (total > 0) {
                    slotReliability[i] = SlotReliabilityStats(
                        totalTransactions = total,
                        successfulTransactions = prefs.getLong("slot_${i}_success", 0),
                        avgLatencyMs = prefs.getFloat("slot_${i}_latency", 0f).toDouble(),
                        lastFailureTimestamp = prefs.getLong("slot_${i}_last_fail", 0),
                        consecutiveFailures = prefs.getInt("slot_${i}_consec_fail", 0)
                    )
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to load reliability stats", e)
        }
    }

    private fun saveReliabilityStats() {
        try {
            val editor = context.getSharedPreferences("sim_reliability", Context.MODE_PRIVATE).edit()
            for ((slot, stats) in slotReliability) {
                editor.putLong("slot_${slot}_total", stats.totalTransactions)
                editor.putLong("slot_${slot}_success", stats.successfulTransactions)
                editor.putFloat("slot_${slot}_latency", stats.avgLatencyMs.toFloat())
                editor.putLong("slot_${slot}_last_fail", stats.lastFailureTimestamp)
                editor.putInt("slot_${slot}_consec_fail", stats.consecutiveFailures)
            }
            editor.apply()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to save reliability stats", e)
        }
    }
}
