package com.pos54link.app.offline

import android.content.Context
import androidx.room.*
import androidx.work.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
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
    val syncedAt: Long? = null
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
    
    private val transactionDao = database.transactionDao()
    private val beneficiaryDao = database.beneficiaryDao()
    
    private val _isOnline = MutableStateFlow(true)
    val isOnline: StateFlow<Boolean> = _isOnline
    
    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing
    
    val pendingTransactionCount: Flow<Int> = transactionDao.getPendingTransactionCount()
    val pendingBeneficiaryCount: Flow<Int> = beneficiaryDao.getPendingBeneficiaryCount()
    
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
     * Queue transaction for offline processing
     */
    suspend fun queueTransaction(transaction: Transaction) {
        val entity = OfflineTransactionEntity(
            id = transaction.id,
            type = transaction.type,
            amount = transaction.amount.toString(),
            currency = transaction.currency,
            recipientId = transaction.recipientId,
            status = "pending_sync",
            data = transaction.toJson(),
            createdAt = System.currentTimeMillis()
        )
        
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
