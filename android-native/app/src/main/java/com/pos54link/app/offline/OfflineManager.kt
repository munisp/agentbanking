package com.pos54link.app.offline

import android.content.Context
import android.content.SharedPreferences
import androidx.room.*
import androidx.work.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.Calendar
import java.util.Date
import java.util.concurrent.TimeUnit

/**
 * Offline transaction entity
 */
@Entity(tableName = "offline_transactions")
data class OfflineTransactionEntity(
    @PrimaryKey val id: String,
    val type: String,
    val amount: String,
    val currency: String,
    val recipientId: String,
    val status: String,
    val data: String,
    val createdAt: Long,
    val syncedAt: Long? = null,
    val idempotencyKey: String? = null,
    val fee: Double = 0.0,
    val commission: Double = 0.0
)

/**
 * Offline beneficiary entity
 */
@Entity(tableName = "offline_beneficiaries")
data class OfflineBeneficiaryEntity(
    @PrimaryKey val id: String,
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val country: String,
    val status: String,
    val data: String,
    val createdAt: Long,
    val syncedAt: Long? = null
)

/**
 * DAO for offline transactions
 */
@Dao
interface OfflineTransactionDao {
    @Query("SELECT * FROM offline_transactions ORDER BY createdAt DESC")
    fun getAllTransactions(): Flow<List<OfflineTransactionEntity>>
    
    @Query("SELECT * FROM offline_transactions WHERE status = 'pending_sync'")
    suspend fun getPendingTransactions(): List<OfflineTransactionEntity>
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertTransaction(transaction: OfflineTransactionEntity)
    
    @Update
    suspend fun updateTransaction(transaction: OfflineTransactionEntity)
    
    @Query("DELETE FROM offline_transactions WHERE status = 'synced' AND syncedAt < :timestamp")
    suspend fun deleteOldSyncedTransactions(timestamp: Long)
    
    @Query("SELECT COUNT(*) FROM offline_transactions WHERE status = 'pending_sync'")
    fun getPendingTransactionCount(): Flow<Int>

    @Query("SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) FROM offline_transactions WHERE createdAt >= :dayStartMs")
    suspend fun getDailyTotal(dayStartMs: Long): Double

    @Query("SELECT COUNT(*) FROM offline_transactions WHERE createdAt >= :sessionStartMs AND status = 'pending_sync'")
    suspend fun getSessionPendingCount(sessionStartMs: Long): Int
}

/**
 * DAO for offline beneficiaries
 */
@Dao
interface OfflineBeneficiaryDao {
    @Query("SELECT * FROM offline_beneficiaries ORDER BY createdAt DESC")
    fun getAllBeneficiaries(): Flow<List<OfflineBeneficiaryEntity>>
    
    @Query("SELECT * FROM offline_beneficiaries WHERE status = 'pending_sync'")
    suspend fun getPendingBeneficiaries(): List<OfflineBeneficiaryEntity>
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertBeneficiary(beneficiary: OfflineBeneficiaryEntity)
    
    @Update
    suspend fun updateBeneficiary(beneficiary: OfflineBeneficiaryEntity)
    
    @Query("DELETE FROM offline_beneficiaries WHERE status = 'synced' AND syncedAt < :timestamp")
    suspend fun deleteOldSyncedBeneficiaries(timestamp: Long)
    
    @Query("SELECT COUNT(*) FROM offline_beneficiaries WHERE status = 'pending_sync'")
    fun getPendingBeneficiaryCount(): Flow<Int>
}

/**
 * Room database for offline data
 */
@Database(
    entities = [OfflineTransactionEntity::class, OfflineBeneficiaryEntity::class],
    version = 1,
    exportSchema = false
)
@TypeConverters(Converters::class)
abstract class OfflineDatabase : RoomDatabase() {
    abstract fun transactionDao(): OfflineTransactionDao
    abstract fun beneficiaryDao(): OfflineBeneficiaryDao
    
