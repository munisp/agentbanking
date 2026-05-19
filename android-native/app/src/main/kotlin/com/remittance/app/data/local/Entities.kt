package com.pos54link.app.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.Index
import java.util.Date

/**
 * Pending Transfer Entity - Stores transfers created offline
 * These are synced to the backend when connectivity is restored
 */
@Entity(
    tableName = "pending_transfers",
    indices = [
        Index(value = ["status"]),
        Index(value = ["idempotencyKey"], unique = true),
        Index(value = ["createdAt"])
    ]
)
data class PendingTransferEntity(
    @PrimaryKey
    val id: String,
    val idempotencyKey: String,
    val recipientName: String,
    val recipientPhone: String,
    val recipientBank: String?,
    val recipientAccountNumber: String?,
    val amount: Double,
    val sourceCurrency: String,
    val destinationCurrency: String,
    val exchangeRate: Double,
    val fee: Double,
    val totalAmount: Double,
    val deliveryMethod: String,
    val note: String?,
    val status: String = "pending", // pending, syncing, completed, failed
    val retryCount: Int = 0,
    val lastError: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val syncedAt: Long? = null,
    val serverTransactionId: String? = null
)

/**
 * Cached Transaction Entity - Stores transaction history for offline viewing
 */
@Entity(
    tableName = "cached_transactions",
    indices = [
        Index(value = ["createdAt"]),
        Index(value = ["type"]),
        Index(value = ["status"])
    ]
)
data class CachedTransactionEntity(
    @PrimaryKey
    val id: String,
    val type: String, // transfer, deposit, withdrawal, payment, airtime
    val status: String,
    val amount: Double,
    val currency: String,
    val fee: Double,
    val description: String,
    val recipientName: String?,
    val recipientPhone: String?,
    val senderName: String?,
    val referenceNumber: String,
    val createdAt: Long,
    val completedAt: Long?,
    val cachedAt: Long = System.currentTimeMillis()
)

/**
 * Cached Beneficiary Entity - Stores beneficiaries for offline access
 */
@Entity(
    tableName = "cached_beneficiaries",
    indices = [
        Index(value = ["isFavorite"]),
        Index(value = ["lastUsedAt"])
    ]
)
data class CachedBeneficiaryEntity(
    @PrimaryKey
    val id: String,
    val name: String,
    val phone: String,
    val email: String?,
    val bankName: String?,
    val bankCode: String?,
    val accountNumber: String?,
    val accountType: String, // phone, email, bank
    val isFavorite: Boolean = false,
    val lastUsedAt: Long? = null,
    val cachedAt: Long = System.currentTimeMillis()
)

/**
 * Cached Wallet Balance Entity - Stores wallet balances for offline viewing
 */
@Entity(
    tableName = "cached_wallet_balances",
    indices = [Index(value = ["currency"])]
)
data class CachedWalletBalanceEntity(
    @PrimaryKey
    val currency: String,
    val balance: Double,
    val availableBalance: Double,
    val pendingBalance: Double,
    val lastUpdatedAt: Long,
    val cachedAt: Long = System.currentTimeMillis()
)

/**
 * Sync State Entity - Tracks sync status for different data types
 */
@Entity(
    tableName = "sync_state",
    indices = [Index(value = ["dataType"], unique = true)]
)
data class SyncStateEntity(
    @PrimaryKey
    val dataType: String, // transactions, beneficiaries, wallet, pending_transfers
    val lastSyncAt: Long?,
    val syncStatus: String, // idle, syncing, error
    val lastError: String?,
    val pendingCount: Int = 0
)
