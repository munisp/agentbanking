package com.pos54link.app.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

/**
 * DAO for Pending Transfers - Offline queue management
 */
@Dao
interface PendingTransferDao {
    
    @Query("SELECT * FROM pending_transfers ORDER BY createdAt DESC")
    fun getAllPendingTransfers(): Flow<List<PendingTransferEntity>>
    
    @Query("SELECT * FROM pending_transfers WHERE status IN ('pending', 'failed') ORDER BY createdAt ASC")
    suspend fun getTransfersToSync(): List<PendingTransferEntity>
    
    @Query("SELECT * FROM pending_transfers WHERE id = :id")
    suspend fun getById(id: String): PendingTransferEntity?
    
    @Query("SELECT COUNT(*) FROM pending_transfers WHERE status IN ('pending', 'failed')")
    fun getPendingCount(): Flow<Int>
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(transfer: PendingTransferEntity)
    
    @Update
    suspend fun update(transfer: PendingTransferEntity)
    
    @Query("UPDATE pending_transfers SET status = :status, lastError = :error, retryCount = retryCount + 1 WHERE id = :id")
    suspend fun updateStatus(id: String, status: String, error: String?)
    
    @Query("UPDATE pending_transfers SET status = 'completed', syncedAt = :syncedAt, serverTransactionId = :serverTxnId WHERE id = :id")
    suspend fun markSynced(id: String, syncedAt: Long, serverTxnId: String)
    
    @Delete
    suspend fun delete(transfer: PendingTransferEntity)
    
    @Query("DELETE FROM pending_transfers WHERE status = 'completed' AND syncedAt < :olderThan")
    suspend fun deleteOldCompleted(olderThan: Long)
}

/**
 * DAO for Cached Transactions - Offline transaction history
 */
@Dao
interface CachedTransactionDao {
    
    @Query("SELECT * FROM cached_transactions ORDER BY createdAt DESC LIMIT :limit")
    fun getRecentTransactions(limit: Int = 50): Flow<List<CachedTransactionEntity>>
    
    @Query("SELECT * FROM cached_transactions WHERE type = :type ORDER BY createdAt DESC LIMIT :limit")
    fun getTransactionsByType(type: String, limit: Int = 50): Flow<List<CachedTransactionEntity>>
    
    @Query("SELECT * FROM cached_transactions WHERE id = :id")
    suspend fun getById(id: String): CachedTransactionEntity?
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(transactions: List<CachedTransactionEntity>)
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(transaction: CachedTransactionEntity)
    
    @Query("DELETE FROM cached_transactions WHERE cachedAt < :olderThan")
    suspend fun deleteOldCache(olderThan: Long)
    
    @Query("DELETE FROM cached_transactions")
    suspend fun clearAll()
}

/**
 * DAO for Cached Beneficiaries - Offline beneficiary access
 */
@Dao
interface CachedBeneficiaryDao {
    
    @Query("SELECT * FROM cached_beneficiaries ORDER BY isFavorite DESC, lastUsedAt DESC NULLS LAST")
    fun getAllBeneficiaries(): Flow<List<CachedBeneficiaryEntity>>
    
    @Query("SELECT * FROM cached_beneficiaries WHERE isFavorite = 1 ORDER BY lastUsedAt DESC NULLS LAST")
    fun getFavorites(): Flow<List<CachedBeneficiaryEntity>>
    
    @Query("SELECT * FROM cached_beneficiaries WHERE name LIKE '%' || :query || '%' OR phone LIKE '%' || :query || '%'")
    fun search(query: String): Flow<List<CachedBeneficiaryEntity>>
    
    @Query("SELECT * FROM cached_beneficiaries WHERE id = :id")
    suspend fun getById(id: String): CachedBeneficiaryEntity?
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(beneficiaries: List<CachedBeneficiaryEntity>)
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(beneficiary: CachedBeneficiaryEntity)
    
    @Query("UPDATE cached_beneficiaries SET lastUsedAt = :timestamp WHERE id = :id")
    suspend fun updateLastUsed(id: String, timestamp: Long)
    
    @Query("UPDATE cached_beneficiaries SET isFavorite = :isFavorite WHERE id = :id")
    suspend fun updateFavorite(id: String, isFavorite: Boolean)
    
    @Delete
    suspend fun delete(beneficiary: CachedBeneficiaryEntity)
    
    @Query("DELETE FROM cached_beneficiaries")
    suspend fun clearAll()
}

/**
 * DAO for Cached Wallet Balances - Offline balance viewing
 */
@Dao
interface CachedWalletBalanceDao {
    
    @Query("SELECT * FROM cached_wallet_balances")
    fun getAllBalances(): Flow<List<CachedWalletBalanceEntity>>
    
    @Query("SELECT * FROM cached_wallet_balances WHERE currency = :currency")
    suspend fun getByCurrency(currency: String): CachedWalletBalanceEntity?
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(balances: List<CachedWalletBalanceEntity>)
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(balance: CachedWalletBalanceEntity)
    
    @Query("DELETE FROM cached_wallet_balances")
    suspend fun clearAll()
}

/**
 * DAO for Sync State - Track sync status
 */
@Dao
interface SyncStateDao {
    
    @Query("SELECT * FROM sync_state WHERE dataType = :dataType")
    suspend fun getState(dataType: String): SyncStateEntity?
    
    @Query("SELECT * FROM sync_state")
    fun getAllStates(): Flow<List<SyncStateEntity>>
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(state: SyncStateEntity)
    
    @Query("UPDATE sync_state SET syncStatus = :status, lastError = :error WHERE dataType = :dataType")
    suspend fun updateStatus(dataType: String, status: String, error: String?)
    
    @Query("UPDATE sync_state SET lastSyncAt = :timestamp, syncStatus = 'idle', lastError = NULL WHERE dataType = :dataType")
    suspend fun markSynced(dataType: String, timestamp: Long)
    
    @Query("UPDATE sync_state SET pendingCount = :count WHERE dataType = :dataType")
    suspend fun updatePendingCount(dataType: String, count: Int)
}