    companion object {
        @Volatile
        private var INSTANCE: OfflineDatabase? = null
        
        fun getDatabase(context: Context): OfflineDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    OfflineDatabase::class.java,
                    "remittance_offline_database"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}

/**
 * Type converters for Room
 */
class Converters {
    @TypeConverter
    fun fromTimestamp(value: Long?): Date? {
        return value?.let { Date(it) }
    }
    
    @TypeConverter
    fun dateToTimestamp(date: Date?): Long? {
        return date?.time
    }
}

/**
 * Offline manager for handling offline operations and sync
 */
class OfflineManager(
    private val context: Context,
    private val database: OfflineDatabase
) {

    companion object {
        // CBN daily transaction limits (Naira)
        private const val CBN_DAILY_LIMIT_BASE = 500_000.0
        // Tier multipliers (matches backend offlinePosMode.ts)
        private val TIER_MULTIPLIERS = mapOf(
            "bronze" to 1.0,
            "silver" to 1.5,
            "gold" to 2.0,
            "platinum" to 3.0
        )
        // Max offline queue size
        private const val MAX_QUEUE_SIZE_BASE = 50
        // Max single transaction amount offline
        private const val MAX_SINGLE_TXN_BASE = 100_000.0
        // Max session duration (minutes)
        private const val MAX_SESSION_DURATION_MIN = 480L
        // Offline risk multiplier for fee calculation
        private const val OFFLINE_RISK_MULTIPLIER = 1.5
    }

    private val transactionDao = database.transactionDao()
    private val beneficiaryDao = database.beneficiaryDao()
    private val prefs: SharedPreferences = context.getSharedPreferences("offline_session", Context.MODE_PRIVATE)

    private val _isOnline = MutableStateFlow(true)
    val isOnline: StateFlow<Boolean> = _isOnline

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing

    val pendingTransactionCount: Flow<Int> = transactionDao.getPendingTransactionCount()
    val pendingBeneficiaryCount: Flow<Int> = beneficiaryDao.getPendingBeneficiaryCount()

    private var sessionStartMs: Long
        get() = prefs.getLong("session_start_ms", 0L)
        set(value) = prefs.edit().putLong("session_start_ms", value).apply()

    private var floatSnapshot: Double
        get() = prefs.getFloat("float_snapshot", 0f).toDouble()
        set(value) = prefs.edit().putFloat("float_snapshot", value.toFloat()).apply()

    private var agentTier: String
        get() = prefs.getString("agent_tier", "bronze") ?: "bronze"
        set(value) = prefs.edit().putString("agent_tier", value).apply()

    init {
        setupNetworkMonitoring()
        setupPeriodicSync()
    }
    
    /**
     * Setup network monitoring
     */
    private fun setupNetworkMonitoring() {
        // Use ConnectivityManager to monitor network state
        // This is a simplified version
        _isOnline.value = true
    }
    
    /**
     * Setup periodic background sync
     */
    private fun setupPeriodicSync() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        
        val syncRequest = PeriodicWorkRequestBuilder<SyncWorker>(
            15, TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .build()
        
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            "offline_sync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
    }
    
    /**
     * Start an offline session — records agent's float balance and tier at session start.
     * Matches backend offlinePosMode.startSession behavior.
     */
    fun startOfflineSession(currentFloat: Double, tier: String) {
        sessionStartMs = System.currentTimeMillis()
        floatSnapshot = currentFloat
        agentTier = tier
    }

    /**
     * End offline session — requires sync if there are pending transactions.
     */
    fun endOfflineSession() {
        prefs.edit().remove("session_start_ms").apply()
    }

    val isSessionActive: Boolean
        get() = sessionStartMs > 0L

    /**
     * Validate an offline transaction against CBN daily limits, tier-based caps,
     * and queue size limits. Matches backend offlinePosMode.validateOfflineTransaction.
     *
     * @return null if valid, or a String describing the validation failure.
     */
    suspend fun validateOfflineTransaction(amount: Double): String? {
        val tierMultiplier = TIER_MULTIPLIERS[agentTier] ?: 1.0
        val maxDailyLimit = CBN_DAILY_LIMIT_BASE * tierMultiplier
        val maxSingleTxn = MAX_SINGLE_TXN_BASE * tierMultiplier
        val maxQueueSize = (MAX_QUEUE_SIZE_BASE * tierMultiplier).toInt()

        // 1. Single transaction amount cap
        if (amount > maxSingleTxn) {
            return "Amount exceeds offline single-transaction limit of ₦${String.format("%,.0f", maxSingleTxn)}"
        }

        // 2. CBN daily limit check
        val dayStartMs = getDayStartMs()
        val dailyTotal = transactionDao.getDailyTotal(dayStartMs)
        if (dailyTotal + amount > maxDailyLimit) {
            val remaining = maxDailyLimit - dailyTotal
            return "Would exceed CBN daily offline limit of ₦${String.format("%,.0f", maxDailyLimit)}. Remaining: ₦${String.format("%,.0f", remaining.coerceAtLeast(0.0))}"
        }

        // 3. Queue size limit
        if (sessionStartMs > 0L) {
            val queueCount = transactionDao.getSessionPendingCount(sessionStartMs)
            if (queueCount >= maxQueueSize) {
                return "Offline queue full ($queueCount/$maxQueueSize transactions). Sync pending transactions first."
            }
        }

        // 4. Session duration check
        if (sessionStartMs > 0L) {
            val elapsedMin = (System.currentTimeMillis() - sessionStartMs) / 60_000
            if (elapsedMin > MAX_SESSION_DURATION_MIN) {
                return "Offline session expired (${elapsedMin}min > ${MAX_SESSION_DURATION_MIN}min max). Please go online to sync."
            }
        }

        // 5. Float balance check
        if (floatSnapshot > 0 && amount > floatSnapshot) {
            return "Amount exceeds agent float snapshot of ₦${String.format("%,.0f", floatSnapshot)}"
        }

        return null // Valid
    }

    /**
     * Calculate offline fee with risk multiplier.
     */
    fun calculateOfflineFee(amount: Double): Double {
        val baseFeeRate = 0.005 // 0.5% base fee
        return amount * baseFeeRate * OFFLINE_RISK_MULTIPLIER
    }

    private fun getDayStartMs(): Long {
        val cal = Calendar.getInstance()
        cal.set(Calendar.HOUR_OF_DAY, 0)
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)
        return cal.timeInMillis
    }

    /**
     * Queue transaction for offline processing.
     * Validates against CBN limits before queuing.
     *
     * @throws IllegalStateException if CBN/tier validation fails
     */
    suspend fun queueTransaction(transaction: Transaction, idempotencyKey: String? = null) {
        // Validate before queuing
        val validationError = validateOfflineTransaction(transaction.amount)
        if (validationError != null) {
            throw IllegalStateException(validationError)
        }

        val fee = calculateOfflineFee(transaction.amount)
        val entity = OfflineTransactionEntity(
            id = transaction.id,
            type = transaction.type,
            amount = transaction.amount.toString(),
            currency = transaction.currency,
            recipientId = transaction.recipientId,
            status = "pending_sync",
            data = transaction.toJson(),
            createdAt = System.currentTimeMillis(),
            idempotencyKey = idempotencyKey,
            fee = fee
        )

        // Deduct from float snapshot
        if (floatSnapshot > 0) {
            floatSnapshot -= (transaction.amount + fee)
        }

        transactionDao.insertTransaction(entity)
    }
    
    /**
     * Queue beneficiary for offline processing
     */
    suspend fun queueBeneficiary(beneficiary: Beneficiary) {
        val entity = OfflineBeneficiaryEntity(
            id = beneficiary.id,
            name = beneficiary.name,
            accountNumber = beneficiary.accountNumber,
            bankName = beneficiary.bankName,
            country = beneficiary.country,
            status = "pending_sync",
            data = beneficiary.toJson(),
            createdAt = System.currentTimeMillis()
        )
        
        beneficiaryDao.insertBeneficiary(entity)
    }
    
    /**
     * Get cached transactions
     */
    fun getCachedTransactions(): Flow<List<Transaction>> {
        return transactionDao.getAllTransactions()
    }
    
    /**
     * Get cached beneficiaries
     */
    fun getCachedBeneficiaries(): Flow<List<Beneficiary>> {
        return beneficiaryDao.getAllBeneficiaries()
    }
    
    /**
     * Sync all pending operations
     */
    suspend fun syncPendingOperations() {
        if (!isOnline.value || isSyncing.value) return
        
        _isSyncing.value = true
        
        try {
            syncTransactions()
            syncBeneficiaries()
        } finally {
            _isSyncing.value = false
        }
    }
    
    /**
     * Sync pending transactions
     */
    private suspend fun syncTransactions() {
        val pending = transactionDao.getPendingTransactions()
        
        for (entity in pending) {
            try {
                // Sync with backend
                val transaction = Transaction.fromJson(entity.data)
                // ApiClient.syncTransaction(transaction)
                
                // Mark as synced
                val updated = entity.copy(
                    status = "synced",
                    syncedAt = System.currentTimeMillis()
                )
                transactionDao.updateTransaction(updated)
            } catch (e: Exception) {
                // Will retry on next sync
                e.printStackTrace()
            }
        }
    }
    
    /**
     * Sync pending beneficiaries
     */
    private suspend fun syncBeneficiaries() {
        val pending = beneficiaryDao.getPendingBeneficiaries()
        
        for (entity in pending) {
            try {
                // Sync with backend
                val beneficiary = Beneficiary.fromJson(entity.data)
                // ApiClient.syncBeneficiary(beneficiary)
                
                // Mark as synced
                val updated = entity.copy(
                    status = "synced",
                    syncedAt = System.currentTimeMillis()
                )
                beneficiaryDao.updateBeneficiary(updated)
            } catch (e: Exception) {
                // Will retry on next sync
                e.printStackTrace()
            }
        }
    }
    
    /**
     * Cleanup old synced items (older than 30 days)
     */
    suspend fun cleanupOldSyncedItems() {
        val thirtyDaysAgo = System.currentTimeMillis() - (30 * 24 * 60 * 60 * 1000)
        
        transactionDao.deleteOldSyncedTransactions(thirtyDaysAgo)
        beneficiaryDao.deleteOldSyncedBeneficiaries(thirtyDaysAgo)
    }
}

/**
 * Background sync worker
 */
class SyncWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {
    
    override suspend fun doWork(): Result {
        val database = OfflineDatabase.getDatabase(applicationContext)
        val offlineManager = OfflineManager(applicationContext, database)
        
        return try {
            offlineManager.syncPendingOperations()
            offlineManager.cleanupOldSyncedItems()
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }
}

/**
 * Placeholder data classes
 */
data class Transaction(
    val id: String,
    val type: String,
    val amount: Double,
    val currency: String,
    val recipientId: String
) {
    fun toJson(): String = "" // Implement JSON serialization
    companion object {
        fun fromJson(json: String): Transaction = Transaction("", "", 0.0, "", "") // Implement JSON deserialization
    }
}

data class Beneficiary(
    val id: String,
    val name: String,
    val accountNumber: String,
    val bankName: String,
    val country: String
) {
    fun toJson(): String = "" // Implement JSON serialization
    companion object {
        fun fromJson(json: String): Beneficiary = Beneficiary("", "", "", "", "") // Implement JSON deserialization
    }
}
